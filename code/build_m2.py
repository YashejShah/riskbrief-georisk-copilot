"""Build the Milestone 2 PDF (7 sections, guideline order) and the supporting document (technical report) from
the real run outputs in test-data/ and the prompt files. Team details and links come from code/m2_config.json.

    python code/build_m2.py   (Python with python-docx, pymupdf, pywin32; Word converts DOCX to PDF)
-> docs/M2_<TeamID>_RiskBrief.pdf  and  docs/GeoRiskCopilot_TechnicalReport.pdf
"""
import json
import re
import sys
from pathlib import Path

import pymupdf
import pythoncom
import win32com.client as win32
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
from riskbrief.rules import GLOSSARY_TEXT, PLAYBOOK_TEXT  # noqa: E402
from riskbrief.llm import MODEL, SETTINGS  # noqa: E402

CFG = json.loads((REPO / "code" / "m2_config.json").read_text(encoding="utf-8"))
CASES = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
HELD = json.loads((REPO / "test-data" / "heldout_cases.json").read_text(encoding="utf-8"))
OUT = REPO / "test-data" / "outputs"
DOCS = REPO / "docs"
VERSIONS = ("v1", "v2", "v3", "v4", "v5", "v6", "final")
S = {v: json.loads((OUT / v / "summary.json").read_text(encoding="utf-8")) for v in VERSIONS + ("final_heldout",)}
NAVY = RGBColor(0x1F, 0x3A, 0x68)
N_VERSIONS = len(VERSIONS)
N_TESTS = len(CASES) + len(HELD)


def rec(v, cid):
    if cid.startswith("H"):
        v = v + "_heldout"
    return json.loads((OUT / v / f"{cid}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ document helpers
class Doc:
    def __init__(self):
        self.d = d = Document()
        s = d.sections[0]
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        s.left_margin = s.right_margin = Cm(1.9)
        s.top_margin = s.bottom_margin = Cm(1.6)
        st = d.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10.5)
        st.paragraph_format.space_after = Pt(4)
        for name, size in (("Heading 1", 15), ("Heading 2", 12), ("Heading 3", 11)):
            h = d.styles[name]
            h.font.name = "Calibri"
            h.font.size = Pt(size)
            h.font.color.rgb = NAVY
        fp = s.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
            r = fp.add_run()
            el = OxmlElement("w:fldChar" if kind else "w:instrText")
            if kind:
                el.set(qn("w:fldCharType"), kind)
            else:
                el.set(qn("xml:space"), "preserve")
                el.text = txt
            r._r.append(el)

    def p(self, text, bold_prefix=None, size=None, italic=False, align=None, after=None):
        para = self.d.add_paragraph()
        if bold_prefix:
            r = para.add_run(bold_prefix)
            r.bold = True
            if size:
                r.font.size = Pt(size)
        for i, part in enumerate(re.split(r"(\*\*[^*]+\*\*)", text)):
            if not part:
                continue
            r = para.add_run(part[2:-2] if part.startswith("**") else part)
            r.bold = part.startswith("**")
            r.italic = italic
            if size:
                r.font.size = Pt(size)
        if align:
            para.alignment = align
        if after is not None:
            para.paragraph_format.space_after = Pt(after)
        return para

    def h(self, text, level=1, new_page=False):
        if new_page:
            self.d.add_page_break()
        return self.d.add_heading(text, level=level)

    def bullets(self, items):
        for it in items:
            para = self.d.add_paragraph(style="List Bullet")
            for part in re.split(r"(\*\*[^*]+\*\*)", it):
                if part:
                    r = para.add_run(part[2:-2] if part.startswith("**") else part)
                    r.bold = part.startswith("**")
            para.paragraph_format.space_after = Pt(1)

    def code(self, text, size=8):
        para = self.d.add_paragraph()
        r = para.add_run(text)
        r.font.name = "Consolas"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
        r._element.rPr.rFonts.set(qn("w:cs"), "Nirmala UI")
        r.font.size = Pt(size)
        para.paragraph_format.space_after = Pt(4)
        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F3F4F6")
        pPr.append(shd)
        return para

    def table(self, rows, widths, size=8.5, header=True):
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                c = t.cell(i, j)
                c.width = Cm(widths[j])
                c.text = ""
                para = c.paragraphs[0]
                para.paragraph_format.space_after = Pt(0)
                r = para.add_run(str(val))
                r.font.size = Pt(size)
                r._element.get_or_add_rPr()
                r._element.rPr.get_or_add_rFonts().set(qn("w:cs"), "Nirmala UI")
                if header and i == 0:
                    r.bold = True
                    pr = c._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), "DCE6F2")
                    pr.append(shd)
        self.d.add_paragraph().paragraph_format.space_after = Pt(0)
        return t

    def img(self, path, width_cm, caption):
        self.d.add_picture(str(path), width=Cm(width_cm))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.p(caption, size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)

    def save_pdf(self, docx_path, pdf_path):
        self.d.save(str(docx_path))
        pythoncom.CoInitialize()
        wd = win32.DispatchEx("Word.Application")
        wd.Visible = False
        wd.DisplayAlerts = 0
        try:
            doc = wd.Documents.Open(str(docx_path), False, True)
            doc.SaveAs2(str(pdf_path), 17)
            doc.Close(0)
        finally:
            wd.Quit()
            pythoncom.CoUninitialize()


