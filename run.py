import argparse
import json
import os
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from strategies import MODEL, STRATEGIES, run_s3
from tools import TOOL_DEFINITIONS

QUESTIONS_PATH = Path(__file__).parent / "data" / "questions.json"
OUTPUTS = Path(__file__).parent / "outputs"

def is_correct(answer, question):
    """My rule (written before the first full run):
    - the name must match exactly (ignoring upper/lower case and spaces),
    - the number, rounded to the question's decimals, may differ from 'value'
      by at most 1 in the last digit."""
    if answer is None:
        return False
    name, number = answer
    if name.strip().lower() != str(question["answer"]).strip().lower():
        return False
    step = 10 ** -question["decimals"]
    return abs(round(number, question["decimals"]) - question["value"]) <= step * 1.0001


def cost(input_tokens, output_tokens):
    price_in = os.getenv("PRICE_INPUT_PER_M")
    price_out = os.getenv("PRICE_OUTPUT_PER_M")
    if not price_in or not price_out:
        return None
    return input_tokens / 1e6 * float(price_in) + output_tokens / 1e6 * float(price_out)

def vague_definitions():
    """C1: the same tools, but lookup has a one-line description."""
    defs = json.loads(json.dumps(TOOL_DEFINITIONS))
    defs[0]["function"]["description"] = "Looks things up."
    return defs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="run name, e.g. 0 (test), 1, 2, c1")
    parser.add_argument("--strategies", nargs="+", default=["S1", "S2", "S3"])
    parser.add_argument("--questions", nargs="+", help="question ids; default: all 20")
    parser.add_argument("--vague", action="store_true", help="C1: vague lookup description (S3 only)")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing: put it in .env")
    client = OpenAI()  

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if args.questions:
        questions = [q for q in questions if q["id"] in args.questions]

    run_dir = OUTPUTS / f"run{args.run}"
    summary = {}

    for strategy in args.strategies:
        out_dir = run_dir / strategy
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []

        for q in questions:
            start = time.time()
            if strategy == "S3" and args.vague:
                result = run_s3(client, q, tool_definitions=vague_definitions())
            else:
                result = STRATEGIES[strategy](client, q)
            seconds = time.time() - start

            correct = is_correct(result["answer"], q)
            row = {
                "id": q["id"],
                "answer": result["answer"],
                "expected": [q["answer"], q["value"]],
                "correct": correct,
                "unanswered": result["answer"] is None,
                "input_tokens": sum(c["input_tokens"] for c in result["calls"]),
                "output_tokens": sum(c["output_tokens"] for c in result["calls"]),
                "model_calls": len(result["calls"]),
                "rounds": result.get("rounds"),
                "votes": result.get("votes"),
                "seconds": round(seconds, 3),
                "temperature_ok": result["temperature_ok"],
            }
            rows.append(row)
            (out_dir / f"{q['id']}.json").write_text(
                json.dumps({**row, "calls": result["calls"], **result["log"]}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            mark = "OK " if correct else ("-- " if row["unanswered"] else "XX ")
            print(f"[run{args.run}] {strategy} {q['id']} {mark} answer={result['answer']} "
                  f"expected={q['answer']}|{q['value']} tokens={row['input_tokens']}+{row['output_tokens']} "
                  f"{row['seconds']}s")

        total_in = sum(r["input_tokens"] for r in rows)
        total_out = sum(r["output_tokens"] for r in rows)
        summary[strategy] = {
            "questions": len(rows),
            "correct": sum(r["correct"] for r in rows),
            "unanswered": sum(r["unanswered"] for r in rows),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "median_seconds": round(statistics.median(r["seconds"] for r in rows), 2),
            "total_seconds": round(sum(r["seconds"] for r in rows), 2),
            "cost_usd": cost(total_in, total_out),
            "temperature_ok": all(r["temperature_ok"] for r in rows),
            "model": MODEL,
            "per_question": {r["id"]: r["correct"] for r in rows},
        }
        (out_dir / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    old = {}
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        old = json.loads(summary_path.read_text(encoding="utf-8"))
    old.update(summary)
    summary_path.write_text(json.dumps(old, indent=2), encoding="utf-8")

    print("\nSUMMARY")
    for s, v in summary.items():
        print(f"{s}: {v['correct']}/{v['questions']} correct, {v['unanswered']} unanswered, "
              f"tokens {v['input_tokens']}+{v['output_tokens']}, median {v['median_seconds']}s, "
              f"total {v['total_seconds']}s, cost {v['cost_usd']}, temperature_ok={v['temperature_ok']}")


if __name__ == "__main__":
    main()