"""Real headless Chromium interaction checks; screenshot saved for PR review."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def test_existing_site_controls_and_packet_registry():
    artifacts = ROOT / "test-artifacts"
    artifacts.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((ROOT/"index.html").as_uri())
        page.locator("#launch").click()
        assert page.locator("#registry details").count() == 1
        assert page.locator("#registry details").first.get_attribute("open") is not None
        page.locator("#shell").uncheck()
        assert not page.locator("#shell").is_checked()
        page.locator("#run").click()
        page.wait_for_timeout(350)
        assert "Pause" in page.locator("#run").inner_text()
        page.locator("#run").click()
        page.screenshot(path=str(artifacts / "browser-preview.png"), full_page=True)
        assert not errors, errors
        browser.close()
