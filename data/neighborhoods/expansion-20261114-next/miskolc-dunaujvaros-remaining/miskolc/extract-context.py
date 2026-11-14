from pathlib import Path
import osmium,json
HERE=Path(__file__).resolve().parent
bbox=(20.65,48.045,20.84,48.13)
class H(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.lines=[];self.areas=[]
 def way(self,w):
  tags=dict(w.tags)
  if not any(k in tags for k in ('highway','railway','waterway','landuse','natural','building')):return
  try:cs=[(n.lon,n.lat) for n in w.nodes]
  except: return
  if not any(bbox[0]<=x<=bbox[2] and bbox[1]<=y<=bbox[3] for x,y in cs):return
  if len(cs)<2:return
  p={'id':w.id,**tags,'sourceUrl':f'https://www.openstreetmap.org/way/{w.id}'}
  if len(cs)>3 and cs[0]==cs[-1] and any(k in tags for k in ('landuse','natural','building')):
   self.areas.append({'type':'Feature','properties':p,'geometry':{'type':'Polygon','coordinates':[cs]}})
  if any(k in tags for k in ('highway','railway','waterway')):
   self.lines.append({'type':'Feature','properties':p,'geometry':{'type':'LineString','coordinates':cs}})
h=H();h.apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='flex_mem')
for kind,features in [('lines',h.lines),('areas',h.areas)]:
 (HERE/f'literal-local-{kind}.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
 print(kind,len(features),flush=True)