# ------------------------------------------------------------------ shared facts
def pct(v, k="all_checks_pass"):
    return f"{S[v][k]}/{S[v]['cases']}"


def check_rate(v, k):
    d = S[v]["per_check"].get(k)
    return f"{d['pass']}/{d['pass'] + d['fail']}" if d else "n/a"


def v1_counts():
    fence = msg = 0
    for c in CASES:
        e = rec("v1", c["id"])["errors"]
        fence += any("code fence" in x for x in e.get("C1", []))
        msg += any("message was written" in x for x in e.get("C8", []))
    return fence, msg


def field_errors(v):
    n = 0
    for c in CASES:
        e = rec(v, c["id"])["errors"]
        flat = e if "C5" in e else {k: x for st in e.values() if isinstance(st, dict) for k, x in st.items()}
        n += bool(flat.get("C5"))
    return n


def blame(v):
    n = 0
    for c in CASES:
        e = rec(v, c["id"])["errors"]
        flat = e if "C7" in e and isinstance(e["C7"], list) and "P1" not in e else \
            {k: x for st in e.values() if isinstance(st, dict) for k, x in st.items()}
        n += any("blame" in x for x in flat.get("C7", []))
    return n


def hindi_fails(v):
    n = tot = 0
    for c in CASES:
        e = rec(v, c["id"])["errors"]
        if isinstance(e.get("P3"), dict):
            tot += 1
            n += any(e["P3"].values())
    return n, tot


def events(v):
    rep = tmpl = over = 0
    for c in CASES:
        r = rec(v, c["id"])
        for e in r.get("events", []):
            rep += bool(e.get("repair"))
            tmpl += bool(e.get("static_template"))
            over += e.get("step") == "oracle_override"
    return rep, tmpl, over


def short(s, n=95):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def prompt_text(version, name):
    t = (REPO / "prompts" / version / f"{name}.txt").read_text(encoding="utf-8")
    sys_part, user_part = t.split("### USER", 1)
    return sys_part.replace("### SYSTEM", "").strip(), user_part.strip()


# ------------------------------------------------------------------ test table rows (final version)
def expected(c):
    from riskbrief.rules import oracle
    from riskbrief.views import merchant_view, validate
    bad = validate(c)
    if bad:
        return "NEEDS_HUMAN (R8), no LLM call, no message"
    o = oracle(merchant_view(c)["view"])
    s = f"{o['action']} ({o['rule']})"
    if o["prepaid"]:
        s += ", prepaid optional"
    s += ", " + ({"en": "EN message", "hi": "EN + HI message"}[c.get("language", "en")] if o["message"]
                 else "no message")
    return s


def actual(c):
    r = rec("final", c["id"])
    f = r["final"]
    b = f["brief"]
    s = f"{b.get('recommended_action')} ({b.get('playbook_rule')})"
    if not r["calls"]:
        return s + ", no LLM call"
    if f.get("message_en"):
        s += ", EN" + (" (template)" if f["message_en"].get("template") else "")
    if f.get("message_hi"):
        s += " + HI" + (" (template)" if f["message_hi"].get("template") else "")
    if not f.get("message_en"):
        s += ", no message"
    ev = r.get("events", [])
    if any(e.get("repair") for e in ev):
        s += "; P4 repair used"
    if any(e.get("step") == "oracle_override" for e in ev):
        s += "; playbook override"
    return s


def passed(c):
    s = S["final_heldout" if c["id"].startswith("H") else "final"]["per_case"][c["id"]]
    r = rec("final", c["id"])
    tmpl = any(e.get("static_template") for e in r.get("events", []))
    return "Pass" if s["all_checks_pass"] and not tmpl else "Fail"


