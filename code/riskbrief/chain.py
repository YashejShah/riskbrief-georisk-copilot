"""RiskBrief prompt versions.

v1     M1 baseline: one call, free-form JSON (action, seller_note, buyer_message), full API JSON as input.
v2     one strong call: glossary + playbook + data tags + JSON schema, merchant view (no PINs/income tier).
v3     chain: P1 brief (schema, few-shot) -> P2 English message (customer view only) -> P3 Hindi (translate).
final  v3 prompts improved after the v3 run + P4 repair driven by the checker + code safety net
       (oracle override, fixed sentences, static templates when a repair also fails).
"""
import json
import re
from pathlib import Path

from . import checks as C
from .llm import chat, parse_json
from .rules import (BRIEF_SCHEMA, CAVEAT, DISCLAIMER, GLOSSARY_TEXT, HINDI_SCHEMA, MESSAGE_SCHEMA, PLAYBOOK_TEXT,
                    REGION_SENTENCE, SINGLE_SCHEMA, V1_KEYS, map_v1_action, oracle)
from .views import customer_view, merchant_view, reviewer_view, validate

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"
EXAMPLES = json.loads((Path(__file__).with_name("examples.json")).read_text(encoding="utf-8"))
# v5 adds a 4th example for the region-only rule R5 (v4 kept writing "the state is high-risk" there);
# final adds a 5th example for R2 (after the R5 example, v5 dropped the reasons of approve-with-codes orders)
_R5 = json.loads((Path(__file__).with_name("examples_r5.json")).read_text(encoding="utf-8"))
_R2_FILE = Path(__file__).with_name("examples_r2.json")
_R2 = json.loads(_R2_FILE.read_text(encoding="utf-8")) if _R2_FILE.exists() else []
_R2_V6 = json.loads((Path(__file__).with_name("examples_r2_v6.json")).read_text(encoding="utf-8")) \
    if Path(__file__).with_name("examples_r2_v6.json").exists() else _R2
# v6's R2 example said "listed 2 reason codes"; the model copied the count ("1 reason code"), which is not an
# input number (C2). final uses the same example without the count.
EXAMPLES_BY_VERSION = {"v3": EXAMPLES, "v4": EXAMPLES, "v5": EXAMPLES + _R5,
                       "v6": EXAMPLES[:1] + _R2_V6 + EXAMPLES[1:] + _R5,
                       "final": EXAMPLES[:1] + _R2 + EXAMPLES[1:] + _R5}
EXAMPLES_FINAL = EXAMPLES_BY_VERSION["final"]


def load_prompt(version: str, name: str):
    text = (PROMPTS / version / f"{name}.txt").read_text(encoding="utf-8")
    sys_part, user_part = text.split("### USER", 1)
    sys_part = sys_part.replace("### SYSTEM", "", 1).strip()
    return ("" if sys_part == "none" else sys_part), user_part.strip()


def fill(template: str, **vars_):
    for k, v in vars_.items():
        template = template.replace("{" + k + "}", v)
    return template


def dumps(x):
    return json.dumps(x, ensure_ascii=False, indent=1)


def examples_text(version="final"):
    parts = ["Examples (from other orders; follow the same style):"]
    for i, ex in enumerate(EXAMPLES_BY_VERSION.get(version, EXAMPLES), 1):
        parts.append(f"Example {i} input:\n<merchant_view>\n{dumps(ex['view'])}\n</merchant_view>\n"
                     f"Example {i} output:\n{json.dumps(ex['brief'], ensure_ascii=False)}")
    return "\n".join(parts) + "\n"


def call(version, name, fmt, **vars_):
    system, user = load_prompt(version, name)
    system = fill(system, glossary=GLOSSARY_TEXT, playbook=PLAYBOOK_TEXT, examples=examples_text(version))
    user = fill(user, **vars_)
    r = chat(system, user, fmt=fmt)
    obj, fenced, err = parse_json(r["text"])
    return {"prompt": name, "system": system, "user": user, "raw": r["text"], "json": obj, "fenced": fenced,
            "parse_error": err, "stats": {k: r[k] for k in ("seconds", "prompt_tokens", "output_tokens")}}


