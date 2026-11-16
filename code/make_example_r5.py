"""Add the R5 (region-only review) few-shot example used by the final P1. The order is a real API grid order
that is NOT in the test set; like T11 it is changed to the API's own fairness-downgrade output (perturbed),
because the API never produced a region-only review on the 240 grid orders.
Also relabels the stored v4 outputs (they were produced while those prompts were called 'final')."""
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief.rules import oracle  # noqa: E402
from riskbrief.views import merchant_view  # noqa: E402

scan = json.loads((REPO / "test-data" / "api_grid_scan.json").read_text(encoding="utf-8"))
cases = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
used = {c["request"]["order_id"] for c in cases} | {"G-001", "G-010", "G-034"}
x = next(x for x in scan if x["status"] == 200 and x["request"]["order_id"] not in used
         and x["request"]["payment_method"] == "card" and x["pins"] == "tier2_same" and x["hour"] == "day")
x = copy.deepcopy(x)
x["response"].update({"risk_score": 82, "decision": "review", "reason_codes": ["HIGH_RISK_REGION"],
                      "fairness_note": "Borderline decline driven only by region risk (HIGH_RISK_REGION) with no "
                                       "other strong signal; downgraded to 'review' so geography alone does not "
                                       "auto-decline an otherwise-normal order."})
view = merchant_view({"request": x["request"], "response": x["response"]})["view"]
orc = oracle(view)
assert orc["rule"] == "R5"
brief = {"order_id": view["order_id"], "status": "ok", "api_decision": "review", "risk_score": view["risk_score"],
         "recommended_action": "OTP_VERIFY", "offer_prepaid_option": False, "secondary_action": "NONE",
         "playbook_rule": "R5",
         "reasons": [{"code": "HIGH_RISK_REGION", "evidence_field": "region_risk",
                      "evidence_value": str(view["region_risk"]), "plain_language": ""}],
         "summary": f"Risk score {view['risk_score']} out of 100, API decision: review. The API's fairness rule changed "
                    "a borderline decline into a review. One reason is a statistic about the billing state; see the "
                    "note below. Ask the customer to confirm the order with an OTP before you ship.",
         "data_quality_notes": [],
         "fairness_check": {"location_or_income_used_as_reason": False,
                            "note": "Location is not a reason to decline or block; only an OTP check is asked."},
         "customer_message_needed": True}
ex = [{"source_order": x["request"]["order_id"] + " (perturbed: region-only fairness downgrade)", "view": view,
       "brief": brief}]
(REPO / "code" / "riskbrief" / "examples_r5.json").write_text(json.dumps(ex, indent=1, ensure_ascii=False),
                                                             encoding="utf-8")
print("R5 example from", x["request"]["order_id"])

for p in (REPO / "test-data" / "outputs" / "v4").glob("T*.json"):
    r = json.loads(p.read_text(encoding="utf-8"))
    r["version"] = "v4"
    if isinstance(r.get("final", {}).get("brief"), dict) and r["final"]["brief"].get("prompt_version") == "final":
        r["final"]["brief"]["prompt_version"] = "v4"
    p.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
print("relabelled v4 outputs")
