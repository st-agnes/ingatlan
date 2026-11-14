#!/usr/bin/env python3
from pathlib import Path
import json,gzip,hashlib,unicodedata
from collections import Counter
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];to=Transformer.from_crs(4326,23700,always_xy=True).transform
paths=['feszek-features.geojson','rural-features.geojson','kincsestelep-features.geojson'];features=[]
for p in paths:features+=json.loads((HERE/p).read_text())['features']
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold()if c.isalnum());keys=[(f['properties']['municipality'],norm(f['properties']['name']))for f in features];assert len(keys)==len(set(keys))
for f in features:
 g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'];assert not f['properties'].get('pointRadiusFallback')
output=HERE/'features.geojson';output.write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
unresolved=[{'municipality':'Gyula','name':'Egykori Ella-major','reason':'Current point is in a45.1km² farmland source surface; no mapped building or compact built-up footprint occurs in the nearby source context. The historical major extent is not inferred from that entire field polygon.'},{'municipality':'Gyula','name':'Sitka','reason':'Point is beside a23.7km² unnamed forest and several meadow/scrub surfaces. Their boundaries do not distinguish the Sitka place from the broader forest; no tiny arbitrary track block is substituted.'},{'municipality':'Hódmezővásárhely','name':'Tegehalom tanya','reason':'Point lies in a1,059.8km² CLC farmland source object; no compact mapped buildings or settlement footprint occur within the nearby source context. This packet does not infer a farmstead from that broad field extent.'}]
(HERE/'unresolved.json').write_text(json.dumps({'places':unresolved,'meaning':'Unresolved in this local source-context packet, not a claim that no map/text source exists elsewhere.'},ensure_ascii=False,indent=2)+'\n')
sourcecounts={}
for name in ['source-areas.geojson.gz','source-roads.geojson.gz','source-buildings.geojson.gz','source-name-points.geojson']:
 raw=(HERE/name).read_bytes();d=json.loads(gzip.decompress(raw)if name.endswith('.gz')else raw);sourcecounts[name]={'featureCount':len(d['features']),'sha256':hashlib.sha256(raw).hexdigest()}
summary={'status':'final_frozen','featureCount':len(features),'municipalities':dict(Counter(f['properties']['municipality']for f in features)),'methods':dict(Counter(f['properties']['method']for f in features)),'radiusFallbackCount':0,'validPolygonCount':len(features),'uniqueMunicipalityNameCount':len(keys),'unresolvedCount':len(unresolved),'aliasReferenceCorrections':['Kecskemét:Űrhegy→Úrihegy','Kecskemét:Repülőtér→Kecskeméti Katonai Repülőtér'],'sourceContext':sourcecounts,'derivedFrom':paths,'outputSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'names':[{'municipality':f['properties']['municipality'],'name':f['properties']['name'],'areaSquareMetres':round(transform(to,shape(f['geometry'])).area,1)}for f in features]}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(HERE/'checkpoint.json').write_text(json.dumps({'status':'final_frozen','persistedFeatures':len(features),'outputSha256':summary['outputSha256']},indent=2)+'\n')
parents={f['properties']['name']:shape(f['geometry'])for f in json.loads((HERE/'source-municipalities.geojson').read_text())['features']};validation={'featureCount':len(features),'allPolygonsValid':True,'uniqueMunicipalityNamePairs':True,'circleCount':0,'sourceSurfacePointOutsideIsNotBuffered':True,'parentMunicipalityDiagnostics':[]}
for f in features:
 city=f['properties']['municipality']
 if city not in parents:continue
 g=transform(to,shape(f['geometry']));parent=transform(to,parents[city]);outside=g.difference(parent).area;validation['parentMunicipalityDiagnostics'].append({'municipality':city,'name':f['properties']['name'],'outsideMunicipalityAreaSquareMetres':round(outside,2)})
(HERE/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
