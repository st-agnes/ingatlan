#!/usr/bin/env python3
"""Reproduce explicitly rough named areas from the saved OSM road-map traces."""
from pathlib import Path
import json,hashlib
from pyproj import Transformer
from shapely.geometry import Polygon,mapping
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=json.loads((HERE/'kapos-traces.json').read_text());reg=json.loads((HERE/'kapos-map-registration.json').read_text())
world=Transformer.from_crs(23700,4326,always_xy=True)
def geographic(x,y,z=None):return world.transform(reg['eovOrigin'][0]+x/reg['scalePixelsPerMetre'],reg['eovOrigin'][1]+(reg['imageHeight']-y)/reg['scalePixelsPerMetre'])
points={r['name']:r for r in reg['labelPoints']};features=[]
for row in spec['areas']:
 geom=Polygon(row['points']);repair=not geom.is_valid
 if repair:geom=make_valid(geom)
 geom=transform(geographic,geom)
 assert geom.is_valid and not geom.is_empty
 label=points[row['name']]['sourcePoint']
 p={'municipality':'Kaposvár','name':row['name'],'method':'map_road_grid_inferred_area','estimated':True,'qualityScore':20,'candidateBoundaryKind':'neighbourhood','sourceUrl':spec['sourceUrl'],'sourcePages':spec['sourcePages'],'source':{'provider':'municipal-description-and-osm-map-inference','url':spec['sourceUrl'],'paths':['data/neighborhoods/sources/municipal-kaposvar-next/all-local-roads-rails.geojson','data/neighborhoods/sources/municipal-kaposvar-donner-next/literal-roads-waterways.geojson','data/neighborhoods/sources/municipal-west/kaposvar-boundary-definitions.json']},'nameEvidence':label,'approximationNote':spec['note'],'absoluteAccuracyMetres':None,'topologyRepairApplied':repair}
 features.append({'type':'Feature','id':'next-kapos:'+row['name'],'properties':p,'geometry':mapping(geom)})
(HERE/'kaposvar-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'kaposvar-summary.json').write_text(json.dumps({'featureCount':len(features),'municipality':'Kaposvár','radiusFallbackCount':0,'sourceBasedOn':'Actual retained roads/rails/waterlines plus saved OSM quarter labels and municipal FVS constituent descriptions.','fineBoundaryStatus':'Manual approximate partitions, not quoted official fine boundaries.','registration':'Direct EOV map of literal OSM source coordinates; trace interpretation accuracy unknown.','allStructurallyValid':True,'inputsSha256':{p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['kapos-traces.json','kapos-map-registration.json']}},ensure_ascii=False,indent=2)+'\n')
print(len(features),'Kaposvár areas')
