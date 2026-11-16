#!/usr/bin/env python3
"""Offline low-confidence neighborhood estimates from archived real source linework/map traces."""
from pathlib import Path
import json,gzip,hashlib,math
from shapely.geometry import shape,Point,Polygon,mapping
from shapely.ops import transform,unary_union,polygonize
from pyproj import Transformer
ROOT=Path(__file__).resolve().parent
T=Transformer.from_crs(4326,23700,always_xy=True).transform
B=Transformer.from_crs(23700,4326,always_xy=True).transform
D=lambda p:json.loads(p.read_text())
def load(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else D(p)
def dump(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
specs=D(ROOT/'selections.json');task=D(ROOT/'source-inputs/task.json');targets={(m['municipality'],t['name']):(m,t) for m in task['municipalities'] for t in m['targets']}
cache={};features=[];proof=[]
for s in specs:
 m,t=targets[(s['municipality'],s['name'])];key=m['contextKey']
 if key not in cache:
  d=ROOT/'source-inputs'/key;roads=load(d/'roads.geojson.gz')['features'];areas=load(d/'areas.geojson.gz')['features'];mun=unary_union([transform(T,shape(f['geometry'])) for f in load(d/'municipality.geojson')['features']]);lines=[mun.boundary];sourceparts=[('municipality',None,mun.boundary)]
  for i,f in enumerate(roads):
   tags=f['properties'].get('tags',{});h=tags.get('highway');g=transform(T,shape(f['geometry']))
   if h in ['motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','track'] or tags.get('waterway') or tags.get('railway'):
    lines.append(g.intersection(mun));sourceparts.append(('road',i,g))
  for i,f in enumerate(areas):
   tags=f['properties'].get('tags',{});g=transform(T,shape(f['geometry']))
   if tags.get('building') or g.area<10000:continue
   if tags.get('landuse') in ['residential','industrial','forest','farmyard','farmland','orchard','vineyard'] or tags.get('natural') in ['wood','water']:
    lines.append(g.boundary.intersection(mun));sourceparts.append(('area',i,g.boundary))
  cells=[x for x in polygonize(unary_union(lines)) if x.area>100 and mun.covers(x.representative_point())];cache[key]=(roads,areas,mun,cells,sourceparts)
 roads,areas,mun,cells,sourceparts=cache[key]
 anchors=[]
 if s['kind']=='native-area':
  f=areas[s['areaIndex']];g=transform(T,shape(f['geometry']));anchors=[f['properties']['source']];method='native-osm-area-neighborhood-footprint-estimate'
 elif s['kind']=='native-and-cells':
  g=unary_union([transform(T,shape(areas[i]['geometry'])) for i in s['areaIndexes']]+[cells[i] for i in s['cellIndexes']]);anchors=[areas[i]['properties']['source'] for i in s['areaIndexes']];method='native-settlement-corridor-and-road-land-estimate'
 elif s['kind']=='rural-remainder':
  excluded=[]
  for i,f in enumerate(areas):
   tags=f['properties'].get('tags',{});z=transform(T,shape(f['geometry']))
   if tags.get('landuse') in ['residential','industrial','commercial','retail','railway'] and z.area>=30000:
    excluded.append(z);anchors.append({'kind':'excluded-built-up-surface','source':f['properties']['source'],'areaM2':z.area})
  extra=[transform(T,shape(f['geometry'])) for f in D(ROOT/s['excludedPriorEstimate'])['features']];g=mun.difference(unary_union(excluded+extra));method='municipal-rural-remainder-physical-landuse-estimate'
 elif s['kind']=='cells':
  g=unary_union([cells[i] for i in s['cellIndexes']]);method='actual-road-landscape-compartment-neighborhood-estimate'
 elif s['kind']=='manual-eov':
  g=Polygon(s['coordinates']);method='manual-actual-road-map-neighborhood-envelope-estimate'
 elif s['kind']=='raster-map':
  from numpy import array,linalg
  controls=D(ROOT/s['registration']);X=array([[p['pixel'][0],p['pixel'][1],1.] for p in controls['controls']]);Y=array([T(*p['coordinates']) for p in controls['controls']]);coef=linalg.lstsq(X,Y,rcond=None)[0];coords=array([[x,y,1.] for x,y in s['pixels']])@coef;g=Polygon(coords);method='municipal-raster-map-rough-neighborhood-trace'
 else:raise ValueError(s['kind'])
 if not g.is_valid:raise ValueError((s['name'],'invalid original geometry'))
 areaBefore=g.area;g=g.intersection(mun)
 if g.geom_type=='GeometryCollection':g=unary_union([x for x in g.geoms if x.geom_type in ['Polygon','MultiPolygon']])
 assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'],s['name']
 if s['kind'] in ['cells','manual-eov','native-and-cells']:
  for typ,i,line in sourceparts:
   length=g.boundary.intersection(line).length
   near=g.boundary.buffer(2).intersection(line).length
   if length>1 or near>15:
    if typ=='municipality':anchors.append({'kind':'municipality-boundary','sharedLengthM':round(length,2)})
    else:
     f=(roads if typ=='road' else areas)[i];anchors.append({'kind':typ,'source':f['properties'].get('source'),'name':f['properties'].get('name'),'sharedLengthM':round(length,2),'within2MetresLengthM':round(near,2)})
 sourceUrl=s.get('sourceUrl') or (t['pointCandidates'][0]['sourceUrl'] if t['pointCandidates'] else t['nameReferences'][0]['sourceUrl'])
 props={'name':s['name'],'municipality':s['municipality'],'method':method,'estimated':True,'confidence':'low','lowConfidence':True,'sourceUrl':sourceUrl,'approximationNote':s['note'],'qualityScore':20,'priority':30,'radiusFallback':False,'sourceContextKey':key,'sourceEvidence':'source-evidence.json','areaKm2':round(g.area/1e6,6)}
 if s['kind']=='native-area':props['footprintOnly']=True
 if s.get('partial'):props['partialExtent']=True
 f={'type':'Feature','id':'round4-shard4:'+s['municipality']+':'+s['name'],'properties':props,'geometry':mapping(transform(B,g))};features.append(f)
 pointInside=[g.covers(transform(T,Point(p['coordinates']))) for p in t['pointCandidates']]
 proof.append({'name':s['name'],'municipality':s['municipality'],'kind':s['kind'],'selection':s,'areaKm2':round(g.area/1e6,6),'originalAreaRetainedFraction':g.area/areaBefore,'knownPointsInside':pointInside,'sourceAnchors':anchors,'valid':g.is_valid,'whollyWithinMunicipality':mun.covers(g) or g.difference(mun).area<.1,'provenanceContext':str(Path('source-inputs')/key),'targetPointGeneratesShapeOrSize':False,'registrationUsesOtherSettlementLabelCorrespondences':s['kind']=='raster-map'})
fc={'type':'FeatureCollection','features':features};dump(ROOT/'features.geojson',fc);dump(ROOT/'source-evidence.json',{'schemaVersion':1,'estimated':True,'confidence':'low','boundaryStatus':'Approximate search neighborhoods inferred from actual archived physical source boundaries or primary municipal map outlines; not authoritative boundaries.','records':proof})
alltargets=[(m['municipality'],t['name']) for m in task['municipalities'] for t in m['targets']];done={(s['municipality'],s['name']) for s in specs}
dump(ROOT/'summary.json',{'featureCount':len(features),'targetCount':len(alltargets),'remainingCount':len(alltargets)-len(done),'allLowConfidence':True,'radiusFallbackCount':0,'municipalities':sorted({s['municipality'] for s in specs}),'featuresSha256':hashlib.sha256((ROOT/'features.geojson').read_bytes()).hexdigest()})
print(json.dumps(D(ROOT/'summary.json'),ensure_ascii=False))
