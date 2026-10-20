import json
from pathlib import Path

OUT = Path(__file__).parent / "outputs"

def load(run, strategy, qid):
    return json.loads((OUT / f"run{run}" / strategy / f"{qid}.json").read_text(encoding="utf-8"))

print("=== C2 / S1: Q-09 run1 (wrong) ===")
d = load(1, "S1", "Q-09")
print("output tokens:", d["output_tokens"])
print("reply:", repr(d["reply"]))

print("\n=== C2 / S2: the 5 samples of the wrong questions, run1 ===")
for qid in ["Q-05", "Q-17", "Q-20"]:
    d = load(1, "S2", qid)
    answers = [s["answer"] for s in d["samples"]]
    print(qid, "expected", d["expected"], "votes", d["votes"], "samples", answers)

print("\n--- one S2 sample for Q-05 (last 900 characters) ---")
d = load(1, "S2", "Q-05")
print(d["samples"][0]["reply"][-900:])

print("\n=== C2 / S3: the most expensive question, run1 ===")
rows = json.loads((OUT / "run1" / "S3" / "results.json").read_text(encoding="utf-8"))
top = max(rows, key=lambda r: r["input_tokens"] + r["output_tokens"])
d = load(1, "S3", top["id"])
print(top["id"], "rounds", d["rounds"], "total", d["input_tokens"], "+", d["output_tokens"])
for i, c in enumerate(d["calls"], 1):
    print(f"  model call {i}: input {c['input_tokens']}, output {c['output_tokens']}, {c['seconds']}s")
for t in d["tool_calls"]:
    print(f"  round {t['round']} {t['tool']} {t['arguments']} -> {t['result'].get('value', t['result'].get('result'))}")

print("\n=== Final Q5: rounds per question in S3 (run1 and run2) ===")
for run in (1, 2):
    rows = json.loads((OUT / f"run{run}" / "S3" / "results.json").read_text(encoding="utf-8"))
    print(f"run{run}:", {r["id"]: r["rounds"] for r in rows})

print("\n=== Final Q4: S2 cost compared with S1 ===")
for run in (1, 2):
    s = json.loads((OUT / f"run{run}" / "summary.json").read_text(encoding="utf-8"))
    c1, c2, c3 = s["S1"]["cost_usd"], s["S2"]["cost_usd"], s["S3"]["cost_usd"]
    print(f"run{run}: S1 ${c1:.4f}, S2 ${c2:.4f}, S3 ${c3:.4f}; S2/S1 = {c2 / c1:.1f}x, S2/S3 = {c2 / c3:.1f}x")