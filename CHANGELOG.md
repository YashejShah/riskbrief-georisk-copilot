# Changelog

All dates are 2026. Milestone 1 (proposal) was submitted on 11 October.

## 16 November
- Set up the local model: Ollama 0.40.16 (portable, project folder only) with `qwen2.5:7b` (Q4_K_M) on the RTX 4070 laptop GPU. Settings for every run: temperature 0, seed 42, num_ctx 8192.
- Built the test set from the real GeoRisk API: 240 synthetic grid orders scanned, 17 test inputs picked (8 normal, 6 edge, 3 invalid; see `test-data/cases.json`). Edge and invalid inputs are real API outputs with one change, labelled "perturbed".
- Wrote the pre-processor (`views.py`): input validation, order_id cleaning, merchant view without PIN codes and income tier, customer view, redacted reviewer view.
- Wrote the playbook oracle and glossary in code (`rules.py`), so the prompt text and the checks use the same tables.
- Wrote the checker C1-C11 (`checks.py`).
- Prompt v1 = the Milestone 1 baseline prompt, unchanged. Ran it on all test inputs.
- Prompt v2 = one strong prompt (glossary, playbook, data tags, JSON schema, merchant view).
- Prompt v3 = first chain: P1 brief with 3 few-shot examples, P2 English message from the customer view only, P3 Hindi translation of the checked English.
- Reading the v3 outputs by hand showed two problems the checker missed: a brief that called the billing state "a high-risk region" (T11) and a Hindi draft that changed "UPI" into "net banking" (T12). Added both to the checker (C7 blame phrases in briefs, C10 payment words kept in Hindi) and re-ran every version with the same checker.
- Also fixed a false alarm in the Hindi script check (it counted the {store_name} placeholder, the order ID and OTP/UPI as non-Hindi letters) and widened the place-blame check ("the state is considered high-risk").
- v4: P1 gets a step-by-step rule picker (v3 often chose R5 for normal review orders and missed the prepaid flag), P3 gets a fixed Hindi glossary and a second example, P4 repair added; code safety net (playbook action wins, fixed region sentence, static template if repair fails). Result 15/17: T11 and T14 still called the billing state high-risk.
- v5: added an R5 (region-only) few-shot example. T11/T14 fixed, but T03/T09 (approve with codes) lost their reasons: 15/17.
- v6: added an R2 example. Its summary said "2 reason codes" and the model copied a count that is not in the input (C2): 14/17. T11 and T14 send the identical first prompt but got different replies.
- final: R2 example without the count: 17/17 on T01-T17.
- Wrote 6 new inputs (H01-H06) after freezing the final prompt and ran them once: 6/6.
- Added the Gradio approval page (`code/app.py`), the Colab notebook (executed, outputs saved), the diagrams, the Hindi review sheet for Tanu, the Milestone 2 PDF and the technical report.
