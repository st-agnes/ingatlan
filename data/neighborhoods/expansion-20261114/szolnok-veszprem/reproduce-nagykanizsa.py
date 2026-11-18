#!/usr/bin/env python3
"""Nagykanizsa rough road/built-up footprint estimates from retained local maps."""
import json,gzip,hashlib
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,mapping,shape,Point
from shapely.ops import transform
from shapely import make_valid
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];DATA=ROOT/'data/neighborhoods'
URL='https://nagykanizsa.hu/letoltesek/2024-04/68_870_nagykanizsa_megyei_jogu_varos_fenntarthato_varosfejlesztesi_strategia.pdf'
BASE_URL='https://merretekerjek.hu/'
REGIONAL=[
 ('Palin',[(390,287),(406,287),(420,303),(425,336),(421,371),(413,390),(400,383),(394,350),(389,323)]),
 ('Kiskanizsa',[(279,473),(312,467),(342,474),(378,497),(369,516),(343,533),(300,526),(280,507)]),
 ('MAORT-telep',[(403,521),(442,523),(455,545),(438,561),(412,550),(398,537)]),
 ('Ligetváros',[(385,601),(425,598),(443,623),(436,645),(409,645),(390,631)]),
 ('Miklósfa',[(397,649),(442,647),(468,675),(452,690),(421,686),(401,675)]),
 ('Bagola',[(508,610),(532,610),(558,632),(547,651),(521,644),(504,630)]),
 ('Nagyfakos',[(649,597),(675,602),(691,618),(678,628),(658,624),(644,612)]),
 ('Kisfakos',[(599,578),(617,577),(637,593),(629,607),(610,604),(595,592)]),
 ('Sánc',[(502,505),(530,504),(548,520),(541,540),(520,538),(500,521)]),
 ('Szabadhegy',[(500,448),(552,441),(564,460),(551,481),(532,482),(511,472)]),
 ('Látóhegy',[(549,545),(578,543),(597,562),(588,580),(561,578),(544,562)]),
 ('Ipari park',[(397,407),(435,405),(453,420),(440,446),(405,442),(389,426)]),
]
CORE=[
 ('Északi városrész',[(93,27),(233,25),(396,27),(421,130),(397,196),(399,263),(281,256),(243,286),(168,298),(127,267),(112,209)]),
 ('Belváros',[(128,267),(168,298),(243,286),(280,256),(399,263),(410,309),(393,350),(385,394),(366,446),(239,469),(150,458),(145,400),(137,347)]),
 ('Északkeleti városrész',[(398,196),(421,130),(515,152),(572,166),(633,143),(648,204),(659,233),(621,248),(574,283),(507,300),(410,309),(399,263)]),
 ('Keleti városrész',[(648,204),(692,184),(749,172),(801,152),(842,157),(852,229),(856,295),(848,332),(784,331),(729,319),(654,321),(656,274)]),
 ('Thury-városrész',[(654,321),(729,319),(784,331),(848,332),(855,389),(854,448),(828,507),(776,512),(718,504),(651,496),(658,432)]),
 ('Katonarét',[(387,444),(438,454),(500,469),(558,477),(607,493),(651,496),(663,554),(657,590),(546,590),(499,580),(447,582),(413,554),(385,523),(373,486)]),
]
REG_ANCHORS=[('Palin',[404,320]),('Kiskanizsa',[334,490]),('Miklósfa',[426,668]),('Bagola',[532,632]),('Nagyfakos',[663,615]),('Kisfakos',[620,593]),('Látóhegy',[576,565]),('Szabadhegy',[532,464]),('Belváros',[430,494])]
CORE_ANCHORS=[('Északi városrész',[260,174]),('Belváros',[230,408]),('Északkeleti városrész',[476,228]),('Keleti városrész',[775,260]),('Thury-városrész',[742,433]),('Katonarét',[568,543])]
def encode(d):return json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 pts=json.loads(gzip.decompress((DATA/'sources/country-osm/named-nodes.geojson.gz').read_bytes()))['features'];points={f['properties']['name']:f for f in pts if f['properties'].get('municipality')=='Nagykanizsa'}
 fwd=Transformer.from_crs(4326,23700,always_xy=True);rev=Transformer.from_crs(23700,4326,always_xy=True);features=[];regs=[];specs=[]
 for key,fn,records,controls,page in [('regional','nagykanizsa-fvs-xref1086.jpeg',REGIONAL,REG_ANCHORS,151),('core','nagykanizsa-fvs-xref1091.jpeg',CORE,CORE_ANCHORS,152)]:
  anchors=[{'name':name,'sourcePixel':xy,'coordinates':points[name]['geometry']['coordinates'],'sourceOsmUrl':points[name]['properties']['source'].get('url')} for name,xy in controls]
  X=np.array([[*a['sourcePixel'],1] for a in anchors]);Y=np.array([fwd.transform(*a['coordinates']) for a in anchors]);M=np.linalg.lstsq(X,Y,rcond=None)[0];res=np.sqrt(np.sum((X@M-Y)**2,axis=1))
  regs.append({'key':key,'sourceMap':fn,'method':'approximate affine named-place correspondence fit in EOV','anchors':anchors,'pixelToEovMatrix':M.tolist(),'anchorResidualsMetres':res.tolist(),'anchorRmsMetres':float(np.sqrt(np.mean(res**2))),'absoluteAccuracyMetres':None,'note':'Label positions/OSM representative points are approximate area positions, not survey controls. Fit residual is not total boundary accuracy.'})
  def world(x,y,z=None):return rev.transform(np.asarray(x)*M[0,0]+np.asarray(y)*M[1,0]+M[2,0],np.asarray(x)*M[0,1]+np.asarray(y)*M[1,1]+M[2,1])
  for i,(name,vertices) in enumerate(records):
   pixel=Polygon(vertices);fixed=not pixel.is_valid
   if fixed:pixel=make_valid(pixel)
   geo=transform(world,pixel);assert geo.is_valid and geo.geom_type in ['Polygon','MultiPolygon'];assert 16<geo.bounds[0]<geo.bounds[2]<18 and 46<geo.bounds[1]<geo.bounds[3]<47
   point=points[name];nameEvidence={'name':name,'coordinates':point['geometry']['coordinates'],'osmUrl':point['properties']['source'].get('url')}
   source={'url':URL,'pdfPageOneBased':page,'nativeMap':str((OUT/fn).relative_to(ROOT)),'mapSha256':sha(OUT/fn),'basemapProviderUrl':BASE_URL,'provider':'municipal-document-basemap-inference','license':'Map image explicitly credits merretekerjek.hu; OSM-derived placement ODbL-1.0; map-specific reuse licence not identified.'}
   properties={'municipality':'Nagykanizsa','name':name,'estimated':True,'method':'map_partition_estimate','candidateBoundaryKind':'neighbourhood','boundaryKind':'neighbourhood','qualityScore':35,'sourcePeriod':'FVS2024 retained road map (original basemap snapshot date unknown)','sourceUrl':URL,'evidenceUrls':[URL,BASE_URL],'source':source,'nameEvidence':nameEvidence,'coordinateReferenceSystem':'EPSG:4326','absoluteAccuracyMetres':None,'approximationNote':'Coarse hand-inferred quarter footprint following built-up patches, main roads, railways and terrain visible in the retained street map. These are NOT quarter outlines explicitly drawn by the source. Regional outlying neighborhoods use visible settlement footprints; central parts use main-road divisions. Labels obscuring edges are bridged by eye.','pointRadiusFallback':False,'georeferencingMethod':'approximate affine named-place correspondence','sourceKey':'nagykanizsa-'+key}
   features.append({'type':'Feature','id':f'expansion:nagykanizsa:{key}:{i+1}','geometry':mapping(geo),'properties':properties});specs.append({'name':name,'mapKey':key,'nativePixelVertices':vertices,'selfIntersectionResolved':fixed,'namePointInsideEstimate':geo.covers(Point(point['geometry']['coordinates']))})
 return features,regs,specs
if __name__=='__main__':
 fs,regs,specs=build();summary={'schemaVersion':1,'featureCount':len(fs),'municipalities':{'Nagykanizsa':len(fs)},'method':'rough map built-up/road subdivision estimate; no source-defined quarter line claim','allGeometryValid':True,'pointRadiusFallbacks':0,'uncoveredNamedPoints':['Bajcsa (outside retained regional map extent)'],'original48AndAdditional26Unchanged':True,'namePointOutsideEstimates':[s['name'] for s in specs if not s['namePointInsideEstimate']]}
 for fn,d in [('nagykanizsa-features.geojson',{'type':'FeatureCollection','features':fs}),('nagykanizsa-summary.json',summary),('nagykanizsa-registration.json',regs),('nagykanizsa-pixel-specifications.json',specs)]: (OUT/fn).write_text(encode(d))
 print(encode(summary));print('RMS',[(r['key'],r['anchorRmsMetres']) for r in regs])
