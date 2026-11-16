"""Draw the four Milestone 2 diagrams from what is actually built (docs/*.png):
prompt workflow, task decomposition, input-output flow and system architecture."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs"
OUT.mkdir(exist_ok=True)
INK = "#1f2937"
BLUE, GREEN, AMBER, GREY, RED = ("#e0e7ff", "#4338ca"), ("#dcfce7", "#15803d"), ("#fef3c7", "#b45309"), \
    ("#f3f4f6", "#6b7280"), ("#fee2e2", "#b91c1c")


def box(ax, x, y, w, h, title, lines=(), c=BLUE, size=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c[0], ec=c[1], lw=1.5))
    ax.text(x + w / 2, y + h - 0.16, title, ha="center", va="top", fontsize=size, fontweight="bold", color=INK)
    for i, t in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.5 - i * 0.27, t, ha="center", va="top", fontsize=8, color=INK)


def arrow(ax, x1, y1, x2, y2, label="", c=INK, dashed=False, lx=0, ly=0):
    if isinstance(c, tuple):              # a (fill, edge) pair was passed: use the edge colour
        c = c[1]
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, lw=1.3, color=c,
                                 ls="--" if dashed else "-"))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha="center", va="center", fontsize=7.6, color=c,
                bbox=dict(fc="white", ec="none", pad=1))


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / name, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", OUT / name)


def prompt_workflow():
    fig, ax = canvas(13, 7.2)
    box(ax, 0.2, 5.6, 2.6, 1.3, "Order + API JSON", ["GeoRisk API /v1/score", "(real response)"], GREY)
    box(ax, 3.3, 5.6, 3.0, 1.3, "Pre-processor (code)", ["validate, clean order_id", "build 3 views, oracle"], GREY)
    box(ax, 7.0, 5.6, 2.4, 1.3, "R8: NEEDS_HUMAN", ["invalid input:", "no LLM call"], RED)
    box(ax, 3.3, 3.5, 3.0, 1.4, "P1 decision brief", ["merchant view, glossary,", "playbook, 3 examples,",
                                                      "JSON schema"], BLUE)
    box(ax, 7.0, 3.5, 2.6, 1.4, "Checker C1-C7, C9, C11", ["code, no LLM"], AMBER)
    box(ax, 10.2, 3.5, 2.6, 1.4, "P4 repair (1 try)", ["gets the exact errors", "then re-checked"], BLUE)
    box(ax, 3.3, 1.2, 3.0, 1.5, "P2 English message", ["customer view only", "(only R3, R4, R5)"], BLUE)
    box(ax, 7.0, 1.2, 2.6, 1.5, "P3 Hindi rendering", ["translates checked EN", "(if Hindi selected)"], BLUE)
    box(ax, 10.2, 1.2, 2.6, 1.5, "Approval page", ["brief, EN, HI, check", "report, redacted JSON",
                                                   "Approve / Edit / Reject"], GREEN)
    box(ax, 0.2, 2.9, 2.6, 1.9, "Code safety net", ["playbook action wins", "fixed region sentence",
                                                    "caveat + disclaimer", "static template if", "repair fails"], AMBER)
    arrow(ax, 2.8, 6.25, 3.3, 6.25)
    arrow(ax, 6.3, 6.25, 7.0, 6.25, "invalid", RED)
    arrow(ax, 4.8, 5.6, 4.8, 4.9, "valid")
    arrow(ax, 6.3, 4.2, 7.0, 4.2)
    arrow(ax, 9.6, 4.45, 10.2, 4.45, "fail", RED, ly=0.15)
    arrow(ax, 10.2, 3.9, 9.6, 3.9, "re-check", ly=-0.15)
    arrow(ax, 8.3, 3.5, 6.3, 2.5, "pass + message needed", GREEN[1])
    arrow(ax, 6.3, 1.95, 7.0, 1.95, "checked EN")
    arrow(ax, 9.6, 1.95, 10.2, 1.95)
    arrow(ax, 3.3, 3.9, 2.8, 3.9, dashed=True)
    ax.text(6.5, 0.5, "P2 and P3 outputs go through the checker too (C1, C2, C7-C10), with the same one-try P4 repair.",
            ha="center", fontsize=8.5, color=INK)
    save(fig, "diagram_prompt_workflow.png")


def task_decomposition():
    fig, ax = canvas(13, 5.4)
    box(ax, 4.5, 4.0, 4.0, 1.1, "Explain one risky order", ["and draft the customer message"], GREEN, 11)
    xs = [0.2, 2.75, 5.3, 7.85, 10.4]
    items = [("1. Understand input", ["validate fields", "map codes (glossary)", "build views"], GREY),
             ("2. Decide action", ["playbook R1-R8 (code)", "P1 cites the rule", "never re-decide"], AMBER),
             ("3. Explain (P1)", ["one reason per code", "evidence field+value", "summary <= 70 words"], BLUE),
             ("4. Talk to customer", ["P2 English draft", "P3 Hindi rendering", "no blame, no location"], BLUE),
             ("5. Check + approve", ["C1-C11 in code", "P4 repair once", "human approves"], GREEN)]
    for x, (t, l, c) in zip(xs, items):
        box(ax, x, 1.0, 2.4, 2.0, t, l, c)
        arrow(ax, 6.5, 4.0, x + 1.2, 3.0)
    save(fig, "diagram_task_decomposition.png")


def io_flow():
    fig, ax = canvas(13, 4.6)
    box(ax, 0.2, 1.0, 3.0, 2.8, "INPUT", ["order: amount, payment method,", "time, PIN codes",
                                          "API: risk_score, decision,", "reason_codes, distance,",
                                          "district/state, fairness_note"], GREY)
    box(ax, 3.9, 2.6, 2.6, 1.3, "merchant view", ["no PINs, no income tier"], AMBER)
    box(ax, 3.9, 0.7, 2.6, 1.3, "customer view", ["order id, amount,", "method, action only"], AMBER)
    box(ax, 7.2, 2.6, 2.6, 1.3, "P1 -> brief JSON", ["action, rule, reasons,", "summary, notes"], BLUE)
    box(ax, 7.2, 0.7, 2.6, 1.3, "P2/P3 -> drafts", ["EN <= 320 chars", "HI <= 400 chars"], BLUE)
    box(ax, 10.5, 1.0, 2.4, 2.8, "OUTPUT", ["checked brief", "EN / HI drafts", "check report",
                                            "status: needs approval"], GREEN)
    arrow(ax, 3.2, 3.0, 3.9, 3.2)
    arrow(ax, 3.2, 1.8, 3.9, 1.35)
    arrow(ax, 6.5, 3.25, 7.2, 3.25)
    arrow(ax, 6.5, 1.35, 7.2, 1.35)
    arrow(ax, 9.8, 3.25, 10.5, 2.9)
    arrow(ax, 9.8, 1.35, 10.5, 1.8)
    save(fig, "diagram_input_output.png")


def architecture():
    fig, ax = canvas(13, 5.6)
    box(ax, 0.2, 3.0, 2.8, 1.9, "GeoRisk API", ["FastAPI + LightGBM", "SHAP reason codes",
                                                "(our AI/ML project)"], GREY)
    box(ax, 0.2, 0.5, 2.8, 1.9, "Test data", ["test-data/cases.json", "15 inputs", "made by make_test_data.py"],
        GREY)
    box(ax, 3.7, 1.4, 3.6, 3.0, "riskbrief (Python)", ["views.py  pre-processor", "rules.py  glossary, playbook",
                                                       "chain.py  v1, v2, v3, final", "checks.py C1-C11",
                                                       "llm.py    Ollama client"], BLUE)
    box(ax, 8.0, 3.2, 2.6, 1.6, "Ollama (local)", ["qwen2.5:7b Q4_K_M", "RTX 4070 8 GB",
                                                   "temp 0, seed 42"], AMBER)
    box(ax, 8.0, 0.6, 2.6, 1.9, "Front ends", ["Gradio approval page", "(code/app.py)", "Colab notebook"],
        GREEN)
    box(ax, 11.2, 1.4, 1.6, 3.0, "Logs", ["outputs/", "<version>/", "run_log", ".jsonl"], GREY)
    arrow(ax, 3.0, 3.9, 3.7, 3.6, "JSON")
    arrow(ax, 3.0, 1.5, 3.7, 2.0)
    arrow(ax, 7.3, 3.6, 8.0, 4.0, "/api/chat")
    arrow(ax, 8.0, 3.6, 7.3, 3.2, "reply", ly=-0.15)
    arrow(ax, 7.3, 2.0, 8.0, 1.6)
    arrow(ax, 10.6, 2.9, 11.2, 2.9)
    save(fig, "diagram_architecture.png")


prompt_workflow()
task_decomposition()
io_flow()
architecture()