# ------------------------------------------------------------------ build the Milestone 2 PDF
def build_m2():
    D = Doc()
    L = CFG["links"]
    # ---- 1 cover
    D.h("1. Cover page")
    D.p(CFG["project_title"], size=17, after=2).runs[0].bold = True
    D.table([["Item", "Detail"], ["Team ID", CFG["team_id"]], ["Team name", CFG["team_name"]],
             ["Project title", CFG["project_title"]], ["Batch", CFG["batch"]], ["Faculty", CFG["faculty"]],
             ["Course", "SCSE4041 Prompt Engineering, Mini Project, Milestone 2"],
             ["Members"] + ["\n".join(f"{m['name']} ({m['enrollment']}) - {m['role']}" for m in CFG["members"])],
             ["Prototype link", L["prototype"]], ["Repository link", L["repository"]],
             ["Reel link", f"{L['reel']} ({L['reel_seconds']} seconds)"],
             ["Counts", f"4 final prompts, {N_TESTS} test inputs, {N_VERSIONS} prompt versions "
                        f"({', '.join(VERSIONS)})"]],
            [4, 13], size=10)
    D.p("Model: " + f"{MODEL} (Q4_K_M) on Ollama 0.40.16, local RTX 4070 Laptop GPU 8 GB; temperature 0, seed 42, "
        "num_ctx 8192. All test orders are synthetic.", size=9.5, italic=True)

    # ---- 2 prompt and solution design
    D.h("2. Prompt and solution design", new_page=True)
    D.h("(a) Design summary", 2)
    f_rep, f_tmpl, f_over = events("final")
    D.p("**What problem, for whom.** Small Indian online sellers get a fraud/RTO risk result from our GeoRisk API as a "
        "score and codes, for example 67 + ODD_HOUR + HIGH_AMOUNT. The person who reviews risky orders cannot tell "
        "from this what to do, and a badly worded message to the customer can lead to a complaint. RiskBrief is for "
        "that order reviewer.")
    D.p("**Input and output.** Input: one order (amount, payment method, time, PIN codes) and the JSON the GeoRisk "
        "API returned for it. Output: a decision brief (action, playbook rule, one plain sentence per reason code, "
        "short summary, data notes), a customer message draft in English and, if the reviewer selects it, in Hindi, "
        "and a check report. A person approves before anything is sent; sending is simulated.")
    D.p("**How many prompts and why.** Four. P1 writes the brief, P2 writes the English message, P3 translates the "
        "checked English into Hindi and P4 repairs an output that failed a code check. We split the work because one "
        f"prompt doing everything (our v2) got the playbook fields wrong in {field_errors('v2')} of 14 valid orders, "
        "and because P2 should never see the score, the reason codes or the location: it gets a customer view with "
        "only the order ID, amount, payment method and action, so it cannot leak them. P3 translates text that has "
        "already passed the checks instead of writing Hindi from scratch. Code (not an LLM) validates the input, "
        "applies the playbook and runs the checks C1-C11.")
    D.p(f"**Tool and model.** {MODEL} on Ollama, on our own laptop GPU. Order data should not leave the seller's "
        "machine, the 4.7 GB model fits in 8 GB of GPU memory, Ollama can force the output into a JSON schema, and "
        "there is no cost per call. Temperature 0 and seed 42 make runs repeatable.")
    D.p("**What changed since Milestone 1.** (1) Built and tested: Milestone 1 had no results. (2) Model: Qwen 2.5 7B "
        "instead of the Qwen3.5-9B / Llama 3.1 8B we listed, because it fits the 8 GB GPU with an 8,192-token "
        "context and was quick to set up; the comparison of models moves to Milestone 3. (3) The test set has 17 "
        "inputs made from the real API; the larger frozen test set, blind human rating and the counterfactual test "
        "move to Milestone 3. (4) Two checks were added after we read the outputs by hand (blame wording about a "
        "place in the brief, payment words changed in Hindi). (5) The reviewer-note refusal check (C12) is not "
        "built yet.")
    D.h("(b) Diagrams", 2)
    D.img(DOCS / "diagram_prompt_workflow.png", 16.5, "Figure 1. Prompt workflow (as built in code/riskbrief/chain.py)")
    D.img(DOCS / "diagram_task_decomposition.png", 16, "Figure 2. Task decomposition")
    D.img(DOCS / "diagram_input_output.png", 16, "Figure 3. Input-output flow and the two views")
    D.img(DOCS / "diagram_architecture.png", 16, "Figure 4. System architecture")
    D.h("(c) Prompt sheets", 2, new_page=False)
    D.p("Shared settings for P1-P4: " + f"{MODEL} on Ollama, temperature {SETTINGS['temperature']}, seed "
        f"{SETTINGS['seed']}, num_ctx {SETTINGS['num_ctx']}, JSON schema passed through Ollama's format option. "
        "{glossary} and {playbook} below are filled from code/riskbrief/rules.py:", size=9.5)
    D.code("{glossary} =\n" + GLOSSARY_TEXT + "\n\n{playbook} =\n" + PLAYBOOK_TEXT, 7.5)
    t02, t12 = rec("final", "T02"), rec("final", "T12")
    p4 = json.loads((REPO / "test-data" / "p4_sample_run.json").read_text(encoding="utf-8"))
    sheets = [
        ("P1", "Decision brief", "Step 1, after the pre-processor", "Turn the API result into a checked, "
         "rule-cited brief for the reviewer.", "P1_brief",
         ["{merchant_view}: the order and API result without PIN codes or income tier (JSON)",
          "{glossary}, {playbook}: fixed tables from rules.py", "{examples}: 5 example input/output pairs (rules "
          "R1, R2, R4, R3, R5) from API orders that are not test inputs (code/riskbrief/examples*.json); the "
          "example outputs were written by us"], "5",
         "JSON, schema BRIEF_SCHEMA in rules.py (order_id, status, api_decision, risk_score, recommended_action, "
         "offer_prepaid_option, secondary_action, playbook_rule, reasons[], summary, data_quality_notes[], "
         "fairness_check, customer_message_needed)", "T02", t02["calls"][0]),
        ("P2", "English customer message", "Step 2, only for review orders (R3, R4, R5)", "Write a short, polite "
         "message that asks the customer to confirm with an OTP.", "P2_message_en",
         ["{customer_view}: order_id, amount_inr, payment_method, action, offer_prepaid_option, "
          "may_say_high_value, store_name placeholder"], "1 BAD/GOOD pair",
         "JSON: order_id, language 'en', message (max 320 characters), facts_used[]", "T02",
         next(c for c in t02["calls"] if c["prompt"] == "P2_message_en")),
        ("P3", "Hindi rendering", "Step 3, only when the reviewer selects Hindi", "Translate the checked English "
         "message into simple Hindi without changing any fact.", "P3_hindi",
         ["{english_message}: the English message that passed the checks"], "2",
         "JSON: order_id, language 'hi', message (max 400 characters)", "T12",
         next(c for c in t12["calls"] if c["prompt"] == "P3_hindi")),
    ]
    for pid, name, step, purpose, fname, variables, nex, fmt, case_id, call in sheets:
        system, user = prompt_text("final", fname)
        D.h(f"{pid} - {name}", 3)
        D.table([["Field", "Value"], ["Prompt ID and name", f"{pid} {name} (prompts/final/{fname}.txt)"],
                 ["Step in the workflow", step], ["Purpose", purpose], ["Tool and model", f"Ollama, {MODEL}"],
                 ["Settings", "temperature 0, seed 42, num_ctx 8192, JSON schema"],
                 ["Variables", "\n".join(variables)], ["Number of examples", nex], ["Output format", fmt]],
                [3.6, 13.4], size=8.5)
        D.p("**Full system prompt:**", after=1)
        D.code(system, 7.3)
        D.p("**User prompt template:**", after=1)
        D.code(user, 7.3)
        D.p(f"**Sample run (test {case_id}, real input and actual output):**", after=1)
        D.code("INPUT (user message as sent):\n" + call["user"] + "\n\nACTUAL OUTPUT:\n" + call["raw"].strip(), 7)
    system, user = prompt_text("final", "P4_repair")
    D.h("P4 - Verify-and-repair", 3)
    D.table([["Field", "Value"], ["Prompt ID and name", "P4 Verify-and-repair (prompts/final/P4_repair.txt)"],
             ["Step in the workflow", "After any P1, P2 or P3 output fails a code check; one try only"],
             ["Purpose", "Fix exactly the errors the checker found, change nothing else."],
             ["Tool and model", f"Ollama, {MODEL}"], ["Settings", "temperature 0, seed 42, num_ctx 8192, "
                                                                   "same JSON schema as the failed step"],
             ["Variables", "{output_kind}: which output failed\n{input_data}: the view that step was given\n"
                           "{previous_output}: the failed JSON\n{errors}: the checker's exact error lines"],
             ["Number of examples", "0"], ["Output format", "The same JSON as the failed step"]], [3.6, 13.4],
            size=8.5)
    D.p("**Full system prompt:**", after=1)
    D.code(system, 7.3)
    D.p("**User prompt template:**", after=1)
    D.code(user, 7.3)
    D.p(f"**Sample run (the v3 brief of test {p4['case']} had these errors; real P4 call):**", after=1)
    D.code("ERRORS SENT:\n" + "\n".join(p4["errors_before"]) + "\n\nACTUAL OUTPUT (repaired brief):\n" +
           json.dumps(p4["repaired_output"], ensure_ascii=False, indent=1) + "\n\nERRORS AFTER REPAIR: " +
           (", ".join(p4["errors_after"]) or "none"), 7)

    # ---- 3 implementation
    D.h("3. Implementation", new_page=True)
    D.p("**What is built.** A Python package (code/riskbrief) with the pre-processor, the playbook oracle and "
        "glossary, the four prompts, the checker C1-C11 and the Ollama client; an evaluation runner that runs every "
        "prompt version on every test input and saves each real output with its checks; a Gradio approval page; and "
        "a Colab notebook with saved outputs. The GeoRisk API itself is our earlier AI/ML project and is used "
        "unchanged.")
    D.table([["Module", "What it does", "Status", "Notes"],
             ["Test-set generator", "Sends synthetic orders to the real GeoRisk API, saves 17 test inputs",
              "Working", "240 grid orders scanned; edge/invalid inputs labelled 'perturbed'"],
             ["Pre-processor", "Validates input, cleans order_id, builds merchant/customer/reviewer views", "Working",
              "Drops PIN codes and income tier before any LLM call"],
             ["Playbook oracle", "Rules R1-R8 in code", "Working", "Overrides the LLM action if they differ"],
             ["P1 decision brief", "Brief JSON with rule, reasons, summary", "Working", "Schema-constrained"],
             ["P2 English message", "Customer draft for review orders", "Working", "Sees the customer view only"],
             ["P3 Hindi rendering", "Translates the checked English", "Working",
              f"{hindi_fails('final')[1]} Hindi tests; read by a person only for these tests so far"],
             ["Checker C1-C11", "Code checks on every LLM output", "Working", "C12 (reviewer notes) not started"],
             ["P4 repair + safety net", "One repair try, then a fixed template; fixed sentences", "Working",
              f"In the final run: {f_rep} repair(s), {f_tmpl} template(s), {f_over} override(s)"],
             ["Approval page (Gradio)", "Run, read, Approve / Edit / Reject", "Working",
              "Sending and OTP are simulated"],
             ["Colab notebook", "Same chain on Colab (T4 GPU) with saved outputs", "Working",
              "First run downloads the 4.7 GB model"],
             ["Blind human rating", "Rubric H1-H6 by both members", "Not started", "Planned for Milestone 3"],
             ["Counterfactual test (X13)", "Change only the location, compare actions", "Not started",
              "Planned for Milestone 3"]],
            [3.4, 5.6, 2.0, 6.0], size=8.2)
    D.h("Prompt iteration log", 2)
    fence, msg = v1_counts()
    h3, h3t = hindi_fails("v3")
    hf, hft = hindi_fails("final")
    e4, e5, e6 = (S[v]["per_case"] for v in ("v4", "v5", "v6"))
    fails = lambda per: ", ".join(k for k, x in per.items() if not x["all_checks_pass"])  # noqa: E731
    D.p("Every version was run on the same 17 inputs T01-T17 with the same model and settings, and scored with the "
        "same checker (two checks were added after v3, then every version was re-scored). 'All checks pass' counts "
        "orders where every applicable check passed; from v2 on, the 3 invalid inputs are stopped by code before "
        "the LLM, which counts as a pass. T01-T17 were used to improve the prompts, so the final version was also "
        "run once on 6 new inputs (H01-H06).", size=9.5)
    D.table([["Version", "What changed", "Why it was changed", "Result after the change"],
             ["v1", "Milestone 1 baseline prompt, unchanged: one call, full API JSON (with PIN codes and income "
                    "tier), free-form JSON with action, seller_note, buyer_message", "Starting point",
              f"All checks pass {pct('v1')}. JSON wrapped in a code fence {fence}/17. A customer message written "
              f"when the playbook says none {msg}/17. Action matched the playbook {pct('v1', 'raw_action_ok')}. "
              "Followed the instruction hidden in the order ID (T10: approve)."],
             ["v2", "One strong prompt: glossary, playbook with rule IDs, <merchant_view> data tags, JSON schema "
                    "through Ollama, no PIN codes or income tier; invalid inputs stopped by code",
              "v1 had no rules, broke the JSON format, wrote messages for every order and obeyed an injected "
              "instruction",
              f"All checks pass {pct('v2')}; action correct {pct('v2', 'raw_action_ok')}; JSON valid "
              f"{check_rate('v2', 'C1')}. Playbook fields (rule, prepaid flag, secondary action) wrong in "
              f"{field_errors('v2')} of 14 valid orders; the brief called the state 'a high-risk region' in "
              f"{blame('v2')}."],
             ["v3", "Split into a chain: P1 brief with 3 examples, P2 English message from the customer view only "
                    "(with a BAD/GOOD example), P3 Hindi as a translation of the checked English",
              "v2 mixed up the playbook fields; the message writer should not see location or score",
              f"All checks pass {pct('v3')}. Playbook fields wrong in {field_errors('v3')} of 14 (often R5 chosen "
              f"for a normal review order). Place blame wording in {blame('v3')}. Hindi failed in {h3} of {h3t} "
              "(T12: 'UPI' became 'net banking', 'high-value' mistranslated)."],
             ["v4", "P1: step-by-step rule picker and a field table per rule, fixed wording for the region code; "
                    "P2: no other payment methods unless prepaid is offered; P3: fixed Hindi glossary and a second "
                    "example; P4 repair; code safety net",
              "v3 errors were about rule choice, place wording and Hindi words",
              f"All checks pass {pct('v4')}. Playbook fields wrong {field_errors('v4')}. Failed: {fails(e4)}: the "
              "brief still called the billing state 'high-risk', also after the P4 repair, so the brief was "
              "escalated to a person."],
             ["v5", "P1: added a 4th example for R5 (region-only review) and a stricter region rule",
              "There was no R5 example; the model kept describing the state as risky",
              f"All checks pass {pct('v5')}. T11 and T14 fixed, but {fails(e5)} broke: approve-with-codes orders "
              "(R2) got an empty reasons list, also after repair."],
             ["v6", "P1: added an R2 example (approve with reason codes)", "There was no R2 example; the new R5 "
                                                                          "example pulled R2 orders towards 'no reasons'",
              f"All checks pass {pct('v6')}. Failed: {fails(e6)}. T03/T09 copied the example's '2 reason codes' "
              "wording as '1 reason code', a number not in the input (C2). T14 called the district high-risk "
              "although its P1 input is identical to T11's, which passed: same input, different output."],
             ["final", "R2 example rewritten without the count; nothing else changed",
              "The count in our own example caused the C2 error",
              f"All checks pass {pct('final')}; raw LLM action correct {pct('final', 'raw_action_ok')}. "
              f"New inputs H01-H06 (run once): {pct('final_heldout')}. In the final run: {f_rep} P4 repair(s), "
              f"{f_tmpl} template(s), {f_over} override(s). Mean {S['final']['mean_seconds_per_case']} s per order."]],
            [1.2, 5.0, 4.0, 6.8], size=7.8)
    D.p("Full text of every version is below (also in prompts/<version>/). A prompt file that did not change from "
        "the previous version is not repeated. The few-shot examples are data files (code/riskbrief/examples*.json): "
        "v3 and v4 use 3 examples, v5 adds the R5 example, v6 and final add the R2 example.", size=9.5)
    prev = {}
    for v in VERSIONS[:-1]:
        for f in sorted((REPO / "prompts" / v).glob("*.txt")):
            text = f.read_text(encoding="utf-8")
            if prev.get(f.name) == text:
                D.p(f"**{v} / {f.stem}**: unchanged from the previous version.", size=9, after=2)
                continue
            prev[f.name] = text
            system, user = prompt_text(v, f.stem)
            D.p(f"**{v} / {f.stem}**", after=1)
            D.code(("SYSTEM:\n" + system + "\n\n" if system else "") + "USER:\n" + user, 6.6)
    D.p("**final / P1-P4**: full text in the prompt sheets, Section 2(c). Only the R2 example data changed from v6.",
        after=4)

    # ---- 4 demonstration and testing
    D.h("4. Demonstration and testing", new_page=True)
    allc = CASES + HELD
    types = {t: sum(c["type"] == t for c in allc) for t in ("Normal", "Edge", "Invalid")}
    D.p(f"Final version on all {N_TESTS} test inputs ({types['Normal']} normal, {types['Edge']} edge, "
        f"{types['Invalid']} invalid). T01-T17 were used while improving the prompts; H01-H06 were written after the "
        "final prompt was frozen and run once. 'Pass' means every applicable check passed in the final output "
        "without falling back to a fixed template. Earlier versions failed many of these tests (Section 3). Full "
        "outputs: test-data/outputs/final/ and final_heldout/.", size=9.5)
    rows = [["No.", "Input (short)", "Type", "Expected output", "Actual output (short)", "Pass/Fail"]]
    for c in allc:
        rows.append([c["id"], short(c["title"], 70), c["type"], expected(c), actual(c), passed(c)])
    D.table(rows, [1.0, 5.0, 1.4, 4.2, 4.3, 1.2], size=7.6)
    fails = [c["id"] for c in allc if passed(c) == "Fail"]
    if fails:
        D.p("Failed tests and why: " + "; ".join(fails), size=9)
    for img, cap in (("run_T02.png", "Test T02: COD order under review, brief + English draft, all checks passed"),
                     ("run_T13_hindi.png", "Test T13: wallet order under review, Hindi selected"),
                     ("run_T10_injection.png", "Test T10: instruction hidden in the order ID is ignored")):
        if (DOCS / img).exists():
            D.img(DOCS / img, 16.5, cap)
    D.h("Known limitations and what we will try next", 2)
    D.bullets([
        "**Tuned on its own tests.** The final prompt was improved on T01-T17 (7 versions), so 17/17 there is "
        "optimistic; only 6 inputs were truly new. Next: the frozen 40-order held-out set from our Milestone 1 "
        "plan, and a second model.",
        "**Same input, different output.** T11 and T14 send exactly the same first prompt, yet in v1, v4, v5 and "
        "v6 the two replies differed, even with temperature 0 and seed 42. One run per input is not enough. Next: run "
        "every input 3 times and report the spread.",
        "**Hindi checked by code and by us on only " + str(hft + 1) + " tests.** The checks cannot judge tone or "
        "naturalness. Next: Tanu's proofreading on more orders and a longer glossary.",
        "**The LLM is not trusted for the action, and the prototype needs a GPU.** The playbook in code overrides "
        "the action. Locally RiskBrief runs on our RTX 4070; on Colab it needs a T4 runtime and a 4.7 GB download "
        "each session.",
    ])

    # ---- 5 repository
    D.h("5. Repository", new_page=True)
    D.p(f"Repository: {L['repository']}")
    if (DOCS / "repo_screenshot.png").exists():
        D.img(DOCS / "repo_screenshot.png", 16.5, "Repository home page")
    D.bullets(["Code for the whole chain (code/riskbrief), the evaluation runner and the approval page are new since "
               "Milestone 1.",
               "prompts/ holds every version: v1 (Milestone 1 baseline), v2 to v6, and final (P1-P4).",
               f"test-data/ holds the {N_TESTS} inputs and every real output of every version with its check results.",
               "docs/ holds the diagrams and this PDF; CHANGELOG.md lists the dated changes."])

    # ---- 6 supporting document marker (pages appended later)
    D.h("6. Supporting document", new_page=True)
    D.p("Type: Technical report (also uploaded at Q16 as GeoRiskCopilot_TechnicalReport.pdf). It follows on the "
        "next pages.")
    return D


