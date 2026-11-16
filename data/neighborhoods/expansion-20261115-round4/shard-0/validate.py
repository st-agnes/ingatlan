#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess,sys
from shapely.geometry import shape
P=Path(__file__).resolve().parent
def hashes():return {str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [P/'features.geojson',*sorted((P/'batches').glob('*/features.geojson'))]}
before=hashes();subprocess.run([sys.executable,str(P/'build.py')],check=True);after=hashes();assert before==after,'Output drift'
fs=json.load(open(P/'features.geojson'))['features'];tasks=json.load(open(P/'assignment.json'))['municipalities'];assigned={(c['municipality'],t['name']) for c in tasks for t in c['targets']};collected={(f['properties']['municipality'],f['properties']['name']) for f in fs};unresolved={(x['municipality'],x['name']) for x in json.load(open(P/'unresolved-decisions.json'))}
assert len(fs)==63 and len(assigned)==65 and collected|unresolved==assigned and not collected&unresolved
for f in fs:
 g=shape(f['geometry']);q=f['properties'];assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']
 assert q['estimated'] and q['lowConfidence'] and q['sourceUrl'] and q['approximationNote'] and q['sourceObjectIds']
for i,f in enumerate(fs):
 for other in fs[i+1:]:
  if f['properties']['municipality']==other['properties']['municipality']:assert not shape(f['geometry']).equals(shape(other['geometry']))
subprocess.run([sys.executable,str(P/'update-reports.py')],check=True)
v=json.load(open(P/'validation.json'));v['deterministicRebuild']=True;v['frozenOutputSha256']=after;v['all65AssignedNamesAccountedFor']=True;v['unresolvedFallbacksRetained']=2
(P/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print('PASS: 63 valid distinct source-based estimates, all 65 attempted/accounted for, deterministic frozen batches')
