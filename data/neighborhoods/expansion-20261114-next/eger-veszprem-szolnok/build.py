#!/usr/bin/env python3
"""Convert explicitly rough road/grid-guided fine area traces, without circles."""
from pathlib import Path
import argparse,json,hashlib
from pyproj import Transformer
from shapely.geometry import Polygon,mapping,Point
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--city',choices=['eger','veszprem','szolnok','all'],default='all');args=parser.parse_args()
prefixes=['eger','veszprem','szolnok'] if args.city=='all' else [args.city]
for prefix in prefixes:
 trace=HERE/(prefix+'-traces.json')
 if not trace.exists():continue
 spec=json.loads(trace.read_text());reg=json.loads((HERE/(prefix+'-registration.json')).read_text());world=Transformer.from_crs(23700,4326,always_xy=True)
 def geo(x,y,z=None):return world.transform(reg['eovOrigin'][0]+x/reg['scalePixelsPerMetre'],reg['eovOrigin'][1]+(reg['height']-y)/reg['scalePixelsPerMetre'])
 labels={r['name']:r['sourcePoint'] for r in reg['labels']};features=[]
 for area in spec['areas']:
  g=Polygon(area['points']);repaired=not g.is_valid
  if repaired:g=make_valid(g)
  g=transform(geo,g);assert g.is_valid and not g.is_empty
  label=labels[area['name']];assert g.covers(Point(label['coordinates'])),area['name']
  p={'name':area['name'],'municipality':spec['city'],'method':'map_road_grid_inferred_area','estimated':True,'qualityScore':20,'candidateBoundaryKind':'neighbourhood','sourceUrl':spec['sourceUrl'],'source':{'provider':'retained-road-map-and-municipal-source-inference','url':spec['sourceUrl'],'path':str((HERE/(prefix+'-roads.geojson')).relative_to(HERE.parents[3])),'sha256':hashlib.sha256((HERE/(prefix+'-roads.geojson')).read_bytes()).hexdigest()},'nameEvidence':label,'boundaryRationale':area['boundaryRationale'],'approximationNote':spec['sourceContext']+' Named place locations and visible street/parcel/canal corridors guide approximate links. This is not an exact, official or printed fine boundary.','absoluteAccuracyMetres':None,'topologyRepairApplied':repaired}
  features.append({'type':'Feature','id':'next-'+prefix+':'+area['name'],'properties':p,'geometry':mapping(g)})
 (HERE/(prefix+'-features.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/(prefix+'-summary.json')).write_text(json.dumps({'municipality':spec['city'],'featureCount':len(features),'radiusFallbackCount':0,'allStructurallyValid':True,'savedLabelPointInsideCount':len(features),'pointContainmentNotIndependentBoundaryAccuracy':True,'method':'manual fine partitions inferred from retained physical map and broader historical source context'},ensure_ascii=False,indent=2)+'\n')
 print(spec['city'],len(features),'valid rough estimates')
