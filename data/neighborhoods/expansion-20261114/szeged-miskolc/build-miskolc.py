#!/usr/bin/env python3
"""Coarse hand estimates of fine quarters within the municipal source map.

Source-map outer group outlines are retained; hand-drawn internal separators
follow visible broad built-up/road transitions and the document's constituent
descriptions. These separators are estimates, NOT recovered KSH boundaries.
"""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw
from pyproj import Transformer
from shapely.geometry import Polygon,shape,mapping,box
from shapely.ops import transform

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=ROOT/'data/neighborhoods/sources/municipal-local-map-next'
URL='https://www.miskolc.hu/sites/default/files/dokumentumtar/mellekletek/2024-11/197_melleklet.pdf'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)

def main():
 reg=json.loads((SOURCE/'miskolc-registration.json').read_text())
 m=np.array(reg['matrixPixelToEov']);inverse=np.linalg.inv(m[:2].T)
 forward=Transformer.from_crs(23700,4326,always_xy=True)
 back=Transformer.from_crs(4326,23700,always_xy=True)
 def to_world(x,y,z=None):
  v=m[:2].T@np.array([x,y])+m[2][:,None] if np.ndim(x) else m[:2].T@np.array([x,y])+m[2]
  return forward.transform(v[0],v[1])
 def to_pixel(x,y,z=None):
  e=np.array(back.transform(x,y));v=inverse@(e-m[2][:,None])if np.ndim(x)else inverse@(e-m[2]);return v[0],v[1]
 source=json.loads((SOURCE/'miskolc-source-raster.geojson').read_text())
 parents={f['properties']['sourceUnitNumber']:transform(to_pixel,shape(f['geometry'])).simplify(.55,preserve_topology=True) for f in source['features']}
 # Source coordinate x-right/y-down. The manual open separators below are
 # extended only for clipping against the source parent; no radial fallback.
 cuts={
  'martin_szirma':[(700,237),(729,237),(757,241),(792,241),(831,238),(880,242)],
  'hejo_goromboly':[(580,307),(621,307),(658,301),(692,306),(727,303),(790,309)],
  'varga_komlo':[(460,240),(520,240),(550,230),(574,238),(594,243),(640,241)],
 }
 def north_of(line):return Polygon([(-100,-100),(1000,-100)]+list(reversed(line))+[(-100,line[0][1])])
 def split(parent,key,north):
  mask=north_of(cuts[key]);return parents[parent].intersection(mask) if north else parents[parent].difference(mask)
 specs=[
  ('martin','Martinkertváros',3,split(3,'martin_szirma',True),['Martin kertváros'],
   'Northern built-up part of source group3; south separator roughly follows the visible built-up/field transition toward Szirma.'),
  ('szirma','Szirma',3,split(3,'martin_szirma',False),[],
   'Southern settlement part of group3 around the Szirma built-up area; separator is approximate.'),
  ('hejocsaba','Hejőcsaba',4,split(4,'hejo_goromboly',True),[],
   'Northern part of group4 around Hejőcsaba; the source text distinguishes it from the southern Görömböly settlement.'),
  ('goromboly','Görömböly',4,split(4,'hejo_goromboly',False),[],
   'Southern part of group4 around Görömböly; broad visible urban fabric transition used for the approximate separator.'),
  ('vargahegy','Vargahegy',11,split(11,'varga_komlo',True),[],
   'Northern/eastern residential slope part of group11; internal separator manually estimated from the map context.'),
  ('komlosteto','Komlóstető',11,split(11,'varga_komlo',False),[],
   'Southern/western built-up part of group11; source identifies Komlóstető and its estate separately from Vargahegy.'),
  ('egyetem','Egyetemváros',9,parents[9].intersection(box(580,230,690,290)),[],
   'University campus in group9. Broad institutional block and adjoining grounds retained; source groups it with Ruzsin.'),
  ('ruzsin','Ruzsin',9,Polygon([(628,196),(649,195),(653,202),(651,214),(637,228),(621,236),(609,231),(623,215)]),[],
   'Hand outline of the garden/residential slope west of Avas north of the university. It overlaps adjacent source planning groups intentionally; no point circle or nearest-point partition.'),
 ]
 # More detailed named areas from the same map/table. The large planning
 # contours supply context; separators between their named constituents are
 # rough hand interpretations rather than claimed fine KSH linework.
 def part(parent,vertices):return parents[parent].intersection(Polygon(vertices))
 specs += [
  ('szentpeteri','Szentpéteri kapu',1,
   part(1,[(660,113),(750,113),(750,170),(660,170)]),['Szentpéterikapu'],
   'Southern built-up corridor of group1; the northern Zsarnai/industrial part is separated approximately.'),
  ('zsarnai','Zsarnai-telep',1,
   part(1,[(665,55),(750,55),(750,114),(665,114)]),['Zsarnaitelep','Zsarnai telep'],
   'Northern named settlement/industrial part of group1; source text and visible fabric distinguish it from Szentpéteri kapu.'),
  ('selyemret','Selyemrét',2,
   part(2,[(716,150),(750,149),(767,175),(746,195),(716,193)]),[],
   'Southwestern housing part of the large eastern source group2, around the visible estate south of the industrial zone.'),
  ('szondi','Szondi-telep',2,
   part(2,[(746,143),(790,141),(805,167),(774,183),(752,171)]),['Szondi telep'],
   'Built-up and industrial block east/northeast of Selyemrét, manually estimated within group2.'),
  ('tetemvar','Tetemvár',6,
   part(6,[(675,113),(705,117),(708,155),(675,158)]),[],
   'Eastern/southeastern old built-up slope of source group6, adjoining Belváros.'),
  ('babonyiberc','Bábonyibérc',6,
   part(6,[(626,25),(682,32),(681,112),(673,140),(643,142),(629,118)]),[],
   'Central/northern hillside of source group6; separator toward Tetemvár and Bodótető is rough.'),
  ('bodoteto','Bodótető',6,
   part(6,[(552,81),(626,90),(642,120),(644,154),(570,166)]),[],
   'Western/southwestern hillside of source group6; source table places Bodótető together with Bedegvölgy, fine separation remains approximate.'),
  ('vologda','Vologda',7,
   part(7,[(635,143),(660,145),(666,151),(662,163),(638,169)]),['Vologda lakótelep'],
   'Western/northwestern housing blocks of the source city-centre group7.'),
  ('jokai','Jókai-lakótelep',7,
   part(7,[(666,143),(684,144),(689,153),(677,161),(665,157)]),['Jókai lakótelep'],
   'Small northern city-centre estate; hand outline follows the broad built-up block visible on the municipal source map.'),
  ('belvaros','Belváros',7,
   part(7,[(668,155),(729,151),(730,191),(675,191),(666,176)]),[],
   'Central/eastern urban core inside group7. Fine cadastral or historic boundary not claimed.'),
  ('avasalja','Avasalja',7,
   part(7,[(633,167),(668,165),(679,176),(673,197),(630,198)]),[],
   'Southwestern old built-up and hillside portion of the city-centre group7.'),
  ('nepkert','Népkert',5,
   part(5,[(686,181),(712,181),(722,190),(718,204),(696,207),(686,197)]),[],
   'Northern park and adjoining urban blocks of group5; approximate broad park/neighbourhood footprint.'),
  ('csabaikapu','Csabai kapu',5,
   part(5,[(685,202),(705,201),(719,210),(705,234),(690,237),(681,220)]),['Csabaikapu'],
   'Southern urban corridor of group5; broad visible street/building transition used as estimate.'),
  ('kilian','Kilián',12,
   part(12,[(491,150),(531,152),(531,215),(491,218)]),['Kilián lakótelep'],
   'Western housing area of the central source group12, east of Diósgyőr.'),
  ('ujdiosgyor','Újdiósgyőr',12,
   part(12,[(529,148),(575,148),(580,218),(529,220)]),['Új Diósgyőr','Új-Diósgyőr'],
   'Middle industrial/residential part of source group12; hand-separated from Kilián and Győri kapu.'),
  ('gyorikapu','Győri kapu',12,
   part(12,[(574,147),(648,147),(649,218),(579,220)]),[],
   'Eastern residential corridor of source group12, approaching Belváros.'),
  ('diosgyor','Diósgyőr',15,
   part(15,[(451,169),(525,168),(527,234),(450,235)]),[],
   'Southeastern built-up part of the Diósgyőr western planning group; castle/urban district area broadly approximated.'),
  ('berekalja','Berekalja',15,
   part(15,[(371,165),(454,166),(455,235),(374,235)]),[],
   'Western/southwestern built-up part of source group15 around Berekalja.'),
  ('majlath','Majláth',15,
   part(15,[(358,90),(512,94),(515,168),(371,166)]),[],
   'Northern valley/settlement portion of the Diósgyőr western source group15. Broad terrain-context estimate, not a measured fine boundary.'),
 ]
 features=[];native=[]
 for ident,name,parent,geom,aliases,note in specs:
  if geom.is_empty or not geom.is_valid:raise ValueError('Invalid native estimate '+name)
  world=transform(to_world,geom)
  if not world.is_valid:raise ValueError('Invalid world estimate '+name)
  p={'name':name,'municipality':'Miskolc','aliases':aliases,
   'method':'manual_parent_partition_estimate' if ident!='ruzsin' else 'manual_map_context_estimate',
   'estimated':True,'boundaryKind':'neighbourhood','sourceParentUnitNumber':parent,
   'sourceUrl':URL,'sourcePath':str((SOURCE/'miskolc-p228-original.jpeg').relative_to(ROOT)),
   'sourcePage':228,'sourceYear':2014,'documentYear':2022,
   'sourceNotes':note,'construction':'Source planning outline plus coarse manually interpreted internal boundary. Fine KSH constituent geometry is not supplied by the source.',
   'claimedAbsoluteAccuracyMetres':None,'confidence':'low',
   'rightsStatus':'Source map reuse rights not established; OSM location/calibration references ODbL-1.0.',
   'source':{'url':URL,'provider':'Miskolc municipal source-map coarse inference',
    'path':str((SOURCE/'miskolc-p228-original.jpeg').relative_to(ROOT)),
    'sha256':digest(SOURCE/'miskolc-p228-original.jpeg'),
    'license':'Source publication reuse terms unspecified; OSM calibration references ODbL-1.0'}}
  features.append({'type':'Feature','id':'expansion:miskolc:coarse:'+ident,'properties':p,'geometry':mapping(world)})
  native.append({'type':'Feature','properties':{'name':name,'parent':parent},'geometry':mapping(geom)})
 write(HERE/'miskolc-features.geojson',{'type':'FeatureCollection','features':features})
 write(HERE/'miskolc-native-traces.geojson',{'type':'FeatureCollection','coordinateSpace':'native image pixels NOT WGS84','features':native})
 write(HERE/'miskolc-trace-report.json',{'municipality':'Miskolc','featureCount':len(features),
  'method':'Coarse source-map/manual internal partition estimates under user2026-11-14 policy.',
  'pointRadiusFallbackCount':0,'names':[f['properties']['name']for f in features],
  'manualSeparators':cuts,'allGeometryValid':True,
  'limitations':['The17group map is not a map of the32fine KSH constituents; new internal boundaries are explicitly estimates.',
  'These are coarse map-context estimates with unknown absolute accuracy; do not describe them as official boundaries.'],
  'inputs':[{'path':str((SOURCE/n).relative_to(ROOT)),'sha256':digest(SOURCE/n)}for n in ['miskolc-p228-original.jpeg','miskolc-registration.json','miskolc-source-raster.geojson','miskolc-source-semantics.json']]})
 im=Image.open(SOURCE/'miskolc-p228-original.jpeg').convert('RGB').resize((1768,1114));d=ImageDraw.Draw(im)
 for f in native:
  g=shape(f['geometry']);geoms=list(g.geoms) if g.geom_type=='MultiPolygon'else[g]
  for part in geoms:d.line([(x*2,y*2)for x,y in part.exterior.coords],fill=(255,0,180),width=3)
  c=g.representative_point();d.text((c.x*2,c.y*2),f['properties']['name'],fill='yellow',stroke_fill='black',stroke_width=1)
 im.save(HERE/'miskolc-traces-preview.png')
 print(json.dumps({'Miskolc':len(features),'pointRadiusFallbackCount':0}))

if __name__=='__main__':main()
