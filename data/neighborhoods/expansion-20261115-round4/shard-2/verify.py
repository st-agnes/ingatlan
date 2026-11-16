#!/usr/bin/env python3
"""Offline integrity/reproducibility verification; not an accuracy assessment."""
from pathlib import Path
import json,hashlib,subprocess,sys
from shapely.geometry import shape,Point
H=Path(__file__).resolve().parent;R=next(p for p in H.parents if (p/'AGENTS.md').exists())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(H/'features.geojson');subprocess.run([sys.executable,str(H/'build.py')],check=True);assert before==sha(H/'features.geojson'),'non-deterministic rebuild'
fc=json.loads((H/'features.geojson').read_text());T=json.loads((H/'task-selection.json').read_text());expected={(m['municipality'],t['name']) for m in T['municipalities'] for t in m['targets']};actual={};points=0
for f in fc['features']:
 p=f['properties'];key=(p['municipality'],p['name']);assert key not in actual;actual[key]=f;g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type=='Polygon';assert p['estimated'] and p['lowConfidence'];assert len(p['boundaryAnchors'])>=3;assert p['sourceUrl'].startswith('http');assert p['method']=='manual_road_map_text_estimate'
 assert not p['partialSourceFootprint'];assert g.bounds[0]>16 and g.bounds[2]<23 and g.bounds[1]>45 and g.bounds[3]<49
 for q in p['namePoints']:assert q['insideEstimatedPolygon'] and g.covers(Point(q['coordinates'])),key;points+=1
 for path,digest in p['sourceContextSha256'].items():assert sha(R/path)==digest,(key,path)
assert set(actual)==expected,(expected-set(actual),set(actual)-expected)
batchkeys=set();batchcounts=[]
for batch in sorted((H/'batches').glob('batch-*')):
 p=batch/'features.geojson';s=json.loads((batch/'summary.json').read_text());assert sha(p)==s['sha256'],batch
 rows=json.loads(p.read_text())['features'];assert len(rows)==s['featureCount']
 for f in rows:
  key=(f['properties']['municipality'],f['properties']['name']);assert key not in batchkeys;batchkeys.add(key);assert f==actual[key],(batch,key)
 batchcounts.append({'batch':batch.name,'featureCount':len(rows),'sha256':s['sha256']})
assert batchkeys==expected
report={'status':'passed','targetCount':len(expected),'featureCount':len(actual),'municipalityCount':len({m for m,n in actual}),'identificationPointCount':points,'allGeometriesValid':True,'allIdentificationPointsInside':True,'allSourceHashesMatch':True,'offlineRebuildByteIdentical':True,'frozenBatchesMatchAggregate':True,'estimatedCount':len(actual),'nativeQuarterPolygonCount':0,'circleCount':0,'pointGeneratedBoxCount':0,'voronoiCount':0,'automaticRoadHullCount':0,'featuresSha256':sha(H/'features.geojson'),'batches':batchcounts,'completeCityCoverageEstablished':False,'nationalCoverageEstablished':False,'absoluteAccuracyEstablished':False}
(H/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
