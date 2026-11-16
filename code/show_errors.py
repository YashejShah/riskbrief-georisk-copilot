"""Print every failed check per case for the given prompt versions (for the iteration log).

    python code/show_errors.py v1 v2 v3 final
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
for v in sys.argv[1:] or ["v1", "v2", "v3", "final"]:
    p = REPO / "test-data" / "outputs" / v / "summary.json"
    if not p.exists():
        continue
    s = json.loads(p.read_text(encoding="utf-8"))
    print(f"===== {v}: all pass {s['all_checks_pass']}/{s['cases']}, raw action ok {s['raw_action_ok']}/{s['cases']}, "
          f"{s['mean_seconds_per_case']} s/case")
    print("     per check:", {k: f"{d['pass']}/{d['pass'] + d['fail']}" for k, d in sorted(s["per_check"].items())})
    kinds = Counter()
    for cid, c in s["per_case"].items():
        for e in c["errors"]:
            kinds[e.split(":")[0] + ":" + e.split(":")[1][:38]] += 1
        if c["errors"]:
            print(f"  {cid}: " + " | ".join(e[:120] for e in c["errors"]))
    print("     most common:", kinds.most_common(8))
