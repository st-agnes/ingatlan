#!/usr/bin/env python3
"""Check the produced packet, not merely mirrored trace coordinates."""
import json,gzip,hashlib
from pathlib import Path
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
fs=json.loads((H/'features.geojson').read_text())['features'];assert len(fs)==20
requested={'Ózd':{'Bánszállás','Bíben-völgy','Center','Csűr','Gubonna puszta','Hársas alja','Kerekhegy','Meggyes','Ráctag','Újváros'},'Szekszárd':{'Bakta','Bottyánhegy','Csatár','Csörge-tó','Felsőváros','Iparterület','Palánkihegy','Parászta','Szőlőhegy','Városközpont'}}
assert len({(f['properties']['municipality'],f['properties']['name'])for f in fs})==20
munis={c:shape(json.loads((H/f'{stem}-source-municipality.geojson').read_text())['features'][0]['geometry'])for c,stem in [('Ózd','ozd'),('Szekszárd','szekszard')]}
points={c:{f['properties']['name']:f for f in json.loads((H/f'{stem}-source-points.geojson').read_text())['features']if f['properties'].get('municipality')==c}for c,stem in [('Ózd','ozd'),('Szekszárd','szekszard')]}
eov=Transformer.from_crs(4326,23700,always_xy=True);rows=[]
for c,names in requested.items():assert {f['properties']['name']for f in fs if f['properties']['municipality']==c}==names
for f in fs:
 p=f['properties'];g=shape(f['geometry']);c=p['municipality'];n=p['name']
 assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']and g.area>0
 assert p['estimated']is True and p['confidence']=='low'and p['sourceUrl'].startswith('https://')and p['method']and p['approximationNote']
 assert 16<g.bounds[0]<g.bounds[2]<23 and 45<g.bounds[1]<g.bounds[3]<49
 known=points[c].get(n);inside=g.intersection(munis[c]).area/g.area
 if known:assert g.covers(Point(known['geometry']['coordinates'])),n
 assert inside>.95,(n,inside)
 rows.append({'municipality':c,'name':n,'areaKm2':round(transform(eov.transform,g).area/1e6,5),'fractionInsideMunicipality':round(inside,5),'knownNamePointInside':True if known else None,'geometryValid':True})
proof={'featureCount':20,'validWgs84Count':20,'knownNamePointsCovered':sum(r['knownNamePointInside']is True for r in rows),'allGeometriesAtLeast95PercentInsideMunicipality':True,'notAnAccuracyCertification':True,'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest(),'features':rows}
(H/'validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in proof.items()if k!='features'},ensure_ascii=False))
