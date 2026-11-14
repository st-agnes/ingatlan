#!/usr/bin/env python3
from pathlib import Path
import collections,gzip,hashlib,json,math,tempfile,unicodedata,sys
import osmium
from shapely import from_wkb
from shapely.geometry import shape,mapping
from shapely.strtree import STRtree

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];DATA=ROOT/'data/neighborhoods'
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
selection_path=HERE/'surface-selection.json'
if selection_path.exists():selection=json.loads(selection_path.read_text())
else:
 inv=json.loads((DATA/'expansion-20261114/inventory/priority-cities.json').read_text())
 selection={x['municipality']:x['missingNames'] for x in inv['cities'] if x['municipality'] in ['Győr','Sopron']};dump(selection_path,selection)
nodes=json.loads((HERE/'name-points.geojson').read_text())['features'];targets=[f for f in nodes if f['properties']['name'] in selection[f['properties']['municipality']]]
tree=STRtree([shape(f['geometry']) for f in targets]);factory=osmium.geom.WKBFactory();candidates=[]
pbf=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf');sha=hashlib.file_digest(pbf.open('rb'),'sha256').hexdigest()
class Handler(osmium.SimpleHandler):
 def area(self,obj):
  tags=dict(obj.tags);landuse=tags.get('landuse');leisure=tags.get('leisure')
  if landuse not in {'residential','allotments','farmyard','industrial','commercial','retail','forest'} and leisure not in {'park','garden'}:return
  try:
   g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
   if g.is_empty or not g.is_valid:return
   # Only the western-Hungarian city regions can contain any of our targets.
   if not (16.4<g.centroid.x<17.85 and 47.58<g.centroid.y<47.8):return
   m2=g.area*111320**2*math.cos(math.radians(g.centroid.y))
   if not 5_000<=m2<=3_000_000:return
   hits=tree.query(g,predicate='covers')
   for hit in hits:
    point=targets[int(hit)];city=point['properties']['municipality'];name=point['properties']['name'];osmtype='way' if obj.from_way() else 'relation';ident='osm:'+osmtype+':'+str(obj.orig_id());url='https://www.openstreetmap.org/'+osmtype+'/'+str(obj.orig_id())
    candidates.append({'type':'Feature','id':ident+':'+city+':'+name,'geometry':mapping(g),'properties':{
      'municipality':city,'name':name,'method':'named_point_source_footprint_estimate','estimated':True,'semanticFootprint':True,'qualityScore':35,
      'sourceRole':'landuse_'+(landuse or leisure),'sourceAreaSquareMetres':round(m2,1),'sourceGeometryUnmodified':True,
      'source':{'provider':'openstreetmap','url':url,'osmType':osmtype,'osmId':obj.orig_id(),'tags':tags,'pbfSha256':sha,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
      'namePoint':{'sourceUrl':point['properties']['source']['url'],'coordinates':point['geometry']['coordinates']},
      'approximationNote':'Actual unchanged mapped source surface containing the named-place point, used as a rough search footprint. The surface is not asserted to be the full neighbourhood boundary. Several place labels may share a surface. No radius, hull or Voronoi construction.'}})
  except (RuntimeError,ValueError):pass
if '--saved-sources' in sys.argv:candidates=json.loads((HERE/'raw-surface-features.geojson').read_text())['features']
else:
 with tempfile.TemporaryDirectory() as tmp:Handler().apply_file(str(pbf),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('landuse','leisure')])
selected={}
for f in sorted(candidates,key=lambda f:(f['properties']['sourceAreaSquareMetres'],f['id'])):
 p=f['properties'];selected.setdefault((p['municipality'],norm(p['name'])),f)
dump(HERE/'raw-surface-features.geojson',{'type':'FeatureCollection','features':candidates})
dump(HERE/'surface-features.geojson',{'type':'FeatureCollection','features':list(selected.values())})
print(json.dumps({'featureCount':len(selected),'sourceAlternatives':len(candidates),'names':[(f['properties']['municipality'],f['properties']['name']) for f in selected.values()]},ensure_ascii=False))
