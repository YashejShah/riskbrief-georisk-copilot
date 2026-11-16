"""Write the 3 few-shot examples for P1 from real API grid orders that are NOT in the test set.
The output part of each example is the team's reference brief: playbook fields from the oracle,
plain-language sentences written by us."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief.rules import oracle  # noqa: E402
from riskbrief.views import merchant_view  # noqa: E402

scan = json.loads((REPO / "test-data" / "api_grid_scan.json").read_text(encoding="utf-8"))
cases = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
used = {c["request"]["order_id"] for c in cases}
ok = [x for x in scan if x["status"] == 200 and x["request"]["order_id"] not in used]

PLAIN = {
    "HIGH_AMOUNT": "The order amount is Rs {amount}, which is Rs 5,000 or more.",
    "LARGE_BILLING_SHIPPING_DISTANCE": "The shipping address is about {dist} km from the billing address, more than "
                                       "300 km.",
    "ODD_HOUR": "The order was placed at {time}, before 06:00.",
    "RISKY_PAYMENT_METHOD": "The payment method is {pm}.",
}
FIELD = {"HIGH_AMOUNT": "amount_inr", "LARGE_BILLING_SHIPPING_DISTANCE": "billing_shipping_distance_km",
         "ODD_HOUR": "order_time", "RISKY_PAYMENT_METHOD": "payment_method"}
PM = {"cod": "cash on delivery", "wallet": "a wallet", "upi": "UPI", "card": "card", "netbanking": "net banking"}


def brief_for(x):
    view = merchant_view({"request": x["request"], "response": x["response"]})["view"]
    orc = oracle(view)
    reasons = []
    for c in view["reason_codes"]:
        val = view[FIELD[c]]
        reasons.append({"code": c, "evidence_field": FIELD[c], "evidence_value": str(val),
                        "plain_language": PLAIN[c].format(amount=f"{view['amount_inr']:,}", time=view["order_time"],
                                                          dist=round(view["billing_shipping_distance_km"] or 0),
                                                          pm=PM[view["payment_method"]])})
    nxt = {"APPROVE": "You can ship it as usual.",
           "OTP_VERIFY": "Ask the customer to confirm the order with an OTP before you ship. If the OTP is not "
                         "confirmed, call the customer."}[orc["action"]]
    if orc["prepaid"]:
        nxt += " You may also offer online payment, but cash on delivery stays available."
    summary = (f"Risk score {view['risk_score']} out of 100, API decision: {view['api_decision']}. "
               + (f"Main reasons: {', '.join(r['plain_language'].rstrip('.').lower() for r in reasons)}. "
                  if reasons else "No reason codes were reported. ") + nxt)
    brief = {"order_id": view["order_id"], "status": "ok", "api_decision": view["api_decision"],
             "risk_score": view["risk_score"], "recommended_action": orc["action"],
             "offer_prepaid_option": orc["prepaid"], "secondary_action": orc["secondary"],
             "playbook_rule": orc["rule"], "reasons": reasons, "summary": summary, "data_quality_notes": [],
             "fairness_check": {"location_or_income_used_as_reason": False,
                                "note": "Location and income were not used as reasons."},
             "customer_message_needed": orc["message"]}
    return {"source_order": x["request"]["order_id"], "view": view, "brief": brief}


want = [
    lambda x: x["response"]["decision"] == "approve" and not x["response"]["reason_codes"],
    lambda x: x["response"]["decision"] == "review" and x["request"]["payment_method"] == "card",
    lambda x: x["response"]["decision"] == "review" and x["request"]["payment_method"] == "cod",
]
examples = []
for w in want:
    x = next((x for x in ok if w(x)), None)
    if x is None:
        raise SystemExit("no example order found")
    examples.append(brief_for(x))
    ok.remove(x)
(REPO / "code" / "riskbrief" / "examples.json").write_text(json.dumps(examples, indent=1, ensure_ascii=False),
                                                         encoding="utf-8")
for e in examples:
    print(e["source_order"], e["brief"]["playbook_rule"], e["brief"]["summary"])
