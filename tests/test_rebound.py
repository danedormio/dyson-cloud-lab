import math

from physics import CloudWorld, AU, DAY, EARTH_KG, SUN_KG

def test_all_bodies_share_rebound_engine():
    world = CloudWorld(3)
    state = world.state()
    assert state["engine"] == "REBOUND IAS15"
    assert len(state["bodies"]) == 5
    assert state["bodies"][0]["mass_kg"] == SUN_KG
    assert state["bodies"][1]["mass_kg"] == EARTH_KG
    assert all(p["mass_kg"] == 1.0 for p in state["bodies"][2:])
    assert len(world.sim.particles) == 5

def test_sun_is_not_pinned_and_total_momentum_is_balanced():
    world = CloudWorld(0)
    before = world.state()
    assert abs(before["bodies"][0]["vy_ms"]) > 0
    world.step(12*DAY)
    after = world.state()
    assert after["bodies"][0]["x_m"] != before["bodies"][0]["x_m"]
    vtot = [v / after["total_mass_kg"] for v in after["momentum_kg_ms"]]
    assert math.hypot(*vtot) < 1e-8

def test_earth_orbit_and_energy_conservation():
    world = CloudWorld(0)
    start = world.state()
    r0 = math.dist([start["bodies"][0][k] for k in ("x_m","y_m","z_m")],
                   [start["bodies"][1][k] for k in ("x_m","y_m","z_m")])
    for _ in range(13):
        world.step(28*DAY)
    end = world.state()
    r1 = math.dist([end["bodies"][0][k] for k in ("x_m","y_m","z_m")],
                   [end["bodies"][1][k] for k in ("x_m","y_m","z_m")])
    assert abs(r1-r0)/AU < 1e-6
    assert abs(end["energy_relative_drift"]) < 1e-8

def test_launch_is_same_one_kg_body_and_signed_impact():
    left = CloudWorld(0)
    a = left.add_incoming(25, -0.5, 0)["bodies"][-1]
    right = CloudWorld(0)
    b = right.add_incoming(25, +0.5, 180)["bodies"][-1]
    assert a["mass_kg"] == b["mass_kg"] == 1.0
    for k in ("x_m", "y_m", "z_m", "vx_ms", "vy_ms", "vz_ms"):
        assert math.isclose(a[k], b[k], abs_tol=1e-4)

def test_endpoints():
    from fastapi.testclient import TestClient
    from server import app
    c = TestClient(app)
    assert c.get("/health").json()["engine"] == "REBOUND IAS15"
    assert c.post("/api/reset",json={"cloud_count":1}).status_code == 200
    s = c.post("/api/launch",json={"speed_kms":25,"impact_au":-1,"offset_degrees":0}).json()
    assert len(s["bodies"])==4
    assert c.post("/api/step",json={"seconds":3600}).status_code == 200
    assert c.post("/api/step",json={"seconds":-1}).status_code == 422

def test_checkpoint_round_trip_continues_orbit():
    from fastapi.testclient import TestClient
    from server import app
    client = TestClient(app)
    client.post("/api/reset", json={"cloud_count": 3})
    client.post("/api/launch", json={"speed_kms": 25, "impact_au": -1.2, "offset_degrees": 35})
    client.post("/api/step", json={"seconds": 86400})
    original = client.get("/api/checkpoint").json()
    assert len(original["bodies"]) == 6
    assert original["time_s"] == 86400
    assert client.post("/api/reset", json={"cloud_count": 0}).status_code == 200
    restored = client.post("/api/restore", json=original)
    assert restored.status_code == 200
    value = restored.json()
    assert math.isclose(value["time_s"], original["time_s"])
    for old, new in zip(original["bodies"], value["bodies"]):
        assert old["mass_kg"] == new["mass_kg"]
        assert old["role"] == new["role"]
        for axis in ("x_m", "y_m", "z_m", "vx_ms", "vy_ms", "vz_ms"):
            assert math.isclose(old[axis], new[axis], rel_tol=1e-14, abs_tol=1e-10)
    assert client.post("/api/step", json={"seconds": 3600}).status_code == 200

