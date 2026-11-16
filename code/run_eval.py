"""Run one or more prompt versions on every test case and save the real outputs.

    python code/run_eval.py v1 v2 v3 final
-> test-data/outputs/<version>/<case>.json   full record (prompts sent, raw replies, checks, final output)
-> test-data/outputs/<version>/summary.json  pass counts per check and per case
-> test-data/run_log.jsonl                   one line per LLM call (version, case, prompt, seconds, tokens)
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief import chain  # noqa: E402
from riskbrief.llm import MODEL, SETTINGS, model_digest  # noqa: E402

CASES_FILE = "heldout_cases.json" if "--heldout" in sys.argv else "cases.json"
CASES = json.loads((REPO / "test-data" / CASES_FILE).read_text(encoding="utf-8"))
LOG = REPO / "test-data" / "run_log.jsonl"


def summarise(version, results):
    per_check, per_case = {}, {}
    for cid, res in results.items():
        errs = res["errors"]
        flat = {}
        if "P1" in errs or "P2" in errs:
            for step, e in errs.items():
                for k, v in e.items():
                    flat.setdefault(k, []).extend(v)
        else:
            flat = errs
        for k, v in flat.items():
            pc = per_check.setdefault(k, {"pass": 0, "fail": 0})
            pc["pass" if not v else "fail"] += 1
        raw_ok = res["raw_action"] == res["oracle"]["action"]
        per_case[cid] = {"all_checks_pass": not any(flat.values()), "raw_action": res["raw_action"],
                         "playbook_action": res["oracle"]["action"], "raw_action_ok": raw_ok,
                         "errors": [f"{k}: {e}" for k, v in flat.items() for e in v],
                         "escalated": res.get("escalated", False),
                         "seconds": round(sum(c["stats"]["seconds"] for c in res["calls"]), 1),
                         "llm_calls": len(res["calls"])}
    llm_cases = [c for c in per_case.values() if c["llm_calls"]]
    return {"version": version, "model": MODEL, "model_digest": model_digest(), "settings": SETTINGS,
            "run_at": datetime.now().isoformat(timespec="seconds"), "cases": len(per_case),
            "all_checks_pass": sum(c["all_checks_pass"] for c in per_case.values()),
            "raw_action_ok": sum(c["raw_action_ok"] for c in per_case.values()),
            "llm_cases": len(llm_cases),
            "mean_seconds_per_case": round(sum(c["seconds"] for c in llm_cases) / max(1, len(llm_cases)), 1),
            "per_check": per_check, "per_case": per_case}


def main():
    heldout = "--heldout" in sys.argv
    versions = [a for a in sys.argv[1:] if a != "--heldout"] or ["v1", "v2", "v3", "final"]
    only = None
    if "--cases" in versions:
        i = versions.index("--cases")
        only, versions = set(versions[i + 1].split(",")), versions[:i]
    for v in versions:
        out = REPO / "test-data" / "outputs" / (v + ("_heldout" if heldout else ""))
        out.mkdir(parents=True, exist_ok=True)
        results = {}
        for case in CASES:
            if only and case["id"] not in only:
                continue
            t0 = time.time()
            res = chain.run(case, v)
            results[case["id"]] = res
            (out / f"{case['id']}.json").write_text(json.dumps({"case": case, **res}, indent=1, ensure_ascii=False),
                                                    encoding="utf-8")
            with LOG.open("a", encoding="utf-8") as f:
                for c in res["calls"]:
                    f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "version": v,
                                        "case": case["id"], "prompt": c["prompt"], **c["stats"],
                                        "parse_ok": c["json"] is not None}) + "\n")
            n_err = sum(len(x) if isinstance(x, list) else sum(len(y) for y in x.values())
                        for x in res["errors"].values())
            print(f"{v:<6} {case['id']}  action raw={res['raw_action']!s:<13} playbook={res['oracle']['action']:<13} "
                  f"errors={n_err:<3} {time.time() - t0:5.1f}s", flush=True)
        if not only:
            s = summarise(v, results)
            (out / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"== {v}: all checks pass {s['all_checks_pass']}/{s['cases']}, raw action = playbook "
                  f"{s['raw_action_ok']}/{s['cases']}, {s['mean_seconds_per_case']} s/case", flush=True)


if __name__ == "__main__":
    main()
