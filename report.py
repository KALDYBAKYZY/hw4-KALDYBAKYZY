"""Make the two B4 tables for SUBMISSION.md from outputs/run1 and outputs/run2.

    python report.py
"""

import json
from pathlib import Path

OUTPUTS = Path(__file__).parent / "outputs"
NAMES = {"S1": "S1 direct", "S2": "S2 think and vote (k = 5)", "S3": "S3 tools"}


def load(run):
    path = OUTPUTS / f"run{run}" / "summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def money(x):
    return "n/a" if x is None else f"{x:.4f}"


print("| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens "
      "| Median seconds per question | Total seconds | Cost ($) |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
for run in (1, 2):
    summary = load(run)
    for s in ("S1", "S2", "S3"):
        v = summary.get(s)
        if not v:
            continue
        print(f"| {run} | {NAMES[s]} | {v['correct']} | {v['unanswered']} | {v['input_tokens']} "
              f"| {v['output_tokens']} | {v['median_seconds']} | {v['total_seconds']} | {money(v['cost_usd'])} |")

print("\n**Per question (run 1):**\n")
print("| Question | S1 | S2 | S3 |")
print("|---|:---:|:---:|:---:|")
summary = load(1)
for i in range(1, 21):
    qid = f"Q-{i:02d}"
    marks = []
    for s in ("S1", "S2", "S3"):
        ok = summary.get(s, {}).get("per_question", {}).get(qid)
        marks.append("" if ok is None else ("✓" if ok else "✗"))
    print(f"| {qid} | " + " | ".join(marks) + " |")