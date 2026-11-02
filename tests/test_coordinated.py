import math
import pytest
from coordinated import CoordinatedCloud, AU, DAY, DT, N, CAPACITY, PACKET_MASS, norm, sub


def test_pair_exchange_closes_energy_momentum_and_angular_momentum():
    w=CoordinatedCloud(); w.launch()
    # Put packet close enough for a genuine central exchange with station 1.
    node=w.sim.particles[1];p=w.sim.particles[-1]
    p.x,p.y,p.z=node.x+.1*AU,node.y,node.z
    before_energy=w.sim.energy()+sum(w.stores)+sum(w.heat)
    before_p=w.momentum(); before_l=w.angular()
    assert w.exchange(N+1,1,-1e12,DT,0)
    after_energy=w.sim.energy()+sum(w.stores)+sum(w.heat)
    assert abs(after_energy-before_energy)<8*math.ulp(before_energy)  # absolute float floor of the full-system sum
    assert norm(sub(before_p,w.momentum()))<1e-6*1e12
    assert abs(w.angular()-before_l)<abs(before_l)*1e-14
    assert all(0<=x<=CAPACITY for x in w.stores)


def test_screening_delay_and_passive_limits():
    for speed,mode in [(45,'Attempt capture'),(80,'Assist only'),(180,'Stand aside')]:
        w=CoordinatedCloud();w.launch(speed=speed)
        assert w.plan==mode
        w.controls(DT)
        assert w.exchanged==0  # no instant plan reception
    w=CoordinatedCloud();w.launch(speed=180);before=w.snapshot()
    w.advance(2)
    assert w.work_total==0 and w.stores==before['stores'] and w.heat==before['heat']
    w=CoordinatedCloud();w.launch(enabled=False);w.advance(2)
    assert w.work_total==0 and w.exchanged==0


def test_empty_store_rejects_energy_consuming_action():
    w=CoordinatedCloud();w.launch();node=w.sim.particles[1];p=w.sim.particles[-1]
    p.x,p.y,p.z=node.x+.1*AU,node.y,node.z
    p.vx=node.vx+10000;w.stores[0]=0
    before=w.snapshot();assert not w.exchange(N+1,1,1e12,DT,0)
    assert w.snapshot()==before


def test_gravity_restart_and_no_packet_baseline():
    w=CoordinatedCloud();w.advance(2);r=CoordinatedCloud(w.snapshot())
    w.advance(2);r.advance(2)
    for a,b in zip(w.sim.particles,r.sim.particles):
        assert math.dist((a.x,a.y,a.z),(b.x,b.y,b.z))<1e-7*AU
    assert abs(w.state()['energy_residual_packet_scale'])<1e-4


def test_active_capture_passive_comparison_and_step_refinement():
    outcomes=[]
    for enabled,step in [(True,DT),(True,DT/2),(False,DT)]:
        w=CoordinatedCloud();w.launch(enabled=enabled)
        for _ in range(30):w.advance(4,step=step)
        s=w.state();outcomes.append(s)
        # Positive/negative work is explicitly balanced; finite-resource bounds hold.
        assert abs(s['energy_residual_packet_scale'])<1e-4
        assert all(0<=x<=CAPACITY for x in w.stores)
        assert all(0<=x<=.25*CAPACITY for x in w.heat)
        assert s['momentum_residual']<1e-5*PACKET_MASS*45000
    assert outcomes[0]['packet']['specific_energy']<0
    assert outcomes[1]['packet']['specific_energy']<0
    assert outcomes[2]['packet']['specific_energy']>0
    assert abs(outcomes[0]['packet']['radius']-outcomes[1]['packet']['radius'])<.03


def test_api_isolation_reproducible_launch_and_persistence(tmp_path):
    from fastapi.testclient import TestClient
    from server import create_app
    from sessions import SessionStore
    app=create_app(SessionStore(tmp_path/'minimal.sqlite3'))
    a,b=TestClient(app),TestClient(app)
    original=b.get('/api/simple').json()
    a.post('/api/simple/step',json={})
    first=a.post('/api/simple/launch',json={}).json()
    assert first['time']==0 and first['packet']
    assert b.get('/api/simple').json()['bodies']==original['bodies']
    assert a.post('/api/simple/launch',json={}).status_code==422
    a.post('/api/simple/reset',json={})
    second=a.post('/api/simple/launch',json={'enabled':False}).json()
    assert first['bodies']==second['bodies']
    state=a.get('/api/simple').json()
    assert state['plan']=='Passive'
    assert a.post('/api/simple/launch',json={'speed':1000}).status_code==422


def test_stellar_approach_stops_without_fake_capture():
    w=CoordinatedCloud();w.launch(offset=0,enabled=False)
    p=w.sim.particles[-1];p.x=.055*AU;p.y=0
    before=w.sim.t
    result=w.advance(2)
    assert w.sim.t==before and result['halted']
    assert result['decision']=='Stellar approach limit'
    assert w.exchanged==0