# ------------------------------------------------------------------ check bundles
def brief_errors(case, brief_obj, perr, view, orc):
    if brief_obj is None:
        return {"C1": C.c1_schema(None, BRIEF_SCHEMA, perr)}
    texts = [brief_obj.get("summary", "")] + [r.get("plain_language", "") for r in brief_obj.get("reasons", [])] + \
        list(brief_obj.get("data_quality_notes", [])) + [(brief_obj.get("fairness_check") or {}).get("note", "")]
    return {"C1": C.c1_schema(brief_obj, BRIEF_SCHEMA), "C2": C.c2_numbers(texts, C.source_numbers(view)),
            "C3": C.c3_reasons(brief_obj, view["reason_codes"]), "C4": C.c4_decision(brief_obj, view),
            "C5": C.c5_action(brief_obj, orc), "C6": C.c6_places(texts, view),
            "C7": C.c7_blame(texts), "C9": C.c9_policy(texts), "C11": C.c11_injection(case, brief_obj, orc)}


def message_errors(msg_obj, perr, cview, view, orc, schema, hindi=False, english=None):
    if msg_obj is None:
        return {"C1": C.c1_schema(None, schema, perr)}
    m = str(msg_obj.get("message", ""))
    keep = [cview["order_id"]] + ([str(cview["amount_inr"])] if english and str(cview["amount_inr"]) in
                                  re.sub(r"(?<=\d),(?=\d)", "", english) else [])
    return {"C1": C.c1_schema(msg_obj, schema), "C2": C.c2_numbers([m], C.source_numbers(cview)),
            "C7": C.c7_banned(m, view, hindi), "C8": C.c8_message(True, orc, m, view),
            "C9": C.c9_policy([m]), "C10": C.c10_length(m, 400 if hindi else 320, hindi,
                                                          keep if hindi else (), english if hindi else None)}


def flat(errs):
    return [f"{k}: {e}" for k, v in errs.items() for e in v]


# ------------------------------------------------------------------ versions
def run_v1(case):
    """M1 baseline prompt exactly as declared (raw ORDER + API JSON, PINs and income tier included)."""
    bad = validate(case)
    view = merchant_view(case)["view"] if not bad else {}
    orc = oracle({"invalid": bad} if bad else view)
    r = call("v1", "P0_baseline", None, order=json.dumps(case["request"], ensure_ascii=False),
             api_json=json.dumps(case["response"], ensure_ascii=False))
    o = r["json"]
    errs = {"C1": C.c1_schema(o, {"required": V1_KEYS, "type": "object"}, r["parse_error"])} if o is not None else \
        {"C1": [f"not valid JSON ({r['parse_error']})"]}
    if r["fenced"]:
        errs["C1"].append("JSON wrapped in a code fence")
    if o is not None:
        src = C.source_numbers({"req": case["request"], "resp": case["response"]})
        texts = [str(o.get("seller_note", "")), str(o.get("buyer_message", ""))]
        act = map_v1_action(o.get("action"))
        errs["C2"] = C.c2_numbers(texts, src)
        errs["C5"] = [] if act == orc["action"] else [f"action '{o.get('action')}' -> {act}, playbook says "
                                                       f"{orc['action']}"]
        if view:
            errs["C6"] = C.c6_places(texts, view)
            errs["C7"] = C.c7_banned(str(o.get("buyer_message", "")), view)
        msg = str(o.get("buyer_message", "") or "")
        errs["C8"] = C.c8_message(bool(msg.strip()), orc, msg, view or {"reason_codes": []})
        errs["C9"] = C.c9_policy(texts)
        errs["C11"] = C.c11_injection(case, {"recommended_action": act}, orc)
    return {"version": "v1", "oracle": orc, "calls": [r], "errors": errs,
            "raw_action": map_v1_action((o or {}).get("action")), "final": o}


