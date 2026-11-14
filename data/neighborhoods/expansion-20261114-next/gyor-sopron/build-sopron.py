#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,mapping,shape
from shapely.validation import make_valid
from shapely.ops import transform

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
src=ROOT/'data/neighborhoods/sources/municipal-sopron-next'
spec=json.loads((HERE/'sopron-manual-traces.json').read_text())
beta=np.array(json.loads((src/'registration.json').read_text())['page1PdfPointsToEovMatrix'])
url=json.loads((src/'source-extraction-proof.json').read_text())['originalUrl']
to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
points={f['properties']['name']:f for f in json.loads((HERE/'name-points.geojson').read_text())['features'] if f['properties']['municipality']=='Sopron'}
features=[];checks=[]
for area in spec['areas']:
 native=np.array(area['ring']);eov=np.c_[native,np.ones(len(native))]@beta;g=transform(to_wgs,Polygon(eov))
 if not g.is_valid:g=make_valid(g)
 assert g.is_valid and not g.is_empty
 point=points[area['name']];assert g.covers(shape(point['geometry'])),area['name']
 p={'municipality':'Sopron','name':area['name'],'method':'manual_cad_street_context_estimate','estimated':True,'boundaryKind':'neighbourhood','qualityScore':25,
  'source':{'provider':'manual-map-context-inference','url':url,'path':str((src/'source-pages1-2.pdf').relative_to(ROOT)),'sha256':hashlib.sha256((src/'source-pages1-2.pdf').read_bytes()).hexdigest(),'page':1},
  'sourceUrl':url,'approximationNote':spec['note'],'absoluteAccuracyEstablished':False,
  'namePoint':{'coordinates':point['geometry']['coordinates'],'sourceUrl':point['properties']['source']['url']}}
 features.append({'type':'Feature','id':'sopron-context:'+area['name'],'properties':p,'geometry':mapping(g)});checks.append({'name':area['name'],'valid':True,'ownPointInside':True})
(HERE/'sopron-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'sopron-summary.json').write_text(json.dumps({'featureCount':len(features),'checks':checks,'circleCount':0,'printedFineBordersClaimed':False},ensure_ascii=False,indent=2)+'\n')
print('Sopron manual CAD-context estimates:',len(features))
