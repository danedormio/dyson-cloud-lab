"""Native validation of the exact C source distributed to the browser worker."""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tarfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
AU=149597870700.
REF=1e12*45000**2

@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    build=tmp_path_factory.mktemp('native-engine')
    subprocess.run([str(ROOT/'engine/build_native.sh'),str(build)],check=True,capture_output=True)
    lib=C.CDLL(str(build/'cloud.so'))
    lib.cloud_reset.argtypes=[C.c_int,C.c_double,C.c_double,C.c_int]
    lib.cloud_launch.argtypes=[C.c_double]*5
    lib.cloud_advance.argtypes=[C.c_double,C.c_double];lib.cloud_advance.restype=C.c_double
    lib.cloud_resolution.argtypes=[C.c_double]
    lib.cloud_output.restype=C.POINTER(C.c_double);lib.cloud_snapshot.restype=C.POINTER(C.c_double)
    lib.cloud_test_exchange.argtypes=[C.c_int,C.c_int,C.c_double,C.c_double,C.c_int]
    return lib

def state(e):
    return list(e.cloud_output()[:e.cloud_state()])

def reset(e,n=900,exact=0,factor=1):
    e.cloud_exact(exact);e.cloud_resolution(factor);assert e.cloud_reset(n,1,30,122333)

def bodies(a):
    return [a[20+i*12:32+i*12] for i in range(int(a[19]))]

def snapshot(e):
    n=e.cloud_save();return list(e.cloud_snapshot()[:n])

def restore(e,a):
    for i,v in enumerate(a):e.cloud_snapshot()[i]=v
    return e.cloud_restore(len(a))

def test_inventory_backreaction_and_massive_resolved_population(engine):
    reset(engine);a=state(engine);b=bodies(a)
    assert len(b)==901 and a[1]==900
    assert math.isclose(sum(x[6] for x in b[1:]),9e20,rel_tol=1e-14)
    assert all(x[6]==1e18 for x in b[1:])
    assert 1<=min(math.dist(x[:3],b[0][:3]) for x in b[1:])<1.1
    assert 29.9<max(math.dist(x[:3],b[0][:3]) for x in b[1:])<=30
    # A COM-frame star moves; no pinned-star or visual-only cloud substitutions.
    assert math.dist(b[0][3:6],[0,0,0])>0
    assert len({round(x[2],3) for x in b[1:]})>800
    reset(engine,240);c=state(engine)
    assert math.isclose(c[12]*240,a[12]*900) and c[18]==a[18]

def test_full_gravity_against_ias15_and_long_coast(engine):
    results=[]
    for exact in [0,1]:
        reset(engine,24,exact);assert engine.cloud_advance(3652.5,1e8)==pytest.approx(3652.5)
        results.append(state(engine))
    assert max(math.dist(x[:3],y[:3]) for x,y in zip(*map(bodies,results)))<1e-8
    for exact in [0,1]:
        reset(engine,900,exact);engine.cloud_advance(8,1e8)
        results.append(state(engine))
    assert max(math.dist(x[:3],y[:3]) for x,y in zip(*map(bodies,results[2:])))<1e-9
    reset(engine);engine.cloud_advance(3652.5,1e8);a=state(engine)
    assert not a[4] and abs(a[11])<1e-4
    # Normalize residual P/L against orbital inventory, not near-zero COM totals.
    assert a[15]<9e20*30000*1e-10
    assert a[16]<9e20*30000*30*AU*1e-10

def test_multiple_insertion_boundary_and_roundtrip(engine):
    reset(engine);engine.cloud_advance(100,1e8);before=state(engine)
    for i in range(3):assert engine.cloud_launch(45,5,0,0,0)==i+1
    a=state(engine);assert a[0]==before[0] and a[2]==3
    assert all(math.isfinite(v) for v in a)
    assert abs(a[11]-before[11])<1e-7 and a[17]>0
    assert math.dist(bodies(a)[901][:3],bodies(a)[902][:3])==pytest.approx(.02)
    saved=snapshot(engine);engine.cloud_advance(2,1e8)
    assert restore(engine,saved);assert state(engine)==a
    # No destructive partial restore on malformed/truncated external snapshots.
    for bad in [saved[:-1],saved[:24],saved[:100],saved[:]]:
        if len(bad)==len(saved):bad[-1]=10000
        assert not restore(engine,bad)
        assert state(engine)==a