def run_v2(case):
    bad = validate(case)
    if bad:
        return needs_human(case, bad, "v2")
    mv = merchant_view(case)
    view, orc = mv["view"], oracle(mv["view"])
    r = call("v2", "P1_single", SINGLE_SCHEMA, merchant_view=dumps(view))
    o = r["json"]
    errs = brief_errors(case, o, r["parse_error"], view, orc)
    if o is not None:
        errs["C1"] = C.c1_schema(o, SINGLE_SCHEMA)
        m = str(o.get("customer_message_en", "") or "")
        cv = customer_view(view, orc)
        for k, v in message_errors({"message": m}, None, cv, view, orc, {"type": "object"}).items():
            if k in ("C7", "C9", "C10") and m.strip():
                errs[k] = errs.get(k, []) + v
        errs["C8"] = C.c8_message(bool(m.strip()), orc, m, view)
    return {"version": "v2", "oracle": orc, "calls": [r], "errors": errs,
            "raw_action": (o or {}).get("recommended_action"), "final": o}


def needs_human(case, bad, version):
    orc = oracle({"invalid": bad})
    brief = {"order_id": str(case.get("request", {}).get("order_id", "")), "status": "ok",
             "recommended_action": "NEEDS_HUMAN", "playbook_rule": "R8",
             "summary": "This order needs a person to look at it. RiskBrief did not call the LLM because: "
                        + "; ".join(bad), "human_approval_required": True}
    return {"version": version, "oracle": orc, "calls": [], "errors": {}, "raw_action": "NEEDS_HUMAN",
            "final": {"brief": brief, "message_en": None, "message_hi": None, "reviewer_view": reviewer_view(case)}}


def run_chain(case, version="v3", repair=False, language=None):
    """v3 (no repair) and final (repair + safety net) share this code; only the prompt folder and the
    repair switch differ."""
    language = language or case.get("language", "en")
    bad = validate(case)
    if bad:
        return needs_human(case, bad, version)
    mv = merchant_view(case)
    view, orc = mv["view"], oracle(mv["view"])
    calls, errors, events = [], {}, []

    # ---- P1 brief
    r1 = call(version, "P1_brief", BRIEF_SCHEMA, merchant_view=dumps(view))
    calls.append(r1)
    e1 = brief_errors(case, r1["json"], r1["parse_error"], view, orc)
    raw_action = (r1["json"] or {}).get("recommended_action")
    brief = r1["json"]
    if flat(e1) and repair:
        rr = call(version, "P4_repair", BRIEF_SCHEMA, errors="\n".join(flat(e1)), input_data=dumps(view),
                  previous_output=r1["raw"], output_kind="decision brief")
        calls.append(rr)
        e1r = brief_errors(case, rr["json"], rr["parse_error"], view, orc)
        events.append({"step": "P1", "repair": True, "errors_before": flat(e1), "errors_after": flat(e1r)})
        if not flat(e1r):
            brief, e1 = rr["json"], e1r
        else:
            e1 = e1r
    errors["P1"] = e1
    escalated = bool(flat(e1)) and repair
    if repair:                                   # code safety net (always applied in the final version)
        brief = dict(brief or {})
        if escalated:
            brief["status"] = "ESCALATE_TO_HUMAN"
            brief["summary"] = ("Automatic checks failed twice, so this brief was not trusted. A person should "
                                "read the API result below.")
        if brief.get("recommended_action") != orc["action"]:
            events.append({"step": "oracle_override", "llm_action": brief.get("recommended_action"),
                           "playbook_action": orc["action"]})
        brief.update({"recommended_action": orc["action"], "playbook_rule": orc["rule"],
                      "offer_prepaid_option": orc["prepaid"], "secondary_action": orc["secondary"],
                      "customer_message_needed": orc["message"], "api_decision": view["api_decision"],
                      "risk_score": view["risk_score"], "human_approval_required": True,
                      "caveat": CAVEAT, "disclaimer": DISCLAIMER, "model_version": view["model_version"],
                      "prompt_version": version, "code_notes": mv["code_notes"]})
        for r in brief.get("reasons", []):
            if r.get("code") == "HIGH_RISK_REGION":
                r["plain_language"] = REGION_SENTENCE
        brief.setdefault("fairness_check", {})["fairness_flag"] = orc["fairness_flag"]

    # ---- P2 English message (only when the playbook says so)
    msg_en = msg_hi = None
    if orc["message"]:
        cv = customer_view(view, orc)
        r2 = call(version, "P2_message_en", MESSAGE_SCHEMA, customer_view=dumps(cv))
        calls.append(r2)
        e2 = message_errors(r2["json"], r2["parse_error"], cv, view, orc, MESSAGE_SCHEMA)
        msg = r2["json"]
        if flat(e2) and repair:
            rr = call(version, "P4_repair", MESSAGE_SCHEMA, errors="\n".join(flat(e2)), input_data=dumps(cv),
                      previous_output=r2["raw"], output_kind="English customer message")
            calls.append(rr)
            e2r = message_errors(rr["json"], rr["parse_error"], cv, view, orc, MESSAGE_SCHEMA)
            events.append({"step": "P2", "repair": True, "errors_before": flat(e2), "errors_after": flat(e2r)})
            msg, e2 = (rr["json"], e2r) if not flat(e2r) else (static_en(cv), e2r)
            if flat(e2r):
                events.append({"step": "P2", "static_template": True})
        errors["P2"] = e2
        msg_en = msg
        # ---- P3 Hindi (translate the checked English text)
        if language == "hi" and msg_en:
            r3 = call(version, "P3_hindi", HINDI_SCHEMA, english_message=str(msg_en.get("message", "")))
            calls.append(r3)
            en_text = str(msg_en.get("message", ""))
            e3 = message_errors(r3["json"], r3["parse_error"], cv, view, orc, HINDI_SCHEMA, hindi=True,
                                english=en_text)
            hi = r3["json"]
            if flat(e3) and repair:
                rr = call(version, "P4_repair", HINDI_SCHEMA, errors="\n".join(flat(e3)),
                          input_data=str(msg_en.get("message", "")), previous_output=r3["raw"],
                          output_kind="Hindi translation")
                calls.append(rr)
                e3r = message_errors(rr["json"], rr["parse_error"], cv, view, orc, HINDI_SCHEMA, hindi=True,
                                     english=en_text)
                events.append({"step": "P3", "repair": True, "errors_before": flat(e3), "errors_after": flat(e3r)})
                hi, e3 = (rr["json"], e3r) if not flat(e3r) else (static_hi(cv), e3r)
                if flat(e3r):
                    events.append({"step": "P3", "static_template": True})
            errors["P3"] = e3
            msg_hi = hi
    else:
        errors["P2"] = {"C8": []}
    return {"version": version, "oracle": orc, "calls": calls, "errors": errors, "raw_action": raw_action,
            "events": events, "escalated": escalated,
            "final": {"brief": brief, "message_en": msg_en, "message_hi": msg_hi,
                      "reviewer_view": reviewer_view(case)}}


