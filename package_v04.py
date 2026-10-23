"""Package source and owned evidence; exclude caches, runtime state and secrets."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
OUT=Path('/mnt/data') if Path('/mnt/data').is_dir() else ROOT/'deliverables'
OUT.mkdir(exist_ok=True)
status=json.loads((ROOT/'DELIVERY_STATUS.json').read_text())
assert status['version']=='0.4.0'
assert status['tests']['failed']==0 and status['tests']['errors']==0 and status['ui']['failed']==0
excluded_dirs={'.git','.venv','__pycache__','.pytest_cache','runtime','deliverables','sessions'}
excluded_suffixes=('.pyc','.db','.db-wal','.db-shm','.sqlite','.sqlite3','.session.enc','.auth.json','.session.json','.key','.vault')
files=[]
for path in sorted(ROOT.rglob('*')):
    if not path.is_file() or path.is_symlink():continue
    rel=path.relative_to(ROOT)
    if any(part in excluded_dirs for part in rel.parts) or path.name.startswith('.env') or path.name.endswith(excluded_suffixes):continue
    if path.name=='FILE_MANIFEST.json':continue
    files.append((path,rel))
manifest={'version':'0.4.0','scope':'Source and owned-fixture evidence; no runtime database, credentials or session state',
          'files':[{'path':str(rel).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha256(path.read_bytes()).hexdigest()} for path,rel in files]}
manifest_path=ROOT/'FILE_MANIFEST.json'
manifest_path.write_text(json.dumps(manifest,indent=2))
archive=OUT/'HandNavigate_v0.4_Source.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for path,rel in files+[(manifest_path,Path('FILE_MANIFEST.json'))]:
        z.write(path,'handnavigate-lab/'+str(rel).replace('\\','/'))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for entry in manifest['files']:
        assert sha256(z.read('handnavigate-lab/'+entry['path'])).hexdigest()==entry['sha256'],entry['path']
checksum=sha256(archive.read_bytes()).hexdigest()
(OUT/'HandNavigate_v0.4_Source.zip.sha256').write_text(checksum+'  '+archive.name+'\n')
print(json.dumps({'archive':str(archive),'files':len(files)+1,'bytes':archive.stat().st_size,'sha256':checksum,'verified':'ZIP CRC and every manifest hash'},indent=2))
