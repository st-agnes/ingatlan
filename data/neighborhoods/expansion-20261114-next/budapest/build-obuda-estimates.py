#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
from shapely.geometry import Polygon,Point,mapping,shape
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent
spec=json.loads((HERE/'obuda-manual-traces.json').read_text())
reg=json.loads((HERE/'obuda-street-context-registration.json').read_text())
width,height=reg['imageSize'];west,south,east,north=reg['wgs84Bounds']
nodes={f['properties']['name']:f for f in json.loads((HERE/'name-point-input.geojson').read_text())['features']}
source='obuda-ivs-2009.pdf';source_sha=hashlib.sha256((HERE/source).read_bytes()).hexdigest()
url='https://obvsz.obuda.hu/wp-content/uploads/2010/10/obuda_ivs_helyzetfeltaras_20090323.pdf'
features=[];checks=[]
for area in spec['areas']:
 coords=[(west+x/width*(east-west),north-y/height*(north-south)) for x,y in area['points']]
 geom=Polygon(coords)
 repaired=not geom.is_valid
 if repaired:geom=make_valid(geom)
 assert geom.is_valid and not geom.is_empty
 point=nodes.get(area['name']);contains=geom.covers(shape(point['geometry'])) if point else None
 assert contains is not False,area['name']
 p={'name':area['name'],'municipality':'Budapest','aliases':area.get('aliases',[]),
    'method':'manual_street_map_text_estimate','estimated':True,'boundaryKind':'neighbourhood','qualityScore':25,
    'source':{'provider':'manual-map-and-text-inference','url':url,'path':str((HERE/source).relative_to(HERE.parents[3])),'sha256':source_sha,'pages':area['pages'],
      'roadGeometryPath':str((HERE/'obuda-source-roads.geojson').relative_to(HERE.parents[3])),'license':'Municipal text/source reuse terms retained; source OSM map © OpenStreetMap contributors, ODbL-1.0'},
    'sourceUrl':url,'evidenceUrls':[url]+area.get('evidenceUrls',[]),'sourcePeriod':'Municipal context 2009; street geometry OSM snapshot 2026-11-12',
    'approximationNote':spec['note'],'absoluteAccuracyEstablished':False,
    'namePoint':{'sourceUrl':point['properties']['source']['url'],'coordinates':point['geometry']['coordinates']} if point else None,
    'topologyRepairApplied':repaired}
 features.append({'type':'Feature','id':'obuda-rough:'+area['name'],'geometry':mapping(geom),'properties':p})
 checks.append({'name':area['name'],'valid':True,'ownNamePointInside':contains,'topologyRepair':repaired})
(HERE/'additional-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'additional-summary.json').write_text(json.dumps({'featureCount':len(features),'method':spec['note'],'circleCount':0,'checks':checks},ensure_ascii=False,indent=2)+'\n')
print('Additional source-context/road-map estimates:',len(features))
