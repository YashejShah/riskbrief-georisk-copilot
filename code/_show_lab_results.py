"""Print the build / review / fix results of the two-labs workflow (journal.jsonl)."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
for line in open(sys.argv[1], encoding="utf-8"):
    e = json.loads(line)
    if e.get("type") != "result":
        continue
    r = e.get("result")
    if isinstance(r, list):
        for x in r:
            print("=" * 20, x.get("key"))
            rv = x.get("review") or {}
            print("REVIEW:", (rv.get("summary") or "")[:700])
            for i in rv.get("issues", []):
                print(f"  [{i['severity']}] {i['where'][:80]}: {i['problem'][:200]}")
            fx = x.get("fixed")
            print("FIX:", json.dumps(fx, ensure_ascii=False)[:1500] if fx else None)
    elif isinstance(r, dict):
        print("-" * 10, list(r.keys())[:6])
        if "deliverables" in r:
            print("  deliverables:", r["deliverables"])
            print("  gaps:", r.get("gaps", "")[:600])
        if "issues" in r:
            print("  review summary:", r.get("summary", "")[:400])
            for i in r["issues"]:
                print(f"  [{i['severity']}] {i['where'][:70]}: {i['problem'][:180]}")
