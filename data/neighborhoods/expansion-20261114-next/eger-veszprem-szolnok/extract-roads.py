#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import osmium
HERE=Path(__file__).resolve().parent;PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
BOXES={'Eger':(20.335,47.86,20.41,47.962),'Veszprém':(17.87,47.065,17.95,47.125),'Szolnok':(20.12,47.12,20.25,47.22)}
PREFIX={'Eger':'eger','Veszprém':'veszprem','Szolnok':'szolnok'};ROADS={c:[] for c in BOXES};AREAS={c:[] for c in BOXES}
class Handler(osmium.SimpleHandler):
 def way(self,way):
  isroad=any(k in way.tags for k in ['highway','railway','waterway']);isarea=len(way.nodes)>3 and way.nodes[0].ref==way.nodes[-1].ref and any(k in way.tags for k in ['leisure','historic','natural','landuse','tourism'])
  if not isroad and not isarea:return
  try:lon,lat=way.nodes[0].lon,way.nodes[0].lat
  except osmium.InvalidLocationError:return
  for city,(left,bottom,right,top) in BOXES.items():
   if not left<=lon<=right or not bottom<=lat<=top:continue
   try:coords=[[node.lon,node.lat] for node in way.nodes]
   except osmium.InvalidLocationError:continue
   p={'name':way.tags.get('name'),'tags':dict(way.tags),'osmWayId':way.id,'nodeRefs':[node.ref for node in way.nodes],'timestamp':str(way.timestamp),'version':way.version,'sourceUrl':'https://www.openstreetmap.org/way/'+str(way.id)}
   if isroad:ROADS[city].append({'type':'Feature','id':'osm:way:'+str(way.id),'properties':p,'geometry':{'type':'LineString','coordinates':coords}})
   if isarea:AREAS[city].append({'type':'Feature','id':'osm:way:'+str(way.id),'properties':p,'geometry':{'type':'Polygon','coordinates':[coords]}})
Handler().apply_file(str(PBF),locations=True)
for city in BOXES:
 for kind,rows in [('roads',ROADS[city]),('areas',AREAS[city])]:
  (HERE/(PREFIX[city]+'-'+kind+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','source':'OSM Hungary 2026-11-12','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','features':rows},ensure_ascii=False,separators=(',',':'))+'\n')
 print(city,len(ROADS[city]),'roads',len(AREAS[city]),'closed source surfaces')
(HERE/'road-extraction.json').write_text(json.dumps({'sourcePbfSha256':hashlib.sha256(PBF.read_bytes()).hexdigest(),'sourceSnapshot':'2026-11-12T21:23:05Z','boundingBoxes':BOXES,'coordinatesUnmodified':True,'wayVersionsAndNodeReferencesRetained':True,'geometryClipped':False,'selection':'First source node inside specified extent. Actual closed ways only in area layer; no artificial closure or geometry repair.'},ensure_ascii=False,indent=2)+'\n')
