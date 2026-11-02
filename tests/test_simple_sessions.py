"""First Light identity is independent of legacy workbench state and credentials."""
from fastapi.testclient import TestClient
from server import create_app
from sessions import SessionStore


def test_simple_identity_and_forget_preserve_legacy_world(tmp_path):
    client=TestClient(create_app(SessionStore(tmp_path/'identity.sqlite3')))
    old=client.get('/api/state').json();legacy_cookie=client.cookies.get('dyson_session')
    simple=client.post('/api/simple/session',json={}).json()
    assert simple['version']=='minimal-cloud-v1.1'
    assert client.cookies.get('dyson_simple_session')!=legacy_cookie
    client.post('/api/simple/launch',json={})
    assert client.get('/api/state').json()['bodies']==old['bodies']
    assert client.cookies.get('dyson_session')==legacy_cookie
    assert client.request('DELETE','/api/simple/session',json={}).status_code==200
    assert client.cookies.get('dyson_session')==legacy_cookie
    assert client.cookies.get('dyson_simple_session') is None
    assert client.get('/api/state').json()['bodies']==old['bodies']


def test_simple_recovery_retains_owner_verification(tmp_path):
    app=create_app(SessionStore(tmp_path/'proof.sqlite3',recovery_key='a'*64))
    a,b=TestClient(app),TestClient(app)
    first=a.post('/api/simple/session',json={'recovery_token':'C'*43}).json()
    second=b.post('/api/simple/session',json={'recovery_token':'D'*43}).json()
    denied=b.post('/api/simple/recover',json={'credential':'D'*43,'capsule':first['recovery']})
    assert denied.status_code==403
    assert b.get('/api/simple').json()['bodies']==second['bodies']
