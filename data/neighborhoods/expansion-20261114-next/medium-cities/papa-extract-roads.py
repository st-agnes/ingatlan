#!/usr/bin/env python3
"""Extract current source streets for the documented Pápa street-boundary descriptions."""
from pathlib import Path
import gzip,json,os,tempfile,time
import osmium
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
PBF=Path(os.environ.get('OTTHONRA_NEIGHBORHOOD_PBF','/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf'))
data=ROOT/'data/neighborhoods/sources/country-osm'
parent=next(f for f in json.loads(gzip.decompress((data/'municipalities.geojson.gz').read_bytes()))['features'] if f['properties']['name']=='Pápa')
points=[f for f in json.loads(gzip.decompress((data/'named-nodes.geojson.gz').read_bytes()))['features'] if f['properties'].get('municipality')=='Pápa']
def all_coords(g):
    x=g['coordinates'];return [p for part in (x if g['type']=='MultiPolygon' else [x]) for ring in part for p in ring]
coords=all_coords(parent['geometry']);bounds=[min(p[0] for p in coords),min(p[1] for p in coords),max(p[0] for p in coords),max(p[1] for p in coords)]
rows=[];start=time.monotonic()
class H(osmium.SimpleHandler):
    def way(self,w):
        tags=dict(w.tags)
        if not any(k in tags for k in ['highway','railway','waterway']):return
        try:
            pts=[[n.lon,n.lat] for n in w.nodes]
            if len(pts)<2:return
            if not any(bounds[0]-.005<=x<=bounds[2]+.005 and bounds[1]-.005<=y<=bounds[3]+.005 for x,y in pts):return
            rows.append({'type':'Feature','id':'osm:way:'+str(w.id),'geometry':{'type':'LineString','coordinates':pts},
                'properties':{'name':tags.get('name'),'source':{'provider':'openstreetmap','osmId':w.id,'url':'https://www.openstreetmap.org/way/'+str(w.id),'tags':tags,'version':w.version,'timestamp':str(w.timestamp),'license':'ODbL-1.0'}}})
        except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='papa-roads-') as tmp:
    H().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway')])
for filename,features in [('papa-roads.geojson',rows),('papa-source-municipality.geojson',[parent]),('papa-name-points.geojson',points)]:
    (HERE/filename).write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'ways':len(rows),'points':len(points),'elapsedSeconds':round(time.monotonic()-start,1)},ensure_ascii=False))
