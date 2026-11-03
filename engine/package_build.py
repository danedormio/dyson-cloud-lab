"""Content-address the executable and ship its complete corresponding source."""
from pathlib import Path
import hashlib,json,tarfile
root=Path(__file__).resolve().parents[1]
out=root/'static/engine'
runtime=out/'cloud-engine.js'
sha=hashlib.sha256(runtime.read_bytes()).hexdigest()
name=f'cloud-engine-{sha[:16]}.js'
runtime.rename(out/name)
with tarfile.open(out/'corresponding-source.tar.gz','w:gz') as archive:
    for path in sorted((root/'engine').rglob('*')):
        if path.is_file():archive.add(path,arcname=str(path.relative_to(root)))
(out/'manifest.json').write_text(json.dumps({'runtime':name,'sha256':sha,'upstream':'REBOUND 4.6.0','license':'GPL-3.0-or-later','source':'corresponding-source.tar.gz','snapshot_format':24001})+'\n')
print(json.dumps({'runtime':name,'bytes':(out/name).stat().st_size,'sha256':sha}))
