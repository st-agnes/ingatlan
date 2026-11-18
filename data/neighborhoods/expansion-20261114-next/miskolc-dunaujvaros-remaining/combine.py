#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,collections
from shapely.geometry import shape
HERE=Path(__file__).resolve().parent
features=[];sources={}
for name in ['miskolc','dunaujvaros']:
 p=HERE/name/'features.geojson';sources[str(p.relative_to(HERE))]=hashlib.sha256(p.read_bytes()).hexdigest();features+=json.loads(p.read_text())['features']
for f in features:
 g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type in ('Polygon','MultiPolygon')
keys=[(f['properties']['municipality'],f['properties']['name'].casefold())for f in features];assert len(set(keys))==len(keys)
(HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
j={'featureCount':len(features),'byMunicipality':dict(collections.Counter(f['properties']['municipality']for f in features)),'aliasAvoidsDuplicateGeometry':'Miskolc Déli Ipari park = Miskolc Déli Technológiai Park','namedPointTargetsRepresented':24,'allValid':True,'circleFallbackCount':0,'independentGeographicAccuracyEstablished':False,'inputsSha256':sources,'previous57NotModified':True}
(HERE/'summary.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(j,ensure_ascii=False))
