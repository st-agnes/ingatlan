#!/usr/bin/env python3
"""Offline source-feature acquisition for additional Szeged quarter circuits."""
import argparse,hashlib,json,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-szeged-more'
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(20.095,46.215,20.145,46.242)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def extract():
 import osmium
 stats={'nativeFilteredWays':0,'selectedWays':0,'invalidSelectedWays':0};features=[];t=time.monotonic()
 class C(osmium.SimpleHandler):
  def way(self,w):
   stats['nativeFilteredWays']+=1
   if not any(n.location.valid()and BBOX[0]<=n.lon<=BBOX[2]and BBOX[1]<=n.lat<=BBOX[3]for n in w.nodes):return
   if not all(n.location.valid()for n in w.nodes):stats['invalidSelectedWays']+=1;return
   tags=dict(w.tags);coords=[[n.lon,n.lat]for n in w.nodes]
   features.append({'type':'Feature','id':f'osm:way:{w.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':w.id,'url':f'https://www.openstreetmap.org/way/{w.id}','nodeRefs':[n.ref for n in w.nodes],'objectVersion':w.version,'objectTimestamp':str(w.timestamp),'tags':tags,'geometryUnmodified':True,'geometryProcessing':'Actual complete way sequence; bbox is acquisition only, never a boundary.','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':coords}});stats['selectedWays']+=1
 with tempfile.TemporaryDirectory(prefix='otthonra-szeged-more-')as temp:
  C().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','natural','man_made','embankment')])
 OUT.mkdir(parents=True,exist_ok=True);p=ROOT/'.local/neighborhoods/szeged-more-local-lines.geojson';write(p,{'type':'FeatureCollection','features':features});write(OUT/'extraction-proof.json',{'sourcePbfSha256':sha(PBF),'acquisitionBboxOnly':BBOX,'statistics':stats,'localExplorationOutput':str(p.relative_to(ROOT)),'outputSha256':sha(p),'elapsedSeconds':round(time.monotonic()-t,3),'nativeFilter':'highway OR railway OR waterway OR natural OR man_made OR embankment after actual location index','geometryRepairs':0});print(json.dumps(stats))

PINNED={
 'klebel-evidence-lines.geojson':'337b33b7f0672fbecb97ff8cae6011e1d513ffc63a8f4b0265526fb0b7a36794',
 'gyalai-water-source-members.geojson':'c109b6ec14fa3b90d5cd96b88e48742a0d3ef8c953d10aee86fc3d0146b2221f',
 'tarjan2019-evidence-lines.geojson':'020d3e227e24fbb975cd0440f49485d08e589ec224a516cfd7fadfddeb8f43c0'
}
def save(p,d,check):
 value=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
 if check:
  if not p.exists()or p.read_bytes()!=value:raise ValueError('Changed/missing obstacle proof: '+str(p))
 else:p.write_bytes(value)

