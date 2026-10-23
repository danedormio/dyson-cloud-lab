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
        restored = state(context, backend.url)
        assert {k:v for k,v in restored.items() if k != 'recovery'} == {k:v for k,v in wanted.items() if k != 'recovery'}
        assert restored['recovery']['checkpoint'] == wanted['recovery']['checkpoint']
        assert restored['recovery']['revision'] > wanted['recovery']['revision']
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


def test_missing_session_recovers_browser_backup(chromium, backend):
    import sqlite3
    a, b = chromium.new_context(), chromium.new_context()
    pa, pb = a.new_page(), b.new_page()
    for page in (pa, pb):
        page.goto(backend.url)
        expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    pa.locator('#once').click()
    expect(pa.locator('#state')).to_contain_text('t=1.00 days')
    expected_a, expected_b = state(a, backend.url), state(b, backend.url)
    old_cookie = a.cookies()[0]['value']
    import hashlib
    with sqlite3.connect(backend.db) as db:
        db.execute('DELETE FROM sessions WHERE id=?', (hashlib.sha256(old_cookie.encode()).hexdigest(),))
    pa.reload()
    expect(pa.locator('#wake')).to_be_hidden(timeout=15000)
    expect(pa.locator('#state')).to_contain_text('t=1.00 days')
    assert a.cookies()[0]['value'] != old_cookie
    assert state(a, backend.url) == expected_a
    assert state(b, backend.url) == expected_b
    a.close()
    b.close()


def test_full_redeploy_browser_backups_and_portable_private_file(chromium, backend):
    a, b = chromium.new_context(), chromium.new_context()
    pa, pb = a.new_page(), b.new_page()
    errors = []
    for page in (pa, pb):
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(backend.url)
        expect(page.locator('#wake')).to_be_hidden(timeout=15000)
        expect(page.locator('#backupStatus')).to_contain_text('Recovery saved on this browser')
    pa.locator('#count').fill('8')
    pa.locator('#reset').click()
    expect(pa.locator('#state')).to_contain_text('10 bodies')
    pa.locator('#launch').click()
    expect(pa.locator('#state')).to_contain_text('11 bodies')
    for page in (pa, pb):
        page.locator('#once').click()
        expect(page.locator('#state')).to_contain_text('t=1.00 days')
        expect(page.locator('#backupStatus')).to_contain_text('Recovery saved on this browser')
    pa.locator('#once').click()
    expect(pa.locator('#state')).to_contain_text('t=2.00 days')
    # Wait for the client durability acknowledgement, not just rendered state.
    pa.wait_for_function('!busy')
    expected_a, expected_b = state(a, backend.url), state(b, backend.url)
    with pa.expect_download() as download:
        pa.locator('#backup').click()
    private_file = Path(download.value.path()).read_bytes()
    backend.stop(crash=True)
    backend.db.unlink() # No SQLite file is retained on the replacement host.
    backend.start()
    a.clear_cookies() # IndexedDB still proves ownership even without a cookie.
    for page in (pa, pb):
        page.reload()
        expect(page.locator('#wake')).to_be_hidden(timeout=15000)
        expect(page.locator('#backupStatus')).to_contain_text('Recovery saved on this browser')
    assert state(a, backend.url) == expected_a
    assert state(b, backend.url) == expected_b
    expect(pa.locator('#count')).to_have_value('8')
    ARTIFACTS.mkdir(exist_ok=True)
    pa.screenshot(path=str(ARTIFACTS/'redeploy-eight-cloud-recovered.png'), full_page=True)
    # Lose host storage a second time: only the downloaded file can restore
    # A in the brand-new browser; B independently uses its browser backup.
    backend.stop(crash=True)
    backend.db.unlink()
    backend.start()
    pb.reload()
    expect(pb.locator('#wake')).to_be_hidden(timeout=15000)
    # An actual downloaded private backup also works in a clean browser.
    imported = chromium.new_context()
    page = imported.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(backend.url)
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    restore_checkpoint(page, private_file)
    expect(page.locator('#state')).to_contain_text('11 bodies')
    expect(page.locator('#state')).to_contain_text('t=2.00 days')
    page.wait_for_function('!busy')
    assert state(imported, backend.url) == expected_a
    assert state(b, backend.url) == expected_b
    page.locator('#once').click()
    expect(page.locator('#state')).to_contain_text('t=3.00 days')
    assert state(b, backend.url) == expected_b
    assert not errors, errors
    for context in (a,b,imported):
        context.close()


def test_unconfigured_key_is_visible_and_does_not_promise_redeploy_recovery(chromium, backend):
    backend.stop()
    backend.recovery_key = None
    backend.start()
    page = chromium.new_page()
    page.goto(backend.url)
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    expect(page.locator('#backupStatus')).to_contain_text('Redeploy recovery unavailable')
    page.close()


def test_late_response_cannot_replace_newer_browser_backup(chromium, backend):
    page = chromium.new_page()
    page.goto(backend.url)
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    older = page.evaluate('snapshot.recovery')
    page.locator('#once').click()
    expect(page.locator('#state')).to_contain_text('t=1.00 days')
    page.wait_for_function('!busy')
    page.evaluate('capsule => RecoveryBackup.accept(capsule)', older)
    assert page.evaluate('(async()=> (await RecoveryBackup.refresh()).capsule.checkpoint.time_s)()') == 86400
    page.close()


def test_browser_storage_failure_is_visible_and_retry_does_not_repeat_step(chromium, backend):
    page = chromium.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(backend.url)
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    page.evaluate("""() => {
      window.realPut = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function() {throw new DOMException('simulated storage full','QuotaExceededError')};
    }""")
    page.locator('#once').click()
    expect(page.locator('#backupStatus')).to_contain_text('NOT saved')
    expect(page.locator('#wake')).to_be_visible()
    assert page.evaluate('(async()=> (await RecoveryBackup.refresh()).capsule.checkpoint.time_s)()') == 0
    page.evaluate('() => { IDBObjectStore.prototype.put = window.realPut; }')
    page.locator('#retryWake').click()
    expect(page.locator('#wake')).to_be_hidden(timeout=15000)
    expect(page.locator('#state')).to_contain_text('t=1.00 days')
    expect(page.locator('#backupStatus')).to_contain_text('Recovery saved on this browser')
    assert page.evaluate('(async()=> (await RecoveryBackup.refresh()).capsule.checkpoint.time_s)()') == 86400
    assert not errors, errors
    page.close()
