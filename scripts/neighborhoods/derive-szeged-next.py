#!/usr/bin/env python3
"""Source-described Szeged quarter circuits; offline original source geometry only."""
import argparse,gzip,hashlib,json,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-szeged-next'
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(20.095,46.225,20.15,46.275)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,d):path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def extract():
 import osmium
 t=time.monotonic();stats={'nativeFilteredWays':0,'selectedWays':0,'invalidSelectedWays':0};features=[]
 class C(osmium.SimpleHandler):
  def way(self,w):
   stats['nativeFilteredWays']+=1
   if not any(n.location.valid() and BBOX[0]<=n.lon<=BBOX[2] and BBOX[1]<=n.lat<=BBOX[3] for n in w.nodes):return
   if not all(n.location.valid() for n in w.nodes):stats['invalidSelectedWays']+=1;return
   tags=dict(w.tags)
   features.append({'type':'Feature','id':f'osm:way:{w.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':w.id,'url':f'https://www.openstreetmap.org/way/{w.id}','nodeRefs':[n.ref for n in w.nodes],'objectVersion':w.version,'objectTimestamp':str(w.timestamp),'tags':tags,'geometryUnmodified':True,'geometryProcessing':'Complete actual way sequence; acquisition rectangle is not a boundary.','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':[[n.lon,n.lat] for n in w.nodes]}});stats['selectedWays']+=1
 with tempfile.TemporaryDirectory(prefix='otthonra-szeged-node-')as temp:
  C().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway')])
 OUT.mkdir(parents=True,exist_ok=True);p=ROOT/'.local/neighborhoods/szeged-all-local-lines.geojson';write(p,{'type':'FeatureCollection','features':features});write(OUT/'extraction-proof.json',{'sourcePbfSha256':sha(PBF),'localExplorationOutput':str(p.relative_to(ROOT)),'acquisitionBboxOnly':BBOX,'statistics':stats,'outputSha256':sha(p),'elapsedSeconds':round(time.monotonic()-t,3),'nativeFilter':'highway OR railway after actual location index','geometryRepairs':0});print(json.dumps(stats))

LINE_SHA='f9776899cb4e6a95f517b65299d3fed783ca2fa0830d22bf1751c7cbea7cab1b'
PRIMARY_URL='https://regi.szegedvaros.hu/letoltheto-csatolmany?ID=26101'
SPECS=[
 {'name':'Tarjánváros','id':'tarjanvaros-ivs-2009-2017','kind':'neighbourhood',
  'names':['József Attila sugárút','Körtöltés','Lugas utca','Csillag tér','Szilléri sugárút','Debreceni utca'],
  'notes':['The2017 municipality document explicitly describes the whole named Tarjánváros subdivision, separately from the smaller Belső-Tarján action area.',
   'This reproduces the2009/2017 IVS footprint. A2019 city-library historian defines the current Tarján housing estate differently, using Retek utca and Murányi utca. The source-era footprint is not silently asserted to be today’s estate boundary.']},
 {'name':'Felsővárosi lakótelep (IVS2009/2017 subdivision)', 'id':'felsovarosi-ivs-2009-2017','kind':'planning_unit',
  'names':['Római körút','Szilléri sugárút','Debreceni utca','József Attila sugárút'],
  'notes':['The2017 ITS numbers this circuit as a named subdivision of the Felsőváros macro unit.',
   'The name/footprint relation conflicts with a municipal concept document: the same four-road area is described as a suburban/garden area, while the housing estate is described farther out. It remains a historical planning subdivision, excluded from verified current-neighborhood counts.']}
]

def save(path,value,check=False):
 content=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
 if check:
  if not path.exists() or path.read_bytes()!=content:raise ValueError('Stale derived file: '+str(path))
 else:path.write_bytes(content)

