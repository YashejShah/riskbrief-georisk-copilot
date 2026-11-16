"""Add the R2 (approve with reason codes) few-shot example used by the final P1: a real API grid order that is
NOT in the test set and not used by the other examples. Also relabels the stored v5 outputs."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief.rules import oracle  # noqa: E402
from riskbrief.views import merchant_view  # noqa: E402

scan = json.loads((REPO / "test-data" / "api_grid_scan.json").read_text(encoding="utf-8"))
cases = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
used = {c["request"]["order_id"] for c in cases} | {"G-001", "G-010", "G-034", "G-169"}
x = next(x for x in scan if x["status"] == 200 and x["request"]["order_id"] not in used
         and x["response"]["decision"] == "approve" and len(x["response"]["reason_codes"]) == 2)
view = merchant_view({"request": x["request"], "response": x["response"]})["view"]
orc = oracle(view)
assert orc["rule"] == "R2", orc
PLAIN = {"HIGH_AMOUNT": f"The order amount is Rs {view['amount_inr']:,}, which is Rs 5,000 or more.",
         "LARGE_BILLING_SHIPPING_DISTANCE": f"The shipping address is about "
                                            f"{round(view['billing_shipping_distance_km'] or 0)} km from the billing "
                                            "address, more than 300 km.",
         "ODD_HOUR": f"The order was placed at {view['order_time']}, before 06:00.",
         "RISKY_PAYMENT_METHOD": "The payment method is " + {"cod": "cash on delivery", "wallet": "a wallet"}.get(
             view["payment_method"], view["payment_method"]) + "."}
FIELD = {"HIGH_AMOUNT": "amount_inr", "LARGE_BILLING_SHIPPING_DISTANCE": "billing_shipping_distance_km",
         "ODD_HOUR": "order_time", "RISKY_PAYMENT_METHOD": "payment_method"}
reasons = [{"code": c, "evidence_field": FIELD[c], "evidence_value": str(view[FIELD[c]]), "plain_language": PLAIN[c]}
           for c in view["reason_codes"]]
brief = {"order_id": view["order_id"], "status": "ok", "api_decision": "approve", "risk_score": view["risk_score"],
         "recommended_action": "APPROVE", "offer_prepaid_option": False, "secondary_action": "NONE",
         "playbook_rule": "R2", "reasons": reasons,
         "summary": f"Risk score {view['risk_score']} out of 100, API decision: approve. The API still listed "
                    "these reasons for information: "
                    + "; ".join(r["plain_language"].rstrip(".").lower() for r in reasons)
                    + ". You can ship it as usual.",
         "data_quality_notes": [],
         "fairness_check": {"location_or_income_used_as_reason": False,
                            "note": "Location and income were not used as reasons."},
         "customer_message_needed": False}
ex = [{"source_order": x["request"]["order_id"], "view": view, "brief": brief}]
(REPO / "code" / "riskbrief" / "examples_r2.json").write_text(json.dumps(ex, indent=1, ensure_ascii=False),
                                                             encoding="utf-8")
print("R2 example from", x["request"]["order_id"], view["reason_codes"])

for v in ("v5", "v6"):
    for p in (REPO / "test-data" / "outputs" / v).glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        r["version"] = v
        if isinstance(r.get("final", {}), dict) and isinstance(r.get("final", {}).get("brief"), dict) and \
                r["final"]["brief"].get("prompt_version") == "final":
            r["final"]["brief"]["prompt_version"] = v
        p.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
print("relabelled v5 and v6 outputs")
