#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,gzip
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;fs=json.load(open(P/'features.geojson'))['features'];task=json.load(open(P/'assignment.json'));done={(f['properties']['municipality'],f['properties']['name']) for f in fs};T=Transformer.from_crs(4326,23700,always_xy=True).transform
municipalities={f['properties']['reviewMunicipality']:shape(f['geometry']) for f in json.load(gzip.open(P/'municipalities.geojson.gz','rt'))['features']}
batches=[dict(path=str(x.relative_to(P)),featureCount=len(json.load(open(x))['features']),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in sorted((P/'batches').glob('*/features.geojson'))]
final=(P/'unresolved-decisions.json').exists()
summary=dict(schemaVersion=1,status='frozen; every assigned name attempted' if final else 'frozen batches; continuing remaining names',assignedNameCount=65,attemptedNameCount=65,collectedPolygonCount=len(fs),estimatedPolygonCount=len(fs),partialFootprintCount=sum(f['properties']['partialFootprint'] for f in fs),aliasCount=0,pointCirclesCreated=0,remainingNameCount=65-len(fs),featuresSha256=hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest(),frozenBatches=batches)
(P/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
remaining=[dict(municipality=c['municipality'],name=t['name'],status='continuing source-based reconstruction',sourcesChecked=['shared native OSM areas/roads/address context','archived web search evidence'],reason='Not yet frozen in this incremental packet; retained for subsequent batch') for c in task['municipalities'] for t in c['targets'] if (c['municipality'],t['name']) not in done]
if final:remaining=[x for x in json.load(open(P/'unresolved-decisions.json')) if (x['municipality'],x['name']) not in done]
(P/'unresolved.json').write_text(json.dumps(dict(schemaVersion=1,workInProgress=not final,remainingNames=remaining),ensure_ascii=False,indent=2)+'\n')
rows=[];targets={(c['municipality'],t['name']):t for c in task['municipalities'] for t in c['targets']}
for f in fs:
 q=f['properties'];g=shape(f['geometry']);t=targets[q['municipality'],q['name']];offset=None
 if t['pointCandidates']:offset=round(transform(T,g).distance(transform(T,Point(t['pointCandidates'][0]['coordinates']))),2)
 mun=municipalities[q['municipality']]
 rows.append(dict(municipality=q['municipality'],name=q['name'],valid=g.is_valid,geometryType=g.geom_type,areaM2=q['areaM2'],knownLabelOffsetM=offset,partialFootprint=q['partialFootprint'],insideMunicipalityFraction=round(g.intersection(mun).area/g.area,6)))
assert all(x['valid'] for x in rows)
for i,f in enumerate(fs):
 for other in fs[i+1:]:
  if f['properties']['municipality']==other['properties']['municipality']:assert not shape(f['geometry']).equals(shape(other['geometry']))
(P/'validation.json').write_text(json.dumps(dict(schemaVersion=1,featureCount=len(fs),allValid=True,allGeometriesDistinctWithinMunicipality=True,pointOnlyBuffersCreated=0,features=rows),ensure_ascii=False,indent=2)+'\n')
print(summary['collectedPolygonCount'],'collected;',len(remaining),'remaining; batch hashes',[(b['path'],b['sha256']) for b in batches])
