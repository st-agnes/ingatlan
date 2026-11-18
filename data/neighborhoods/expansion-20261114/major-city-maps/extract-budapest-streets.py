#!/usr/bin/env python3
"""Extract bounded named Soroksár streets from the already acquired countryPBF."""
import osmium,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
NAMES={'Homokszem utca','Könyves utca','Kő utca','Ugarszél út','Szentlőrinci út','Erzsébet utca','Dobó utca','Felső Duna sor','Táncsics Mihály utca','Csendes utca','Sínpár utca','Grassalkovich út','Rézöntő utca','Vecsés út'}
class Collect(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.features=[]
 def way(self,w):
  n=w.tags.get('name')
  if n not in NAMES:return
  coords=[[x.lon,x.lat] for x in w.nodes]
  if not coords or not any(19.09<x<19.22 and 47.37<y<47.44 for x,y in coords):return
  self.features.append({'type':'Feature','id':'osm:way:'+str(w.id),'properties':{'name':n,'sourceUrl':'https://www.openstreetmap.org/way/'+str(w.id),'version':w.version,'timestamp':str(w.timestamp),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'geometry':{'type':'LineString','coordinates':coords}})
c=Collect();c.apply_file(str(PBF),locations=True)
(HERE/'evidence/budapest-soroksar-streets.geojson').write_text(json.dumps({'type':'FeatureCollection','sourcePbfSha256':hashlib.sha256(PBF.read_bytes()).hexdigest(),'features':c.features},ensure_ascii=False,separators=(',',':'))+'\n')
print(len(c.features),sorted({f['properties']['name'] for f in c.features}))
