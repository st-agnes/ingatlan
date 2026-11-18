#!/usr/bin/env python3
"""Combine the three nonduplicated source-based Makó packets offline."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
inputs=['municipal/features.geojson','historic-features.geojson','road-cell-features.geojson']
features=[]
for fn in inputs:
 for f in json.loads((H/fn).read_text())['features']:
  if fn.startswith('municipal/'):
   for key in ['sourceImage','sourcePixelTraceFile','registrationFile']:
    if key in f['properties']:f['properties'][key]=str(((H/fn).parent/f['properties'][key]).resolve().relative_to(H.resolve()))
  features.append(f)
keys=[(f['properties']['municipality'],f['properties']['name'])for f in features];assert len(keys)==len(set(keys))==34
points={f['properties']['name']:f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']};assert set(points)=={n for c,n in keys}
muni=shape(json.loads(gzip.open(H/'source-municipality.geojson.gz','rt').read())['features'][0]['geometry']);eov=Transformer.from_crs(4326,23700,always_xy=True);validation=[]
for f in features:
 p=f['properties'];g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']and g.area>0
 assert p['estimated']is True and p['sourceUrl'].startswith('https://')and p['approximationNote']and p['method']
 assert 20.3<g.bounds[0]<g.bounds[2]<20.7 and 46.1<g.bounds[1]<g.bounds[3]<46.4
 inside=g.intersection(muni).area/g.area;assert inside>.95
 knownInside=g.covers(Point(points[p['name']]['geometry']['coordinates']))
 if p['method']!='historical_source_map_enclosure_estimate':assert knownInside,p['name']
 validation.append({'name':p['name'],'method':p['method'],'areaKm2':round(transform(eov.transform,g).area/1e6,6),'fractionWithinMunicipality':round(inside,6),'knownModernNamePointInside':knownInside,'geometryValid':True})
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':len(features),'municipality':'Makó','municipalSourceOutlines':8,'historicalSourceFootprints':17,'actualRoadCircuitFragments':9,'estimatedCount':34,'allValidWgs84':True,'circleOrPointRectangleCount':0,'independentModernAccuracyEstablished':False,'completeCityCoverageEstablished':False,'knownModernNamePointsInside':sum(r['knownModernNamePointInside']for r in validation),'names':[f['properties']['name']for f in features],'inputFiles':inputs,'importOnly':'features.geojson'}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(H/'validation.json').write_text(json.dumps({'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest(),'allValid':True,'historicalPointExclusionsAreReportedNotHidden':True,'features':validation},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
