"""Shared local/live user journey; checks pixels and actual REBOUND preview state."""
import json
from pathlib import Path
from playwright.sync_api import expect


def observe_sandbox(page, url, expected_sha=None):
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url,timeout=90000)
    expect(page.locator('#wake')).to_be_hidden(timeout=180000)
    page.wait_for_function('window.sandbox?.draft && explorer.projected?.length>0')
    if expected_sha:
        expect(page.locator('#buildVersion')).to_have_text('Build: '+expected_sha)
    page.get_by_role('button',name='Launch',exact=True).click()
    slider=page.locator('#impactSlider');slider.scroll_into_view_if_needed()
    page.evaluate('''()=>{window.sandboxHash=()=>{const gl=explorer.gl,p=new Uint8Array(can.width*can.height*4);gl.readPixels(0,0,can.width,can.height,gl.RGBA,gl.UNSIGNED_BYTE,p);let h=2166136261;for(let i=0;i<p.length;i+=16)h=Math.imul(h^p[i],16777619);return h>>>0}}''')
    before=page.evaluate('({time:snapshot.time_s,bodies:snapshot.bodies,events:snapshot.boundary_events,start:window.sandbox.draft.start,hash:window.sandboxHash()})')
    requests=[]
    page.on('request',lambda r: requests.append(r.url) if '/api/launch-preview' in r.url else None)
    box=slider.bounding_box()
    page.mouse.move(box['x']+box['width']*.51,box['y']+box['height']/2)
    page.mouse.down();page.mouse.move(box['x']+box['width']*.54,box['y']+box['height']/2,steps=8);page.mouse.up()
    page.wait_for_function('(start)=>JSON.stringify(window.sandbox.draft.start)!==JSON.stringify(start)',arg=before['start'])
    page.wait_for_function('(h)=>window.sandboxHash()!==h',arg=before['hash'])
    assert not requests,'Draft updates must not start expensive automatic integration'
    assert page.evaluate('snapshot.bodies')==before['bodies']
    assert page.evaluate('snapshot.time_s')==before['time']
    for field,value in [('speed','45'),('impact','1.3'),('angle','25'),('arrivalMass','1000'),('azimuth','20'),('elevation','18')]:
        page.locator('#'+field).fill(value)
        assert page.locator('#'+field+'Slider').get_attribute('aria-valuetext')==value
    page.locator('#frameAim').click()
    page.locator('#traceLaunch').click()
    page.wait_for_function('window.sandbox.validPreview()?.positions_m.length===97',timeout=45000)
    result=page.evaluate('window.sandbox.validPreview()')
    assert page.evaluate('snapshot.bodies')==before['bodies']
    assert page.evaluate('snapshot.boundary_events')==before['events']
    page.wait_for_timeout(120);with_preview=page.evaluate('window.sandboxHash()')
    page.evaluate('window.savedPreview=window.sandbox.preview;window.sandbox.preview=null')
    page.wait_for_timeout(120)
    assert page.evaluate('window.sandboxHash()')!=with_preview
    page.evaluate('window.sandbox.preview=window.savedPreview')
    output=Path('test-artifacts');output.mkdir(exist_ok=True)
    prefix='live-sandbox' if expected_sha else 'sandbox'
    page.evaluate('document.querySelector(".controlScroll").scrollTop=0;scrollTo(0,0)')
    page.screenshot(path=str(output/(prefix+'-preview.png')),full_page=True)
    page.locator('#launch').click()
    page.wait_for_function('(n)=>snapshot.bodies.length===n+1',arg=len(before['bodies']),timeout=30000)
    page.wait_for_function('!busy')
    body=page.evaluate('snapshot.bodies.at(-1)')
    assert body==result['initial_body']
    assert page.evaluate('window.sandbox.validPreview()') is None
    expect(page.locator('#launchToast')).to_be_visible()
    page.locator('#focusView').click()
    assert page.locator('body').evaluate("e=>e.classList.contains('focusMode')")
    page.locator('#view').press('ArrowRight');page.locator('#view').press('+')
    page.locator('#view').press('Escape');expect(page.locator('#launch')).to_be_visible()
    page.locator('#tour').click();expect(page.locator('#quickStart')).to_be_visible()
    page.get_by_role('button',name='Let’s explore ↗').click();expect(page.locator('#quickStart')).to_be_hidden()
    page.locator('#view').press('Space');assert page.evaluate('running')
    page.wait_for_timeout(1000);page.locator('#view').press('Space');assert not page.evaluate('running')
    page.wait_for_function('!busy')
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate('scrollTo(0,0)');page.wait_for_timeout(200)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('#launch').is_visible()
    page.screenshot(path=str(output/(prefix+'-mobile.png')),full_page=True)
    page.get_by_role('button',name='Launch',exact=True).click()
    value=page.locator('#speed').input_value();page.locator('#speedSlider').press('ArrowRight')
    assert page.locator('#speed').input_value()!=value
    assert not errors,errors
    evidence={'draft_pointer_changes_pixels':True,'draft_network_requests':0,'preview_points':97,
              'preview_world_unchanged':True,'launched_body_matches_preview':True,
              'mobile_overflow':False,'keyboard_help_focus_play':True,'revision':expected_sha or 'local'}
    (output/(prefix+'-observations.json')).write_text(json.dumps(evidence,indent=2))
    return evidence
