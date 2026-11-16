# RiskBrief (team GeoRisk Copilot)

RiskBrief turns the JSON of our GeoRisk fraud/RTO scoring API into three things a small Indian online shop can use:

1. a **decision brief** for the order reviewer: what to do (from the store playbook), why (one plain sentence per reason code), and a short summary,
2. a polite **customer message draft** in English, and in Hindi when the reviewer selects it,
3. a **check report**: code checks C1-C11 (valid JSON, every number grounded, reason codes match the API, action matches the playbook, no place or blame words, no links or phone numbers, length and Hindi script). A failed output gets one repair try (prompt P4); if that also fails, a safe fixed template is used.

A person always approves before anything goes to a customer. Sending and the OTP step are simulated.

SCSE4041 Mini Project (Prompt Engineering), Bennett University. Milestone 2.

| Member | Enrollment no. | Main work in Milestone 2 |
|---|---|---|
| Yashej Yang Shah (lead) | S24CSEU0256 | test-set generator, pre-processor, playbook oracle, checker C1-C11, P4 repair, Ollama runner and evaluation, approval page, repository |
| Tanu Somani | S24CSEU0355 | P1-P3 prompt wording and few-shot examples, Hindi glossary and proofreading of Hindi outputs, review of test results, reel voice-over |

## Prototype

- **Colab notebook (saved outputs, can be re-run on a free T4 GPU):** [code/RiskBrief_Colab.ipynb](code/RiskBrief_Colab.ipynb) - open in Colab: https://colab.research.google.com/github/YashejShah/riskbrief-georisk-copilot/blob/main/code/RiskBrief_Colab.ipynb
- **Local approval page (Gradio):** `python code/app.py` then open http://127.0.0.1:7860

## Model and settings

`qwen2.5:7b` (Q4_K_M) on Ollama, running locally on an RTX 4070 Laptop GPU (8 GB). Temperature 0, seed 42, num_ctx 8192. JSON schema enforced through Ollama's `format` option for P1-P4. No order data leaves the laptop. All test orders are synthetic.

## How to run

```
# 1. Ollama with the model
ollama pull qwen2.5:7b
# 2. Python 3.11+ with: pip install jsonschema gradio
python code/run_eval.py v1 v2 v3 final      # re-run every prompt version on the 17 test inputs
python code/show_errors.py                  # print the failed checks per version
python code/app.py                          # approval page
```

`code/make_test_data.py` rebuilds the test set from the real GeoRisk API (needs the API's own requirements). The API is our earlier AI/ML course project and is not part of this repository.

## Folders

| Path | What is inside |
|---|---|
| `prompts/v1/` | Milestone 1 baseline prompt (one call) |
| `prompts/v2/` | one strong prompt: glossary, playbook, data tags, JSON schema |
| `prompts/v3/` | first prompt chain: P1 brief, P2 English message, P3 Hindi |
| `prompts/v4/` - `v6/` | rule picker, Hindi glossary, P4 repair; then few-shot examples for R5 and R2 |
| `prompts/final/` | final prompts P1-P4 (one file per prompt) |
| `code/riskbrief/` | views (pre-processor), rules (glossary, playbook, schemas), chain, checks, Ollama client |
| `code/` | test-set generator, evaluation runner, approval page, notebook and diagram builders |
| `test-data/` | `cases.json` (T01-T17), `heldout_cases.json` (H01-H06), `outputs/<version>/` (every real output and its checks), `run_log.jsonl`, `hindi_review.md` |

## Results (same 17 inputs, same model, settings and checker)

| Version | v1 | v2 | v3 | v4 | v5 | v6 | final | final on H01-H06 |
|---|---|---|---|---|---|---|---|---|
| All checks pass | 0/17 | 6/17 | 10/17 | 15/17 | 15/17 | 14/17 | 17/17 | 6/6 |
| `docs/` | diagrams and the Milestone 2 PDF |
| `CHANGELOG.md` | dated changes since Milestone 1 |

## Limits

Synthetic orders only; the scoring model is trained on synthetic data and is decision support, not proof of fraud. RiskBrief never cancels an order and never uses location or income as a reason. Messages are drafts until a person approves them.
