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

def test_rebound_frontend_real_api():
    """Drive the actual REBOUND backend + frontend together via Chromium."""
    import subprocess
    import sys
    import socket
    import time
    import urllib.request
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        for _ in range(100):
            if proc.poll() is not None:
                raise AssertionError("backend exited before becoming ready: "+proc.stderr.read().decode())
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    assert response.status == 200
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("backend startup timeout")
        artifacts = ROOT / "test-artifacts"
        artifacts.mkdir(exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_function("document.querySelector(\'#state\').textContent.includes(\'REBOUND IAS15\')", timeout=15000)
            assert "72 bodies" not in page.locator("#state").inner_text()  # Sun and Earth are separate bodies
            assert "74 bodies" in page.locator("#state").inner_text()
            page.locator("#impact").fill("-0.5")
            page.locator("#launch").click()
            page.wait_for_function("document.querySelector(\'#state\').textContent.includes(\'75 bodies\')", timeout=15000)
            assert page.locator("#list details").count() == 1
            page.locator("#once").click()
            page.wait_for_function("document.querySelector(\'#state\').textContent.includes(\'t=1.00 days\')", timeout=15000)
            page.locator("#showShell").uncheck()
            assert not page.locator("#showShell").is_checked()
            page.screenshot(path=str(artifacts / "rebound-staging.png"), full_page=True)
            assert not errors, errors
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
