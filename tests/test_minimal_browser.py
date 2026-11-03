from pathlib import Path
import json
import math


def test_minimal_launch_controls_motion_and_mobile(backend,chromium):
    page=chromium.new_page(viewport={'width':1440,'height':960})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(backend.url+'/simple-legacy')
    page.wait_for_function('!!window.cloudView?.world')
    page.wait_for_timeout(600)
    initial=page.evaluate('window.cloudView.world')
    assert initial['time']==0 and len(initial['bodies'])==49
    # Scene has actually moving resolved positions, not a loading placeholder.
    page.click('#play');page.wait_for_function('(t)=>window.cloudView.world.time>t',arg=initial['time'])
    page.click('#play');page.wait_for_timeout(600)
    moved=page.evaluate('window.cloudView.world')
    assert math.dist((moved['bodies'][1]['x'],moved['bodies'][1]['y']),
                     (initial['bodies'][1]['x'],initial['bodies'][1]['y']))>.001
    # Actual slider pointer changes launch geometry without adding a packet.
    slider=page.locator('#offset').bounding_box()
    page.mouse.click(slider['x']+.2*slider['width'],slider['y']+slider['height']/2)
    assert page.locator('#offsetValue').inner_text()!='0.65 AU'
    page.locator('#offset').evaluate("el=>{el.value='0.65'}")
    page.locator('#offset').dispatch_event('input')
    # Launch during live playback queues the click and returns to a paused scene.
    page.click('#play')
    page.click('#launch');page.wait_for_function('window.cloudView.world.packet!==null')
    assert page.locator('#play').inner_text()=='Play'
    page.wait_for_timeout(600)
    assert page.evaluate('window.cloudView.world.time')==0
    assert page.locator('#launch').is_disabled()
    page.click('#play');page.wait_for_function('window.cloudView.world.time>=2');page.click('#play')
    page.wait_for_timeout(600)
    assert page.evaluate('window.cloudView.trail.length')>=3
    # Selection is an actual canvas pointer operation.
    pt=page.evaluate('(()=>{let b=window.cloudView.world.bodies[9];return window.cloudView.project(b.x,b.y,b.z)})()')
    canvas=page.locator('canvas').bounding_box();page.mouse.click(canvas['x']+pt[0],canvas['y']+pt[1])
    assert page.locator('#inspector').is_visible()
    artifacts=Path('test-artifacts');artifacts.mkdir(exist_ok=True)
    page.screenshot(path=str(artifacts/'minimal-desktop.png'))
    page.click('#reset');page.wait_for_function('window.cloudView.world.packet===null')
    page.uncheck('#coord');page.locator('#speed').press('End');page.click('#launch')
    page.wait_for_function('window.cloudView.world.plan==="Passive"')
    assert page.evaluate('window.cloudView.world.work_j')==0
    page.click('#reset');page.wait_for_function('window.cloudView.world.packet===null')
    page.check('#coord');page.click('#launch');page.wait_for_function('window.cloudView.world.plan==="Stand aside"')
    page.set_viewport_size({'width':390,'height':900})
    assert page.evaluate('document.documentElement.scrollWidth')<=390
    assert page.locator('#launch').is_visible()
    page.screenshot(path=str(artifacts/'minimal-mobile.png'))
    (artifacts/'minimal-browser-observations.json').write_text(json.dumps({'errors':errors,'animated_days':moved['time'],'launch_rewinds_to_same_phase':True,'passive_and_stand_aside_verified':True}))
    assert errors==[]
    page.close()


def test_minimal_scene_resumes_after_server_storage_loss(backend,chromium):
    page=chromium.new_page(viewport={'width':1200,'height':900})
    page.goto(backend.url+'/simple-legacy')
    page.wait_for_function('!!window.cloudView?.world')
    page.wait_for_timeout(600)
    page.click('#launch');page.wait_for_function('window.cloudView.world.packet!==null')
    initial=page.evaluate('window.cloudView.world.bodies')
    # Simulate an ephemeral service redeploy; same recovery key, lost server DB.
    backend.stop();backend.db.unlink();backend.start()
    page.reload()
    page.wait_for_function('!!window.cloudView?.world?.packet')
    page.wait_for_timeout(600)
    assert page.locator('#play').inner_text()=='Play'
    recovered=page.evaluate('window.cloudView.world')
    assert recovered['packet'] is not None and len(recovered['bodies'])==len(initial)
    assert recovered['plan']=='Attempt capture'
    assert page.locator('#decision').inner_text()!='Preparing the cloud'
    page.close()


def test_cloud_volume_paused_start_rate_and_camera(backend,chromium):
    page=chromium.new_page(viewport={'width':1440,'height':960})
    page.goto(backend.url+'/simple-legacy')
    page.wait_for_function('!!window.cloudView?.world')
    initial=page.evaluate('window.cloudView.world')
    assert initial['time']==0
    assert len(set(round(math.dist((b['x'],b['y'],b['z']),(0,0,0)),3) for b in initial['bodies'][1:]))>40
    assert min(b['z'] for b in initial['bodies'])<-.5 and max(b['z'] for b in initial['bodies'])>.5
    page.wait_for_timeout(1100)
    assert page.evaluate('window.cloudView.world.time')==0
    assert page.locator('#play').inner_text()=='Play'
    steps=[]
    page.on('request',lambda r: steps.append(r.post_data_json['days']) if r.url.endswith('/api/simple/step') else None)
    page.select_option('#rate','0.25');page.click('#play')
    page.wait_for_function('window.cloudView.world.time>0')
    page.click('#play');page.wait_for_timeout(400)
    slow=list(steps);steps.clear()
    page.select_option('#rate','16');page.click('#play')
    page.wait_for_function('(t)=>window.cloudView.world.time>t+2',arg=page.evaluate('window.cloudView.world.time'))
    page.click('#play');page.wait_for_timeout(400)
    assert slow and steps and min(steps)>max(slow)*10
    canvas=page.locator('canvas');before=canvas.screenshot()
    box=canvas.bounding_box();page.mouse.move(box['x']+600,box['y']+300)
    page.mouse.down();page.mouse.move(box['x']+750,box['y']+390,steps=8);page.mouse.up()
    assert canvas.screenshot()!=before
    page.click('#reset');page.wait_for_function('window.cloudView.world.time===0')
    assert page.locator('#play').inner_text()=='Play'
    Path('test-artifacts').mkdir(exist_ok=True)
    page.screenshot(path='test-artifacts/cloud-volume-paused.png')
    page.close()


