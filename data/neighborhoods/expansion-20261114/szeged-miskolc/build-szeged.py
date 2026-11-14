#!/usr/bin/env python3
"""Fast source-map estimates under the user's 2026-11-14 collection policy.

No place-point circles are used. Visible source interiors are flood-filled;
occlusions and small broken strokes are completed with explicit hand traces.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label, binary_fill_holes
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union, transform
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / 'data/neighborhoods/sources/municipal-szeged-raw-next'
IMAGE = SOURCE / 'henits-p24-xref249.jpeg'
REGISTRATION = SOURCE / 'registration.json'
URL = 'https://doktori.bibl.u-szeged.hu/id/eprint/1759/1/doktori_HL.pdf'
UNITS = [
 (1,'Történelmi városközpont',(662,373)), (2,'Belső városrész',(619,374)),
 (3,'Alsóváros',(555,510)), (4,'Móraváros',(549,413)),
 (5,'Rókus-Móraváros',(571,328)), (6,'Rókus',(627,298)),
 (7,'Ófelsőváros',(695,280)), (8,'Újszeged kertváros',(852,454)),
 (9,'Fodorkert',(719,181)), (10,'Füvészkert',(752,546)),
 (11,'Marostő',(898,506)), (12,'Tápé',(936,318)),
 (13,'Petőfitelep',(842,232)), (14,'Új-Petőfitelep',(792,116)),
 (15,'Baktó',(684,77)), (16,'Béketelep',(516,166)),
 (17,'Gyálarét',(428,781)), (18,'Szőreg',(932,738)),
 (19,'Klebelsberg-telep',(457,584)), (20,'Kecskés-telep',(405,512)),
 (21,'Szentmihály',(274,650)), (22,'Felsőváros',(787,289)),
 (23,'Tarján',(751,220)), (24,'Makkosháza',(670,180)),
 (25,'Északi városrész',(651,234)), (26,'Újrókus',(588,192)),
 (27,'Újszőreg',(869,612)), (28,'Odessza',(722,450)),
 (29,'Sárga üdülőtelep',(900,354)), (30,'Tömörkény-üdülőtelep',(848,342)),
 (31,'Villanegyed',(773,404)), (32,'Belső ipari övezet',(498,324)),
 (33,'Tiszavirág üdülőtelep',(1031,280)),
 (34,'Külső ipari övezet',(371,252)), (35,'Kiskundorozsma',(132,177)),
 (37,'Bodomi kiskertek',(214,743)), (38,'Ballagitói kiskertek',(535,610)),
 (39,'Gyálaréti kiskertek',(403,846)), (40,'Marostői kiskertek',(877,569)),
 (41,'Szőregi kiskertek',(993,632)), (42,'Tápéi kiskertek',(878,179)),
 (43,'Tompaszigeti kiskertek',(429,650)),
]
# Native image coordinates, x-right/y-down. These approximate the visible
# black outline, interpolating through labels or breaks without a point buffer.
MANUAL = {
 12:[[891,220],[902,245],[913,258],[926,268],[936,279],[947,269],
     [958,279],[971,261],[983,275],[997,259],[1005,269],[1026,251],
     [1043,268],[1023,282],[1005,305],[993,326],[981,340],[965,351],
     [948,359],[929,361],[905,353],[865,342],[843,334],[864,288],
     [877,254],[884,225]],
 27:[[819,573],[833,582],[855,591],[879,599],[901,611],[919,623],
     [939,639],[930,660],[910,651],[891,642],[896,633],[873,626],
     [847,611],[822,592]],
 29:[[866,342],[881,345],[902,350],[928,359],[924,365],[902,360],
     [882,354],[865,349]],
 30:[[832,329],[844,332],[864,338],[865,347],[848,343],[833,337]],
 33:[[1011,305],[1020,286],[1027,273],[1036,270],[1043,279],
     [1036,288],[1023,297]],
 37:[[205,717],[221,726],[242,748],[215,770],[198,749]],
}

def write(path, value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def raster_union(mask):
 runs=[]
 for y,row in enumerate(mask):
  d=np.diff(np.r_[False,row,False].astype(int))
  runs.extend(box(int(a),y,int(b),y+1) for a,b in zip(np.where(d==1)[0],np.where(d==-1)[0]))
 return unary_union(runs)

def main():
 rgb=np.array(Image.open(IMAGE).convert('RGB'))
 components,count=label(~(rgb.max(2)<80))
 edge=set(np.r_[components[0],components[-1],components[:,0],components[:,-1]])|{0}
 registration=json.loads(REGISTRATION.read_text())
 matrix=np.array(registration['pixelToEovMatrix'])
 offset=np.array(registration['pixelToEovOffset'])
 inv=Transformer.from_crs(23700,4326,always_xy=True)
 def project(x,y,z=None):
  coords=matrix@np.array([x,y])+offset[:,None] if np.ndim(x) else matrix@np.array([x,y])+offset
  return inv.transform(coords[0],coords[1])
 pixels={};records=[];features=[]
 for number,name,(x,y) in UNITS:
  if number in MANUAL:
   geom=Polygon(MANUAL[number]);method='manual_visible_map_outline'
   construction='Hand trace of visible source boundary; label-covered/broken segments linearly interpolated.'
  else:
   ids=Counter(components[y-11:y+12,x-11:x+12].ravel())
   choices=[(i,c) for i,c in ids.items() if i not in edge]
   if not choices:raise ValueError(f'No enclosed source interior: {number} {name}')
   chosen=max(choices,key=lambda pair:pair[1])[0]
   mask=binary_fill_holes(components==chosen)
   geom=raster_union(mask).simplify(0.8,preserve_topology=True)
   if geom.geom_type!='Polygon' or geom.area<500:raise ValueError(f'Unexpected source interior: {number} {name}')
   method='source_map_interior_estimate'
   construction='Dark-stroke flood fill, text holes filled, 0.8 native-pixel topology-preserving simplification.'
  if number==21:
   # The printed 21/37 divider has a small gap. Keep Szentmihály from
   # inheriting Bodom by cutting along the explicitly traced divider.
   geom=geom.difference(Polygon(MANUAL[37]));construction+=' Bodom separator completed with explicit hand trace.'
  if not geom.is_valid or geom.is_empty:raise ValueError(f'Invalid pixel geometry: {name}')
  world=transform(project,geom)
  if not world.is_valid or world.is_empty:raise ValueError(f'Invalid world geometry: {name}')
  pixels[number]=geom
  aliases={9:['Fodor-kert'],10:['Fűvészkert'],14:['Új-Petőfi-telep','Újpetőfitelep'],
           19:['Klebelsbergtelep','Klebersberg-telep'],20:['Kecskés István-telep'],
           37:['Bodom'],38:['Ballagi-tói kiskertek']}.get(number,[])
  note=''
  if number==37:note='Bodomi(27) is a body-text numbering typo: the southwestern cell37 matches the Bodom place position; cell27 remains Újszőreg as repeatedly keyed in the body.'
  if number in [32,34]:note='Descriptive inner/outer industrial-zone names distinguish the two visible gray cells; numbering differs in the companion KSH2014 map.'
  if number==8:note='The map calls this cell Újszeged; the qualified display name distinguishes it from the broader Újszeged union retained below.'
  p={'name':name,'municipality':'Szeged','aliases':aliases,'method':method,
     'estimated':True,'boundaryKind':'neighbourhood','sourceUnitNumber':number,
     'sourceUrl':URL,'sourcePath':str(IMAGE.relative_to(ROOT)),
     'sourcePage':24,'sourceFigure':'3.2','sourceYear':2003,'sourceReproducedYear':2013,
     'sourceCoordinateSpace':'native1174x1018image','construction':construction,
     'georeferencingPath':str(REGISTRATION.relative_to(ROOT)),
     'sourceNotes':note,'claimedAbsoluteAccuracyMetres':None,
     'rightsStatus':'Source map reuse rights not established; OSM road controls ODbL-1.0.',
     'source':{'url':URL,'provider':'Henits2013/KSH2003 source-map estimate',
               'path':str(IMAGE.relative_to(ROOT)),'sha256':digest(IMAGE),
               'license':'Source publication reuse terms unspecified; OSM road controls ODbL-1.0'}}
  features.append({'type':'Feature','id':f'expansion:szeged:henits2003:{number}',
                   'properties':p,'geometry':mapping(world)})
  records.append({'number':number,'name':name,'method':method,
                  'nativePixelArea':geom.area,'geometryValid':world.is_valid,'notes':note})
 # Source explicitly describes Belváros as1+2, Újszeged including its
 # villa/garden/neighbourhood/estate subdivisions, and the two industrial cells.
 for key,name,numbers in [('belvaros','Belváros',[1,2]),
                         ('ujszeged','Újszeged',[8,10,11,28,31]),
                         ('ipari','Ipari övezet',[32,34])]:
  geom=unary_union([pixels[n] for n in numbers])
  p=dict(features[0]['properties']);p.update({'name':name,'aliases':[],
   'method':'source_map_parent_union','sourceUnitNumbers':numbers,'sourceUnitNumber':None,
   'construction':'Union of explicitly related source-map subdivisions; overlaps with children intentionally retained.',
   'sourceNotes':'Named broader area and its finer subdivisions are both searchable under the user collection policy.'})
  features.append({'type':'Feature','id':'expansion:szeged:parent:'+key,
   'properties':p,'geometry':mapping(transform(project,geom))})
 write(HERE/'szeged-features.geojson',{'type':'FeatureCollection','features':features})
 write(HERE/'szeged-native-traces.geojson',{'type':'FeatureCollection',
  'coordinateSpace':'native image pixels, NOT WGS84',
  'features':[{'type':'Feature','properties':{'sourceUnitNumber':n},'geometry':mapping(g)} for n,g in pixels.items()]})
 write(HERE/'szeged-trace-report.json',{'municipality':'Szeged','featureCount':len(features),
   'sourceCellCount':len(UNITS),'parentUnionCount':3,'pointRadiusFallbackCount':0,
   'manualTraceCellNumbers':sorted(MANUAL),'records':records,
   'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in [IMAGE,REGISTRATION]],
   'unknowns':['The source map does not show a distinct36cell.','This is not a claim of complete current Szeged coverage.',
    'Map generalization and manual georeferencing make borders approximate.'],
   'dependencies':['numpy','Pillow','scipy','shapely','pyproj']})
 preview=Image.open(IMAGE).convert('RGB');draw=ImageDraw.Draw(preview)
 for n,g in pixels.items():
  geoms=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
  for poly in geoms:draw.line(list(poly.exterior.coords),fill=(220,0,180),width=2)
 preview.save(HERE/'szeged-traces-preview.png')
 print(json.dumps({'Szeged':len(features),'sourceCells':len(UNITS),'manualCompletions':len(MANUAL),'pointRadiusFallback':0}))

if __name__=='__main__':main()
