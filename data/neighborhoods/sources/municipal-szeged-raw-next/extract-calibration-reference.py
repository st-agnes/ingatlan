"""Select complete actual Szeged major roads and Tisza reference from local PBF."""
from pathlib import Path
import json,hashlib
import osmium
from shapely.geometry import LineString,box,mapping
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
EXPECTED='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
assert sha(PBF)==EXPECTED
names=['Belvárosi híd','Bertalan híd','Tisza Lajos körút','Római körút','Londoni körút','Moszkvai körút','Párizsi körút','Brüsszeli körút','Kossuth Lajos sugárút','József Attila sugárút','Petőfi Sándor sugárút','Dorozsmai út','Szabadkai út','Bajai út','Algyői út','Kálvária sugárút','Budapesti körút','Makkosházi körút','Rókusi körút','Temesvári körút','Bécsi körút','Csongrádi sugárút','Szegedi út','Tisza','Híd utca','Székely sor','Derkovits fasor','Aradi vértanúk tere','Kelemen László utca','Felső Tisza-part','Alsó kikötő sor','Népkert sor','Boldogasszony sugárút','Izabella híd']
ways={};ids=set()
for w in osmium.FileProcessor(str(PBF),entities=osmium.osm.WAY).with_filter(osmium.filter.TagFilter(*[('name',n) for n in names])):
 ns=[n.ref for n in w.nodes];t=dict(w.tags)
 if len(ns)<2 or not(t.get('highway') or t.get('waterway')):continue
 ways[w.id]={'nodeRefs':ns,'tags':t,'objectVersion':w.version,'objectTimestamp':str(w.timestamp)};ids.update(ns)
coords={}
for n in osmium.FileProcessor(str(PBF),entities=osmium.osm.NODE).with_filter(osmium.filter.IdFilter(ids)):
 assert n.location.valid();coords[n.id]=[n.location.lon,n.location.lat]
assert set(coords)==ids
bbox=box(20.0,46.18,20.25,46.32);features=[]
for ident,w in sorted(ways.items()):
 g=LineString([coords[n] for n in w['nodeRefs']])
 if not g.intersects(bbox):continue
 p={'name':w['tags'].get('name'),'source':{'provider':'OpenStreetMap','osmType':'way','osmId':ident,'url':f'https://www.openstreetmap.org/way/{ident}','pbfSha256':EXPECTED,**w,'geometryUnmodified':True,'geometryProcessing':'Complete original node sequence; selection bounds never used for clipping or generating a contour.','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}}
 features.append({'type':'Feature','id':f'osm:way:{ident}','properties':p,'geometry':mapping(g)})
(ROOT/'.local/neighborhoods/szeged-raw-review/henits2013/calibration-geographic-reference-local-only.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n')
proof={'schemaVersion':1,'pbfPath':str(PBF.relative_to(ROOT)),'pbfSha256':EXPECTED,'countryNamedWaysExamined':len(ways),'countrySourceNodesResolved':len(coords),'completeSelectedReferenceWays':len(features),'selectedNames':names,'filterBoundsWgs84':[20.0,46.18,20.25,46.32],'boundsSelectOnlyNotGeometry':True,'sourcePlacePointsUsedForFit':False,'networkUsed':False,'globalRegistryModified':False}
(P/'calibration-reference-extraction-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'ways':len(features),'names':sorted({f['properties']['name'] for f in features})}))
