#!/usr/bin/env python3
"""Archive two cities' actual street/campus source geometry for coarse local tracing."""
from pathlib import Path
import json,gzip,tempfile,hashlib
import osmium
from shapely import from_wkb
from shapely.geometry import shape,mapping

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
DATA=ROOT/'data/neighborhoods'
parents={f['properties']['name']:f for f in json.loads(gzip.decompress((DATA/'sources/country-osm/municipalities.geojson.gz').read_bytes()))['features'] if f['properties']['name'] in ['Debrecen','Kecskemét']}
bounds={n:shape(f['geometry']).bounds for n,f in parents.items()}
manifest=json.loads((DATA/'sources/country-osm/manifest.json').read_text());digest=hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest();assert digest==manifest['input']['sha256']
factory=osmium.geom.WKBFactory();roads=[];areas=[]
def matching(bb):return [n for n,b in bounds.items() if not(bb[2]<b[0] or bb[0]>b[2] or bb[3]<b[1] or bb[1]>b[3])]
def source(obj,kind,ident,tags):return {'provider':'openstreetmap','osmType':kind,'osmId':ident,'url':f'https://www.openstreetmap.org/{kind}/{ident}','tags':tags,'version':obj.version,'timestamp':str(obj.timestamp),'pbfSha256':digest,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
class Handler(osmium.SimpleHandler):
    def way(self,obj):
        tags=dict(obj.tags)
        if not any(tags.get(k) for k in ['highway','railway','waterway']):return
        if tags.get('highway') in ['footway','path','steps','cycleway','corridor','pedestrian','bridleway','proposed','construction']:return
        try:
            pts=[(n.lon,n.lat) for n in obj.nodes]
            if len(pts)<2:return
            bb=[min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
            cities=matching(bb)
            if not cities:return
            g=from_wkb(bytes.fromhex(factory.create_linestring(obj)))
            if not g.is_valid:return
            roads.append({'type':'Feature','id':'osm:way:'+str(obj.id),'properties':{'name':tags.get('name'),'municipalities':cities,'source':source(obj,'way',obj.id,tags)},'geometry':mapping(g)})
        except (RuntimeError,ValueError):pass
    def area(self,obj):
        tags=dict(obj.tags)
        if not tags.get('landuse') and tags.get('aeroway')!='aerodrome':return
        try:
            g=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
            if not g.is_valid:return
            cities=matching(g.bounds)
            if not cities:return
            kind='way' if obj.from_way() else 'relation';ident=obj.orig_id()
            areas.append({'type':'Feature','id':f'osm:{kind}:{ident}','properties':{'name':tags.get('name'),'municipalities':cities,'source':source(obj,kind,ident,tags)},'geometry':mapping(g)})
        except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='deb-kecs-context-') as tmp:
    Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','landuse','aeroway')])
for name,features in [('context-roads.geojson',roads),('context-source-areas.geojson',areas),('context-municipalities.geojson',list(parents.values()))]:
    (HERE/name).write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'roads':len(roads),'sourceAreas':len(areas)}),flush=True)
