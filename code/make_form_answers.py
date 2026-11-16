"""Write the Milestone 2 form answers (Q1-Q24) from the same config and results the PDF uses, so the numbers in
the form always match the PDF.   python code/make_form_answers.py -> docs/M2_form_answers.txt"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CFG = json.loads((REPO / "code" / "m2_config.json").read_text(encoding="utf-8"))
CASES = json.loads((REPO / "test-data" / "cases.json").read_text(encoding="utf-8"))
HELD = json.loads((REPO / "test-data" / "heldout_cases.json").read_text(encoding="utf-8"))
VERSIONS = ["v1", "v2", "v3", "v4", "v5", "v6", "final"]
m = CFG["members"]
L = CFG["links"]
MODULES = ["Test-set generator", "Pre-processor", "Playbook oracle", "P1 decision brief", "P2 English message",
           "P3 Hindi rendering", "Checker C1-C11", "P4 repair + safety net", "Approval page (Gradio)", "Colab notebook"]
ans = [
    ("1. Team ID", CFG["team_id"]),
    ("2. Team Name as given in Milestone 1", CFG["team_name"]),
    ("3. Project Title/Name", CFG["project_title"]),
    ("4. Team Leader Name", m[0]["name"]),
    ("5. Team Leader Enrollment No.", m[0]["enrollment"]),
    ("6. Group (Batch)", CFG["batch"]),
    ("7. Enrollment numbers (one per line)", "\n".join(x["enrollment"] for x in m)),
    ("8. Project Type (at most 2)", "App with code\nPrompt-only workflow"),
    ("9. Main AI tool and model", "Qwen 2.5 7B (qwen2.5:7b, Q4_K_M) on Ollama, running locally on an RTX 4070 laptop "
                                  "GPU; Colab T4 for the shared notebook"),
    ("10. Number of prompts in the final solution", "4"),
    ("11. Prototype link", L["prototype"]),
    ("12. Repository link", L["repository"]),
    ("13. Reel link", L["reel"]),
    ("14. Reel length in seconds", L["reel_seconds"]),
    ("15. Supporting document type", "Technical Report"),
    ("16. Upload", "docs/GeoRiskCopilot_TechnicalReport.pdf"),
    ("17. Number of test inputs", str(len(CASES) + len(HELD))),
    ("18. Number of prompt versions", str(len(VERSIONS))),
    ("19. Prototype status", "Some modules working  (2 modules in the status table are 'Not started': blind human "
                             "rating and the counterfactual test, both planned for Milestone 3)"),
    ("20. Names of working modules", "\n".join(f"{i}. {x}" for i, x in enumerate(MODULES, 1))),
    ("21. Upload Milestone 2 PDF", f"docs/M2_{CFG['team_id']}_{CFG['project_title_short']}.pdf"),
    ("22. Main task of each member",
     f"{m[0]['enrollment']} – {m[0]['name']} – Test-set generator, pre-processor, playbook oracle, checker C1-C11, "
     "P4 repair, evaluation runner, approval page, Colab notebook and repository\n"
     f"{m[1]['enrollment']} – {m[1]['name']} – Wording of prompts P1-P3 and their examples, Hindi glossary and "
     "proofreading of the Hindi outputs, review of the test results, reel voice-over"),
    ("23. Anything the evaluator should know (optional)",
     "The Colab notebook opens with saved outputs from a real run. To run it again: Runtime > Change runtime type > "
     "T4 GPU, then Run all (the first cell installs Ollama and downloads the 4.7 GB model, a few minutes). The local "
     "approval page is code/app.py (needs Ollama with qwen2.5:7b). All test orders are synthetic."),
    ("24. Confirmation", "Tick only after Tanu Somani has agreed to the contribution table in Section 7."),
]
text = "Milestone 2 form answers (copy each into the form)\n" + "=" * 52 + "\n\n" + "\n\n".join(
    f"{q}\n{a}" for q, a in ans) + "\n"
(REPO / "docs" / "M2_form_answers.txt").write_text(text, encoding="utf-8")
print(text)