def analyze(check=False):
 from shapely.geometry import shape,Point
 from shapely.ops import transform,unary_union,polygonize,nearest_points
 from pyproj import Transformer
 for name,expected in PINNED.items():
  if sha(OUT/name)!=expected:raise ValueError('Changed archived source: '+name)
 k=json.loads((OUT/'klebel-evidence-lines.geojson').read_text())['features']
 water=json.loads((OUT/'gyalai-water-source-members.geojson').read_text())['features']
 byid={int(f['id'].split(':')[-1]):f for f in k}
 rail=[f for f in k if f['properties']['source']['tags'].get('railway')in['rail','disused','abandoned','razed']]
 tx=Transformer.from_crs(4326,23700,always_xy=True).transform
 wb=unary_union([shape(f['geometry'])for f in water]);wmetric=transform(tx,wb)
 rows=[]
 for f in rail:
  g=transform(tx,shape(f['geometry']));a,b=nearest_points(g,wmetric)
  rows.append({'id':f['id'],'railway':f['properties']['source']['tags']['railway'],
   'gapMetresEpsg23700':g.distance(wmetric),'closestRailEov':[a.x,a.y],'closestBankEov':[b.x,b.y]})
 rows.sort(key=lambda r:r['gapMetresEpsg23700'])
 source_category=[byid[i]for i in[39429434,398438047,398438048,398438049,398438050,398438051,398438052,398438143]]+rail+water
 cells=list(polygonize(unary_union([shape(f['geometry'])for f in source_category])))
 label=Point(20.1163732,46.2295209)
 if any(g.covers(label)for g in cells):raise ValueError('An unexpected literal source-category circuit now covers the quarter; investigate before changing this proof')
 drain=unary_union([shape(byid[i]['geometry'])for i in[398438047,398438143]])
 east=next(x for x in rows if x['id']=='osm:way:430272966')
 t=json.loads((OUT/'tarjan2019-evidence-lines.geojson').read_text())['features']
 corridor_names={'József Attila sugárút','Körtöltés','Lugas utca','Csillag tér','Szilléri sugárút','Retek utca','Murányi utca'}
 named=[f for f in t if f['properties']['name']in corridor_names and f['properties']['source']['tags']['highway']not in['cycleway','footway','path']]
 ramp=next(f for f in t if f['id']=='osm:way:749440771');surface=named+[ramp]
 ts=[]
 for g in polygonize(unary_union([shape(f['geometry'])for f in surface])):
  if g.area<1e-6:continue
  used=[f for f in surface if g.boundary.intersection(shape(f['geometry'])).length>1e-10]
  ts.append({'bounds':list(g.bounds),'areaDegreesSquared':g.area,'sourceCorridorNames':sorted({f['properties']['name']for f in used}),
   'actualSourceLineIds':sorted({f['id']for f in used})})
 result={'reviewedAt':'2026-11-13','sourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
  'admittedNewQuarterPolygons':0,'geometryRepairs':0,'inventedClosingEdges':0,'inputSha256':PINNED,
  'klebel':{'liveDisusedAbandonedRailWays':len(rail),'waterRelationId':'osm:relation:1483931','actualWaterBankWays':len(water),
   'actualWaterBankMembersAllOuter':all(f['properties']['memberRoles']==['outer']for f in water),
   'westernDrainAndCulvertLiterallyMeetWaterBank':drain.intersects(wb),
   'exactSourceCategoryPolygonizedCells':len(cells),'closedCellsCoveringActualQuarterLabel':0,
   'namedLabel':{'id':'osm:node:982345167','name':'Klebelsbergtelep','coordinates':[20.1163732,46.2295209]},
   'smallestRailToCurrentWaterBankGaps':rows[:5],'plausibleEasternIndustrialRail':east,
   'interpretation':'The primary2007 source says physical railway embankment, not merely track centerline. The unrecorded/evidentially unresolved southeast embankment-to-old-water-basin linkage remains a task. A present water surface is also not guaranteed to equal the historical basin edge. No arbitrary connection is supplied.'},
  'tarjan2019':{'namedMainCorridorsPlusActualRampLargeCells':ts,'actualMuranyiToDykeRampId':ramp['id'],
   'rampIsOriginalSourceGeometry':True,'rampOpenedTag':ramp['properties']['source']['tags'].get('start_date'),
   'interpretation':'The actual2019 cycleway ramp resolves physical access from Murányi to Körtöltés. It does not establish the quarter limit: house-number-side requirements north of Budapesti, two József Attila/Murányi junctions and the precise outer property corridor remain ambiguous. No union is admitted as a current quarter. This is a source version of existing Tarján, never a second canonical quarter.'},
  'usableForAddressAssignment':False}
 save(OUT/'obstacle-proof.json',result,check)
 print(json.dumps({'newQuarterPolygons':0,'klebelLiteralCoveringCells':0,'nearestEastRailBankGapMetres':round(east['gapMetresEpsg23700'],3),'tarjanSourceVersionUnresolved':True,'check':check}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.extract:extract()
 else:analyze(a.check)
