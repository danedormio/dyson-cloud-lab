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
