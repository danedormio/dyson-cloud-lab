"""Regression for the owner's existing-browser startup failure; no real user data."""
from pathlib import Path
import json

OLD_RECORD={"format":"dyson-private-backup-v1","credential":"B"*43,
            "capsule":{"format":"dyson-recovery-v1","owner":"0"*64,"signature":"0"*64}}


def seed(page, name, record):
    page.evaluate('''async ({name,record})=>{await new Promise((resolve,reject)=>{
      const r=indexedDB.open(name,1);r.onupgradeneeded=()=>r.result.createObjectStore('backups');
      r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result;
      const tx=db.transaction('backups','readwrite');tx.objectStore('backups').put(record,'current');
      tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)}})}''',dict(name=name,record=record))


def read_record(page,name,key='current'):
    return page.evaluate('''async ({name,key})=>new Promise((resolve,reject)=>{
      const r=indexedDB.open(name,1);r.onsuccess=()=>{const db=r.result;
      const tx=db.transaction('backups','readonly');const q=tx.objectStore('backups').get(key);
      q.onsuccess=()=>resolve(q.result);tx.oncomplete=()=>db.close();q.onerror=()=>reject(q.error)}})''',dict(name=name,key=key))


def test_old_workbench_recovery_cannot_block_minimal_startup(backend,chromium):
    page=chromium.new_page(viewport={'width':1440,'height':960})
    page.goto(backend.url+'/health')
    seed(page,'dyson-private-backups',OLD_RECORD)
    page.context.add_cookies([dict(name='dyson_session',value='A'*43,url=backend.url+'/api')])
    page.goto(backend.url+'/simple')
    try:
        page.wait_for_function('window.cloudView?.world?.time>0',timeout=6000)
    except Exception:
        Path('test-artifacts').mkdir(exist_ok=True)
        page.screenshot(path='test-artifacts/startup-existing-profile-failure.png')
        print(json.dumps(dict(reason=page.locator('#reason').inner_text(),
            buttons={name:page.locator('#'+name).is_disabled() for name in ['play','reset','launch']})))
        raise
    assert read_record(page,'dyson-private-backups')==OLD_RECORD
    page.click('#play');page.wait_for_timeout(500)
    assert page.locator('#reset').is_enabled() and page.locator('#launch').is_enabled()
    Path('test-artifacts').mkdir(exist_ok=True)
    page.screenshot(path='test-artifacts/startup-existing-profile-fixed.png')
    page.click('#launch');page.wait_for_function('!!window.cloudView.world.packet')
    assert read_record(page,'dyson-private-backups')==OLD_RECORD
    page.close()


def test_retry_reconnects_after_startup_service_failure(backend,chromium):
    page=chromium.new_page()
    attempts=[]
    def fail_once(route):
        if route.request.method=='POST' and not attempts:
            attempts.append('failed')
            route.fulfill(status=503,content_type='application/json',body='{"detail":"Service is waking up"}')
        else:
            attempts.append('retried');route.continue_()
    page.route('**/api/simple/session',fail_once)
    page.goto(backend.url+'/simple')
    page.wait_for_function('document.querySelector("#play").textContent==="Retry connection"')
    assert page.locator('#play').is_enabled() and page.locator('#reset').is_enabled()
    assert page.locator('#launch').is_disabled()
    page.click('#play')
    page.wait_for_function('window.cloudView?.world?.time>0')
    assert 'retried' in attempts
    page.click('#play');page.wait_for_timeout(300)
    page.click('#launch');page.wait_for_function('!!window.cloudView.world.packet')
    page.close()


def test_start_fresh_archives_unrecoverable_scene_without_touching_old_work(backend,chromium):
    page=chromium.new_page()
    page.goto(backend.url+'/health')
    seed(page,'dyson-private-backups',OLD_RECORD)
    seed(page,'dyson-first-light-backups',OLD_RECORD)
    page.context.add_cookies([dict(name='dyson_simple_session',value='A'*43,url=backend.url+'/api')])
    page.goto(backend.url+'/simple')
    page.wait_for_function('document.querySelector("#play").textContent==="Retry connection"')
    assert page.locator('#reset').inner_text()=='Start fresh'
    page.click('#reset');page.wait_for_function('window.cloudView?.world?.time>0')
    archived=page.evaluate('''async ()=>new Promise(resolve=>{
      const r=indexedDB.open('dyson-first-light-backups',1);r.onsuccess=()=>{
        const db=r.result;const tx=db.transaction('backups','readonly');const q=tx.objectStore('backups').getAll();
        q.onsuccess=()=>resolve(q.result);tx.oncomplete=()=>db.close()}})''')
    assert OLD_RECORD in archived
    assert read_record(page,'dyson-private-backups')==OLD_RECORD
    page.click('#play');page.wait_for_timeout(300)
    page.click('#launch');page.wait_for_function('!!window.cloudView.world.packet')
    page.click('#reset');page.wait_for_function('window.cloudView.world.packet===null')
    page.close()


def test_blocked_browser_storage_still_allows_temporary_physics_session(backend,chromium):
    page=chromium.new_page()
    page.add_init_script("IDBFactory.prototype.open=()=>{throw new DOMException('Storage blocked','SecurityError')}")
    page.goto(backend.url+'/simple')
    page.wait_for_function('window.cloudView?.world?.time>0')
    page.click('#play');page.wait_for_timeout(300)
    assert 'temporary session' in page.locator('#connection').inner_text()
    page.click('#launch');page.wait_for_function('!!window.cloudView.world.packet')
    assert page.locator('#reset').is_enabled()
    page.close()


def test_retry_reads_committed_state_after_lost_step_response(backend,chromium):
    page=chromium.new_page()
    committed=[]
    def lose_once(route):
        if not committed:
            result=route.fetch();committed.append(result.json()['time']);route.abort()
        else:route.continue_()
    page.route('**/api/simple/step',lose_once)
    page.goto(backend.url+'/simple')
    page.wait_for_function('document.querySelector("#play").textContent==="Retry connection"')
    requests=[]
    page.on('request',lambda r:requests.append(r.url.rsplit('/',1)[-1]) if '/api/simple' in r.url else None)
    page.click('#play')
    page.wait_for_function('(t)=>window.cloudView?.world?.time>=t',arg=committed[0])
    assert requests[0]=='session'
    assert page.locator('#reason').get_attribute('class')!='error'
    page.close()
