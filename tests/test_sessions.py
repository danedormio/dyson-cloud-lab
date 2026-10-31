"""Ownership, durable transactions, abuse bounds and numerical restart contract."""
from concurrent.futures import ThreadPoolExecutor
import math

from fastapi.testclient import TestClient
import pytest

from physics import CloudWorld, AU, DAY
from server import create_app
from sessions import COOKIE_NAME, MAX_CHECKPOINT_BYTES, SessionStore


def test_session_fixture_restores_store_between_overrides_and_after_error(tmp_path):
    from conftest import isolated_sessions
    from server import app

    original_state = app.state
    original_store = app.state.sessions
    original_client = TestClient(app)
    expected = original_client.get('/api/state').json()
    stores = [SessionStore(tmp_path / f'isolated-{i}.sqlite3') for i in range(2)]
    for store in stores:
        with isolated_sessions(app, store):
            assert app.state is original_state
            assert app.state.sessions is store
            client = TestClient(app)
            assert client.post('/api/reset', json={'cloud_count': 0}).status_code == 200
            assert client.post('/api/step', json={'seconds': DAY}).status_code == 200
            assert client.get('/api/state').json()['time_s'] == DAY
        assert app.state.sessions is original_store
        assert original_client.get('/api/state').json() == expected

    with pytest.raises(RuntimeError, match='simulated test failure'):
        with isolated_sessions(app, stores[0]):
            raise RuntimeError('simulated test failure')
    assert app.state is original_state
    assert app.state.sessions is original_store
    assert original_client.get('/api/state').json() == expected


def test_session_fixture_rejects_missing_application_initialization(tmp_path):
    from conftest import isolated_sessions
    from server import create_app

    app = create_app(SessionStore(tmp_path / 'initialized.sqlite3'))
    del app.state.sessions  # Deliberately broken initialization must not be repaired by the fixture.
    with pytest.raises(AttributeError, match='sessions'):
        with isolated_sessions(app, SessionStore(tmp_path / 'replacement.sqlite3')):
            pytest.fail('fixture concealed missing application session state')
    assert not hasattr(app.state, 'sessions')


def client_pair(tmp_path, **kw):
    store = SessionStore(tmp_path / "worlds.sqlite3", **kw)
    app = create_app(store)
    return store, TestClient(app), TestClient(app)


def test_isolation_every_endpoint_and_restart(tmp_path):
    store, a, b = client_pair(tmp_path)
    for c in (a, b):
        assert c.post('/api/session', json={}).status_code == 200
    assert a.cookies.get(COOKIE_NAME) != b.cookies.get(COOKIE_NAME)
    original_b = b.get('/api/state').json()
    a.post('/api/reset', json={'cloud_count': 1})
    a.post('/api/launch', json={'impact_au': -1})
    a.post('/api/step', json={'seconds': DAY})
    saved_a = a.get('/api/checkpoint').json()
    assert b.post('/api/restore', json=saved_a).status_code == 403
    assert b.get('/api/state').json() == original_b
    a.post('/api/reset', json={'cloud_count': 0})
    assert a.post('/api/restore', json=saved_a).status_code == 200
    expected_a = a.get('/api/state').json()
    # New app and registry, not just a cleared Python dictionary.
    restarted = create_app(SessionStore(store.path))
    recovered_a, recovered_b = TestClient(restarted), TestClient(restarted)
    recovered_a.cookies.update(a.cookies)
    recovered_b.cookies.update(b.cookies)
    assert recovered_a.get('/api/state').json() == expected_a
    assert recovered_b.get('/api/state').json() == original_b
    b.post('/api/reset', json={'cloud_count': 3})
    saved_b = b.get('/api/checkpoint').json()
    b.post('/api/step', json={'seconds': DAY})
    assert b.post('/api/restore', json=saved_b).status_code == 200
    assert recovered_a.get('/api/state').json() == expected_a


@pytest.mark.parametrize('token', ['malformed', 'x'*43, 'x'*10000], ids=['malformed','unknown','oversized'])
def test_forged_cookie_never_creates_or_recovers(tmp_path, token):
    store, a, forged = client_pair(tmp_path)
    expected = a.get('/api/state').json()
    forged.cookies.set(COOKIE_NAME, token)
    for method, path, payload in [('get', '/api/state', None), ('get','/api/checkpoint',None),
                                  ('post','/api/session',{}), ('post','/api/step',{}),
                                  ('post','/api/reset',{}), ('post','/api/launch',{}),
                                  ('post','/api/restore',{})]:
        r = getattr(forged, method)(path, **({'json':payload} if payload is not None else {}))
        assert r.status_code == 401
    assert a.get('/api/state').json() == expected
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 1


