#!/usr/bin/env python3
"""Coarse Békéscsaba quarter estimates from retained municipal raster/OSM names.
No network required. No circular/point-radius shapes are generated.
"""
import json,gzip,hashlib
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,mapping,shape
from shapely import make_valid
from shapely.ops import transform
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];DATA=ROOT/'data/neighborhoods'
# Vertices are hand estimates in the municipal raster's original936x662pixel
# space. Internal lines follow visible road/canal/grid directions approximately;
# they are not presented as boundaries explicitly printed in the source image.
SPECS=[
 ('Kisrét',[(318,169),(391,61),(423,97),(441,99),(438,64),(466,50),(470,160),(486,177),(543,182),(589,167),(560,203),(525,243),(510,272),(483,247),(432,246),(402,253),(374,238),(353,213)],[]),
 ('Felsőnyomás',[(22,199),(77,171),(144,128),(217,187),(318,111),(359,83),(391,61),(318,169),(352,214),(375,241),(402,253),(406,299),(372,315),(328,308),(284,327),(229,351),(202,346),(186,309),(71,340),(60,260),(37,230)],[]),
 ('Nagyrét',[(525,244),(562,203),(591,167),(605,104),(639,113),(657,101),(751,111),(775,171),(812,156),(851,177),(881,224),(899,239),(895,285),(878,329),(900,349),(901,369),(871,352),(837,371),(812,387),(787,359),(749,354),(740,376),(717,375),(686,378),(653,379),(627,360),(591,355),(592,303),(577,277),(561,255)],[]),
 ('Fürjes',[(186,309),(205,349),(229,351),(285,328),(328,310),(361,328),(365,347),(355,361),(366,395),(380,401),(394,443),(372,449),(351,461),(319,464),(286,473),(239,455),(223,461),(231,489),(216,491),(235,452),(222,416),(214,390),(203,358)],[]),
 ('Kerek',[(216,621),(229,568),(232,511),(229,489),(286,473),(320,464),(352,461),(373,449),(395,443),(412,468),(450,450),(466,467),(477,493),(507,486),(523,514),(467,548),(402,564),(385,614),(318,615),(281,616),(281,620)],[]),
 ('Kenderföldek',[(458,447),(479,443),(495,447),(507,464),(515,479),(531,509),(518,516),(506,488),(478,494),(469,474)],[]),
 ('Belváros',[(481,315),(495,307),(514,311),(527,329),(527,340),(512,348),(491,343),(480,333)],[]),
 ('Oncsakertek',[(505,263),(540,251),(559,270),(570,286),(552,301),(526,302),(512,285)],[]),
 ('Dobozi úti kertek',[(579,242),(614,231),(645,251),(639,274),(613,290),(593,279)],[]),
 ('Kastélyszőlők',[(561,412),(586,409),(606,419),(623,441),(603,450),(581,438),(565,429)],[]),
 ('Békekertek',[(544,297),(571,288),(589,307),(592,328),(571,338),(552,326)],[]),
 ('Keletikertek',[(590,343),(616,340),(635,355),(641,371),(617,380),(597,371)],[]),
 ('Borjúrétikertek',[(611,378),(637,372),(659,388),(650,408),(624,412),(610,399)],[]),
 ('Nyugati kertváros',[(367,319),(395,307),(412,322),(423,340),(405,353),(383,349),(362,339)],[]),
 ('Áchim András-lakótelep',[(412,274),(436,264),(455,279),(458,296),(435,307),(415,299)],[]),
 ('Kazinczy-lakótelep',[(438,326),(454,323),(466,337),(462,349),(448,350),(438,340)],[]),
 ('Penza-lakótelep',[(503,335),(518,331),(530,340),(529,351),(516,356),(506,351)],[]),
 ('Millenniumi lakótelep',[(438,313),(449,311),(461,320),(459,330),(449,331),(438,326)],[]),
 ('Veszei kertek',[(740,337),(758,330),(779,342),(785,360),(774,370),(750,360)],[]),
 ('Makkoshát',[(460,405),(482,408),(505,417),(505,435),(486,449),(466,440)],[]),
 ('Veszely',[(716,332),(734,330),(749,340),(743,356),(727,361),(714,348)],[]),
 ('Tabán',[(463,311),(478,309),(491,316),(489,327),(476,332),(464,325)],[]),
 ('Felsővég',[(450,288),(472,285),(491,298),(491,313),(472,322),(453,312)],[]),
 ('Alsóvég',[(476,342),(496,344),(509,355),(506,370),(489,375),(476,361)],[]),
 ('Északi ipartelep',[(433,246),(482,246),(508,254),(503,268),(486,281),(461,274),(437,264)],[]),
 ('Déli iparterület',[(467,369),(485,375),(503,386),(506,407),(485,416),(466,405)],[]),
]
def encode(d):return json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def build():
 proof=json.loads((DATA/'sources/municipal-east/bekescsaba-geometry-proof.json').read_text());A=np.array(proof['affineToEov']['matrix']);b=np.array(proof['affineToEov']['offset']);rev=Transformer.from_crs(23700,4326,always_xy=True)
 def world(x,y,z=None):return rev.transform(A[0,0]*np.asarray(x)+A[0,1]*np.asarray(y)+b[0],A[1,0]*np.asarray(x)+A[1,1]*np.asarray(y)+b[1])
 points=json.loads(gzip.decompress((DATA/'sources/country-osm/named-nodes.geojson.gz').read_bytes()))['features'];points={f['properties']['name']:f for f in points if f['properties'].get('municipality')=='Békéscsaba'}
 fs=[];spec=[];url='https://bekescsaba.hu/uploads/files/images/Teljes-varos-kitoeltoett.webp'
 for i,(name,vertices,aliases) in enumerate(SPECS):
  p=Polygon(vertices);fixed=not p.is_valid
  if fixed:p=make_valid(p)
  geo=transform(world,p);assert geo.is_valid and geo.geom_type in ['Polygon','MultiPolygon']
  assert 20<geo.bounds[0]<geo.bounds[2]<22 and 46<geo.bounds[1]<geo.bounds[3]<48
  prop={'municipality':'Békéscsaba','name':name,'aliases':aliases,'estimated':True,'method':'map_partition_estimate','candidateBoundaryKind':'neighbourhood','boundaryKind':'neighbourhood','qualityScore':30,'sourcePeriod':'Undated municipal neighborhood map, acquired2026-11-13; historical/current extent not guaranteed','sourceUrl':url,'evidenceUrls':[url,'https://bekescsaba.hu/terkepek'],'sourcePath':'data/neighborhoods/sources/municipal-east/bekescsaba-quarters-map.webp','sourceSha256':proof['sourceSha256'],'absoluteAccuracyMetres':None,'coordinateReferenceSystem':'EPSG:4326','approximationNote':'Coarse manual subdivision estimate using the retained municipal map outer/colored built-up outlines, visible road/canal/grid directions and local place positions. These INTERNAL lines are inferred; the municipal image does not explicitly delineate every listed subquarter. No circle/Voronoi generated.','georeferencingMethod':'Existing municipal-perimeter affine fit in EPSG23700, converted toEPSG4326','source':{'provider':'municipal-map-plus-osm-name-inference','url':url,'sourceImage':'data/neighborhoods/sources/municipal-east/bekescsaba-quarters-map.webp','sourceImageSha256':proof['sourceSha256'],'license':'Source map reuse licence not identified; OSM-derived name/placement ODbL-1.0'}}
  if name in points:prop['nameEvidence']={'name':name,'coordinates':points[name]['geometry']['coordinates'],'osmUrl':points[name]['properties']['source'].get('url')}
  else:prop['nameEvidence']={'name':name,'kind':'literal municipal map label'}
  fs.append({'type':'Feature','id':f'expansion:bekescsaba:additional:{i+1}','properties':prop,'geometry':mapping(geo)})
  spec.append({'municipality':'Békéscsaba','name':name,'sourcePixelVertices':vertices,'selfIntersectionResolved':fixed})
 return fs,spec
if __name__=='__main__':
 fs,spec=build();fc={'type':'FeatureCollection','features':fs};summary={'schemaVersion':1,'status':'additional_packet_ready','featureCount':len(fs),'municipalities':{'Békéscsaba':len(fs)},'distinctCityNames':len({(f['properties']['municipality'],f['properties']['name']) for f in fs}),'method':'rough map subdivision inference; unprinted internal boundary segments explicitly marked estimated','pointRadiusFallbacks':0,'geometryAllValid':True,'old48PacketModified':False,'reproduce':'python3 reproduce-additional.py (numpy,shapely,pyproj)'}
 for name,d in [('additional-features.geojson',fc),('additional-summary.json',summary),('additional-pixel-specifications.json',spec)]: (OUT/name).write_text(encode(d))
 print(encode(summary))
