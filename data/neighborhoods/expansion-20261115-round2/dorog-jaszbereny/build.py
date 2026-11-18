#!/usr/bin/env python3
"""Rebuild the collected neighbourhood estimates from frozen local source evidence."""
import gzip,hashlib,json
from pathlib import Path
from collections import Counter
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import Polygon,Point,shape,mapping
from shapely.ops import transform,unary_union
H=Path(__file__).resolve().parent
F=Transformer.from_crs(4326,23700,always_xy=True).transform
I=Transformer.from_crs(23700,4326,always_xy=True).transform
def load(name):
 b=(H/name).read_bytes();return json.loads(gzip.decompress(b) if name.endswith('.gz') else b)
def write(name,obj): (H/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')
def polygonal(g):
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 return unary_union([q for q in g.geoms if q.geom_type in ['Polygon','MultiPolygon']])
def main():
 targets=load('baseline-targets.json')['targets'];bykey={(q['municipality'],q['name']):q for q in targets}
 areas={f['id']:f for f in load('source-areas.geojson.gz')['features']}
 mun={f['properties'].get('name',f['properties'].get('municipality')):shape(f['geometry']) for f in load('source-municipalities.geojson')['features']}
 features=[];checks=[]
 specifications=load('trace-specifications.json')
 for spec in specifications['traces']:
  city,name=spec['municipality'],spec['name'];record=bykey[(city,name)]
  if 'pixelRing' in spec:
   reg=load(spec['registration']);x1,y1,x2,y2=reg['metreBounds'];scale=reg['scale']
   projected=Polygon([(x1+x/scale,y2-y/scale) for x,y in spec['pixelRing']]);g=transform(I,projected)
  elif 'sourceAreaIds' in spec:
   g=unary_union([shape(areas[ident]['geometry']) for ident in spec['sourceAreaIds']])
  else:raise ValueError('No source-backed construction for '+name)
  g=polygonal(make_valid(g))
  if city in mun:g=polygonal(make_valid(g.intersection(mun[city])))
  if g.is_empty or not g.is_valid:raise ValueError('Invalid geometry for '+name)
  point=Point(record['pointCandidates'][0]['coordinates']);contains=g.covers(point)
  area=transform(F,g).area
  if not contains and not spec.get('allowOutsideLabel'):raise ValueError('Name label outside inferred area: '+name)
  if area>spec.get('maximumAreaSquareMetres',2000000):raise ValueError('Unexpectedly large inference: '+name)
  p={'municipality':city,'name':name,'method':spec.get('method','map_or_text_estimate'),'estimated':True,'lowConfidence':True,'semanticFootprint':True,'pointRadiusFallback':False,'qualityScore':28,'candidateBoundaryKind':'neighbourhood','nameEvidence':record['pointCandidates'],'sourceUrl':record['pointCandidates'][0]['sourceUrl'],'source':{'provider':'archived-physical-road-address-and-planning-map-interpretation','path':str(H.relative_to(H.parents[3])),'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'constructionEvidence':spec,'approximateAreaSquareMetres':round(area,1),'approximationNote':spec['note']+' Low-confidence practical search footprint; not an official cadastral boundary. Streets, shared spaces and adjacent yards are included; no circular or label-only geometric fallback.'}
  features.append({'type':'Feature','id':'round2:dorog-jaszbereny:'+hashlib.sha256((city+'|'+name).encode()).hexdigest()[:20],'properties':p,'geometry':mapping(g)})
  checks.append({'municipality':city,'name':name,'valid':g.is_valid,'labelCovered':contains,'areaSquareMetres':round(area,1)})
 features.sort(key=lambda f:(f['properties']['municipality'],f['properties']['name']))
 write('features.geojson',{'type':'FeatureCollection','features':features})
 for city,filename in [('Dorog',specifications.get('dorogOutput','dorog-features.geojson')),('Jászberény','jaszbereny-features.geojson')]:
  rows=[f for f in features if f['properties']['municipality']==city]
  if rows:write(filename,{'type':'FeatureCollection','features':rows})
 covered={(f['properties']['municipality'],f['properties']['name']) for f in features}
 unresolved=[{'municipality':q['municipality'],'name':q['name'],'reason':'No sufficiently useful source-based estimate completed in this packet; further work remains, not evidence that no source exists.'} for q in targets if (q['municipality'],q['name']) not in covered]
 write('unresolved.json',unresolved)
 summary={'status':'frozen_completed_packet','featureCount':len(features),'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),'targetCount':len(targets),'unresolvedCount':len(unresolved),'circleCount':0,'allEstimated':True,'allLowConfidence':True,'completeNationalCoverage':False}
 write('summary.json',summary);write('validation.json',{'scope':'technical_geometry_and_source_label_only_not_precision_review','features':checks,'uniqueCityNameCount':len(covered),'featureCount':len(features),'validCount':sum(c['valid'] for c in checks)})
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