def test_checkpoint_tampering_limits_and_atomicity(tmp_path):
    _, a, _ = client_pair(tmp_path)
    a.post('/api/reset', json={'cloud_count':0})
    expected = a.get('/api/state').json()
    exported = a.get('/api/checkpoint').json()
    for change in ({'owner': 'forged'}, {'time_s': 123}, {'signature': 'forged'}, {'signature': '☀'},
                   {'bodies': []}, {'expires_at': 1}):
        assert a.post('/api/restore', json={**exported, **change}).status_code == 403
    assert a.post('/api/restore', json={}).status_code == 403
    assert a.post('/api/reset', json={'cloud_count':201}).status_code == 422
    assert a.post('/api/restore', content=b'x'*(MAX_CHECKPOINT_BYTES+1),
                  headers={'content-type':'application/json'}).status_code == 413
    # No content-length header / chunked requests must enforce the same bound.
    assert a.post('/api/restore', content=iter([b'x'*65536]*5),
                  headers={'content-type':'application/json'}).status_code == 413
    assert a.get('/api/state').json() == expected
    a.post('/api/reset', json={'cloud_count':199})
    assert a.post('/api/launch', json={}).status_code == 200
    full = a.get('/api/state').json()
    assert len(full['bodies']) == 202
    assert a.post('/api/launch', json={}).status_code == 409
    assert a.get('/api/state').json() == full


def test_session_capacity_expiry_and_expired_checkpoint(tmp_path):
    now = [1000.0]
    store, a, b = client_pair(tmp_path, max_sessions=1, ttl_seconds=10, clock=lambda: now[0])
    assert a.get('/api/state').status_code == 200
    cp = a.get('/api/checkpoint').json()
    assert b.get('/api/state').status_code == 429
    now[0] += 9
    a.get('/api/state') # refresh session but not the exported checkpoint
    now[0] += 2
    assert a.post('/api/restore', json=cp).status_code == 410
    now[0] += 10
    assert a.get('/api/state').status_code == 401
    assert b.get('/api/state').status_code == 200
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 1


def test_cookie_security_csrf_and_private_responses(tmp_path):
    _, a, b = client_pair(tmp_path)
    response = a.get('/api/state')
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
    assert response.headers['cache-control'] == 'no-store'
    expected = a.get('/api/state').json()
    assert a.post('/api/reset', json={}, headers={'Origin':'https://evil.example'}).status_code == 403
    assert a.post('/api/step', json={}, headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
    assert a.post('/api/reset', content='{}', headers={'content-type':'text/plain'}).status_code == 415
    assert a.get('/api/state').json() == expected
    secure = TestClient(a.app, base_url='https://testserver')
    assert 'Secure' in secure.get('/api/state').headers['set-cookie']


def test_cross_worker_serialization_no_lost_updates(tmp_path):
    store, a, _ = client_pair(tmp_path)
    a.post('/api/reset', json={'cloud_count':0})
    token = a.cookies.get(COOKIE_NAME)
    def step_once(_):
        worker = TestClient(create_app(SessionStore(store.path)))
        worker.cookies.set(COOKIE_NAME, token)
        return worker.post('/api/step', json={'seconds':3600}).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(step_once, range(8))) == [200]*8
    assert a.get('/api/state').json()['time_s'] == 8*3600


