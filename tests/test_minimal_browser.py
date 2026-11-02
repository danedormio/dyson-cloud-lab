from pathlib import Path
import json
import math


def test_minimal_launch_controls_motion_and_mobile(backend,chromium):
    page=chromium.new_page(viewport={'width':1440,'height':960})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(backend.url+'/simple')
    page.wait_for_function('window.cloudView?.world?.time>=2')
    page.click('#play');page.wait_for_timeout(600)
    initial=page.evaluate('window.cloudView.world')
    assert initial['time']>0 and len(initial['bodies'])==49
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
    # Launch during live playback must queue rather than silently drop the click.
    page.click('#play')
    page.click('#launch');page.wait_for_function('window.cloudView.world.packet!==null')
    page.click('#play');page.wait_for_timeout(600)
    assert page.evaluate('window.cloudView.world.time')<=4
    assert page.locator('#launch').is_disabled()
    page.click('#play');page.wait_for_function('window.cloudView.world.time>=8');page.click('#play')
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
    page.goto(backend.url+'/simple')
    page.wait_for_function('window.cloudView?.world?.time>=2')
    page.click('#play');page.wait_for_timeout(600)
    page.click('#launch');page.wait_for_function('window.cloudView.world.packet!==null')
    initial=page.evaluate('window.cloudView.world.bodies')
    # Simulate an ephemeral service redeploy; same recovery key, lost server DB.
    backend.stop();backend.db.unlink();backend.start()
    page.reload()
    page.wait_for_function('!!window.cloudView?.world?.packet')
    page.click('#play');page.wait_for_timeout(600)
    recovered=page.evaluate('window.cloudView.world')
    assert recovered['packet'] is not None and len(recovered['bodies'])==len(initial)
    assert recovered['plan']=='Attempt capture'
    assert page.locator('#decision').inner_text()!='Preparing the cloud'
    page.close()
