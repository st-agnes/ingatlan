#!/usr/bin/env python3
"""Actual anonymous buildings near two remaining former estates, not estimates."""
import gzip, hashlib, json, math, tempfile
from pathlib import Path
import osmium
from shapely import from_wkb
from shapely.geometry import Polygon, mapping

HERE=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
OUT=HERE/'residual-buildings'
targets=[t for c in json.loads((HERE/'tasks/shard-0.json').read_text())['municipalities'] for t in c['targets']
    if t['name'] in {'Árkosháza-puszta','Sandipuszta'}]
factory=osmium.geom.WKBFactory()
collections={t['name']:[] for t in targets}
pbfsha=hashlib.file_digest(PBF.open('rb'),'sha256').hexdigest()

class Handler(osmium.SimpleHandler):
    def way(self,obj):
        if not obj.is_closed() or not obj.nodes or not obj.nodes[0].location.valid():return
        x,y=obj.nodes[0].lon,obj.nodes[0].lat
        matches=[]
        for target in targets:
            lon,lat=target['pointCandidates'][0]['coordinates']
            if abs(x-lon)<1500/111320/math.cos(math.radians(lat)) and abs(y-lat)<1500/111320:
                matches.append(target['name'])
        if not matches:return
        try:
            g=Polygon(from_wkb(bytes.fromhex(factory.create_linestring(obj))).coords)
            if g.is_empty or not g.is_valid:return
            tags=dict(obj.tags)
            f={'type':'Feature','id':f'osm:way:{obj.id}','geometry':mapping(g),'properties':{
                'name':tags.get('name'),'tags':tags,'source':{'provider':'openstreetmap','osmType':'way','osmId':obj.id,
                'url':f'https://www.openstreetmap.org/way/{obj.id}','objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),
                'pbfSha256':pbfsha,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}}}
            for name in matches:collections[name].append(f)
        except (RuntimeError,ValueError):pass

with tempfile.TemporaryDirectory(prefix='residual-buildings-') as temp:
    Handler().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('building')])
OUT.mkdir(exist_ok=True)
for name,features in collections.items():
    path=OUT/('arkoshaza.geojson.gz' if name=='Árkosháza-puszta' else 'sandipuszta.geojson.gz')
    path.write_bytes(gzip.compress((json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n').encode(),mtime=0))
manifest={'targets':targets,'pbfSha256':pbfsha,'sourceRole':'Actual building context within 1.5 km rectangular viewports only. No neighbourhood inference.',
    'counts':{k:len(v) for k,v in collections.items()}}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(manifest['counts'],ensure_ascii=False))
