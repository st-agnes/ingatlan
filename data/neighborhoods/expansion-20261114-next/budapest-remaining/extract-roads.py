#!/usr/bin/env python3
"""One local PBF scan; compressed complete source ways split into four sectors."""
from pathlib import Path
import gzip,json,tempfile
import osmium
HERE=Path(__file__).resolve().parent
groups={s:[] for s in ['northwest','northeast','southwest','southeast']}
class Reader(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags)
  if not (t.get('highway') or t.get('waterway') or t.get('railway')):return
  try:cs=[[n.lon,n.lat] for n in w.nodes]
  except osmium.InvalidLocationError:return
  if not any(18.84<x<19.37 and 47.34<y<47.65 for x,y in cs):return
  if len(cs)<2:return
  x=sum(c[0] for c in cs)/len(cs);y=sum(c[1] for c in cs)/len(cs)
  sector=('north' if y>=47.50 else 'south')+('west' if x<19.07 else 'east')
  groups[sector].append({'type':'Feature','id':'osm:way:'+str(w.id),'geometry':{'type':'LineString','coordinates':cs},'properties':{'name':t.get('name'),'source':{'url':'https://www.openstreetmap.org/way/'+str(w.id),'osmType':'way','osmId':w.id,'tags':t,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','geometryUnmodified':True,'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'}}})
with tempfile.TemporaryDirectory() as tmp:
 Reader().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf',locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','waterway','railway')])
for sector,fs in groups.items():
 payload=(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n').encode()
 with (HERE/(sector+'-source-roads.geojson.gz')).open('wb') as out:
  with gzip.GzipFile(filename='',fileobj=out,mode='wb',mtime=0) as z:z.write(payload)
 print(sector,len(fs),'source ways',len(payload),'uncompressed bytes',flush=True)
