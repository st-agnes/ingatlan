#!/usr/bin/env python3
"""One bounded final cohort of map-barrier cell estimates, not Voronoi areas."""
from collections import Counter
import gzip, hashlib, json, os, sys, time, unicodedata
from pathlib import Path
import tempfile
import osmium
from shapely import from_wkb
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, polygonize, transform
from shapely.strtree import STRtree
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[4]
DATA=ROOT/'data/neighborhoods'
OUT=Path(__file__).resolve().parent
PBF=Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF',str(ROOT/'.local/neighborhoods/hungary-latest.osm.pbf')))
CITIES=['Székesfehérvár','Nyíregyháza']
ROAD_KINDS={'motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','service'}
def enc(x):return (json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def write(name,x):(OUT/name).write_bytes(enc(x))
def load(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
def norm(x):return ''.join(c for c in unicodedata.normalize('NFD',x).casefold() if c.isalnum())
def main():
 start=time.monotonic();manifest=load(DATA/'sources/country-osm/manifest.json')
 saved_sources='--saved-sources' in sys.argv[1:]
 if any(a!='--saved-sources' for a in sys.argv[1:]):raise ValueError('Usage: extract.py [--saved-sources]')
 digest=manifest['input']['sha256'] if saved_sources else hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest()
 assert digest==manifest['input']['sha256']
 parents={f['properties']['name']:f for f in load(DATA/'sources/country-osm/municipalities.geojson.gz')['features'] if f['properties']['name'] in CITIES}
 parent_shapes={n:shape(f['geometry']) for n,f in parents.items()}
 bounds={n:g.bounds for n,g in parent_shapes.items()}
 labels=[f for f in load(DATA/'sources/country-osm/named-nodes.geojson.gz')['features'] if f['properties'].get('municipality') in CITIES]
 barrier_features=[];factory=osmium.geom.WKBFactory();stats=Counter()
 class Handler(osmium.SimpleHandler):
  def way(self,obj):
   tags=dict(obj.tags)
   if not(tags.get('highway') in ROAD_KINDS or tags.get('railway') in {'rail','light_rail','narrow_gauge'} or tags.get('waterway') in {'river','stream','canal'}):return
   try:
    pts=[(n.lon,n.lat) for n in obj.nodes]
    if len(pts)<2:return
    bb=(min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts))
    cities=[n for n,b in bounds.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
    if not cities:return
    geom=from_wkb(bytes.fromhex(factory.create_linestring(obj)))
    if geom.is_empty or not geom.is_valid:return
    ident='osm:way:'+str(obj.id)
    barrier_features.append({'type':'Feature','id':ident,'geometry':mapping(geom),'properties':{'name':tags.get('name'),'municipalities':cities,'source':{'osmType':'way','osmId':obj.id,'url':'https://www.openstreetmap.org/way/'+str(obj.id),'tags':tags,'version':obj.version,'timestamp':str(obj.timestamp),'pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}}})
   except (RuntimeError,ValueError):stats['failed_source_ways']+=1
 if saved_sources:
  barrier_features=load(OUT/'source-barriers.geojson')['features']
  assert all(f['properties']['source']['pbfSha256']==digest for f in barrier_features)
  labels=load(OUT/'source-labels.geojson')['features']
  parents={f['properties']['name']:f for f in load(OUT/'source-municipalities.geojson')['features']}
  parent_shapes={n:shape(f['geometry']) for n,f in parents.items()}
 else:
  with tempfile.TemporaryDirectory(prefix='town-barrier-cells-') as tmp:
   Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway')])
  write('source-barriers.geojson',{'type':'FeatureCollection','features':barrier_features})
  write('source-municipalities.geojson',{'type':'FeatureCollection','features':list(parents.values())})
  write('source-labels.geojson',{'type':'FeatureCollection','features':labels})
 print(json.dumps({'barrierWays':len(barrier_features),'elapsedSeconds':round(time.monotonic()-start,1)}),flush=True)
 forward=Transformer.from_crs(4326,23700,always_xy=True).transform
 inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
 existing=set()
 for filename in ['search-areas.geojson','neighborhoods.geojson','estimated-candidates.geojson']:
  path=DATA/filename
  if path.exists():
   for f in load(path)['features']:
    p=f['properties'];city=p.get('municipality');name=p.get('name')
    if city and name:existing.add((city,norm(name)))
 for cohort in ['machine','machine-footprints','machine-other-footprints']:
  for f in load(DATA/'expansion-20261114'/cohort/'features.geojson')['features']:
   p=f['properties'];existing.add((p['municipality'],norm(p['name'])))
 selection_path=OUT/'street-block-selection.json'
 frozen_selection={(r['municipality'],norm(r['name'])) for r in load(selection_path)['selected']} if selection_path.exists() else None
 all_candidates=[];city_summary=[]
 for city in CITIES:
  parent=transform(forward,parent_shapes[city]);local=[f for f in labels if f['properties']['municipality']==city]
  point_shapes=[transform(forward,shape(f['geometry'])) for f in local];tree=STRtree(point_shapes)
  roads=[f for f in barrier_features if city in f['properties']['municipalities']]
  lines=[parent.boundary]
  lines += [transform(forward,shape(f['geometry'])).intersection(parent) for f in roads]
  network=unary_union([g for g in lines if not g.is_empty]);cells=list(polygonize(network));counts=Counter()
  for i,cell in enumerate(cells):
   if not parent.covers(cell.representative_point()):continue
   if not(1_000<=cell.area<=800_000) or cell.area/parent.area>0.5:counts['outside_area_bounds']+=1;continue
   hits=[int(k) for k in tree.query(cell,predicate='covers')];keys={(city,norm(local[k]['properties']['name'])) for k in hits}
   if len(keys)!=1:counts['no_label' if not keys else 'multiple_labels']+=1;continue
   label=local[hits[0]];name=label['properties']['name'];key=city,norm(name)
   if not any(word in name.casefold() for word in ['lakópark','lakótelep','lakónegyed','lakókert']) and not(city=='Nyíregyháza' and name in ['KIs-Jósa','Tópart','Alvéges','Déli Alközpont','Északi alközpont','Kerti lak','Cúgosrész I.']):continue
   if frozen_selection is not None:
    if key not in frozen_selection:counts['not_in_frozen_selection']+=1;continue
   elif key in existing:counts['already_has_polygon']+=1;continue
   nearby=[]
   for f in roads:
    line=transform(forward,shape(f['geometry']))
    overlap=cell.boundary.intersection(line).length
    if overlap>25:nearby.append({'id':f['id'],'name':f['properties']['name'],'tags':f['properties']['source']['tags'],'boundaryOverlapMetres':round(overlap,1),'url':f['properties']['source']['url']})
   geo=transform(inverse,cell)
   assert geo.is_valid and not geo.is_empty
   feature={'type':'Feature','id':'physical-cell:'+city+':'+str(i),'geometry':mapping(geo),'properties':{
    'municipality':city,'name':name,'method':'physical_barrier_cell_estimate','estimated':True,'semanticFootprint':True,
    'candidateBoundaryKind':'neighbourhood','qualityScore':10,'pointRadiusFallback':False,
    'sourceUrl':label['properties']['source']['url'],'source':{'provider':'osm-physical-map-cell-inference','pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','barrierSourcePath':str((OUT/'source-barriers.geojson').relative_to(ROOT))},
    'nameEvidence':[{'coordinates':label['geometry']['coordinates'],'name':name,'sourceUrl':label['properties']['source']['url']}],
    'boundingSourceWays':nearby,'approximateAreaSquareMetres':round(cell.area,1),
    'approximationNote':'Actual OSM local and major street, railway, river/stream/canal courses and municipal boundary polygonized into a closed map cell containing one named quarter point. The cell is an approximate searchable area, not an observed complete quarter border. Only small housing-estate/local-unit names are selected; this can capture one physical street block within a broader named estate. Grade-separated crossings and local extent can differ. No nearest-point/Voronoi split, radius, buffer or convex hull.'}}
   all_candidates.append(feature);counts['single_name_missing_candidate']+=1
  city_summary.append({'municipality':city,'barrierWayCount':len(roads),'polygonizedCellCount':len(cells),'counts':dict(counts)})
 # Largest physically bounded cells first, with a round-robin across towns and
 # at most20newnames; this is one deliberately bounded follow-up cohort.
 remaining={city:sorted([f for f in all_candidates if f['properties']['municipality']==city],key=lambda f:-f['properties']['approximateAreaSquareMetres']) for city in CITIES}
 selected=[];seen=set()
 while any(remaining.values()) and len(selected)<80:
  for city in CITIES:
   if not remaining[city]:continue
   f=remaining[city].pop(0);key=(city,norm(f['properties']['name']))
   if key not in seen:selected.append(f);seen.add(key)
   if len(selected)>=80:break
 write('street-block-features.geojson',{'type':'FeatureCollection','features':selected})
 write('all-candidate-cells.geojson',{'type':'FeatureCollection','features':all_candidates})
 summary={'featureCount':len(selected),'municipalityCount':len({f['properties']['municipality'] for f in selected}),'municipalities':dict(Counter(f['properties']['municipality'] for f in selected)),'candidates':len(all_candidates),'cities':city_summary,'sourcePbfSha256':digest,'sourceLabelCount':len(labels),'sourceBarrierWays':len(barrier_features),'method':'physical_barrier_cell_estimate','circleOrVoronoiConstructed':0,'elapsedSeconds':round(time.monotonic()-start,2),'stats':dict(stats),'nationalCoveragePercentage':None}
 write('street-block-summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
