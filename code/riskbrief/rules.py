"""Fixed knowledge used by every prompt version and by the code checks: reason-code glossary,
merchant playbook (the oracle), fixed sentences, schemas. The prompts get the glossary and the
playbook as text built from these same tables, so the prompt and the code never disagree."""
import re

KNOWN_CODES = ["HIGH_AMOUNT", "LARGE_BILLING_SHIPPING_DISTANCE", "ODD_HOUR", "RISKY_PAYMENT_METHOD",
               "HIGH_RISK_REGION"]
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "cod"]
DECISIONS = ["approve", "review", "decline"]
ACTIONS = ["APPROVE", "OTP_VERIFY", "MANUAL_REVIEW", "NEEDS_HUMAN"]
RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R8"]

GLOSSARY = {
    "HIGH_AMOUNT": "the order amount is Rs 5,000 or more",
    "LARGE_BILLING_SHIPPING_DISTANCE": "the shipping address is more than 300 km from the billing address",
    "ODD_HOUR": "the order was placed before 06:00 (early morning)",
    "RISKY_PAYMENT_METHOD": "the payment method is cash on delivery or a wallet",
    "HIGH_RISK_REGION": "(explained by a fixed sentence added by code; never explain it yourself)",
}
CONSTANTS = {0, 6, 50, 79, 80, 100, 300, 5000}           # numbers the glossary/bands themselves use

REGION_SENTENCE = ("The billing state's rate in the model's synthetic training data is above average. "
                   "This alone is never a reason to decline, block or cancel an order.")
CAVEAT = ("The risk score comes from a model trained on synthetic data. It is decision support, not proof "
          "of fraud.")
DISCLAIMER = "AI-drafted. A person must check and approve it before anything is sent to the customer."
DOWNGRADE_PREFIX = "Borderline decline driven only by region risk"

GLOSSARY_TEXT = "\n".join(f"- {k}: {v}" for k, v in GLOSSARY.items()) + (
    "\nThe API lists at most 3 codes (the biggest contributors). A missing code does NOT mean that factor had "
    "no effect, so never say a factor did not matter. Codes always push risk UP; never say a code lowers risk."
    "\nScore bands: approve below 50, review 50-79, decline 80 and above. The API decision is final; never "
    "change it, even if the score looks like another band.")

