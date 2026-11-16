#!/usr/bin/env python3
"""Build an explicitly selected frozen batch from shared actual source contexts."""
import argparse,gzip,hashlib,json
from pathlib import Path
from collections import Counter
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import Polygon,Point,shape,mapping
from shapely.ops import transform,unary_union
H=Path(__file__).resolve().parent;R=H.parents[3];F=Transformer.from_crs(4326,23700,always_xy=True).transform;I=Transformer.from_crs(23700,4326,always_xy=True).transform
def read(p):
 b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n')
TASK=read(H/'targets.json');TARGETS={(q['municipality'],q['name']):(c,q) for c in TASK['municipalities'] for q in c['targets']}
def polygonal(g):
 g=make_valid(g)
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 return unary_union([polygonal(q) for q in g.geoms if q.geom_type in ['Polygon','MultiPolygon','GeometryCollection']])
def build(batch):
 folder=H/batch;specs=read(folder/'specifications.json');features=[];validation=[];inputs={}
 for spec in specs['features']:
  key=(spec['municipality'],spec['name']);city,target=TARGETS[key];ctx=R/TASK['contextRoot']/city['contextKey'];geoms=[];sourceAreas=[]
  if spec.get('nativeAreaIds'):
   rows=read(ctx/'areas.geojson.gz')['features'];byid={str(f['id']):f for f in rows}
   for ident in spec['nativeAreaIds']:
    f=byid[str(ident)];geoms.append(shape(f['geometry']));sourceAreas.append({'id':str(f['id']),'properties':f['properties']})
  for part in spec.get('parts',[]):
   reg=read(H/part['registration']);x1,y1,x2,y2=reg['metreBounds'];s=reg['scale']
   ring=part['pixelRing'];assert len(ring)>=4
   assert not (len(ring)==4 and len({p[0] for p in ring})==2 and len({p[1] for p in ring})==2),'Four-corner rectangle is not an acceptable inferred footprint'
   geoms.append(transform(I,Polygon([(x1+x/s,y2-y/s) for x,y in ring])))
  if not geoms:raise ValueError('No source-backed geometry for '+str(key))
  g=polygonal(unary_union(geoms));mun=read(ctx/'municipality.geojson')['features']
  if mun:g=polygonal(g.intersection(shape(mun[0]['geometry'])))
  assert not g.is_empty and g.is_valid,key
  area=transform(F,g).area;assert 1000<area<spec.get('maximumAreaSquareMetres',30000000),(key,area)
  covered=[g.covers(Point(c['coordinates'])) for c in target['pointCandidates']]
  assert any(covered) or spec.get('allowLabelOutside'),(key,'label outside')
  urls=spec.get('evidenceUrls',[]);method=spec.get('method','map_or_text_estimate')
  p={'municipality':key[0],'name':key[1],'method':method,'estimated':True,'lowConfidence':True,'qualityScore':spec.get('qualityScore',24),'semanticFootprint':bool(spec.get('nativeAreaIds')),'pointRadiusFallback':False,'candidateBoundaryKind':'neighbourhood','nameEvidence':target['pointCandidates'],'sourceUrl':urls[0] if urls else target['pointCandidates'][0]['sourceUrl'],'evidenceUrls':urls,'source':{'provider':'archived-native-physical-road-landuse-and-local-source-interpretation','path':str(ctx.relative_to(R)),'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'constructionEvidence':spec,'sourceAreaEvidence':sourceAreas,'approximateAreaSquareMetres':round(area,1),'approximationNote':spec['note']+' Low-confidence practical whole-area estimate; not an official current cadastral boundary. No coordinate-radius circle, point-only box, Voronoi or point hull.'}
  features.append({'type':'Feature','id':'round4:shard3:'+hashlib.sha256((key[0]+'|'+key[1]).encode()).hexdigest()[:22],'properties':p,'geometry':mapping(g)})
  validation.append({'municipality':key[0],'name':key[1],'valid':g.is_valid,'labelCandidatesCovered':covered,'areaSquareMetres':round(area,1)})
  for name in ['roads.geojson.gz','areas.geojson.gz','addresses.geojson.gz','municipality.geojson']:
   path=ctx/name;inputs[str(path.relative_to(R))]=hashlib.sha256(path.read_bytes()).hexdigest()
 features.sort(key=lambda f:(f['properties']['municipality'],f['properties']['name']))
 assert len(features)==len({(f['properties']['municipality'],f['properties']['name']) for f in features})
 write(folder/'features.geojson',{'type':'FeatureCollection','features':features});write(folder/'validation.json',{'scope':'technical_and_label_coverage_not_geographic_precision','featureCount':len(features),'features':validation})
 summary={'status':'frozen_completed_batch','batch':batch,'featureCount':len(features),'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),'allEstimated':True,'allLowConfidence':True,'circleCount':0,'sourceInputSha256':inputs,'outputSha256':hashlib.sha256((folder/'features.geojson').read_bytes()).hexdigest()}
 write(folder/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='sourceInputSha256'},ensure_ascii=False))
def main():
 p=argparse.ArgumentParser();p.add_argument('batch');a=p.parse_args();build(a.batch)
if __name__=='__main__':main()
