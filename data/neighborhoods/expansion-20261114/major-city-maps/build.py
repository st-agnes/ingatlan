#!/usr/bin/env python3
"""Expansion under broad approximate-search policy; historical/native geometries retained."""
import json, hashlib, collections, math
from pathlib import Path
import fitz
import numpy as np
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import Polygon, MultiPolygon, mapping, shape
from shapely.ops import transform, unary_union
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
FEATURES=[]
TO_WGS=Transformer.from_crs(23700,4326,always_xy=True).transform

def read(p): return json.loads((ROOT/p).read_text())
def polygon_only(g):
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 return unary_union([x for x in g.geoms if x.geom_type in ['Polygon','MultiPolygon']])
def put(name,city,g,method,sourcepaths,urls,**extra):
 if not g.is_valid:g=polygon_only(make_valid(g))
 assert g.geom_type in ['Polygon','MultiPolygon'] and g.is_valid and not g.is_empty,(name,g.geom_type)
 assert 16<g.bounds[0]<23 and 45<g.bounds[1]<49,(name,g.bounds)
 FEATURES.append({'type':'Feature','id':'expansion-majorcity:'+city+':'+name,'properties':{'name':name,'municipality':city,'method':method,'sourcePaths':sourcepaths,'evidenceUrls':urls,'estimated':True,'approximationNotes':'Historical source extents and approximate georeferencing accepted for broad property search; no survey or legal accuracy claimed.','sourceSha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sourcepaths},**extra},'geometry':mapping(g)})

def gyor():
 src='data/neighborhoods/sources/municipal-gyor-next/'
 pdf=fitz.open(ROOT/(src+'gyor-its.source.pdf')); drawings=pdf[268].get_drawings()
 beta=np.array(read(src+'independent-review.json')['georeferencing']['matrix'])
 # Manual crosswalk of actual black circuit numbers to blue drawing indices in figure97.
 # The separately retained map shows both source numbers and red native drawing indices.
 draw={1:92,2:81,3:84,4:79,5:94,6:41,7:83,8:78,9:45,10:76,11:96,12:93,13:90,14:88,15:36,16:75,17:40,18:97,19:44,20:43,21:86,22:73,23:23,24:28,25:24,26:31,27:30,28:82,29:91,30:89,31:39,32:34,33:72,34:95,35:87,36:85,37:27,38:29,39:25,40:42,41:26,42:38,43:35,44:77,45:33,46:32}
 names={1:'Belváros',2:'Nádorváros',3:'Kelet-Nádorváros',4:'Dél-Nádorváros',5:'Újváros',6:'Révfalu',7:'Adyváros',8:'Marcalváros I.',9:'Marcalváros II.',10:'József Attila lakótelep',11:'Gorkijváros',12:'Sziget',13:'Kelet-Révfalu',14:'Gyárváros 4.',15:'Jancsifalu',16:'Szabadhegy I.',17:'Nyugat-Újváros',18:'Pinnyéd',19:'Kisbácsa',20:'Bácsa',21:'Likócs',22:'Kismegyer',23:'Győrszentiván',24:'Gyirmót',25:'Ménfőcsanak I.',26:'Sárás',27:'Góré-dűlő',28:'Nyugat-Nádorváros',29:'Gyárváros 1.',30:'Gyárváros 2.',31:'Gyárváros 3.',32:'Ipari Park',33:'Raktárváros',34:'Mákos-dűlő',35:'Kiskút',36:'Déli iparterület',37:'Rabkert',38:'Bevásárlóközpont I.',39:'Győrszentiván-Kertváros',40:'Kikötő (győri rész)',41:'Nagyhegy',42:'Szabadhegy II.',43:'Iparterület',44:'Temető',45:'Bevásárlóközpont II.',46:'Ménfőcsanak II.'}
 groups={'Belváros':[1],'Újváros':[5,17,11,34],'Sziget':[12],'Pinnyéd':[18],'Révfalu':[6,13],'Kisbácsa':[19],'Bácsa':[20],'Sárás':[26],'Gyárváros':[29,30,31,14,35],'Likócs':[21],'Győrszentiván':[23,39,41,40],'Rabkert':[37],'Góré-dűlő':[27],'Nádorváros':[2,3,28,4,44,15,43],'Adyváros':[7],'Marcalváros':[8,9,45],'József Attila lakótelep':[10],'Szabadhegy':[16,42,36,33,32],'Kismegyer':[22],'Ménfőcsanak':[25,46,38],'Gyirmót':[24]}
 polygons={};repaired=[]
 for number,index in draw.items():
  coords=[]
  for item in drawings[index]['items']:
   assert item[0]=='l';a,b=tuple(item[1]),tuple(item[2])
   if not coords:coords.append(a)
   if coords[-1]!=a:coords.append(a)
   coords.append(b)
  native=Polygon(coords);g=transform(TO_WGS,Polygon((np.c_[np.array(coords),np.ones(len(coords))]@beta).tolist()))
  fixed=not g.is_valid
  if fixed:g=polygon_only(make_valid(g));repaired.append(number)
  polygons[number]=g
  # Generic cemetery/shopping facilities are preserved as source geometry but not invented neighborhood names.
  if number not in [38,43,44,45]:
   put(names[number],'Győr',g,'source_vector_georeferenced', [src+'gyor-its.source.pdf',src+'independent-review.json'],['https://gyor.hu/easy-docs/5dc9829cb6d4c'], sourceYear=2006,documentYear=2014,sourceCircuitNumber=number,sourceDrawingIndex=index,geometryRepair='make_valid_polygon_components' if fixed else None,sourceSubdivisionKind='named_planning_circuit')
 for name,ns in groups.items():
  if len(ns)==1:continue
  put(name,'Győr',unary_union([polygons[n] for n in ns]),'source_vector_group_union',[src+'gyor-its.source.pdf',src+'independent-review.json'],['https://gyor.hu/easy-docs/5dc9829cb6d4c'],sourceYear=2006,documentYear=2014,sourceCircuitNumbers=ns,sourceSubdivisionKind='parent_quarter',alternativeToIndividualCircuit=True)
 (HERE/'evidence/gyor-crosswalk.json').write_text(json.dumps({'sourcePrintedMapPage':269,'sourceTablePages':[271,272],'sourceDrawings':draw,'sourceCircuitNames':names,'quarterGroups':groups,'repairedSourceCircuitNumbers':repaired,'omittedGenericFacilityCircuitNumbers':[38,43,44,45]},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
 gyor()
 (HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 print(collections.Counter(f['properties']['municipality'] for f in FEATURES))