def test_restart_continuation_conservation_over_earth_orbit(tmp_path):
    store, a, _ = client_pair(tmp_path)
    a.post('/api/reset', json={'cloud_count':3})
    a.post('/api/step', json={'seconds':28*DAY})
    saved = a.get('/api/checkpoint').json()
    reference = CloudWorld(0)
    reference.restore(saved)
    # Continuous reference has no intermediate state-only restarts.
    for _ in range(12):
        reference.step(28*DAY)
    for _ in range(12):
        worker = TestClient(create_app(SessionStore(store.path)))
        worker.cookies.update(a.cookies)
        assert worker.post('/api/step', json={'seconds':28*DAY}).status_code == 200
    actual = a.get('/api/state').json()
    expected = reference.state()
    assert actual['time_s'] == expected['time_s'] == 364*DAY
    assert actual['total_mass_kg'] == expected['total_mass_kg']
    def angular(state):
        axes = (('y_m','vz_ms','z_m','vy_ms'), ('z_m','vx_ms','x_m','vz_ms'), ('x_m','vy_ms','y_m','vx_ms'))
        return [math.fsum(p['mass_kg']*(p[x]*p[vy]-p[y]*p[vx]) for p in state['bodies'])
                for x,vy,y,vx in axes]
    initial_l, final_l = angular(saved), angular(actual)
    angular_drift = math.dist(initial_l, final_l) / math.hypot(*initial_l)
    assert angular_drift < 1e-8
    assert abs(actual['energy_relative_drift']) < 1e-8
    assert math.hypot(*actual['momentum_kg_ms']) / actual['total_mass_kg'] < 1e-8
    max_position_error = max(math.dist([p[k] for k in ('x_m','y_m','z_m')],
                                     [q[k] for k in ('x_m','y_m','z_m')]) / AU
                             for p,q in zip(actual['bodies'], expected['bodies']))
    max_velocity_error = max(math.dist([p[k] for k in ('vx_ms','vy_ms','vz_ms')],
                                     [q[k] for k in ('vx_ms','vy_ms','vz_ms')])
                             for p,q in zip(actual['bodies'], expected['bodies']))
    assert max_position_error < 1e-8
    assert max_velocity_error < 1e-4
    print(f'364-day restarted/reference: position={max_position_error:.3e} AU, velocity={max_velocity_error:.3e} m/s, energy drift={actual["energy_relative_drift"]:.3e}, angular drift={angular_drift:.3e}')
    # Save/restore must retain the original diagnostic baseline rather than zeroing drift.
    assert a.get('/api/checkpoint').json()['initial_energy_j'] == saved['initial_energy_j']


def test_nonfinite_malformed_and_deep_json_fail_safely(tmp_path):
    _, a, _ = client_pair(tmp_path)
    expected = a.get('/api/state').json()
    for raw in ('{"seconds":NaN}', '{"seconds":Infinity}', '{', '['*2000+'0'+']'*2000):
        assert a.post('/api/step', content=raw, headers={'content-type':'application/json'}).status_code == 422
    # This parses as JSON but can exceed the canonicalizer's recursion budget.
    nested = '{"signature":"' + '0'*64 + '","nested":' + '['*800 + '0' + ']'*800 + '}'
    assert a.post('/api/restore', content=nested, headers={'content-type':'application/json'}).status_code in (403, 422)
    assert a.get('/api/state').json() == expected


def test_request_rate_limit_survives_process_recreation(tmp_path):
    now = [1000.0]
    store, a, _ = client_pair(tmp_path, clock=lambda: now[0], max_requests_per_minute=2)
    assert a.get('/api/state').status_code == 200
    assert a.post('/api/step', json={}).status_code == 200
    worker = TestClient(create_app(SessionStore(store.path, clock=lambda: now[0], max_requests_per_minute=2)))
    worker.cookies.update(a.cookies)
    assert worker.post('/api/step', json={}).status_code == 429
    now[0] += 61
    assert worker.get('/api/state').json()['time_s'] == 3600


def test_failed_storage_commit_never_acknowledges_mutation(tmp_path):
    store, a, _ = client_pair(tmp_path)
    expected = a.get('/api/state').json()
    with store.connect() as db:
        db.execute("CREATE TRIGGER deny_save BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END")
    assert a.post('/api/step', json={}).status_code == 503
    with store.connect() as db:
        db.execute('DROP TRIGGER deny_save')
    assert a.get('/api/state').json() == expected


def test_unavailable_database_connection_is_retryable(tmp_path, monkeypatch):
    import sqlite3
    store, a, _ = client_pair(tmp_path)
    expected = a.get('/api/state').json()
    def unavailable():
        raise sqlite3.OperationalError('simulated unavailable mount')
    with monkeypatch.context() as patch:
        patch.setattr(store, 'connect', unavailable)
        assert a.post('/api/step', json={}).status_code == 503
        assert a.get('/health').status_code == 503
    assert a.get('/api/state').json() == expected


def test_eight_cloud_reset_and_integration_are_valid(tmp_path):
    _, a, _ = client_pair(tmp_path)
    result = a.post('/api/reset', json={'cloud_count':8})
    assert result.status_code == 200
    assert len(result.json()['bodies']) == 10
    stepped = a.post('/api/step', json={'seconds':86400})
    assert stepped.status_code == 200
    assert math.isfinite(stepped.json()['gravitational_energy_j'])
    assert abs(stepped.json()['energy_relative_drift']) < 1e-8