def build_contribution():
    D = Doc()
    D.h("7. Team contribution")
    m = CFG["members"]
    c = CFG["contribution"]
    D.table([["Member name", "Enrollment no.", "Role", "Tasks done in Milestone 2", "Evidence", "Contribution (%)"],
             [m[0]["name"], m[0]["enrollment"], m[0]["role"],
              "Test-set generator from the real API; pre-processor and views; playbook oracle; checker C1-C11; P4 "
              "repair and safety net; evaluation runner; approval page; Colab notebook; repository",
              "code/make_test_data.py, code/riskbrief/*.py, code/run_eval.py, code/app.py, prompts/final/P4_repair.txt,"
              " test-data/outputs/", c[m[0]["enrollment"]]],
             [m[1]["name"], m[1]["enrollment"], m[1]["role"],
              "Wording of P1-P3 and their examples; Hindi glossary in P3; proofreading of the Hindi outputs; review of "
              "the test results; reel voice-over",
              "prompts/final/P1_brief.txt, P2_message_en.txt, P3_hindi.txt; test-data/hindi_review.md; reel",
              c[m[1]["enrollment"]]]],
            [2.6, 2.4, 2.4, 5.0, 3.6, 1.6], size=8.3)
    D.p("Both members reviewed every prompt change. Both members agree with this table.", size=9.5)
    D.p("AI assistance: we used an AI assistant (Claude) to help write code and draft text. Every result in this "
        "document comes from our own runs, saved in test-data/.", size=9, italic=True)
    return D


