#!/usr/bin/env python3
"""Inspect real footprint/cell alternatives for every point target, without output selection."""
from pathlib import Path
import gzip,json,time
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;R=P.parent/'contexts';FW=Transformer.from_crs(4326,23700,always_xy=True).transform;IV=Transformer.from_crs(23700,4326,always_xy=True).transform
T=json.loads((P/'targets.json').read_text());choices=[];reports=[]
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
for city in T['municipalities']:
 name=city['municipality'];ctx=R/city['contextKey'];report={'municipality':name,'targets':[]};reports.append(report)
 if not (ctx/'roads.geojson.gz').exists():report['status']='context_pending';continue
 if not any(t['pointCandidates'] for t in city['targets']):report['status']='unlocated_requires_manual_source';continue
 parent=transform(FW,shape(read(ctx/'municipality.geojson')['features'][0]['geometry']));roads=read(ctx/'roads.geojson.gz')['features'];areas=read(ctx/'areas.geojson.gz')['features'];ag=[transform(FW,shape(f['geometry'])) for f in areas];lg=[transform(FW,shape(f['geometry'])).intersection(parent) for f in roads];targets=[(t,transform(FW,Point(t['pointCandidates'][0]['coordinates']))) for t in city['targets'] if t['pointCandidates']]
 for t,pt in targets:
  rr={'name':t['name'],'footprints':[],'cells':[]};report['targets'].append(rr)
  ids=sorted([i for i,g in enumerate(ag) if g.distance(pt)<500 and g.area>1000],key=lambda i:(ag[i].distance(pt),ag[i].area))[:7]
  for i in ids:
   f=areas[i];p=f['properties'];rr['footprints'].append({'id':f['id'],'tags':p.get('tags',p.get('source',{}).get('tags',{})),'distanceMetres':round(ag[i].distance(pt)),'areaSquareMetres':round(ag[i].area)})
 for variant in ['major','street','rural']:
  segments=[];used=[]
  for i,f in enumerate(roads):
   p=f['properties'];tags=p.get('tags',p.get('source',{}).get('tags',{}));hw=tags.get('highway');rail=tags.get('railway');water=tags.get('waterway')
   if variant=='major' and hw not in {'motorway','trunk','primary','secondary','tertiary','unclassified'} and rail not in {'rail','light_rail'} and water not in {'river','canal','stream'}:continue
   if variant=='street' and hw in {'path','footway','cycleway','steps','track','bridleway','pedestrian'}:continue
   g=lg[i]
   if g.is_empty:continue
   segments.append(g);used.append(i)
  cells=list(polygonize(unary_union([parent.boundary]+segments)))
  for t,pt in targets:
   rr=next(r for r in report['targets'] if r['name']==t['name'])
   for g in cells:
    if not g.covers(pt) or g.area<1000 or g.area>12_000_000:continue
    ids=[roads[i]['id'] for i in used if g.boundary.intersection(lg[i]).length>20];ident=city['contextKey']+':'+t['name']+':'+variant
    props={'municipality':name,'name':t['name'],'variant':variant,'contextKey':city['contextKey'],'areaSquareMetres':round(g.area),'sourceLineIds':ids};rr['cells'].append({'id':ident,'variant':variant,'areaSquareMetres':round(g.area),'boundingSourceWays':len(ids)});choices.append({'type':'Feature','id':ident,'properties':props,'geometry':mapping(transform(IV,g))})
 report['status']='alternatives_saved';print(name,len(roads),len(areas),flush=True)
(P/'analysis.json').write_text(json.dumps({'municipalities':reports},ensure_ascii=False,indent=2)+'\n');(P/'candidate-cells.geojson').write_text(json.dumps({'type':'FeatureCollection','features':choices},ensure_ascii=False,separators=(',',':'))+'\n');print('candidate_count',len(choices),flush=True)
