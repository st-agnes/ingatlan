#!/usr/bin/env python3
"""Preserve actual local OSM landuse polygons, including unlabelled candidates."""
from pathlib import Path
import json,tempfile,time,os,hashlib
import osmium
from shapely import from_wkb
from shapely.geometry import mapping
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
PBF=Path('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
EXPECTED_HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
with PBF.open('rb') as file:
 assert hashlib.file_digest(file,'sha256').hexdigest()==EXPECTED_HASH,'Source PBF differs from frozen snapshot'
factory=osmium.geom.WKBFactory();features=[];start=time.monotonic()
class H(osmium.SimpleHandler):
 def area(self,obj):
  tags=dict(obj.tags)
  if not(tags.get('landuse') in {'residential','allotments','farmyard','industrial','construction','commercial'} or tags.get('leisure')=='park'):return
  try:
   geom=from_wkb(bytes.fromhex(factory.create_multipolygon(obj)))
   if geom.is_empty or not geom.is_valid:return
   x,y,xx,yy=geom.bounds
   if xx<21.48 or x>21.88 or yy<47.82 or y>48.08:return
   typ='way' if obj.from_way() else 'relation';ident=obj.orig_id()
   features.append({'type':'Feature','id':f'osm:{typ}:{ident}','properties':{'tags':tags,'sourceUrl':f'https://www.openstreetmap.org/{typ}/{ident}','objectVersion':obj.version,'objectTimestamp':str(obj.timestamp)},'geometry':mapping(geom)})
  except (RuntimeError,ValueError):pass
with tempfile.TemporaryDirectory(prefix='nyir-local-polygons-') as tmp:
 H().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(tmp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('landuse','leisure')])
(OUT/'source-landuse.geojson').write_text(json.dumps({'type':'FeatureCollection','sourcePbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'count':len(features),'seconds':time.monotonic()-start}))
