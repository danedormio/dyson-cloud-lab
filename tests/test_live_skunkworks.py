"""Explicit deployed-browser acceptance, only run by an authorized manual dispatch."""
import json
import math
import os
from pathlib import Path
import time

import pytest
from playwright.sync_api import expect

URL='https://dyson-cloud-lab-rebound-staging.onrender.com'


def observe_parity(page, expected_sha=None):
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL if expected_sha else os.environ['DYSON_TEST_URL'],timeout=90000)
    expect(page.locator('#wake')).to_be_hidden(timeout=180000)
    if expected_sha:
        expect(page.locator('#buildVersion')).to_have_text('Build: '+expected_sha,timeout=10000)
    rates=page.locator('#rate option').evaluate_all('(options)=>options.map(o=>Number(o.value))')
    assert {3600,86400,604800,15778800,31557600,63115200,157788000,315576000,631152000}.issubset(rates)
    page.locator('#geometry').select_option('sphere');page.locator('#count').fill('72')
    page.locator('#reset').click();expect(page.locator('#state')).to_contain_text('74 bodies')
    page.wait_for_function('!busy')
    evidence=page.evaluate('''()=>({time:snapshot.time_s,points:snapshot.bodies.slice(2).map(b=>[b.x_m,b.y_m,b.z_m]),velocities:snapshot.bodies.slice(2).map(b=>[b.vx_ms,b.vy_ms,b.vz_ms]),sun:snapshot.bodies[0],camera:[explorer.az,explorer.el,explorer.distance]})''')
    sun=evidence['sun'];origin=[sun[k] for k in ('x_m','y_m','z_m')];velocity=[sun[k] for k in ('vx_ms','vy_ms','vz_ms')]
    normals=[];radials=[]
    for point,speed in zip(evidence['points'],evidence['velocities']):
        r=[p-o for p,o in zip(point,origin)];v=[p-o for p,o in zip(speed,velocity)]
        h=[r[1]*v[2]-r[2]*v[1],r[2]*v[0]-r[0]*v[2],r[0]*v[1]-r[1]*v[0]]
        normals.append([x/math.hypot(*h) for x in h]);radials.append([x/math.hypot(*r) for x in r])
    for vectors in (radials,normals):
        for axis in range(3):
            assert min(p[axis] for p in vectors)<-.8 and max(p[axis] for p in vectors)>.8
    evidence['orbital_plane_extents']=[[min(p[i] for p in normals),max(p[i] for p in normals)] for i in range(3)]
    # Test the visible canvas, not just an object-list select control.
    page.locator('#view').scroll_into_view_if_needed();page.wait_for_timeout(150)
    q=page.evaluate('explorer.projected.find(p=>p.id===3)');box=page.locator('#view').bounding_box()
    page.mouse.click(box['x']+q['x'],box['y']+q['y'])
    page.wait_for_function('laboratory.prediction?.positions_m.length===97',timeout=30000)
    chosen=page.evaluate('selected');assert chosen is not None
    page.evaluate("""()=>{window.hashCanvas=()=>{const gl=explorer.gl,p=new Uint8Array(can.width*can.height*4);gl.readPixels(0,0,can.width,can.height,gl.RGBA,gl.UNSIGNED_BYTE,p);let hash=2166136261;for(let i=0;i<p.length;i+=16)hash=Math.imul(hash^p[i],16777619);return hash>>>0}}""")
    page.wait_for_timeout(150);with_line=page.evaluate('window.hashCanvas()')
    page.locator('#selectedTrail').uncheck();page.wait_for_timeout(150)
    assert page.evaluate('window.hashCanvas()')!=with_line
    evidence['trajectory_pixels_differ']=True
    page.locator('#selectedTrail').check()
    output=Path('test-artifacts');output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/('live-skunkworks-selection.png' if expected_sha else 'prototype-parity-selection.png')),full_page=True)
    evidence['forecast']=page.evaluate('laboratory.prediction')
    page.locator('#rate').select_option('31557600')
    page.evaluate('window.observedFrames=[];window.recordFrames=true;function observe(){if(window.recordFrames){window.observedFrames.push({t:performance.now(),render:motion.time,x:explorer.projected.find(p=>p.id===3)?.x,pixels:window.observedFrames.length%5===0?window.hashCanvas():null});requestAnimationFrame(observe)}}requestAnimationFrame(observe)')
    page.locator('#play').click();page.wait_for_timeout(1800);page.locator('#play').click()
    page.wait_for_function('!busy');page.evaluate('window.recordFrames=false')
    frames=page.evaluate('window.observedFrames');evidence['frames']=frames
    assert len(frames)>=10
    assert len({round(f['x'] or 0,2) for f in frames})>=8
    assert len({f['pixels'] for f in frames if f['pixels'] is not None})>=3
    assert max(f['render'] or 0 for f in frames)>min(f['render'] or 0 for f in frames)
    # Rotation and zoom survive while body motion remains actual backend evolution.
    page.locator('#view').press('ArrowRight');page.locator('#view').press('+')
    assert page.evaluate('[explorer.az,explorer.el,explorer.distance]')!=evidence['camera']
    for impact in ('1.2','-1.2'):
        before=page.evaluate('snapshot.bodies.length');page.locator('#impact').fill(impact);page.locator('#launch').click()
        page.wait_for_function('(n)=>snapshot.bodies.length===n+1',arg=before)
        page.wait_for_function('!busy')
    evidence['additional_objects']=2
    page.locator('#rate').select_option('63115200')
    start=page.evaluate('snapshot.time_s');page.locator('#advance').click()
    expect(page.locator('#cancelAdvance')).to_be_hidden(timeout=120000)
    assert page.evaluate('snapshot.time_s')-start==63115200
    page.wait_for_function('laboratory.prediction?.body_id===selected && laboratory.prediction.positions_m.length===97',timeout=30000)
    evidence['two_year_delta_s']=63115200;evidence['final_time_s']=page.evaluate('snapshot.time_s')
    assert not errors,errors
    return evidence


@pytest.mark.skipif(not os.environ.get('DYSON_LIVE_SHA'),reason='Requires explicit live acceptance dispatch')
def test_live_skunkworks(chromium):
    expected=os.environ.get('DYSON_LIVE_SHA')
    assert expected,'Live acceptance requires explicit deployed SHA'
    context=chromium.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
    evidence=observe_parity(page,expected)
    output=Path('test-artifacts');output.mkdir(exist_ok=True)
    # Physical fixture data only; no credential or private backup is captured.
    (output/'live-skunkworks-observations.json').write_text(json.dumps(evidence,indent=2))
    page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(output/'live-skunkworks-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(output/'live-skunkworks-mobile.png'),full_page=True)
    print('LIVE_BROWSER_EVIDENCE',json.dumps({'expected_sha':expected,'build_text':page.locator('#buildVersion').inner_text(),'orbital_plane_extents':evidence['orbital_plane_extents'],'frames':len(evidence['frames']),'pixel_hashes':len({f['pixels'] for f in evidence['frames'] if f['pixels'] is not None}),'trajectory_pixels_differ':evidence['trajectory_pixels_differ'],'additional_objects':evidence['additional_objects'],'two_year_delta_s':evidence['two_year_delta_s']}))
    from sandbox_observer import observe_sandbox
    print('LIVE_SANDBOX_EVIDENCE',json.dumps(observe_sandbox(context.new_page(),URL,expected)))
    context.close()