PLAYBOOK_TEXT = """R1  decision approve, no reason codes            -> APPROVE, prepaid offer false, secondary NONE, no customer message
R2  decision approve, with reason codes          -> APPROVE (codes are for information only), prepaid false, NONE, no message
R3  decision review, payment cod                 -> OTP_VERIFY, prepaid offer true (optional, COD stays available), secondary MANUAL_CALL, customer message yes
R4  decision review, payment upi/card/netbanking/wallet -> OTP_VERIFY, prepaid false, secondary MANUAL_CALL, customer message yes
R5  decision review AND (every code is HIGH_RISK_REGION OR fairness_note says the decision was downgraded) -> OTP_VERIFY only, prepaid false, secondary NONE, fairness flag, customer message yes (R5 wins over R3/R4)
R6  decision decline                             -> MANUAL_REVIEW (a person decides; never cancel), prepaid false, NONE, no customer message
R7  (extra) district/state are null              -> keep the action, add a data-quality note
Never use the buyer's location, state, district or income as a reason to decline, block or cancel."""

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {"type": "string"},
        "status": {"type": "string", "enum": ["ok", "refused"]},
        "api_decision": {"type": "string", "enum": DECISIONS},
        "risk_score": {"type": "integer"},
        "recommended_action": {"type": "string", "enum": ACTIONS},
        "offer_prepaid_option": {"type": "boolean"},
        "secondary_action": {"type": "string", "enum": ["NONE", "MANUAL_CALL"]},
        "playbook_rule": {"type": "string", "enum": ["R1", "R2", "R3", "R4", "R5", "R6"]},
        "reasons": {"type": "array", "items": {
            "type": "object",
            "properties": {"code": {"type": "string", "enum": KNOWN_CODES},
                           "evidence_field": {"type": "string"}, "evidence_value": {"type": "string"},
                           "plain_language": {"type": "string"}},
            "required": ["code", "evidence_field", "evidence_value", "plain_language"]}},
        "summary": {"type": "string"},
        "data_quality_notes": {"type": "array", "items": {"type": "string"}},
        "fairness_check": {"type": "object", "properties": {
            "location_or_income_used_as_reason": {"type": "boolean"}, "note": {"type": "string"}},
            "required": ["location_or_income_used_as_reason", "note"]},
        "customer_message_needed": {"type": "boolean"},
    },
    "required": ["order_id", "status", "api_decision", "risk_score", "recommended_action", "offer_prepaid_option",
                 "secondary_action", "playbook_rule", "reasons", "summary", "data_quality_notes",
                 "fairness_check", "customer_message_needed"],
}
SINGLE_SCHEMA = {  # v2: one call returns the brief and the customer message together
    "type": "object",
    "properties": {**BRIEF_SCHEMA["properties"], "customer_message_en": {"type": "string"}},
    "required": BRIEF_SCHEMA["required"] + ["customer_message_en"],
}
MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {"order_id": {"type": "string"}, "language": {"type": "string", "enum": ["en"]},
                   "message": {"type": "string"}, "facts_used": {"type": "array", "items": {"type": "string"}}},
    "required": ["order_id", "language", "message", "facts_used"],
}
HINDI_SCHEMA = {
    "type": "object",
    "properties": {"order_id": {"type": "string"}, "language": {"type": "string", "enum": ["hi"]},
                   "message": {"type": "string"}},
    "required": ["order_id", "language", "message"],
}
V1_KEYS = ["action", "seller_note", "buyer_message"]


def oracle(view: dict) -> dict:
    """The merchant playbook in code. view = validated merchant view (or {'invalid': [...]})."""
    if view.get("invalid"):
        return {"rule": "R8", "action": "NEEDS_HUMAN", "prepaid": False, "secondary": "NONE", "message": False,
                "fairness_flag": False}
    d, codes = view["api_decision"], view["reason_codes"]
    downgraded = (view.get("fairness_note") or "").startswith(DOWNGRADE_PREFIX)
    if d == "approve":
        return {"rule": "R2" if codes else "R1", "action": "APPROVE", "prepaid": False, "secondary": "NONE",
                "message": False, "fairness_flag": False}
    if d == "decline":
        return {"rule": "R6", "action": "MANUAL_REVIEW", "prepaid": False, "secondary": "NONE", "message": False,
                "fairness_flag": False}
    if (codes and all(c == "HIGH_RISK_REGION" for c in codes)) or downgraded:
        return {"rule": "R5", "action": "OTP_VERIFY", "prepaid": False, "secondary": "NONE", "message": True,
                "fairness_flag": True}
    if view["payment_method"] == "cod":
        return {"rule": "R3", "action": "OTP_VERIFY", "prepaid": True, "secondary": "MANUAL_CALL", "message": True,
                "fairness_flag": False}
    return {"rule": "R4", "action": "OTP_VERIFY", "prepaid": False, "secondary": "MANUAL_CALL", "message": True,
            "fairness_flag": False}


# v1 (M1 baseline) used free-text action names; fixed mapping written before any run.
V1_ACTION_MAP = [(r"approve", "APPROVE"), (r"otp", "OTP_VERIFY"), (r"prepaid", "OTP_VERIFY"),
                 (r"call", "MANUAL_REVIEW"), (r"review|manual|hold", "MANUAL_REVIEW"),
                 (r"decline|cancel|reject|block", "DECLINE")]


def map_v1_action(text: str) -> str:
    t = (text or "").lower()
    for pat, act in V1_ACTION_MAP:
        if re.search(pat, t):
            return act
    return "UNKNOWN"
