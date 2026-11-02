"""Explicit deployed-browser acceptance, only run by an authorized manual dispatch."""
import json
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
    page.locator('#geometry').select_option('sphere');page.locator('#count').fill('72')
    page.locator('#reset').click();expect(page.locator('#state')).to_contain_text('74 bodies')
    page.wait_for_function('!busy')
    evidence=page.evaluate('''()=>({time:snapshot.time_s,points:snapshot.bodies.slice(2).map(b=>[b.x_m,b.y_m,b.z_m]),camera:[explorer.az,explorer.el,explorer.distance]})''')
    # Test the visible canvas, not just an object-list select control.
    page.locator('#view').scroll_into_view_if_needed();page.wait_for_timeout(150)
    q=page.evaluate('explorer.projected.find(p=>p.id===3)');box=page.locator('#view').bounding_box()
    page.mouse.click(box['x']+q['x'],box['y']+q['y'])
    page.wait_for_function('laboratory.prediction?.positions_m.length===97',timeout=30000)
    chosen=page.evaluate('selected');assert chosen is not None
    evidence['forecast']=page.evaluate('laboratory.prediction')
    page.locator('#rate').select_option('31557600')
    page.evaluate('window.observedFrames=[];window.recordFrames=true;function observe(){if(window.recordFrames){window.observedFrames.push({t:performance.now(),render:motion.time,x:explorer.projected.find(p=>p.id===3)?.x});requestAnimationFrame(observe)}}requestAnimationFrame(observe)')
    page.locator('#play').click();page.wait_for_timeout(1800);page.locator('#play').click()
    page.wait_for_function('!busy');page.evaluate('window.recordFrames=false')
    frames=page.evaluate('window.observedFrames');evidence['frames']=frames
    assert len(frames)>=10
    assert len({round(f['x'] or 0,2) for f in frames})>=8
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
    context.close()
