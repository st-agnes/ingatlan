#!/usr/bin/env python3
"""Use actual small OSM land-use outlines even when several labels share them."""
from pathlib import Path
import collections,gzip,hashlib,json,math,tempfile,unicodedata,sys
import osmium
from shapely import from_wkb
from shapely.geometry import mapping,shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
DATA=ROOT/'data/neighborhoods'
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
core=json.loads((HERE/'district-input.geojson').read_text())['features']
bud=json.loads((HERE/'name-point-input.geojson').read_text())['features']
selection=json.loads((HERE/'selection.json').read_text())
missing=[f for f in bud if f['properties']['name'] in selection['pointNames']]
points=[shape(f['geometry']) for f in missing];tree=STRtree(points)
alltree=STRtree([shape(f['geometry']) for f in bud])
factory=osmium.geom.WKBFactory();stats=collections.Counter();candidates=[]
pbf_sha=json.loads((HERE/'footprint-raw-features.geojson').read_text())['features'][0]['properties']['source']['pbfSha256']

class Handler(osmium.SimpleHandler):
 def area(self,obj):
  tags=dict(obj.tags);landuse=tags.get('landuse');leisure=tags.get('leisure')
  if landuse not in {'residential','allotments','industrial','commercial','retail'} and leisure not in {'park','garden','nature_reserve'}:return
  try:
   g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
   if g.is_empty or not g.is_valid:return
   if not (g.bounds[0]<19.4 and g.bounds[2]>18.8 and g.bounds[1]<47.7 and g.bounds[3]>47.3):return
   m2=g.area*111320**2*math.cos(math.radians(g.centroid.y))
   if not 10_000<=m2<=3_000_000:return
   hits=tree.query(g,predicate='covers')
   if not len(hits):return
   allhits=alltree.query(g,predicate='covers')
   ident='osm:'+('way' if obj.from_way() else 'relation')+':'+str(obj.orig_id())
   source={'provider':'openstreetmap','osmType':'way' if obj.from_way() else 'relation','osmId':obj.orig_id(),
    'url':'https://www.openstreetmap.org/'+('way' if obj.from_way() else 'relation')+'/'+str(obj.orig_id()),'tags':tags,
    'pbfSha256':pbf_sha,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
   for hit in hits:
    point=missing[int(hit)];name=point['properties']['name']
    candidates.append({'type':'Feature','id':ident+':'+norm(name),'geometry':mapping(g),'properties':{
     'municipality':'Budapest','name':name,'method':'named_point_source_footprint_estimate','estimated':True,
     'semanticFootprint':True,'sourceRole':'landuse_'+(landuse or leisure),'source':source,'sourceUrl':source['url'],
     'sourceGeometryUnmodified':True,'sourceAreaSquareMetres':round(m2,1),'qualityScore':35,
     'namePoint':{'id':point['id'],'coordinates':point['geometry']['coordinates'],'sourceUrl':point['properties']['source']['url']},
     'containedSourceLabels':[bud[int(i)]['properties']['name'] for i in allhits],
     'approximationNote':'The actual mapped surface containing the place label is used as a rough search extent. Multiple labels are allowed because parent/child and historical subdivisions may overlap. This is not a source-labelled neighbourhood border; no circle or Voronoi construction.'}})
   stats['sourceOutlines']+=1
  except (RuntimeError,ValueError):stats['invalidOrUnassembled']+=1

if '--saved-sources' in sys.argv:
 candidates=json.loads((HERE/'footprint-raw-features.geojson').read_text())['features']
 stats=collections.Counter(json.loads((HERE/'summary.json').read_text())['stats'])
else:
 assert hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest()==pbf_sha
 with tempfile.TemporaryDirectory() as tmp:
  Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('landuse','leisure')])
selected={}
for f in sorted(candidates,key=lambda f:(f['properties']['sourceAreaSquareMetres'],f['id'])):
 selected.setdefault(norm(f['properties']['name']),f)
dump(HERE/'footprint-raw-features.geojson',{'type':'FeatureCollection','features':candidates})
dump(HERE/'footprint-features.geojson',{'type':'FeatureCollection','features':list(selected.values())})
# Large historical halves are constructed from current district boundaries;
# districts remain independently searchable, so overlap is intentional.
districts={f['properties']['name']:f for f in core if f['properties']['municipality']=='Budapest' and f['properties'].get('sourceProperties',{}).get('sourceRole')=='district'}
buda_names=['I. kerület','II. kerület','III. kerület','XI. kerület','XII. kerület','XXII. kerület']
parents=[]
for name,names in [('Buda',buda_names),('Pest',[n for n in districts if n not in buda_names])]:
 members=[districts[n] for n in names if n in districts]
 g=unary_union([shape(f['geometry']) for f in members]);assert g.is_valid
 parents.append({'type':'Feature','id':'budapest-half:'+name,'geometry':mapping(g),'properties':{'municipality':'Budapest','name':name,
  'method':'source_vector_parent_union','estimated':True,'boundaryKind':'parent_area','sourceSubdivisionKind':'parent_quarter',
  'source':{'provider':'derived-openstreetmap','path':'data/neighborhoods/search-areas.geojson','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
  'sourceDistrictNames':names,'approximationNote':'Broad search-area convention: Buda is the union of west-bank districts I,II,III,XI,XII,XXII; Pest is the other Budapest districts, including Csepel and Soroksár. This coarse parent classification is not a claim about the boundaries of the three historic pre-unification cities.'}})
dump(HERE/'parent-features.geojson',{'type':'FeatureCollection','features':parents})
footprints=[f for f in selected.values() if f['properties']['name'] not in {'Buda','Pest'}]
dump(HERE/'features.geojson',{'type':'FeatureCollection','features':parents+footprints})
dump(HERE/'summary.json',{'featureCount':len(parents)+len(footprints),'footprintNames':len(footprints),'parentNames':len(parents),'rawFootprintAlternatives':len(candidates),'stats':dict(stats),'circleCount':0,'nationalCompletenessClaimed':False})
print(json.dumps({'parents':len(parents),'footprintNames':len(selected),'rawAlternatives':len(candidates),'names':[f['properties']['name'] for f in selected.values()]},ensure_ascii=False))
