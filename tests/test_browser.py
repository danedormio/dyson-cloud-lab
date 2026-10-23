"""Actual Chromium interactions, independent contexts and killed-server recovery."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'test-artifacts'


def test_existing_site_controls_and_packet_registry(chromium):
    # HTTP matches deployment and works where managed Chromium blocks file://.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/index.html', timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        page = chromium.new_page(viewport={'width':1440, 'height':900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/index.html')
        page.locator('#launch').click()
        assert page.locator('#registry details').count() == 1
        assert page.locator('#registry details').first.get_attribute('open') is not None
        page.locator('#shell').uncheck()
        assert not page.locator('#shell').is_checked()
        page.locator('#run').click()
        page.wait_for_timeout(350)
        assert 'Pause' in page.locator('#run').inner_text()
        page.locator('#run').click()
        ARTIFACTS.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / 'browser-preview.png'), full_page=True)
        assert not errors, errors
        page.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_rebound_frontend_real_api(chromium, backend):
    page = chromium.new_page(viewport={'width':1440, 'height':900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(backend.url)
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    expect(page.locator('#state')).to_contain_text('74 bodies')
    page.locator('#impact').fill('-0.5')
    page.locator('#launch').click()
    expect(page.locator('#state')).to_contain_text('75 bodies')
    assert page.locator('#list details').count() == 1
    page.locator('#once').click()
    expect(page.locator('#state')).to_contain_text('t=1.00 days')
    page.locator('#showShell').uncheck()
    assert not page.locator('#showShell').is_checked()
    ARTIFACTS.mkdir(exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / 'rebound-staging.png'), full_page=True)
    assert not errors, errors
    page.close()


def state(context, url):
    response = context.request.get(url + '/api/state')
    assert response.status == 200
    return response.json()


def download_checkpoint(page):
    with page.expect_download() as result:
        page.locator('#save').click()
    return Path(result.value.path()).read_bytes()


def restore_checkpoint(page, raw):
    with page.expect_file_chooser() as result:
        page.locator('#restore').click()
    result.value.set_files({'name':'checkpoint.json', 'mimeType':'application/json', 'buffer':raw})


def test_two_private_universes_ui_checkpoint_and_crash_recovery(chromium, backend):
    a, b = chromium.new_context(), chromium.new_context()
    pages = [a.new_page(), b.new_page()]
    errors = []
    for page in pages:
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(backend.url)
        expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    pa, pb = pages
    assert a.cookies()[0]['value'] != b.cookies()[0]['value']
    original_b = state(b, backend.url)
    # UI round-trip for BOTH owners; signed exports may not cross owners.
    for page, context, other in ((pa,a,b), (pb,b,a)):
        untouched = state(other, backend.url)
        page.locator('#launch').click()
        expect(page.locator('#state')).to_contain_text('75 bodies')
        page.locator('#once').click()
        expect(page.locator('#state')).to_contain_text('t=1.00 days')
        raw = download_checkpoint(page)
        wanted = state(context, backend.url)
        denied = other.request.post(backend.url+'/api/restore', data=json.loads(raw))
        assert denied.status == 403
        assert state(other, backend.url) == untouched
        page.locator('#reset').click()
        expect(page.locator('#state')).to_contain_text('74 bodies')
        expect(page.locator('#state')).to_contain_text('t=0.00 days')
        restore_checkpoint(page, raw)
        expect(page.locator('#state')).to_contain_text('75 bodies')
        expect(page.locator('#state')).to_contain_text('t=1.00 days')
        assert state(context, backend.url) == wanted
        assert state(other, backend.url) == untouched
    # Deliberately diverge the worlds before a real process kill.
    pa.locator('#once').click()
    expect(pa.locator('#state')).to_contain_text('t=2.00 days')
    expected_a, expected_b = state(a, backend.url), state(b, backend.url)
    backend.stop(crash=True)
    pa.locator('#once').click()
    expect(pa.locator('#wake')).to_be_visible()
    expect(pa.locator('#retryWake')).to_be_visible(timeout=15000)
    ARTIFACTS.mkdir(exist_ok=True)
    pa.screenshot(path=str(ARTIFACTS/'session-disconnected.png'), full_page=True)
    backend.start()
    pa.locator('#retryWake').click()
    expect(pa.locator('#wake')).to_be_hidden(timeout=15000)
    pb.reload()
    expect(pb.locator('#wake')).to_be_hidden(timeout=15000)
    assert state(a, backend.url) == expected_a
    assert state(b, backend.url) == expected_b
    expect(pa.locator('#state')).to_contain_text('t=2.00 days')
    expect(pb.locator('#state')).to_contain_text('t=1.00 days')
    pa.screenshot(path=str(ARTIFACTS/'session-a-recovered.png'), full_page=True)
    pb.screenshot(path=str(ARTIFACTS/'session-b-recovered.png'), full_page=True)
    # Continued UI mutation after restart still respects isolation.
    pa.locator('#reset').click()
    expect(pa.locator('#state')).to_contain_text('74 bodies')
    assert state(b, backend.url) == expected_b
    assert not errors, errors
    a.close()
    b.close()


def test_missing_session_requires_explicit_new_universe(chromium, backend):
    import sqlite3
    a, b = chromium.new_context(), chromium.new_context()
    pa, pb = a.new_page(), b.new_page()
    for page in (pa, pb):
        page.goto(backend.url)
        expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    expected_b = state(b, backend.url)
    old_cookie = a.cookies()[0]['value']
    import hashlib
    with sqlite3.connect(backend.db) as db:
        db.execute('DELETE FROM sessions WHERE id=?', (hashlib.sha256(old_cookie.encode()).hexdigest(),))
    pa.reload()
    expect(pa.locator('#newSession')).to_be_visible(timeout=15000)
    expect(pa.locator('#wakeMessage')).to_contain_text('401')
    assert state(b, backend.url) == expected_b
    pa.locator('#newSession').click()
    expect(pa.locator('#wake')).to_be_hidden(timeout=15000)
    expect(pa.locator('#state')).to_contain_text('74 bodies')
    assert a.cookies()[0]['value'] != old_cookie
    assert state(b, backend.url) == expected_b
    a.close()
    b.close()
