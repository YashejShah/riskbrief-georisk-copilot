"""Open the repository and the Colab prototype link in a fresh, logged-out browser profile (like a private window),
save a screenshot of the repository page for Section 5, and report whether each link opens without sign-in."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
CFG = json.loads((REPO / "code" / "m2_config.json").read_text(encoding="utf-8"))
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 1000})          # fresh profile: no cookies, no login
    page = ctx.new_page()
    r = page.goto(CFG["links"]["repository"], wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(REPO / "docs" / "repo_screenshot.png"))
    print("repository:", r.status, page.title())
    r = page.goto(CFG["links"]["prototype"], wait_until="domcontentloaded")
    page.wait_for_timeout(12000)
    page.screenshot(path=str(REPO / "docs" / "_prev_colab.png"))
    body = page.inner_text("body")[:3000]
    print("prototype:", r.status, page.title(), "| sign-in asked:", "Sign in" in body and "RiskBrief" not in body,
          "| notebook text visible:", "RiskBrief" in body)
    b.close()
