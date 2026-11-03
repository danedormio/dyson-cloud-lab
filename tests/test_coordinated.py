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


def test_remote_decisions_do_not_read_instantaneous_packet_geometry():
    def commands(current_x):
        w=CoordinatedCloud();w.launch();w.sim.t=10000;w.plan_time=0
        w.observations=[[5000,[AU,.1*AU,0],[0,27000,0]]]
        # Two different undelivered current packet states, same arrived telemetry.
        packet=w.sim.particles[-1];packet.x=current_x*AU;packet.y=.2*AU
        result=[]
        def spy(i,j,impulse,dt,store_id):
            if i==N+1:result.append((j,impulse))
            return False
        w.exchange=spy
        w.controls(DT)
        return result
    first,second=commands(1.),commands(-1.)
    assert first and first==second


def test_spatial_cloud_and_legacy_envelopes():
    w=CoordinatedCloud()
    bodies=list(w.sim.particles)[1:]
    assert min(p.z for p in bodies)<-.5*AU and max(p.z for p in bodies)>.5*AU
    assert len(set(round(norm([p.x,p.y,p.z])/AU,3) for p in bodies))>40
    for p,r in zip(bodies,w.reference_radii):
        assert abs(sum(x*v for x,v in zip([p.x,p.y,p.z],[p.vx,p.vy,p.vz])))<1e-7*r*norm([p.vx,p.vy,p.vz])
    saved=w.snapshot();restored=CoordinatedCloud(saved)
    assert restored.reference_radii==w.reference_radii
    del saved['reference_radii']
    assert CoordinatedCloud(saved).reference_radii==[(.8+.4*(k//16))*AU for k in range(N)]


def test_launch_and_restore_keep_live_integrator_particles():
    w=CoordinatedCloud();w.launch(angle=133,elevation=37,roll=-71,offset=.85,speed=61)
    before=w.snapshot();w.advance(2)
    assert before['bodies']!=w.snapshot()['bodies']
    # Compare independently acquired C views: cached references must stay live.
    for body,actual in zip(w.state()['bodies'],w.sim.particles):
        assert body['x']==actual.x/AU and body['vz']==actual.vz
    r=CoordinatedCloud(w.snapshot());r.advance(2);w.advance(2)
    assert r.launch_settings==w.launch_settings
    for a,b in zip(w.sim.particles,r.sim.particles):
        assert math.dist((a.x,a.y,a.z),(b.x,b.y,b.z))<1e-7*AU


def test_three_dimensional_launch_geometry_and_input_limits(tmp_path):
    from fastapi.testclient import TestClient
    from server import create_app
    from sessions import SessionStore
    c=TestClient(create_app(SessionStore(tmp_path/'aim.sqlite3')))
    for angle,elevation,roll in [(133,37,-71),(-180,90,180),(180,-90,-180)]:
        c.post('/api/simple/reset',json={})
        s=c.post('/api/simple/launch',json=dict(angle=angle,elevation=elevation,roll=roll,speed=61,offset=.85)).json()
        p=s['bodies'][-1];position=[p[k] for k in ['x','y','z']];velocity=[p[k]/61000 for k in ['vx','vy','vz']]
        assert abs(norm(position)-math.hypot(2.2,.85))<1e-12
        assert abs(dot_for_test(position,velocity)+2.2)<1e-12
        assert abs(norm(velocity)-1)<1e-12
        assert s['launch_settings']['elevation']==elevation
    for field,value in [('angle',181),('elevation',91),('roll',181)]:
        assert c.post('/api/simple/launch',json={field:value}).status_code==422


def dot_for_test(a,b):
    return math.fsum(x*y for x,y in zip(a,b))


def test_display_links_distinguish_packet_and_neighbor_coupling():
    w=CoordinatedCloud();w.launch();node=w.sim.particles[1];p=w.sim.particles[-1]
    p.x,p.y,p.z=node.x+.1*AU,node.y,node.z
    assert w.exchange(N+1,1,-1e12,DT,0)
    j=min(range(2,N+1),key=lambda j:math.dist([node.x,node.y,node.z],
        [w.sim.particles[j].x,w.sim.particles[j].y,w.sim.particles[j].z]))
    assert w.exchange(1,j,1e12,DT,0)
    assert w.state()['links']==[1]
    assert w.state()['neighbor_links']==[[1,j]]
    restored=CoordinatedCloud(w.snapshot())
    assert restored.state()['links']==[1] and restored.state()['neighbor_links']==[[1,j]]


def test_radial_bound_orbit_has_finite_apoapsis():
    w=CoordinatedCloud();w.launch();sun=w.sim.particles[0];p=w.sim.particles[-1]
    p.x,p.y,p.z=sun.x+AU,sun.y,sun.z
    p.vx,p.vy,p.vz=sun.vx-1000,sun.vy,sun.vz
    orbit=w.state()['packet']
    assert orbit['specific_energy']<0 and orbit['eccentricity']==1
    assert orbit['periapsis']==0 and .99<orbit['apoapsis']<1.01
