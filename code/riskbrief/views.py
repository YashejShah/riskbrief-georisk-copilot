"""Pre-processor (plain Python, no LLM): validate the input, clean order_id, build the three views.

merchant view   -> P1 (no PIN codes, no income tier, no IP/e-mail/phone)
customer view   -> P2 (only what the customer may be told: order id, amount, payment method, action)
reviewer view   -> approval page (API JSON with income tier removed and PINs masked)
"""
import copy
import re

from .rules import DECISIONS, KNOWN_CODES, PAYMENT_METHODS

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}")


def clean_order_id(raw):
    raw = str(raw or "").strip()
    m = ID_RE.match(raw)
    clean = m.group(0) if m else "UNKNOWN"
    return clean, clean != raw


def validate(case: dict) -> list:
    """Return a list of problems (empty list = valid)."""
    req, resp = case.get("request") or {}, case.get("response") or {}
    bad = []
    amt = req.get("amount")
    if not isinstance(amt, (int, float)) or amt <= 0:
        bad.append(f"amount must be a positive number (got {amt!r})")
    if req.get("payment_method") not in PAYMENT_METHODS:
        bad.append(f"unknown payment_method {req.get('payment_method')!r}")
    if resp.get("decision") not in DECISIONS:
        bad.append(f"decision missing or unknown ({resp.get('decision')!r})")
    sc = resp.get("risk_score")
    if not isinstance(sc, int) or not 0 <= sc <= 100:
        bad.append(f"risk_score must be an integer 0-100 (got {sc!r})")
    codes = resp.get("reason_codes")
    if not isinstance(codes, list):
        bad.append("reason_codes missing")
    else:
        unknown = [c for c in codes if c not in KNOWN_CODES]
        if unknown:
            bad.append(f"unknown or not merchant-facing reason code(s): {unknown}")
    return bad


def order_time(ts):
    m = re.search(r"T(\d{2}):(\d{2})", str(ts or ""))
    return f"{m.group(1)}:{m.group(2)}" if m else None


def merchant_view(case: dict, sanitize=True) -> dict:
    req, resp = case["request"], case["response"]
    geo = resp.get("geo_signals") or {}
    oid, changed = clean_order_id(req.get("order_id")) if sanitize else (req.get("order_id"), False)
    dist = geo.get("billing_shipping_distance_km")
    view = {
        "order_id": oid,
        "amount_inr": req.get("amount"),
        "payment_method": req.get("payment_method"),
        "order_time": order_time(req.get("timestamp")),
        "risk_score": resp.get("risk_score"),
        "api_decision": resp.get("decision"),
        "reason_codes": list(resp.get("reason_codes") or []),
        "billing_shipping_distance_km": None if dist is None else round(float(dist), 1),
        "region_risk": geo.get("region_risk"),
        "billing_district": geo.get("billing_district"),
        "billing_state": geo.get("billing_state"),
        "model_version": resp.get("model_version"),
        "fairness_note": resp.get("fairness_note"),
    }
    notes = []
    if changed:
        notes.append("order_id contained extra text; it was removed before the LLM call")
    if view["billing_district"] is None or view["billing_state"] is None:
        notes.append("billing district/state unknown (PIN code not found in the lookup)")
    return {"view": view, "code_notes": notes}


def customer_view(mview: dict, oracle_out: dict) -> dict:
    return {"order_id": mview["order_id"], "amount_inr": mview["amount_inr"],
            "payment_method": mview["payment_method"], "action": oracle_out["action"],
            "offer_prepaid_option": oracle_out["prepaid"],
            "may_say_high_value": "HIGH_AMOUNT" in mview["reason_codes"], "store_name": "{store_name}"}


def reviewer_view(case: dict) -> dict:
    resp = copy.deepcopy(case["response"])
    (resp.get("geo_signals") or {}).pop("income_tier", None)
    req = copy.deepcopy(case["request"])
    cust = req.get("customer") or {}
    for k in ("billing_pincode", "shipping_pincode"):
        if cust.get(k):
            cust[k] = str(cust[k])[:3] + "***"
    return {"request": req, "response": resp}
