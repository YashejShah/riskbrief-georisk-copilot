"""Open the reel link in a fresh, logged-out browser profile and report whether it plays without sign-in."""
import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    r = page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(8000)
    body = page.inner_text("body")[:4000]
    page.screenshot(path=sys.argv[2])
    need_access = any(s in body for s in ("Request access", "You need access", "Sign in to continue"))
    print("status", r.status, "| title:", page.title(), "| access/sign-in wall:", need_access,
          "| file name shown:", "RiskBrief" in body or "reel" in body.lower())
    b.close()