def test_malformed_checkpoint_does_not_overwrite_running_simulation():
    from fastapi.testclient import TestClient
    from server import app
    client = TestClient(app)
    client.post("/api/reset", json={"cloud_count": 1})
    original = client.get("/api/checkpoint").json()
    corrupt = {**original, "bodies": [dict(x) for x in original["bodies"]]}
    corrupt["bodies"][0]["mass_kg"] = 1.0
    result = client.post("/api/restore", json=corrupt)
    assert result.status_code == 403  # tampering fails ownership/authenticity validation
    current = client.get("/api/checkpoint").json()
    # Export expiry and signature refresh, but every physical and solver field
    # must remain identical after the rejected restore.
    assert {k: v for k, v in current.items() if k not in ("signature", "expires_at")} == {
        k: v for k, v in original.items() if k not in ("signature", "expires_at")}


def test_all_supported_populations_have_distinct_finite_initial_conditions():
    for count in range(201):
        world = CloudWorld(count)
        s = world.state()
        assert len(s['bodies']) == count + 2
        assert math.isfinite(s['gravitational_energy_j'])
        assert all(math.isfinite(b[k]) for b in s['bodies']
                   for k in ('x_m','y_m','z_m','vx_ms','vy_ms','vz_ms','mass_kg'))
        locations = {(b['x_m'],b['y_m'],b['z_m']) for b in s['bodies']}
        assert len(locations) == count + 2
        assert math.hypot(*s['momentum_kg_ms']) / s['total_mass_kg'] < 1e-8
    assert CloudWorld(8).checkpoint()['scenario_version'] == 2


def test_eight_cloud_bodies_conserve_over_364_days():
    world = CloudWorld(8)
    initial = world.state()
    def angular(s):
        return math.fsum(b['mass_kg']*(b['x_m']*b['vy_ms']-b['y_m']*b['vx_ms']) for b in s['bodies'])
    for _ in range(13):
        world.step(28*DAY)
    final = world.state()
    assert math.isfinite(final['gravitational_energy_j'])
    assert abs(final['energy_relative_drift']) < 1e-8
    assert abs(angular(final)-angular(initial))/abs(angular(initial)) < 1e-8
    assert math.hypot(*final['momentum_kg_ms'])/final['total_mass_kg'] < 1e-8
    assert final['total_mass_kg'] == initial['total_mass_kg']
    print(f'eight-cloud 364-day energy drift={final["energy_relative_drift"]:.3e}')


def test_legacy_checkpoint_keeps_its_original_coordinates():
    original = CloudWorld(3)
    original.step(DAY)
    legacy = original.checkpoint()
    legacy.pop('scenario_version')
    restored = CloudWorld(8)
    restored.restore(legacy)
    assert restored.checkpoint()['scenario_version'] == 1
    assert restored.state() == original.state()


def test_explorer_rate_steps_match_direct_backend_and_reset():
    # All UI rate values use the existing bounded step contract. Presentation
    # must not introduce a second propagator or alter the reset fixture.
    for seconds in (3600, DAY, 7*DAY):
        world = CloudWorld(8)
        initial = world.state()
        direct = CloudWorld(8)
        direct.sim.integrate(seconds, exact_finish_time=1)
        stepped = world.step(seconds)
        assert stepped == direct.state()
        assert abs(stepped['energy_relative_drift']) < 1e-8
        assert math.hypot(*stepped['momentum_kg_ms'])/stepped['total_mass_kg'] < 1e-8
        assert world.reset(8) == initial


def test_workshop_geometry_and_mass_are_deterministic_and_recoverable():
    args = dict(cloud_count=12, cloud_mass_kg=1e12, inner_au=1.5, outer_au=3.5, inclination_deg=40)
    world = CloudWorld(0)
    initial = world.reset(**args)
    assert initial == CloudWorld(0).reset(**args)
    sun = initial['bodies'][0]
    for body in initial['bodies'][2:]:
        assert body['mass_kg'] == 1e12
        assert 1.5 < math.dist([body[k] for k in ('x_m','y_m','z_m')],
                              [sun[k] for k in ('x_m','y_m','z_m')]) / AU < 3.5
    assert any(abs(b['z_m']) > .01*AU for b in initial['bodies'][2:])
    world.add_incoming(40, .7, 30, mass_kg=1e15, azimuth_deg=20, elevation_deg=25)
    for _ in range(4):
        world.step(20*DAY)
    restored = CloudWorld(0)
    restored.restore(world.checkpoint())
    assert restored.state() == world.state()
    assert restored.state()['scenario'] == args
    assert len(restored.state()['boundary_events']) == 1
    assert abs(world.state()['energy_relative_drift']) < 1e-8


