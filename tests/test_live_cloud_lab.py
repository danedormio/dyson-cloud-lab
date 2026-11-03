"""Explicit hosted acceptance at the actual authorized development revision."""
import json
import os
from pathlib import Path
import time
import urllib.request
import pytest
from test_cloud_lab_browser import observe_baseline,open_lab

URL='https://dyson-cloud-lab-rebound-staging.onrender.com'

@pytest.mark.skipif(not os.environ.get('DYSON_LIVE_SHA'),reason='Requires explicit hosted acceptance dispatch')
def test_live_cloud_lab(chromium):
    expected=os.environ['DYSON_LIVE_SHA']
    # Free hosting can wake; verify exact source before claiming hosted parity.
    for attempt in range(30):
        try:
            with urllib.request.urlopen(URL+'/health',timeout=30) as r:health=json.load(r)
            if health.get('revision')==expected:break
        except OSError:pass
        time.sleep(3)
    else:raise AssertionError({'expected':expected,'observed':health if 'health' in locals() else None})
    context=chromium.new_context(viewport={'width':1600,'height':1000})
    context.add_cookies([{'name':'dyson_simple_session_v13','value':'A'*43,'url':URL+'/api'}])
    page=context.new_page();evidence=observe_baseline(page,URL)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path='test-artifacts/live-cloud-mobile.png',full_page=True)
    page.click('#launch');page.wait_for_function('cloudView.world.np===1')
    page.select_option('#rate','7305');started=time.monotonic();page.click('#play')
    page.wait_for_function('cloudView.world.packets[0].specific_energy<0 || cloudView.world.halted',timeout=180000)
    page.click('#play');world=page.evaluate('cloudView.world')
    assert not world['halted'] and world['packets'][0]['specific_energy']<0
    evidence['capture_seconds']=time.monotonic()-started;evidence['capture_day']=world['time'];evidence['packet']=world['packets'][0]
    evidence['energy_residual']=world['residual'];evidence['revision']=expected
    page.screenshot(path='test-artifacts/live-cloud-bound.png',full_page=True)
    assert abs(world['residual'])<1e-4
    Path('test-artifacts/live-skunkworks-observations.json').write_text(json.dumps(evidence,indent=2))
    print('LIVE_CLOUD_EVIDENCE',json.dumps(evidence))
    context.close()
