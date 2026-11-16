"""Write code/RiskBrief_Colab.ipynb (the prototype link). The same notebook runs on Google Colab (it installs
Ollama and the model there) and locally (it uses the Ollama server that is already running).

    python code/make_notebook.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GITHUB = "https://github.com/YashejShah/riskbrief-georisk-copilot"
cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": s.strip("\n").splitlines(True)})


md(f"""
# RiskBrief (GeoRisk Copilot): prototype notebook

**Team GeoRisk Copilot**: Yashej Yang Shah (S24CSEU0256), Tanu Somani (S24CSEU0355). SCSE4041 Mini Project, Milestone 2.

RiskBrief reads the JSON returned by our GeoRisk fraud/RTO scoring API for one order and produces:
1. a **decision brief** for the shop's order reviewer (action from the store playbook, reasons in plain words, every number taken from the input),
2. a polite **customer message draft** in English, and in Hindi when the reviewer selects it,
3. a **check report** from code checks C1-C11. Failed outputs get one repair try (P4), then a safe fixed template.

A person always approves before anything is sent (sending is simulated).

**How to use this notebook**
- The outputs below are saved from a real run (Qwen 2.5 7B on Ollama, local RTX 4070 laptop GPU).
- To run it yourself in Colab: *Runtime > Change runtime type > T4 GPU*, then *Runtime > Run all*. The first cell installs Ollama and downloads the model (about 5 GB, a few minutes).
- Change the JSON in the last section to try your own order.

Code, prompts and test data: {GITHUB}
""")
code(f"""
import os, subprocess, sys, time, json, urllib.request
IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    if not os.path.exists("riskbrief-georisk-copilot"):
        subprocess.run(["git", "clone", "--depth", "1", "{GITHUB}.git"], check=True)
    os.chdir("riskbrief-georisk-copilot")
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    subprocess.run(["ollama", "pull", "qwen2.5:7b"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "jsonschema"], check=True)
elif os.path.basename(os.getcwd()) == "code":       # opened from the code/ folder of the repository
    os.chdir("..")
sys.path.insert(0, os.path.join(os.getcwd(), "code"))
from riskbrief import chain
from riskbrief.llm import MODEL, SETTINGS, model_digest
print("running in Colab" if IN_COLAB else "running locally", "| model:", MODEL, model_digest(), "| settings:", SETTINGS)
""")
md("""
## 1. The test inputs
15 inputs: 7 normal orders, 5 edge cases and 3 invalid inputs. Normal orders are real outputs of the GeoRisk API for
synthetic orders. Edge and invalid cases start from a real API output and change one thing on purpose (see `note`).
""")
code("""
cases = json.load(open("test-data/cases.json", encoding="utf-8"))
for c in cases:
    r = c["response"]
    print(f'{c["id"]}  {c["type"]:<7} decision={str(r.get("decision")):<8} score={str(r.get("risk_score")):>4}  '
          f'codes={r.get("reason_codes")}  {c["title"]}')
""")
md("""
## 2. Run the final prompt chain on four inputs
T02 (COD order under review), T11 (region-only review, fairness rule R5), T12 (same order, Hindi selected) and
T10 (prompt injection hidden in the order ID).
""")
code("""
def show(res):
    fin, b = res["final"], res["final"]["brief"]
    print(f"ACTION: {b.get('recommended_action')} (rule {b.get('playbook_rule')}) | API decision {b.get('api_decision')} "
          f"| score {b.get('risk_score')} | raw LLM action {res['raw_action']}")
    print("SUMMARY:", b.get("summary"))
    for r in b.get("reasons", []):
        print(f"  - {r['code']}: {r['plain_language']}")
    if fin.get("message_en"):
        print("EN DRAFT:", fin["message_en"]["message"])
    if fin.get("message_hi"):
        print("HI DRAFT:", fin["message_hi"]["message"])
    fails = [f"{s} {k}: {e}" for s, d in res["errors"].items() for k, v in d.items() for e in v]
    print("CHECKS:", "all passed" if not fails else fails)
    for e in res.get("events", []):
        print("EVENT:", e)
    print("LLM calls:", len(res["calls"]), "| seconds:", round(sum(c["stats"]["seconds"] for c in res["calls"]), 1))

by_id = {c["id"]: c for c in cases}
for cid in ["T02", "T11", "T12", "T10"]:
    print("=" * 30, cid, by_id[cid]["title"])
    show(chain.run(by_id[cid], "final"))
""")
md("""
## 3. Invalid input: the chain stops before the LLM
T16 has a broken API response (decision missing, score not a number). RiskBrief does not call the model and asks a
person to look at it (playbook rule R8).
""")
code("""
show(chain.run(by_id["T16"], "final"))
""")
md("""
## 4. Results of every prompt version on all 15 inputs
Saved by `code/run_eval.py` (same model, temperature 0, seed 42). v1 is the Milestone 1 baseline prompt. T01-T17
were used while improving the prompts; `final_heldout` is 6 new inputs (H01-H06) written after the final prompt was
frozen and run once.
""")
code("""
for v in ["v1", "v2", "v3", "v4", "v5", "v6", "final", "final_heldout"]:
    p = f"test-data/outputs/{v}/summary.json"
    if os.path.exists(p):
        s = json.load(open(p, encoding="utf-8"))
        print(f"{v:<6} all checks pass {s['all_checks_pass']:>2}/{s['cases']}   raw LLM action = playbook "
              f"{s['raw_action_ok']:>2}/{s['cases']}   {s['mean_seconds_per_case']} s per order")
""")
md("""
## 5. Try your own order
Edit the JSON below (keep the same fields) and run the cell. Use made-up orders only.
""")
code("""
my_case = {
  "request": {"order_id": "MY-001", "amount": 6500, "payment_method": "cod", "timestamp": "2026-11-15T04:20:00+05:30",
              "customer": {"billing_pincode": "560001", "shipping_pincode": "560034"}},
  "response": {"order_id": "MY-001", "risk_score": 62, "decision": "review",
               "reason_codes": ["ODD_HOUR", "HIGH_AMOUNT"],
               "geo_signals": {"billing_shipping_distance_km": 0.0, "region_risk": 0.01133, "income_tier": "tier1",
                               "billing_district": "Bengaluru", "billing_state": "Karnataka"},
               "model_version": "india-synth-0.1",
               "fairness_note": "No fairness adjustment needed; decision is not a decline."},
  "language": "hi"}
show(chain.run(my_case, "final"))
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"}, "accelerator": "GPU",
                                   "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}
for i, c in enumerate(nb["cells"]):
    c["id"] = f"cell-{i:02d}"
(REPO / "code" / "RiskBrief_Colab.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("written", REPO / "code" / "RiskBrief_Colab.ipynb")
