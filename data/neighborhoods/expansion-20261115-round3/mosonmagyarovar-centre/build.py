#!/usr/bin/env python3
"""Offline historic-centre and riverside search extents from frozen source ways."""
from pathlib import Path
import json,gzip,hashlib,math
from shapely.geometry import shape,mapping,Point,Polygon,LineString
from shapely.ops import transform,unary_union
from pyproj import Transformer
H=Path(__file__).resolve().parent
ROOT=H.parents[3]
def load(n):
 p=H/n;return json.load(gzip.open(p,'rt')) if n.endswith('.gz') else json.loads(p.read_text())
def dump(n,x):(H/n).write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
ways={x['id']:x for x in load('source-roads.geojson.gz')['features']};target={x['name']:x for x in load('target-selection.json')}
municipality=load('municipality.geojson');municipal=shape(municipality['features'][0]['geometry']) if 'features' in municipality else shape(municipality['geometry'])
fwd=Transformer.from_crs(4326,23700,always_xy=True).transform
roadseams=[]
def append(cs,new):
 if cs and new and cs[-1]!=new[0]:
  length=transform(fwd,LineString([cs[-1],new[0]])).length
  roadseams.append({'from':cs[-1],'to':new[0],'metres':round(length,1),'kind':'explicit_inferred_connection'})
 cs.extend(new if not cs or cs[-1]!=new[0] else new[1:])
def coords(ident,reverse=False):
 cs=ways['osm:way:'+str(ident)]['geometry']['coordinates'];return list(reversed(cs)) if reverse else cs