def static_en(cv):
    extra = (" If you prefer, you can also pay online by UPI or card; cash on delivery stays available."
             if cv["offer_prepaid_option"] else "")
    hv = "high-value order" if cv.get("may_say_high_value") else "order"
    return {"order_id": cv["order_id"], "language": "en", "template": True,
            "message": f"Thank you for your {hv} {cv['order_id']}! We will send you a one-time password (OTP) to "
                       f"confirm it.{extra} - {{store_name}}", "facts_used": ["order_id", "action"]}


def static_hi(cv):
    extra = (" आप चाहें तो UPI या कार्ड से ऑनलाइन भुगतान भी कर सकते हैं; कैश ऑन डिलीवरी भी उपलब्ध रहेगी।"
             if cv["offer_prepaid_option"] else "")
    hv = "ज़्यादा कीमत वाले ऑर्डर" if cv.get("may_say_high_value") else "ऑर्डर"
    return {"order_id": cv["order_id"], "language": "hi", "template": True,
            "message": f"आपके {hv} {cv['order_id']} के लिए धन्यवाद! इसे पक्का करने के लिए हम आपको एक वन-टाइम "
                       f"पासवर्ड (OTP) भेजेंगे।{extra} - {{store_name}}"}


def run(case, version):
    if version == "v1":
        return run_v1(case)
    if version == "v2":
        return run_v2(case)
    if version == "v3":
        return run_chain(case, "v3", repair=False)
    if version in ("v4", "v5", "v6"):
        return run_chain(case, version, repair=True)
    return run_chain(case, "final", repair=True)
