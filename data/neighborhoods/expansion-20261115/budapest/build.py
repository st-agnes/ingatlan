#!/usr/bin/env python3
"""Deterministic offline build of manually traced, explicitly estimated bounds."""
from pathlib import Path
import hashlib,json,math
from shapely.geometry import Polygon,shape,mapping
HERE=Path(__file__).resolve().parent
spec=json.loads((HERE/'manual-traces.json').read_text())
points={f['properties']['name']:f for f in json.loads((HERE/'name-points.geojson').read_text())['features']}
pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*-source-roads.geojson.gz'))}
features=[];checks=[]
for a in spec['areas']:
 g=Polygon(a['ring']);p=points[a['name']];inside=g.covers(shape(p['geometry']))
 assert g.is_valid and not g.is_empty,(a['name'],g.is_valid)
 assert g.geom_type=='Polygon',a['name']
 area=g.area*111320**2*math.cos(math.radians(g.centroid.y))
 assert 1000<area<10000000,(a['name'],area)
 url=a['urls'][0]
 props={'name':a['name'],'municipality':'Budapest','method':'manual_street_map_text_estimate','estimated':True,'lowConfidence':True,'qualityScore':20,'sourceUrl':url,'source':{'provider':'archived-street-map-and-public-text','url':url},'supportingUrls':list(dict.fromkeys(a['urls']+[p['properties']['source']['url']])),'approximationNote':spec['note']+' '+a['note'],'boundaryAnchors':a['anchors'],'contextImage':a['contextImage'],'sourceContextSha256':pins,'namePoint':{'coordinates':p['geometry']['coordinates'],'sourceUrl':p['properties']['source']['url'],'insideEstimatedPolygon':inside},'absoluteAccuracyEstablished':False,'areaSquareMetres':round(area,1)}
 features.append({'type':'Feature','id':'budapest-20261115:'+a['name'],'properties':props,'geometry':mapping(g)})
 checks.append({'name':a['name'],'valid':g.is_valid,'pointInside':inside,'areaSquareMetres':round(area,1)})
out={'type':'FeatureCollection','features':features}
(HERE/'features.geojson').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
missing=[n for n in points if n not in {f['properties']['name'] for f in features}]
(HERE/'summary.json').write_text(json.dumps({'date':'2026-11-15','municipality':'Budapest','featureCount':len(features),'estimatedFeatureCount':len(features),'machineSourcePolygonCount':0,'circleCount':0,'voronoiCount':0,'startingMissingNames':len(points),'remainingNames':missing,'pointOutsideNames':[c['name'] for c in checks if not c['pointInside']],'checks':checks},ensure_ascii=False,indent=2)+'\n')
print('Built',len(features),'estimated polygons;',len(missing),'names remain')
