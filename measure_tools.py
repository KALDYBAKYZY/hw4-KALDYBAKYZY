"""Final question 3: how many tokens do the two tool definitions add to every S3 request?

Sends the same tiny message twice: once without tools, once with them.
The difference in prompt_tokens is the cost of the tool definitions.
Then the same with the vague lookup description (C1).

    python measure_tools.py
"""

import json

from dotenv import load_dotenv
from openai import OpenAI

from strategies import MODEL, REASONING_EFFORT
from tools import TOOL_DEFINITIONS

load_dotenv()
client = OpenAI()
messages = [{"role": "user", "content": "Say OK."}]


def prompt_tokens(tools=None):
    kwargs = {"model": MODEL, "messages": messages, "reasoning_effort": REASONING_EFFORT, "max_completion_tokens": 5}
    if tools:
        kwargs["tools"] = tools
    return client.chat.completions.create(**kwargs).usage.prompt_tokens


vague = json.loads(json.dumps(TOOL_DEFINITIONS))
vague[0]["function"]["description"] = "Looks things up."

base = prompt_tokens()
full = prompt_tokens(TOOL_DEFINITIONS)
short = prompt_tokens(vague)
print(f"without tools:             {base} prompt tokens")
print(f"with my two tools:         {full} prompt tokens  -> the tools add {full - base}")
print(f"with vague lookup (C1):    {short} prompt tokens  -> the tools add {short - base}")
print(f"my lookup description costs {full - short} more tokens than 'Looks things up.' in every request")