"""Owner baseline journeys, with real browser-worker REBOUND (no physics mocks)."""
import json
import math
from pathlib import Path
import time
from playwright.sync_api import expect

OUTPUT=Path('test-artifacts')

def open_lab(page,url):
    page.goto(url+'/simple',timeout=90000)
    page.wait_for_function('window.cloudView?.world?.n===900',timeout=30000)
    expect(page.locator('#play')).to_be_enabled()
    assert not page.evaluate('cloudView.playing')
    return page.evaluate('cloudView.world')

def pixel_hash(page):
    return page.evaluate('''()=>{const a=document.querySelector('#space').getContext('2d').getImageData(0,0,document.querySelector('#space').width,document.querySelector('#space').height).data;let h=2166136261;for(let i=0;i<a.length;i+=16)h=Math.imul(h^a[i],16777619);return h>>>0}''')

def observe_baseline(page,url):
    errors=[];api=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:api.append(r.url) if '/api/simple/' in r.url else None)
    initial=open_lab(page,url);assert initial['bodyCount']==901
    assert len(initial['bodies'])==901 and all(b['mass']>0 for b in initial['bodies'])
    assert len({round(b['z'],3) for b in initial['bodies'][1:]})>800
    page.wait_for_timeout(150);baseline=pixel_hash(page)
    # Each reference checkbox changes actual canvas pixels, not only labels.
    for guide in ['plane','bounds','earth']:
        expect(page.locator('#'+guide)).to_be_checked()
        before=pixel_hash(page);page.uncheck('#'+guide);page.wait_for_timeout(100)
        assert pixel_hash(page)!=before
        page.check('#'+guide)
    OUTPUT.mkdir(exist_ok=True);page.screenshot(path=str(OUTPUT/'local-cloud-desktop.png'))
    rates=page.locator('#rate option').evaluate_all('(a)=>a.map(x=>Number(x.value))')
    assert max(rates)==7305 and min(rates)<1
    page.select_option('#rate','7305');start=time.monotonic();page.click('#play')
    page.wait_for_function('cloudView.world.time>365.25',timeout=10000)
    elapsed=time.monotonic()-start;coast=page.evaluate('cloudView.world')
    assert max(math.dist([a[k] for k in ['x','y','z']],[b[k] for k in ['x','y','z']]) for a,b in zip(initial['bodies'][1:],coast['bodies'][1:]))>.1
    for i in range(3):
        page.click('#launch');page.wait_for_function('(n)=>cloudView.world.np===n',arg=i+1)
        assert page.evaluate('cloudView.playing')
    launched=page.evaluate('cloudView.world');assert launched['time']>=coast['time']
    page.wait_for_function('(t)=>cloudView.world.time>t+4',arg=launched['time'],timeout=15000)
    page.click('#play');page.wait_for_timeout(250)
    paused=page.evaluate('cloudView.world');assert paused['np']==3 and not paused['halted']
    assert all(math.isfinite(p['specific_energy']) for p in paused['packets'])
    assert page.locator('#packets button').count()==3
    page.locator('#packets button').first.click();expect(page.locator('#inspectTitle')).to_have_text('Packet 1')
    expect(page.locator('#inspectBody')).to_contain_text('Closest approach')
    page.click('#closeInspect');page.screenshot(path=str(OUTPUT/'local-cloud-multiple-packets.png'))
    page.wait_for_timeout(500);page.reload();page.wait_for_function('window.cloudView?.world?.np===3')
    restored=page.evaluate('cloudView.world');assert restored['time']==paused['time'] and not page.evaluate('cloudView.playing')
    # Reset is a real replacement scene and is paused, unlike live insertion.
    page.click('#reset');page.wait_for_function('cloudView.world.np===0 && cloudView.world.time===0')
    assert not page.evaluate('cloudView.playing')
    assert not api and not errors,(api,errors)
    return {'elements':900,'live_packets':3,'coast_days':coast['time'],'coast_seconds':elapsed,'restored_days':restored['time'],'errors':errors,'server_simulation_requests':len(api)}

def test_full_owner_baseline(backend,chromium):
    page=chromium.new_page(viewport={'width':1600,'height':1000})
    try:observe_baseline(page,backend.url)
    finally:page.context.close()

def test_paused_simultaneous_packets_are_finite_and_saved(backend,chromium):
    page=chromium.new_page();open_lab(page,backend.url)
    for i in range(3):page.click('#launch');page.wait_for_function('(n)=>cloudView.world.np===n',arg=i+1)
    assert not page.evaluate('cloudView.playing')
    assert page.evaluate('cloudView.world.packets.every(p=>Number.isFinite(p.specific_energy))')
    page.wait_for_timeout(500);page.reload();page.wait_for_function('window.cloudView?.world?.np===3')
    assert page.evaluate('cloudView.world.time')==0
    page.click('#play');page.wait_for_function('cloudView.world.time>10');page.click('#play')
    assert page.evaluate('cloudView.world.halted')==0
    page.context.close()

