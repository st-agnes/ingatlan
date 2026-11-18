import osmium,json,hashlib
from pathlib import Path
out=Path(__file__).resolve().parent;root=out.parents[3];pbf=root/'.local/neighborhoods/hungary-latest.osm.pbf'
expected='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
h=hashlib.sha256()
with pbf.open('rb') as stream:
 for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
assert h.hexdigest()==expected, 'Pinned OSM PBF changed'
# Bounds select reference objects only. They never generate or clip any boundary.
# Only ways with all original nodes selected are retained, complete and unchanged.
coords={};objects=[]
class N(osmium.SimpleHandler):
 def node(self,o):
  x,y=o.location.lon,o.location.lat
  if 16.786<x<16.802 and 46.875<y<46.896:
   coords[o.id]=(x,y)
   if o.tags: objects.append({'type':'Feature','id':f'osm:node:{o.id}','properties':{'osmType':'node','osmId':o.id,'version':o.version,'timestamp':str(o.timestamp),'tags':dict(o.tags)},'geometry':{'type':'Point','coordinates':[x,y]}})
N().apply_file(str(pbf));print('nodes',len(coords),flush=True)
class W(osmium.SimpleHandler):
 def way(self,o):
  ids=[n.ref for n in o.nodes]
  if not any(n in coords for n in ids):return
  if not all(n in coords for n in ids):return
  ps=[coords[n] for n in ids]
  if len(ps)<2:return
  typ='Polygon' if ps[0]==ps[-1] else 'LineString'
  objects.append({'type':'Feature','id':f'osm:way:{o.id}','properties':{'osmType':'way','osmId':o.id,'version':o.version,'timestamp':str(o.timestamp),'tags':dict(o.tags),'nodeRefs':ids},'geometry':{'type':typ,'coordinates':[ps] if typ=='Polygon' else ps}})
W().apply_file(str(pbf));print('objects',len(objects),flush=True)
(out/'hathaz-geographic-reference.geojson').write_text(json.dumps({'type':'FeatureCollection','features':objects},ensure_ascii=False,indent=2)+'\n')