def build(check=False):
 from shapely.geometry import shape,mapping
 from shapely.ops import unary_union,polygonize
 from pyproj import Geod
 path=OUT/'tarjan-circuit-source-lines.geojson'
 if sha(path)!=LINE_SHA:raise ValueError('Changed actual-way input')
 facts=json.loads((OUT/'source-facts.json').read_text())
 roads=json.loads(path.read_text())['features'];geod=Geod(ellps='WGS84')
 cp=ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
 municipalities=json.loads(gzip.decompress(cp.read_bytes()))['features']
 parent=next(f for f in municipalities if f['properties']['name']=='Szeged' and f['properties'].get('usedForAssociation'))
 pg=shape(parent['geometry']);outputs=[];proofs=[]
 for spec in SPECS:
  selected=[f for f in roads if f['properties']['name'] in spec['names']]
  gs=[shape(f['geometry']) for f in selected]
  candidates=[]
  for poly in polygonize(unary_union(gs)):
   used=[f for f,g in zip(selected,gs) if poly.boundary.intersection(g).length>1e-10]
   if set(spec['names'])<={f['properties']['name']for f in used}:candidates.append((poly,used))
  if len(candidates)!=1:raise ValueError('Unique full source circuit not found: '+spec['name'])
  poly,used=candidates[0]
  if not poly.is_valid or poly.interiors or not poly.exterior.is_closed or not pg.covers(poly):raise ValueError('Invalid/open/holed/outside-parent source circuit')
  edges={tuple(sorted((tuple(a),tuple(b)))) for f in used for a,b in zip(f['geometry']['coordinates'],f['geometry']['coordinates'][1:])}
  chain=list(poly.exterior.coords)
  if any(tuple(sorted((a,b)))not in edges for a,b in zip(chain,chain[1:])):raise ValueError('Synthetic edge or intersection vertex')
  for f in used:
   t=f['properties']['source']['tags']
   if t.get('bridge')not in(None,'no')or t.get('tunnel')not in(None,'no')or t.get('layer')not in(None,'0'):raise ValueError('Grade-separated edge requires explicit review')
  area,perim=geod.geometry_area_perimeter(poly);ids=sorted({f['id']for f in used})
  props={'name':spec['name'],'municipality':'Szeged','boundaryKind':spec['kind'],
   'canonicalNameIsNeighborhood':spec['kind']=='neighbourhood',
   'sourcePeriod':'IVS2009 subdivisions quoted in adopted ITS annex200/2017(IV.28), printedp96; OSM2026-11-12T21:23:05Z.',
   'method':'Source-text road circuit polygonized from actual complete named OSM ways; every output edge is a consecutive original node edge.',
   'sourceDocuments':[{'url':PRIMARY_URL,'documentTitle':'200/2017.(IV.28.)Kgy.sz.határozat1.sz.melléklete','printedPage':96,
    'retrieval':'public_web_search_indexed_text','fullPdfDownloaded':False,'sourcePdfSha256':None,
    'factualTranscript':'source-facts.json','factualTranscriptSha256':sha(OUT/'source-facts.json')}],
   'evidenceUrls':[PRIMARY_URL], 'sourceLineIds':ids,
   'sourceNameEvidence':{'status':'municipal_source_era_name','currentExactFootprintConfirmed':False},
   'quality':'source-described-historical-street-circuit','estimated':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,
   'usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None,
   'geometryVerificationStatus':'source_circuit_reproduced_not_surveyed','reviewStatus':'independent_review_required',
   'reviewNotes':spec['notes']+['The underlying text is a municipal source; this derived geometry is not an official municipal GIS or legal boundary.',
    'Road centerlines and divided carriageways are approximations to broadly stated corridors. Exact parcel-side limits and absolute accuracy remain unknown.',
    'No clipping, buffer, Voronoi, hull, snapping, arbitrary connector or geometry repair is used.'],
   'areaM2':abs(area),'perimeterM':perim,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; factual subdivision descriptions Szeged MJV ITS2017,p96.'}
  outputs.append({'type':'Feature','id':'manual:szeged:'+spec['id'],'properties':props,'geometry':mapping(poly)})
  proofs.append({'id':outputs[-1]['id'],'name':spec['name'],'boundaryKind':spec['kind'],'sourceLineIds':ids,
   'requiredNamedCorridors':spec['names'],'boundaryVerticesIncludingClosure':len(chain),'allEdgesConsecutiveActualSourceNodes':True,
   'sourceWays':len(used),'closed':True,'valid':True,'holes':0,'insideSzeged':True,
   'areaM2':abs(area),'perimeterM':perim,'syntheticVertices':0,'syntheticEdges':0,'gradeSeparatedSourceWays':0})
 for a,b in [(outputs[0],outputs[1])]:
  if shape(a['geometry']).intersection(shape(b['geometry'])).area>1e-16:raise ValueError('Derived subdivision interiors overlap')
 save(OUT/'szeged-street-candidates.geojson',{'type':'FeatureCollection','features':outputs},check)
 save(OUT/'municipality.geojson',{'type':'FeatureCollection','features':[parent]},check)
 save(OUT/'conversion-proof.json',{'sourceLineFile':'tarjan-circuit-source-lines.geojson','sourceLineSha256':LINE_SHA,
  'sourceFactsSha256':sha(OUT/'source-facts.json'),'municipalityArchiveSha256':sha(cp),
  'osmSourceSnapshot':'2026-11-12T21:23:05Z','osmSourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
  'candidates':proofs,'geometryRepairs':0,'unexplainedClosingEdges':0,'overlappingInteriorPairs':0},check)
 print(json.dumps({'candidates':len(outputs),'sourceEraNeighborhoods':1,'historicalPlanningSubdivisions':1,'check':check}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.extract:extract()
 else:build(a.check)
