"""RiskBrief approval page (Gradio). Pick a test order or paste an order + GeoRisk API JSON, run the final
prompt chain on the local model, read the brief, the English/Hindi drafts and the check report, then
Approve / Edit / Reject. Sending and the OTP step are SIMULATED (nothing is sent anywhere).

    python code/app.py      -> http://127.0.0.1:7860
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief import chain  # noqa: E402
from riskbrief.llm import MODEL  # noqa: E402

CASES = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
CHOICES = [f"{c['id']} ({c['type']}): {c['title']}" for c in CASES]
DECISIONS = REPO / "test-data" / "approval_log.jsonl"


def load_case(choice):
    c = CASES[CHOICES.index(choice)]
    return json.dumps({"request": c["request"], "response": c["response"]}, indent=1, ensure_ascii=False), \
        c.get("language", "en")


def fmt_brief(b):
    if not b:
        return "No brief."
    lines = [f"### Action: **{b.get('recommended_action')}**  (playbook rule {b.get('playbook_rule')})", "",
             f"API decision **{b.get('api_decision', '-')}**, risk score **{b.get('risk_score', '-')}**"
             f"  |  status: {b.get('status')}", ""]
    if b.get("offer_prepaid_option"):
        lines += ["Prepaid option may be offered (cash on delivery stays available).", ""]
    if b.get("secondary_action") not in (None, "NONE"):
        lines += [f"If the OTP is not confirmed: {b.get('secondary_action')}", ""]
    lines.append(b.get("summary", ""))
    for r in b.get("reasons", []) or []:
        lines.append(f"- **{r.get('code')}** ({r.get('evidence_field')} = {r.get('evidence_value')}): "
                     f"{r.get('plain_language')}")
    for n in (b.get("data_quality_notes") or []) + (b.get("code_notes") or []):
        lines.append(f"- Data note: {n}")
    if b.get("caveat"):
        lines += ["", f"*{b['caveat']}*", f"*{b.get('disclaimer', '')}*"]
    return "\n".join(lines)


def check_report(res):
    rows = []
    for step, errs in res.get("errors", {}).items():
        for k, v in errs.items():
            rows.append(f"{step} {k}: {'PASS' if not v else 'FAIL - ' + '; '.join(v)}")
    for e in res.get("events", []):
        if e.get("step") == "oracle_override":
            rows.append(f"Playbook override: LLM said {e['llm_action']}, playbook says {e['playbook_action']}")
        elif e.get("repair"):
            rows.append(f"{e['step']} repair (P4): {len(e['errors_before'])} error(s) before, "
                        f"{len(e['errors_after'])} after")
        elif e.get("static_template"):
            rows.append(f"{e['step']}: repair failed, safe fixed template used")
    secs = sum(c["stats"]["seconds"] for c in res.get("calls", []))
    rows.append(f"LLM calls: {len(res.get('calls', []))}, total {secs:.1f} s, model {MODEL}")
    return "\n".join(rows) or "No LLM call (input failed validation, NEEDS_HUMAN)."


def run(case_json, language):
    try:
        data = json.loads(case_json)
    except json.JSONDecodeError as e:
        return "Input is not valid JSON: " + str(e), "", "", "", "{}"
    case = {"id": "ui", "request": data.get("request", {}), "response": data.get("response", {}),
            "language": language}
    res = chain.run_chain(case, "final", repair=True, language=language) if not chain.validate(case) else \
        chain.needs_human(case, chain.validate(case), "final")
    fin = res["final"]
    en = (fin.get("message_en") or {}).get("message", "") if fin.get("message_en") else "(no customer message)"
    hi = (fin.get("message_hi") or {}).get("message", "") if fin.get("message_hi") else ""
    return fmt_brief(fin.get("brief")), en, hi, check_report(res), \
        json.dumps(fin.get("reviewer_view"), indent=1, ensure_ascii=False)


def decide(decision, en, hi, case_json):
    rec = {"time": datetime.now().isoformat(timespec="seconds"), "decision": decision, "message_en": en,
           "message_hi": hi, "input_order_id": json.loads(case_json).get("request", {}).get("order_id")}
    with DECISIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if decision == "Approve":
        return "Approved. (Simulated) OTP step started and message queued. Nothing was really sent."
    if decision == "Edit":
        return "Saved as edited draft. A person changed the text before approval."
    return "Rejected. No message will be sent; the order stays with the reviewer."


with gr.Blocks(title="RiskBrief - order review assistant") as demo:
    gr.Markdown("# RiskBrief: order review assistant\nGeoRisk API result -> decision brief -> customer message "
                f"draft (EN/HI) -> automatic checks -> human approval. Model: `{MODEL}` on Ollama (local).")
    with gr.Row():
        with gr.Column(scale=5):
            pick = gr.Dropdown(CHOICES, value=CHOICES[1], label="Test order")
            lang = gr.Radio(["en", "hi"], value="en", label="Customer message language")
            box = gr.Code(language="json", label="Order + GeoRisk API response (editable)", lines=18)
            btn = gr.Button("Run RiskBrief", variant="primary")
        with gr.Column(scale=6):
            brief = gr.Markdown(label="Decision brief")
            en = gr.Textbox(label="English message draft (needs approval)", lines=3)
            hi = gr.Textbox(label="Hindi message draft (needs approval)", lines=3)
            report = gr.Textbox(label="Check report", lines=8)
            with gr.Row():
                a = gr.Button("Approve")
                e = gr.Button("Edit")
                r = gr.Button("Reject")
            status = gr.Markdown()
            with gr.Accordion("Redacted API JSON (income tier removed, PINs masked)", open=False):
                red = gr.Code(language="json")
    pick.change(load_case, pick, [box, lang])
    demo.load(load_case, pick, [box, lang])
    btn.click(run, [box, lang], [brief, en, hi, report, red])
    a.click(lambda x, y, z: decide("Approve", x, y, z), [en, hi, box], status)
    e.click(lambda x, y, z: decide("Edit", x, y, z), [en, hi, box], status)
    r.click(lambda x, y, z: decide("Reject", x, y, z), [en, hi, box], status)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