def test_expired_server_cookie_and_legacy_backup_cannot_block_cloud(backend,chromium):
    context=chromium.new_context();context.add_cookies([{'name':'dyson_simple_session_v13','value':'A'*43,'url':backend.url+'/api'}])
    page=context.new_page();page.route('**/api/**',lambda route:route.abort())
    page.add_init_script("localStorage.setItem('dyson-cloud-backup', 'legacy retained fixture')")
    open_lab(page,backend.url);expect(page.locator('#notice')).to_be_hidden()
    page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    assert page.evaluate("localStorage.getItem('dyson-cloud-backup')")=='legacy retained fixture'
    context.close()

def test_blocked_browser_storage_still_has_working_cloud(backend,chromium):
    page=chromium.new_page();page.add_init_script("Object.defineProperty(window,'indexedDB',{get(){throw new Error('blocked')}})")
    open_lab(page,backend.url);expect(page.locator('#saveStatus')).to_contain_text('Temporary scene')
    page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    with page.expect_download() as event:page.click('#exportScene')
    assert event.value.suggested_filename=='dyson-cloud-scene.json'
    page.context.close()

def test_corrupt_snapshot_retained_but_new_cloud_ready(backend,chromium):
    page=chromium.new_page();open_lab(page,backend.url)
    page.evaluate('''async()=>{await new Promise((resolve,reject)=>{let r=indexedDB.open('dyson-local-laboratory',1);r.onsuccess=()=>{let tx=r.result.transaction('scenes','readwrite');tx.objectStore('scenes').put({format:'dyson-local-scene-v2',snapshot:new Float64Array([24001,900]).buffer,sha256:'bad checksum'},'current');tx.oncomplete=()=>{r.result.close();resolve()}};r.onerror=reject})}''')
    page.reload();page.wait_for_function('window.cloudView?.world?.n===900')
    expect(page.locator('#notice')).to_contain_text('retained')
    expect(page.locator('#downloadPrevious')).to_be_visible()
    page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    retained=page.evaluate('''async()=>await new Promise(resolve=>{let r=indexedDB.open('dyson-local-laboratory',1);r.onsuccess=()=>{let q=r.result.transaction('scenes').objectStore('scenes').getAllKeys();q.onsuccess=()=>resolve(q.result.filter(k=>String(k).startsWith('retained-')).length)}})''')
    assert retained>=1;page.context.close()

def test_3d_aiming_inspection_camera_and_mobile(backend,chromium):
    page=chromium.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));open_lab(page,backend.url)
    page.locator('summary').first.click()
    for control,value in [('az',73),('el',35),('roll',-42),('offset',-7)]:
        page.locator('#'+control).evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input"))}',value)
    aim=page.evaluate('cloudView.aimGeometry()');page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    body=page.evaluate('cloudView.world.bodies.at(-1)')
    assert math.dist([body[k] for k in ['x','y','z']],aim['position'])<1e-10
    before=page.evaluate('cloudView.project(20,0,0)');box=page.locator('#space').bounding_box()
    page.mouse.move(box['x']+100,box['y']+250);page.mouse.down();page.mouse.move(box['x']+170,box['y']+280);page.mouse.up()
    assert page.evaluate('cloudView.project(20,0,0)')!=before
    page.click('#home');assert page.evaluate('cloudView.project(20,0,0)')==before
    OUTPUT.mkdir(exist_ok=True);page.screenshot(path=str(OUTPUT/'local-cloud-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.locator('#play')).to_be_in_viewport();expect(page.locator('#launch')).to_be_in_viewport()
    assert not errors;page.context.close()

def test_scene_file_roundtrip_and_invalid_layout_preserve_current(backend,chromium):
    import base64,hashlib
    page=chromium.new_page();open_lab(page,backend.url)
    page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    with page.expect_download() as event:page.click('#exportScene')
    record=json.loads(Path(event.value.path()).read_text())
    page.click('#reset');page.wait_for_function('cloudView.world.np===0')
    page.set_input_files('#importScene',{'name':'scene.json','mimeType':'application/json','buffer':json.dumps(record).encode()})
    page.wait_for_function('cloudView.world.np===1')
    assert not page.evaluate('cloudView.playing')
    raw=base64.b64decode(record['snapshot'])[:800]
    record['snapshot']=base64.b64encode(raw).decode();record['sha256']=hashlib.sha256(raw).hexdigest()
    page.set_input_files('#importScene',{'name':'bad-layout.json','mimeType':'application/json','buffer':json.dumps(record).encode()})
    expect(page.locator('#notice')).to_contain_text('layout is invalid')
    assert page.evaluate('cloudView.world.np')==1
    page.context.close()