# West perimeter uses the actual Ady Endre and Városkapu/Fő street alignments.
cs=[]
for ident,rev in [(831923054,True),(831923053,True),(61849619,True),(191146434,False),(338037851,True),(1548851301,True),(452971476,True),(154342433,True)]:append(cs,coords(ident,rev))
# Eastern perimeter follows the original Malom-ági Lajta line, cut at the
# southern historic-street approach. This is not the whole Magyaróvár parent.
r=coords(891575594);south=min(range(len(r)),key=lambda i:transform(fwd,Point(r[i])).distance(transform(fwd,Point(cs[-1]))))
append(cs,list(reversed(r[:south+1])))
append(cs,coords(891575596,True))
r=coords(179959503);north=min(range(len(r)),key=lambda i:transform(fwd,Point(r[i])).distance(transform(fwd,Point(cs[0]))))
append(cs,list(reversed(r[north:])))
append(cs,[cs[0]])
centre=Polygon(cs)
if not centre.is_valid:raise ValueError('Invalid centre source-line closure')
# Dunapart uses an explicit larger landward street/plot interpretation, and
# original Mosoni-Duna river line along the east. No river/water polygon reused.
spec=load('dunapart-trace.json');b=load('dunapart-registration.json')['bounds'];W,Hh=1500,1200
land=[[round(b[0]+x/W*(b[2]-b[0]),9),round(b[3]-y/Hh*(b[3]-b[1]),9)] for x,y in spec['landwardPixels']]
# Connect the northern landward end to the nearest actual river vertex, then
# follow the river south, and return along the recorded street-block perimeter.
riverways=[f for f in ways.values() if f['properties'].get('name')=='Mosoni-Duna']
chosenRiver=min(riverways,key=lambda f:max(shape(f['geometry']).distance(Point(land[0])),shape(f['geometry']).distance(Point(land[-1]))))
riverways=[chosenRiver]
rr=shape(chosenRiver['geometry'])
if rr.geom_type!='LineString':raise ValueError('Selected Mosoni-Duna source is not a line')
raw=list(rr.coords);a=min(range(len(raw)),key=lambda i:Point(raw[i]).distance(Point(land[0])));z=min(range(len(raw)),key=lambda i:Point(raw[i]).distance(Point(land[-1])))
segment=raw[a:z+1] if a<z else list(reversed(raw[z:a+1]))
duna=Polygon(segment+list(reversed(land)))
if not duna.is_valid:raise ValueError('Invalid riverside trace')
features=[];checks=[]
for name,g,refs,note in [('Belváros',centre,['osm:way:'+str(i) for i in [831923054,831923053,61849619,191146434,338037851,1548851301,452971476,154342433,891575594,891575596,179959503]],'Independent narrow historic-centre estimate enclosing the Fő/Magyar old-town street fabric, using Ady/Városkapu/Fő western approaches and the Malom-ági Lajta eastern perimeter. It excludes the separate castle and Wittmann-park grounds and is not an alias/copy of the broad Magyaróvár quarter. Short street/river approach connections are explicitly inferred; exact protected-boundary alignment has not been checked.'),('Dunapart',duna,[x['id'] for x in riverways],'Rough west-bank riverside neighbourhood extent, including the Fazekas/Petőfi/Duna/Felsőötház/Aranyossziget street and residential plots towards Rév. The east follows the native river centreline, so a narrow channel strip can remain; most of the output is landward residential/green neighbourhood. It is not a water-surface polygon, channel buffer, point radius or the whole Moson parent. Landward edge and street-block joining links are low-confidence manual interpretations.')]:
 g=g.intersection(municipal)
 if g.is_empty or not g.is_valid or g.geom_type not in ['Polygon','MultiPolygon']:raise ValueError('Invalid/clipped '+name)
 point=Point(target[name]['pointCandidates'][0]['coordinates'])
 sourceurls=[ways[i]['properties']['source']['url'] for i in refs]
 feature={'type':'Feature','id':'moson-centre:'+hashlib.sha256(name.encode()).hexdigest()[:20],'geometry':mapping(g),'properties':{'name':name,'municipality':'Mosonmagyaróvár','municipalityId':'city:Mosonmagyaróvár','method':'source_line_text_extent_estimate','boundaryKind':'neighbourhood','searchable':True,'estimated':True,'lowConfidence':True,'qualityScore':25,'pointRadiusFallback':False,'wholeQuarterAccuracyVerified':False,'sourceRole':'rough_whole_neighbourhood_extent','approximationNote':note,'namePoint':target[name]['pointCandidates'][0],'sourceLineIds':refs,'manualTraceFile':str((H/'dunapart-trace.json').relative_to(ROOT)) if name=='Dunapart' else str((H/'build.py').relative_to(ROOT)),'source':{'provider':'manual-osm-road-river-and-municipal-text-inference','url':'https://www.movinnov.hu/docs/IVS-1.pdf' if name=='Belváros' else target[name]['pointCandidates'][0]['sourceUrl'],'supportingUrls':sourceurls,'sourcePath':str((H/'source-roads.geojson.gz').relative_to(ROOT)),'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','snapshotDate':'2026-11-12T21:23:05Z','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'evidenceFile':str((H/'source-facts.json').relative_to(ROOT))}}
 features.append(feature);checks.append({'name':name,'valid':g.is_valid,'coversNamePoint':g.covers(point),'areaSquareMetres':round(transform(fwd,g).area,1)})
dump('features.geojson',{'type':'FeatureCollection','features':features})
parent=next(f for f in load('prior-quarters.geojson')['features'] if f['properties']['name']=='Magyaróvár');pg=shape(parent['geometry']);cg=shape(features[0]['geometry']);ratio=transform(fwd,cg).area/transform(fwd,pg).area
proof={'scope':'technical_not_surveyed_accuracy_review','featureCount':2,'allValid':all(x['valid'] for x in checks),'allCoverNamePoint':all(x['coversNamePoint'] for x in checks),'checks':checks,'historicCentreAreaVsMagyarovarParentRatio':round(ratio,4),'centreIdenticalToParent':cg.equals(pg),'centreCoveredByBroaderParentFraction':round(transform(fwd,cg.intersection(pg)).area/transform(fwd,cg).area,4),'inferredCentreConnections':roadseams,'riverSourceWayCount':len(riverways)}
dump('validation.json',proof);dump('unresolved.json',[])
dump('summary.json',{'schemaVersion':1,'featureCount':2,'municipality':'Mosonmagyaróvár','names':['Belváros','Dunapart'],'circleCount':0,'aliasesAdded':0,'methods':{'source_line_text_extent_estimate':2},'allEstimated':True,'remainingBaselineMissingNames':0,'geojsonSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest()})
print(json.dumps(proof,ensure_ascii=False))
