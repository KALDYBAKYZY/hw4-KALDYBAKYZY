import json
import os
import re
import time
from collections import Counter
from pathlib import Path

from tools import TOOL_DEFINITIONS, TOOLS

MODEL = "gpt-5.6-luna"
K_SAMPLES = 5          
MAX_ROUNDS = 10     
TEMPERATURE = 1.0     
REASONING_EFFORT = "none"

CORPUS_PATH = Path(__file__).parent / "data" / "corpus.jsonl"

ANSWER_RULE = (
    "End your reply with exactly one last line in this format:\n"
    "ANSWER: <district name or yes/no> | <number>\n"
    "Write the number without units and without thousand separators."
)

SYSTEM_DOCS = (
    "You answer questions about the Nine Rivers Region using only the documents given below. "
    "Read them carefully: some profiles are ARCHIVED and must not be used, correction notices "
    "replace the numbers they correct, and units can differ between districts.\n\n"
    + ANSWER_RULE
)

S1_INSTRUCTION = "Give the answer directly. Do not write your working."
S2_INSTRUCTION = "Think step by step: write down each fact you use and each calculation, then give the answer."

SYSTEM_TOOLS = (
    "You answer questions about the Nine Rivers Region. You do not have the documents. "
    "Use the lookup tool for every fact and the calculate tool for every calculation. "
    "You may call several tools in one turn when they do not depend on each other.\n\n"
    + ANSWER_RULE
)

def load_documents_text():
    """All 17 documents as one text block (for S1 and S2)."""
    lines = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                doc = json.loads(line)
                lines.append(f"[{doc['id']}] {doc['title']}\n{doc['text']}")
    return "\n\n".join(lines)

DOCUMENTS = load_documents_text()

def user_message(question):
    """The same user message for all three strategies. Uses the decimals, never the answer."""
    return f"{question['question']}\nRound the number to {question['decimals']} decimal places."

def parse_answer(text):
    """Find the last 'ANSWER: name | number' line. Returns (name, number) or None."""
    if not text:
        return None
    matches = re.findall(r"ANSWER:\s*([^|\n]+?)\s*\|\s*(-?[\d,]*\.?\d+)", text)
    if not matches:
        return None
    name, number = matches[-1]
    try:
        return name.strip(), float(number.replace(",", ""))
    except ValueError:
        return None

class Recorder:

    def __init__(self, client):
        self.client = client
        self.calls = []
        self.temperature_ok = True

    def chat(self, messages, tools=None):
        kwargs = {"model": MODEL, "messages": messages, "reasoning_effort": REASONING_EFFORT}
        if tools:
            kwargs["tools"] = tools
        if self.temperature_ok:
            kwargs["temperature"] = TEMPERATURE

        start = time.time()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            if "temperature" in str(e).lower() and self.temperature_ok:
                self.temperature_ok = False
                kwargs.pop("temperature")
                start = time.time()
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise
        seconds = time.time() - start

        usage = response.usage
        self.calls.append({
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "seconds": round(seconds, 3),
        })
        return response.choices[0].message

def run_s1(client, question):
    rec = Recorder(client)
    messages = [
        {"role": "system", "content": SYSTEM_DOCS + "\n\n" + S1_INSTRUCTION + "\n\nDOCUMENTS:\n\n" + DOCUMENTS},
        {"role": "user", "content": user_message(question)},
    ]
    reply = rec.chat(messages)
    return {
        "answer": parse_answer(reply.content),
        "calls": rec.calls,
        "temperature_ok": rec.temperature_ok,
        "log": {"reply": reply.content},
    }

def run_s2(client, question, k=K_SAMPLES):
    rec = Recorder(client)
    messages = [
        {"role": "system", "content": SYSTEM_DOCS + "\n\n" + S2_INSTRUCTION + "\n\nDOCUMENTS:\n\n" + DOCUMENTS},
        {"role": "user", "content": user_message(question)},
    ]
    samples = []
    for _ in range(k):
        reply = rec.chat(messages)
        samples.append({"reply": reply.content, "answer": parse_answer(reply.content)})

    keys = []
    for s in samples:
        if s["answer"]:
            name, number = s["answer"]
            keys.append((name.lower(), round(number, question["decimals"])))
    if keys:
        (name, number), votes = Counter(keys).most_common(1)[0]
        answer = (name, number)
    else:
        answer, votes = None, 0

    return {
        "answer": answer,
        "votes": votes,
        "calls": rec.calls,
        "temperature_ok": rec.temperature_ok,
        "log": {"samples": samples},
    }

def check_arguments(name, raw_arguments):
    if name not in TOOLS:
        return None, f"unknown tool '{name}'"
    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as e:
        return None, f"arguments are not valid JSON: {e.msg}"
    if not isinstance(args, dict):
        return None, "arguments must be a JSON object"

    schema = next(t["function"]["parameters"] for t in TOOL_DEFINITIONS if t["function"]["name"] == name)
    for key in schema["required"]:
        if key not in args:
            return None, f"missing required argument '{key}'"
    for key in args:
        if key not in schema["properties"]:
            return None, f"unknown argument '{key}'"
    return args, None

def message_to_dict(message):
    """Keep the model's message unchanged, including its tool_calls."""
    data = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ]
    return data

def run_s3(client, question, tool_definitions=TOOL_DEFINITIONS, max_rounds=MAX_ROUNDS):
    rec = Recorder(client)
    messages = [
        {"role": "system", "content": SYSTEM_TOOLS},
        {"role": "user", "content": user_message(question)},
    ]
    tool_log = []

    for round_number in range(1, max_rounds + 1):
        reply = rec.chat(messages, tools=tool_definitions)
        messages.append(message_to_dict(reply))

        if not reply.tool_calls:
            return {
                "answer": parse_answer(reply.content),
                "rounds": round_number,
                "calls": rec.calls,
                "temperature_ok": rec.temperature_ok,
                "log": {"tool_calls": tool_log, "messages": messages},
            }

        for call in reply.tool_calls:
            start = time.time()
            args, error = check_arguments(call.function.name, call.function.arguments)
            result = {"error": error} if error else TOOLS[call.function.name](**args)
            ms = round((time.time() - start) * 1000, 3)

            tool_log.append({
                "round": round_number,
                "id": call.id,
                "tool": call.function.name,
                "arguments": call.function.arguments,
                "result": result,
                "ms": ms,
            })
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return {
        "answer": None,
        "rounds": max_rounds,
        "hit_round_limit": True,
        "calls": rec.calls,
        "temperature_ok": rec.temperature_ok,
        "log": {"tool_calls": tool_log, "messages": messages},
    }

STRATEGIES = {"S1": run_s1, "S2": run_s2, "S3": run_s3}