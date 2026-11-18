from pathlib import Path
import json
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;fw=Transformer.from_crs(4326,23700,always_xy=True).transform;iv=Transformer.from_crs(23700,4326,always_xy=True).transform
areas=json.load(open(P/'source-areas.geojson'))['features'];lines=json.load(open(P/'source-lines.geojson'))['features'];targets=json.load(open(P/'targets.json'));out=[]
for city,sourceid in [('Mátészalka','osm:relation:2558406'),('Orosháza','osm:relation:3062951')]:
 source=next(f for f in areas if f['id']==sourceid);parent=transform(fw,shape(source['geometry']))
 for variant in ['major','arterial']:
  ls=[parent.boundary];src=[]
  for f in lines:
   if city not in f['properties']['municipalities']:continue
   t=f['properties']['tags'];hw=t.get('highway')
   if hw and hw not in {'primary','secondary','tertiary','trunk','motorway'} and not(variant=='arterial' and hw=='unclassified'):continue
   if not(hw or t.get('railway') in {'rail','light_rail'} or t.get('waterway') in {'river','canal','stream'}):continue
   g=transform(fw,shape(f['geometry'])).intersection(parent)
   if g.is_empty:continue
   ls.append(g);src.append((f,g))
  cs=list(polygonize(unary_union(ls)))
  for t in targets:
   if t['municipality']!=city:continue
   pt=transform(fw,Point(t['pointCandidates'][0]['coordinates']))
   for g in cs:
    if g.covers(pt):
     props={'municipality':city,'name':t['name'],'variant':'footprint-'+variant,'sourceAreaId':sourceid,'sourceLineIds':[f['id'] for f,l in src if g.boundary.intersection(l).length>20],'area':round(g.area)}
     out.append({'type':'Feature','id':city+':'+t['name']+':footprint-'+variant,'properties':props,'geometry':mapping(transform(iv,g))});print(city,t['name'],variant,round(g.area))
(P/'candidate-footprint-cells.geojson').write_text(json.dumps({'type':'FeatureCollection','features':out},ensure_ascii=False,separators=(',',':'))+'\n')
