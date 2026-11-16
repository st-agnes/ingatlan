#!/usr/bin/env python3
"""Offline manual/source polygon assembly; no point-only geometry generation."""
from pathlib import Path
import json,hashlib,math,gzip
from shapely.geometry import Polygon,shape,mapping,Point
H=Path(__file__).resolve().parent;R=next(x for x in H.parents if (x/'AGENTS.md').exists())
task=json.loads((H/'task-selection.json').read_text());targets={(m['municipality'],t['name']):t for m in task['municipalities'] for t in m['targets']};fs=[];checks=[]
for fn in sorted((H/'specs').glob('*.json')):
 for a in json.loads(fn.read_text()).get('areas',[]):
  key=(a['municipality'],a['name']);assert key in targets,key
  g=Polygon(a['ring']);assert g.is_valid and not g.is_empty and g.geom_type=='Polygon',key
  area=g.area*111320**2*math.cos(math.radians(g.centroid.y));assert 1000<area<30000000,(key,area)
  inputs={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in a['contextPaths']};np=targets[key]['pointCandidates'];inside=[g.covers(Point(p['coordinates'])) for p in np]
  pr={'name':a['name'],'municipality':a['municipality'],'method':'manual_road_map_text_estimate','estimated':True,'lowConfidence':True,'qualityScore':20,'geometryScope':'whole_locality_estimate','partialSourceFootprint':False,'sourceUrl':a['urls'][0],'source':{'provider':'preserved-actual-source-geometry-and-public-text','url':a['urls'][0]},'supportingUrls':list(dict.fromkeys(a['urls']+[p['sourceUrl'] for p in np])),'approximationNote':'Rough search-area estimate using preserved actual roads, parcels/surfaces and cited locality evidence. Not an official or surveyed boundary. '+a['note'],'boundaryAnchors':a['anchors'],'sourceInputPaths':a['contextPaths'],'sourceContextSha256':inputs,'namePoints':[dict(p,insideEstimatedPolygon=v) for p,v in zip(np,inside)],'areaSquareMetres':round(area,1),'absoluteAccuracyEstablished':False,'fullConventionalExtentEstablished':False}
  fs.append({'type':'Feature','id':'round4-shard2:'+key[0]+':'+key[1],'properties':pr,'geometry':mapping(g)});checks.append({'municipality':key[0],'name':key[1],'valid':True,'pointsInside':inside,'areaSquareMetres':round(area,1)})
keys={(f['properties']['municipality'],f['properties']['name']) for f in fs};assert len(keys)==len(fs)
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n')
remaining=[{'municipality':m,'name':n} for m,n in targets if (m,n) not in keys]
(H/'summary.json').write_text(json.dumps({'date':'2026-11-15','baselineCommit':task['baselineCommit'],'targetCount':len(targets),'featureCount':len(fs),'estimatedFeatureCount':len(fs),'remainingNames':remaining,'circleCount':0,'voronoiCount':0,'completeCityCoverageEstablished':False,'checks':checks},ensure_ascii=False,indent=2)+'\n')
print('Built',len(fs),'polygons;',len(remaining),'names remain')