def build_tech_report():
    D = Doc()
    s = D.d.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.3)
    D.d.styles["Normal"].font.size = Pt(9.5)
    D.p("RiskBrief: Technical report", size=15, after=0).runs[0].bold = True
    D.p(f"Team {CFG['team_name']} ({CFG['team_id']}): " + ", ".join(f"{x['name']} ({x['enrollment']})"
                                                                    for x in CFG["members"]), size=9, italic=True)
    D.p("**Architecture.** Synthetic order -> GeoRisk API (FastAPI, LightGBM, SHAP reason codes; our AI/ML project) "
        "-> pre-processor in Python (validation, order_id cleaning, merchant view without PIN codes and income tier, "
        "customer view, redacted reviewer view, playbook oracle R1-R8) -> P1 decision brief -> checker -> P2 English "
        "message -> checker -> P3 Hindi translation (if selected) -> checker -> approval page. A failed check gets one "
        "P4 repair with the exact errors; if that fails, a fixed template is used. Invalid inputs never reach the LLM.")
    D.p(f"**Tools and models.** {MODEL} (Q4_K_M, 4.7 GB) on Ollama 0.40.16, local RTX 4070 Laptop GPU (8 GB); "
        "temperature 0, seed 42, num_ctx 8192; JSON schemas enforced through Ollama's format option; Python 3.13, "
        "jsonschema, Gradio for the approval page; Google Colab notebook as the shareable prototype.")
    D.p("**Prompt design.** P1 has a role, numbered rules, the glossary and playbook as fixed tables, a step-by-step "
        "rule picker, data in <merchant_view> tags treated as data only, and 5 examples (one per playbook rule). P2 sees only the customer "
        "view, has tone and banned-word rules and a BAD/GOOD example. P3 translates the checked English with a fixed "
        "glossary and 2 examples. P4 gets the checker's exact error lines. Code, not the LLM, owns the decision: "
        "the playbook overrides the LLM action and adds the fixed region sentence, caveat and disclaimer.")
    D.p("**Test results (T01-T17: 8 normal, 6 edge, 3 invalid; same model, settings and checker; H01-H06 are new "
        "inputs run once on the final version).**")
    D.table([["Version", "All checks pass", "Raw action = playbook", "s per order"]] +
            [[v, pct(v), pct(v, "raw_action_ok"), S[v]["mean_seconds_per_case"]] for v in VERSIONS] +
            [["final on H01-H06", pct("final_heldout"), pct("final_heldout", "raw_action_ok"),
              S["final_heldout"]["mean_seconds_per_case"]]],
            [4, 3.5, 4, 3], size=8.5)
    D.p("Main errors: v1 code-fenced JSON, messages for orders that need none, an obeyed injection; v2 wrong playbook "
        "fields and 'high-risk region' wording; v3 wrong rule choice (R5) and a Hindi draft that changed UPI into net "
        "banking; v4 the state still called high-risk; v5 an R5 example fixed that but approve-with-codes orders lost "
        "their reasons; v6 an R2 example fixed that but its wording put an ungrounded count into the output. Two "
        "checks were added after reading outputs by hand, and every version was re-scored with the same checker.")
    D.p("**Limitations.** The final prompt was tuned on T01-T17 (only 6 truly new inputs); identical inputs gave "
        "different outputs in 4 of 7 versions despite temperature 0; Hindi reviewed only on a few tests; the action "
        "is safe only because code overrides the LLM; the prototype needs a GPU. Next (Milestone 3): 40-order "
        "frozen test set, 3 runs per input, blind human rating H1-H6, counterfactual location test, second model.")
    return D


