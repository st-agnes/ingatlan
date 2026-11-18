#!/usr/bin/env python3
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
files=['gyongyos-features.geojson','satoralja-features.geojson'];features=[]
for fn in files:
 if (H/fn).exists():features+=json.loads((H/fn).read_text())['features']
assert len({(f['properties']['municipality'],f['properties']['name'])for f in features})==len(features)
munis={f['properties']['name']:shape(f['geometry'])for f in json.loads(gzip.open(H/'source-municipalities.geojson.gz','rt').read())['features']};points={(f['properties']['municipality'],f['properties']['name']):f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']};t=Transformer.from_crs(4326,23700,always_xy=True);rows=[]
for f in features:
 p=f['properties'];g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.area>0 and g.geom_type in ['Polygon','MultiPolygon']
 assert p['estimated']is True and p['confidence']=='low'and p['sourceUrl']and p['approximationNote']
 ratio=g.intersection(munis[p['municipality']]).area/g.area;assert ratio>.99
 known=points.get((p['municipality'],p['name']));hit=g.covers(Point(known['geometry']['coordinates']))if known else None
 rows.append({'municipality':p['municipality'],'name':p['name'],'areaKm2':round(transform(t.transform,g).area/1e6,6),'fractionWithinMunicipality':round(ratio,7),'knownNamePointInside':hit,'geometryValid':True})
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
wanted=json.loads((H/'target-names.json').read_text());keys={(p['municipality'],p['name'])for p in [f['properties']for f in features]};remaining=[{'municipality':r['municipality'],'name':r['name']}for r in wanted if r['municipality']!='Kalocsa'and(r['municipality'],r['name'])not in keys]
summary={'featureCount':len(features),'byMunicipality':{c:sum(f['properties']['municipality']==c for f in features)for c in ['Gyöngyös','Sátoraljaújhely']},'allValidWgs84':True,'allEstimatedLowConfidence':True,'pointRadiusOrCircleCount':0,'independentAccuracyEstablished':False,'completeCityCoverageEstablished':False,'importOnly':'features.geojson','names':[{'municipality':f['properties']['municipality'],'name':f['properties']['name']}for f in features]}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(H/'validation.json').write_text(json.dumps({'allValid':True,'features':rows,'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n');(H/'unresolved.json').write_text(json.dumps({'remainingTargetNames':remaining,'independentModernAccuracyEstablished':False,'wholeQuarterExtentsAreEstimates':True,'completeCityCoverageEstablished':False},ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