def test_external_insertion_ledger_closes_mass_energy_and_vector_momentum():
    world = CloudWorld(0)
    before = world.state()
    after = world.add_incoming(40, .7, 32, mass_kg=1e24, azimuth_deg=23, elevation_deg=17)
    event = after['boundary_events'][0]
    body = after['bodies'][-1]
    assert math.isclose(after['total_mass_kg']-before['total_mass_kg'], event['mass_kg'], rel_tol=1e-9)
    assert math.isclose(after['gravitational_energy_j']-before['gravitational_energy_j'], event['energy_j'], rel_tol=1e-10)
    for i in range(3):
        assert math.isclose(after['momentum_kg_ms'][i]-before['momentum_kg_ms'][i], event['momentum_kg_ms'][i], rel_tol=1e-12)
        assert math.isclose(after['angular_momentum_kg_m2_s'][i]-before['angular_momentum_kg_m2_s'][i], event['angular_momentum_kg_m2_s'][i], rel_tol=1e-12)
    assert math.isclose(math.hypot(body['vx_ms'],body['vy_ms'],body['vz_ms']),40000,rel_tol=1e-14)
    assert after['reference_time_s'] == 0
    journal = world.checkpoint()['boundary_events']
    world.step(15*DAY)
    assert world.checkpoint()['boundary_events'] == journal
    final = world.state()
    assert abs(final['energy_relative_drift']) < 1e-8
    for key in ('momentum_kg_ms', 'angular_momentum_kg_m2_s'):
        assert math.dist(final[key],after[key]) / math.hypot(*after[key]) < 1e-10


def test_osculating_observables_use_sun_relative_state_not_role():
    for speed, bound in [(10, True), (40, False)]:
        w = CloudWorld(0)
        s = w.add_incoming(speed, .5, 20, elevation_deg=15)
        o = s['orbits'][-1]
        b, sun = s['bodies'][-1], s['bodies'][0]
        r = math.dist([b[k] for k in ('x_m','y_m','z_m')], [sun[k] for k in ('x_m','y_m','z_m')])
        v = math.dist([b[k] for k in ('vx_ms','vy_ms','vz_ms')], [sun[k] for k in ('vx_ms','vy_ms','vz_ms')])
        expected = v*v/2-w.sim.G*(SUN_KG+b['mass_kg'])/r
        assert math.isclose(o['specific_energy_j_kg'], expected, rel_tol=1e-14)
        assert (o['specific_energy_j_kg'] < 0) is bound
        assert (o['eccentricity'] < 1) is bound
        assert o['periapsis_au'] > 0
        assert o['radial_kms'] < 0


def test_atomic_replay_and_invalid_scenarios_preserve_sessions():
    from fastapi.testclient import TestClient
    from server import app
    a,b = TestClient(app),TestClient(app)
    untouched = b.get('/api/state').json()
    payload = {'scenario': {'cloud_count':8,'inclination_deg':35,'cloud_mass_kg':100},
               'launch': {'speed_kms':40,'impact_au':.5,'elevation_deg':20,'mass_kg':1e9}}
    first = a.post('/api/replay',json=payload)
    assert first.status_code == 200
    initial = first.json()
    a.post('/api/step',json={'seconds':DAY})
    again = a.post('/api/replay',json=payload).json()
    assert again['bodies'] == initial['bodies']
    assert again['boundary_events'] == initial['boundary_events']
    assert again['time_s'] == 0
    assert b.get('/api/state').json() == untouched
    for endpoint, invalid in [('/api/reset',{'inner_au':3,'outer_au':2}),
                              ('/api/launch',{'speed_kms':301}),
                              ('/api/launch',{'mass_kg':-1}),
                              ('/api/launch',{'elevation_deg':90}),
                              ('/api/replay',{'scenario':{'cloud_count':200},'launch':{}})]:
        assert a.post(endpoint,json=invalid).status_code in (409,422)
        assert a.get('/api/state').json()['bodies'] == initial['bodies']
    # Identical insertion at the same time is refused, not a singularity/500.
    assert a.post('/api/launch',json=payload['launch']).status_code == 422


def test_old_physical_checkpoints_without_workshop_metadata_still_load():
    world = CloudWorld(3)
    old = world.checkpoint()
    for key in ('scenario','boundary_events','reference_time_s'):
        old.pop(key)
    restored = CloudWorld(0)
    restored.restore(old)
    assert restored.state()['bodies'] == world.state()['bodies']
    assert restored.state()['scenario'] is None
    assert restored.state()['boundary_events'] == []