def main():
    DOCS.mkdir(exist_ok=True)
    tmp = DOCS / "_build"
    tmp.mkdir(exist_ok=True)
    m2 = build_m2()
    m2.save_pdf(tmp / "m2_a.docx", tmp / "m2_a.pdf")
    tr = build_tech_report()
    tr_pdf = DOCS / "GeoRiskCopilot_TechnicalReport.pdf"
    tr.save_pdf(tmp / "tech.docx", tr_pdf)
    cb = build_contribution()
    cb.save_pdf(tmp / "m2_c.docx", tmp / "m2_c.pdf")
    out = pymupdf.open(str(tmp / "m2_a.pdf"))
    out.insert_pdf(pymupdf.open(str(tr_pdf)))
    out.insert_pdf(pymupdf.open(str(tmp / "m2_c.pdf")))
    name = f"M2_{CFG['team_id']}_{CFG['project_title_short']}.pdf"
    out.set_metadata({"title": f"Milestone 2 - {CFG['project_title']}", "author": CFG["team_name"]})
    out.save(str(DOCS / name), garbage=3, deflate=True)
    print(f"{name}: {out.page_count} pages, {(DOCS / name).stat().st_size / 1e6:.2f} MB; technical report "
          f"{pymupdf.open(str(tr_pdf)).page_count} page(s)")


if __name__ == "__main__":
    main()
