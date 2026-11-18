from pathlib import Path
import json,hashlib,shutil
P=Path(__file__).resolve().parent;R=P.parent/'contexts';S=json.load(open(P/'selection.json'));records=[]
for key in sorted({s['contextKey'] for s in S}):
 d=P/'source-inputs'/key;d.mkdir(parents=True,exist_ok=True)
 for n in ['roads.geojson.gz','areas.geojson.gz','municipality.geojson','labels.geojson']:
  src=R/key/n;dest=d/n
  if not dest.exists():shutil.copyfile(src,dest)
  assert dest.read_bytes()==src.read_bytes()
  records.append({'path':str(dest.relative_to(P)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'origin':str(src.relative_to(P.parent.parent.parent.parent))})
(P/'provenance.json').write_text(json.dumps({'provider':'OpenStreetMap','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','osmTimestamp':'2026-11-12T21:23:05Z','files':records},ensure_ascii=False,indent=2)+'\n')