def test_playback_blends_acknowledged_samples_and_pause_is_exact(backend,chromium):
    page=chromium.new_page()
    page.add_init_script("""const originalFetch=window.fetch;
      let steps=0;window.fetch=async (...args)=>{
      const response=await originalFetch(...args);
      if(String(args[0]).endsWith('/api/simple/step')){
        steps++;await new Promise(r=>setTimeout(r,steps===1?900:2500));
      }return response;};""")
    page.goto(backend.url+'/simple-legacy');page.wait_for_function('!!window.cloudView?.world')
    page.click('#play');page.wait_for_function('window.cloudView.world.time>0')
    first=page.evaluate('({t:cloudView.renderTime,physics:cloudView.world.time,b:cloudView.renderBodies[1]})')
    assert 0<=first['t']<first['physics']
    page.wait_for_timeout(250)
    second=page.evaluate('({t:cloudView.renderTime,physics:cloudView.world.time,b:cloudView.renderBodies[1]})')
    assert first['physics']==second['physics'] and first['t']<second['t']<=second['physics']
    assert math.dist([first['b'][k] for k in ['x','y','z']],[second['b'][k] for k in ['x','y','z']])>0
    page.click('#play');page.wait_for_timeout(40)
    assert page.evaluate('cloudView.renderTime===cloudView.world.time')
    assert page.evaluate('cloudView.renderBodies[1].x===cloudView.world.bodies[1].x')
    page.close()


def test_3d_aim_orbit_inspection_recovery_and_mobile_launch(backend,chromium):
    page=chromium.new_page(viewport={'width':1440,'height':960})
    page.goto(backend.url+'/simple-legacy');page.wait_for_function('!!window.cloudView?.world')
    requests=[];page.on('request',lambda r:requests.append(r.url) if '/api/simple' in r.url else None)
    before=page.locator('canvas').screenshot()
    page.locator('.aim3d summary').click()
    for field,value in [('angle',133),('elevation',37),('roll',-71),('offset',.85),('speed',61)]:
        page.locator('#'+field).evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input"))}',value)
    expected=page.evaluate('cloudView.aimGeometry()')
    assert page.locator('canvas').screenshot()!=before
    assert not requests and page.evaluate('cloudView.world.time')==0
    page.click('#launch');page.wait_for_function('!!cloudView.world.packet')
    packet=page.evaluate('cloudView.world.bodies.at(-1)')
    for i,key in enumerate(['x','y','z']):assert abs(packet[key]-expected['position'][i])<1e-12
    for i,key in enumerate(['vx','vy','vz']):assert abs(packet[key]-expected['velocity'][i])<1e-8
    page.click('#packetinfo')
    assert page.locator('#inspector').is_visible()
    assert 'Closest approach:' in page.locator('#selectedstate').inner_text()
    assert 'Eccentricity:' in page.locator('#selectedstate').inner_text()
    page.reload();page.wait_for_function('!!cloudView?.world?.packet')
    assert page.locator('#elevation').input_value()=='37'
    assert page.locator('#roll').input_value()=='-71'
    assert page.locator('#play').inner_text()=='Play'
    page.click('#reset');page.wait_for_function('cloudView.world.packet===null')
    page.set_viewport_size({'width':390,'height':900})
    page.locator('.aim3d summary').click();page.locator('#elevation').evaluate('el=>{el.value=45;el.dispatchEvent(new Event("input"))}')
    page.click('#launch');page.wait_for_function('!!cloudView.world.packet');page.wait_for_timeout(400)
    assert page.evaluate('document.documentElement.scrollWidth')<=390
    assert page.locator('canvas').bounding_box()['y']>=-10
    page.click('#play');page.wait_for_function('cloudView.world.time>0');page.click('#play')
    page.click('#home');page.click('#packetinfo')
    Path('test-artifacts').mkdir(exist_ok=True)
    page.screenshot(path='test-artifacts/complete-cloud-mobile.png',full_page=True)
    page.close()


def test_reset_clears_legacy_arrival_notice(backend,chromium):
    page=chromium.new_page()
    page.goto(backend.url+'/simple-legacy');page.wait_for_function('!!cloudView?.world')
    page.click('#launch');page.wait_for_function('!!cloudView.world.packet')
    def legacy_metadata(route):
        response=route.fetch();state=response.json();state['launch_settings']=None
        route.fulfill(response=response,json=state)
    page.route('**/api/simple/session',legacy_metadata)
    page.reload();page.wait_for_function('document.querySelector("#launchhint").textContent.includes("Earlier saved run")')
    page.unroute('**/api/simple/session',legacy_metadata)
    page.click('#reset');page.wait_for_function('!cloudView.world.packet')
    assert 'Earlier saved run' not in page.locator('#launchhint').inner_text()
    assert 'Press Play' in page.locator('#launchhint').inner_text()
    page.click('#launch');page.wait_for_function('!!cloudView.world.launch_settings')
    assert 'Earlier saved run' not in page.locator('#launchhint').inner_text()
    page.close()
