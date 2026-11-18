#!/usr/bin/env python3
"""One local country-PBF pass; preserve literal source roads for fine map estimates."""
from pathlib import Path
import json,hashlib
import osmium

HERE=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
BBOX={'Pécs':(18.14,46.015,18.29,46.125),'Szeged':(20.125,46.22,20.27,46.305)}
COLLECT={city:[] for city in BBOX}
class Handler(osmium.SimpleHandler):
 def way(self,way):
  if not any(k in way.tags for k in ['highway','railway','waterway']):return
  if len(way.nodes)<2:return
  try:lon,lat=way.nodes[0].lon,way.nodes[0].lat
  except osmium.InvalidLocationError:return
  for city,(left,bottom,right,top) in BBOX.items():
   if not left<=lon<=right or not bottom<=lat<=top:continue
   try:coords=[[node.lon,node.lat] for node in way.nodes]
   except osmium.InvalidLocationError:continue
   COLLECT[city].append({'type':'Feature','id':'osm:way:'+str(way.id),'properties':{'name':way.tags.get('name'),'tags':dict(way.tags),'osmWayId':way.id,'nodeRefs':[node.ref for node in way.nodes],'timestamp':str(way.timestamp),'version':way.version,'sourceUrl':'https://www.openstreetmap.org/way/'+str(way.id)},'geometry':{'type':'LineString','coordinates':coords}})
h=Handler();h.apply_file(str(PBF),locations=True)
for city,rows in COLLECT.items():
 path=HERE/('pecs-roads.geojson' if city=='Pécs' else 'szeged-roads.geojson')
 path.write_text(json.dumps({'type':'FeatureCollection','source':'OpenStreetMap Hungary snapshot 2026-11-12','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','features':rows},ensure_ascii=False,separators=(',',':'))+'\n')
 print(city,len(rows),path.stat().st_size)
(HERE/'road-extraction.json').write_text(json.dumps({'sourcePbfSha256':hashlib.sha256(PBF.read_bytes()).hexdigest(),'sourceSnapshot':'2026-11-12T21:23:05Z','featuresByMunicipality':{c:len(f) for c,f in COLLECT.items()},'coordinatesUnmodified':True,'wayVersionsRetained':True,'nodeReferencesAndCoordinatesRetained':True,'individualNodeVersionsRetained':False,'selection':'Ways with highway/railway/waterway and first node in stated small town extent; no geometry clipping.','boundingBoxes':BBOX},ensure_ascii=False,indent=2)+'\n')
