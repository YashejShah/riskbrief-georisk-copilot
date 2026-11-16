"""Write test-data/hindi_review.md: every Hindi draft of the final version next to its English text, with empty
columns for the human proofreading (to be filled in by Tanu Somani; nothing here is filled in by a tool)."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
rows = []
for folder in ("final", "final_heldout"):
    for p in sorted((REPO / "test-data" / "outputs" / folder).glob("[TH]*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        hi = (r.get("final") or {}).get("message_hi")
        if hi:
            en = r["final"]["message_en"]["message"]
            rows.append(f"| {p.stem} | {en} | {hi['message']} |  |  |  |")
text = ("# Hindi proofreading (final version)\n\nReviewer: Tanu Somani (S24CSEU0355). Date: ____\n\n"
        "Rate each draft 0-2: 0 = wrong or unclear, 1 = understandable but needs edits, 2 = natural and correct.\n\n"
        "| Test | English draft | Hindi draft | Meaning same? (yes/no) | Fluency 0-2 | Suggested correction |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
(REPO / "test-data" / "hindi_review.md").write_text(text, encoding="utf-8")
print(len(rows), "Hindi drafts listed")
