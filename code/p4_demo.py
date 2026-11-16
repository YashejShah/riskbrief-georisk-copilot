"""Real sample run for the P4 repair prompt (for its prompt sheet): take a v3 brief that failed the checker,
send it to P4 with the checker's exact errors, and check the repaired output again.

    python code/p4_demo.py T05   -> test-data/p4_sample_run.json
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief import chain  # noqa: E402
from riskbrief.rules import BRIEF_SCHEMA, oracle  # noqa: E402
from riskbrief.views import merchant_view  # noqa: E402

cid = sys.argv[1] if len(sys.argv) > 1 else "T05"
rec = json.loads((REPO / "test-data" / "outputs" / "v3" / f"{cid}.json").read_text(encoding="utf-8"))
case = rec["case"]
view = merchant_view(case)["view"]
orc = oracle(view)
p1 = rec["calls"][0]
errs = chain.flat(chain.brief_errors(case, p1["json"], p1["parse_error"], view, orc))
if not errs:
    raise SystemExit(f"{cid}: the v3 brief has no errors, pick another case")
r = chain.call("final", "P4_repair", BRIEF_SCHEMA, errors="\n".join(errs), input_data=chain.dumps(view),
               previous_output=p1["raw"], output_kind="decision brief")
after = chain.flat(chain.brief_errors(case, r["json"], r["parse_error"], view, orc))
out = {"case": cid, "errors_before": errs, "previous_output": p1["json"], "repair_user_prompt": r["user"],
       "repaired_output": r["json"], "errors_after": after, "stats": r["stats"]}
(REPO / "test-data" / "p4_sample_run.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(cid, "errors before:", errs)
print("errors after:", after, "|", r["stats"])