def test_central_reaction_impulse_conserves_reservoirs_and_momenta(engine):
    reset(engine,1);engine.cloud_launch(45,5,0,0,0);a=snapshot(engine)
    node=24+7;cargo=24+14
    # Controlled reachable pair, radial relative motion. Physical test fixture.
    for k in range(3):a[cargo+1+k]=a[node+1+k]+(1e9 if k==0 else 0)
    for k in range(3):a[cargo+4+k]=a[node+4+k]+(1000 if k==0 else 0)
    assert restore(engine,a);before=state(engine)
    assert engine.cloud_test_exchange(2,1,-1e15,1e5,0)
    after=state(engine);b0=bodies(before);b1=bodies(after)
    impulse=[(b1[2][k+3]-b0[2][k+3])*b0[2][6] for k in range(3)]
    reaction=[(b1[1][k+3]-b0[1][k+3])*b0[1][6] for k in range(3)]
    assert math.dist(impulse,[-1e15,0,0])<1
    assert math.dist(impulse,[-v for v in reaction])<1e9
    kinetic=sum(.5*x[6]*sum(v*v for v in x[3:6]) for x in b1)-sum(.5*x[6]*sum(v*v for v in x[3:6]) for x in b0)
    reservoirs=(after[7]-before[7])+(after[8]-before[8])
    assert abs(kinetic+reservoirs)<2e13
    assert after[7]>before[7] and after[8]>before[8]
    # Central direction has zero pair torque, and budgets reject excess work.
    r=[(b0[2][k]-b0[1][k])*AU for k in range(3)]
    assert r[1]==r[2]==0
    assert not engine.cloud_test_exchange(2,1,1e40,1e-20,0)

def test_capture_is_conditional_convergent_and_passive_comparison(engine):
    results=[]
    for factor in [1,.5,.25]:
        reset(engine,factor=factor);engine.cloud_launch(45,5,0,0,0)
        engine.cloud_advance(1380,1e8);a=state(engine);results.append(a)
        assert not a[4] and abs(a[11])<1e-4 and a[-7]<0
        assert a[8]>0 and a[10]>0
        for body in bodies(a)[1:901]:assert 0<=body[7]<=1 and 0<=body[8]<=.25
    coarse,half,fine=[a[-11:] for a in results]
    assert abs(half[4]-fine[4])<abs(coarse[4]-half[4])
    assert abs(coarse[7]-fine[7])/fine[7]<.1  # coarse apoapsis error disclosed
    assert abs(half[7]-fine[7])/fine[7]<.01
    reset(engine);engine.cloud_coordination(0);engine.cloud_launch(45,5,0,0,0);engine.cloud_advance(1380,1e8);a=state(engine)
    assert a[-7]>0 and a[8]==a[9]==a[10]==0
    reset(engine);engine.cloud_launch(3000,5,0,0,0);a=state(engine)
    assert a[-10]==3
    engine.cloud_advance(100,1e8);a=state(engine)
    assert not a[4] and a[9]==a[10]==0

def test_distributed_runtime_matches_source_and_native(engine):
    with tarfile.open(ROOT/'static/engine/corresponding-source.tar.gz') as source:
        for p in (ROOT/'engine').rglob('*'):
            if p.is_file():assert source.extractfile(str(p.relative_to(ROOT))).read()==p.read_bytes()
    manifest=json.loads((ROOT/'static/engine/manifest.json').read_text())
    assert hashlib.sha256((ROOT/'static/engine'/manifest['runtime']).read_bytes()).hexdigest()==manifest['sha256']
    script='''const fs=require('fs'),m=JSON.parse(fs.readFileSync('static/engine/manifest.json'));require('./static/engine/'+m.runtime)().then(e=>{e._cloud_reset(900,1,30,122333);e._cloud_launch(45,5,0,0,0);e._cloud_launch(45,5,0,0,0);e._cloud_advance(10,1e8);let n=e._cloud_state(),a=Array.from(e.HEAPF64.slice(e._cloud_output()/8,e._cloud_output()/8+n));let saved=e._cloud_save();if(!e._cloud_restore(saved))throw Error('restore');console.log(JSON.stringify(a));});'''
    wasm=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT))
    reset(engine);engine.cloud_launch(45,5,0,0,0);engine.cloud_launch(45,5,0,0,0);engine.cloud_advance(10,1e8);native=state(engine)
    assert len(wasm)==len(native) and not wasm[4]
    assert max(math.dist(x[:3],y[:3]) for x,y in zip(bodies(wasm),bodies(native)))<1e-10
    assert abs(wasm[11]-native[11])<1e-6
