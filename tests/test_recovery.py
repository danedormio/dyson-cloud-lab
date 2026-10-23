"""Recovery after total host storage loss, with provenance and ownership checks."""
import copy
import math
import secrets
import sqlite3

from fastapi.testclient import TestClient
import pytest

from physics import AU, CloudWorld, DAY
from server import create_app
from sessions import SessionStore


def client(path, key, **kw):
    return TestClient(create_app(SessionStore(path, recovery_key=key, **kw)))


def bootstrap(c, proof):
    response = c.post('/api/session', json={'recovery_token':proof})
    assert response.status_code == 200
    assert response.json()['recovery']
    return response.json()


def recover(c, saved, proof):
    return c.post('/api/recover', json={'credential':proof, 'capsule':saved['recovery']})


def physical(state):
    return {k:v for k,v in state.items() if k != 'recovery'}


def test_two_owners_recover_from_completely_new_database(tmp_path):
    key = secrets.token_hex(32)
    a, b = client(tmp_path/'old.sqlite3', key), client(tmp_path/'old.sqlite3', key)
    pa, pb = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    bootstrap(a, pa)
    bootstrap(b, pb)
    a.post('/api/reset', json={'cloud_count':8})
    a.post('/api/launch', json={})
    sa = a.post('/api/step', json={'seconds':2*DAY}).json()
    sb = b.post('/api/step', json={'seconds':DAY}).json()
    fresh = tmp_path/'empty-after-redeploy.sqlite3'
    ra, rb = client(fresh, key), client(fresh, key)
    assert recover(ra, sa, pb).status_code == 403
    assert recover(rb, sb, pa).status_code == 403
    assert physical(recover(ra, sa, pa).json()) == physical(sa)
    assert physical(recover(rb, sb, pb).json()) == physical(sb)
    assert ra.cookies != rb.cookies
    ra.post('/api/reset', json={})
    assert physical(rb.get('/api/state').json()) == physical(sb)


def test_recovery_uses_latest_live_world_and_never_overwrites_other_owner(tmp_path):
    key = secrets.token_hex(32)
    a, b = client(tmp_path/'live.sqlite3', key), client(tmp_path/'live.sqlite3', key)
    pa, pb = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    older = bootstrap(a, pa)
    bootstrap(b, pb)
    latest = a.post('/api/step', json={'seconds':DAY}).json()
    untouched_b = b.get('/api/state').json()
    # Deliberate private-backup import switches caller ownership, not B's world.
    importer = client(tmp_path/'live.sqlite3', key)
    importer.cookies.update(b.cookies)
    assert physical(recover(importer, older, pa).json()) == physical(latest)
    assert b.get('/api/state').json() == untouched_b
    with sqlite3.connect(tmp_path/'live.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 2


def test_backup_tampering_key_loss_and_expiry_fail_closed(tmp_path):
    key = secrets.token_hex(32)
    proof = secrets.token_urlsafe(32)
    source = client(tmp_path/'source.sqlite3', key, clock=lambda:1000)
    saved = bootstrap(source, proof)
    target = client(tmp_path/'target.sqlite3', key, clock=lambda:1001)
    corrupt = copy.deepcopy(saved)
    corrupt['recovery']['checkpoint']['bodies'][0]['mass_kg'] = 1
    assert recover(target, corrupt, proof).status_code == 403
    assert recover(client(tmp_path/'wrong.sqlite3', secrets.token_hex(32)), saved, proof).status_code == 403
    assert recover(client(tmp_path/'disabled.sqlite3', ''), saved, proof).status_code == 503
    assert recover(client(tmp_path/'expired.sqlite3', key, clock=lambda:1000+366*DAY), saved, proof).status_code == 410
    with sqlite3.connect(tmp_path/'target.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0
    with pytest.raises(ValueError, match='32-byte hex'):
        SessionStore(tmp_path/'bad-key.sqlite3', recovery_key='invalid-test-config')


def test_missing_cookie_cannot_silently_replace_a_browser_backup(tmp_path):
    key = secrets.token_hex(32)
    c = client(tmp_path/'new.sqlite3', key)
    r = c.post('/api/session', json={'recovery_token':secrets.token_urlsafe(32), 'has_backup':True})
    assert r.status_code == 401
    with sqlite3.connect(tmp_path/'new.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0


def test_recovery_capacity_body_bounds_and_quotas(tmp_path):
    key = secrets.token_hex(32)
    pa, pb = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    source = client(tmp_path/'source.sqlite3', key)
    saved = bootstrap(source, pa)
    capped = client(tmp_path/'capped.sqlite3', key, max_sessions=1)
    bootstrap(capped, pb)
    assert recover(capped, saved, pa).status_code == 429
    limited = client(tmp_path/'limited.sqlite3', key, max_requests_per_minute=2)
    bootstrap(limited, pa)
    assert recover(limited, saved, pa).status_code == 200
    assert recover(limited, saved, pa).status_code == 429
    # Only server-issued bounded worlds may be submitted, not unsigned bodies.
    assert limited.post('/api/recover', json={'credential':pa,'capsule':{'checkpoint':{'bodies':[{}]*203}}}).status_code == 403


def test_migrate_existing_database_without_losing_world(tmp_path):
    path = tmp_path/'legacy.sqlite3'
    token, key = secrets.token_urlsafe(32), secrets.token_hex(32)
    import hashlib
    from sessions import encode
    world = CloudWorld(3)
    world.step(DAY)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY, signing_key TEXT NOT NULL, checkpoint TEXT NOT NULL, expires REAL NOT NULL)')
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), secrets.token_hex(32), encode(world.checkpoint()), 1e12))
    c = client(path, key)
    c.cookies.set('dyson_session', token)
    result = bootstrap(c, secrets.token_urlsafe(32))
    assert physical(result) == world.state()


def test_numerical_continuation_after_actual_storage_loss(tmp_path):
    key, proof = secrets.token_hex(32), secrets.token_urlsafe(32)
    c = client(tmp_path/'original.sqlite3', key)
    bootstrap(c, proof)
    c.post('/api/reset', json={'cloud_count':8})
    saved = c.post('/api/step', json={'seconds':28*DAY}).json()
    reference = CloudWorld(0)
    reference.restore(saved['recovery']['checkpoint'])
    for i in range(12):
        reference.step(28*DAY)
        c = client(tmp_path/f'redeploy-{i}.sqlite3', key)
        assert recover(c, saved, proof).status_code == 200
        saved = c.post('/api/step', json={'seconds':28*DAY}).json()
    actual, expected = saved, reference.state()
    position = max(math.dist([p[k] for k in ('x_m','y_m','z_m')], [q[k] for k in ('x_m','y_m','z_m')])/AU
                   for p,q in zip(actual['bodies'], expected['bodies']))
    velocity = max(math.dist([p[k] for k in ('vx_ms','vy_ms','vz_ms')], [q[k] for k in ('vx_ms','vy_ms','vz_ms')])
                   for p,q in zip(actual['bodies'], expected['bodies']))
    assert actual['time_s'] == expected['time_s'] == 364*DAY
    assert actual['total_mass_kg'] == expected['total_mass_kg']
    assert position < 1e-8
    assert velocity < 1e-4
    assert abs(actual['energy_relative_drift']) < 1e-8
    assert math.hypot(*actual['momentum_kg_ms'])/actual['total_mass_kg'] < 1e-8
    print(f'12 full storage-loss recoveries: position={position:.3e} AU velocity={velocity:.3e} m/s energy={actual["energy_relative_drift"]:.3e}')


def test_parallel_worker_schema_migration_is_atomic(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    key = secrets.token_hex(32)
    path = tmp_path/'parallel-start.sqlite3'
    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(lambda _: SessionStore(path, recovery_key=key), range(4)))
    with stores[0].connect() as db:
        columns = {row[1] for row in db.execute('PRAGMA table_info(sessions)')}
        assert {'recovery_owner','saved_at','revision'} <= columns
