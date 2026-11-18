#!/usr/bin/env python3
"""Build deliberately coarse, source-map based WGS84 quarter polygons.

Dependencies: numpy, pyproj, shapely. Historical source dates and approximate
name-anchor georeferencing are explicit; these are not surveyed boundaries.
"""
import hashlib,json,math,gzip
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,mapping,shape
from shapely import make_valid
from shapely.ops import transform

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
DATA=ROOT/'data/neighborhoods'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def enc(d):return json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'

# Source-native pixel vertices, manually approximated by following the visible
# colored outlines. Small label/leader/stroke gaps are bridged, not audited.
# Maps are historical functional/local partitions, with overlaps allowed.
SZOLNOK=[
 ('Pletykafalu',[(107,175),(113,160),(123,148),(149,141),(179,146),(205,151),(194,164),(173,175),(151,192),(141,208),(137,197),(120,186)]),
 ('Széchenyi-lakótelep',[(211,87),(214,74),(224,64),(267,66),(267,90),(258,98),(245,97),(241,105),(233,97),(223,100)]),
 ('Északi ipari terület',[(153,110),(159,53),(171,55),(196,75),(223,100),(240,119),(198,127),(156,139),(156,119)]),
 ('Déli ipari terület',[(94,280),(110,256),(136,220),(150,201),(172,184),(198,172),(209,184),(232,187),(236,196),(230,205),(237,225),(222,259),(202,248),(187,273),(181,295),(182,303),(162,309),(145,319),(132,326),(111,355),(101,351)]),
 ('Belváros',[(244,139),(257,146),(278,149),(299,154),(291,164),(273,170),(254,175),(253,166),(248,154)]),
 ('Déli városközpont',[(210,159),(224,155),(246,151),(251,161),(255,177),(244,185),(229,183),(211,183),(208,173)]),
 ('Északi városközpont',[(245,121),(252,115),(267,111),(286,110),(286,131),(280,149),(256,146),(248,138)]),
 ('Mátyás király úti lakótelep',[(224,141),(231,134),(237,139),(231,144)]),
 ('Nagy Imre körúti lakótelep',[(215,149),(226,143),(236,144),(231,150),(222,154)]),
 ('József Attila úti lakótelep',[(207,160),(213,150),(224,154),(219,158)]),
 ('Tallinn lakótelep',[(286,111),(307,110),(313,126),(287,134)]),
 ('Várkonyi téri lakótelep',[(282,134),(292,133),(295,143),(300,154),(286,151)]),
 ('Zagyvaparti lakótelep',[(274,132),(281,130),(284,134),(288,135),(286,150),(278,149)]),
 ('Alcsi',[(308,111),(327,115),(347,122),(352,131),(361,132),(364,145),(336,153),(305,163),(295,144),(289,132),(312,126)]),
 ('Tiszaliget',[(246,198),(254,185),(271,179),(292,175),(326,172),(351,173),(348,183),(340,193),(306,199),(284,202),(272,210),(242,211)]),
 ('Alcsiszög',[(291,162),(313,162),(334,164),(352,168),(356,172),(331,171),(309,171),(291,174)]),
 ('Kertváros',[(293,200),(312,197),(330,194),(333,198),(315,219),(303,242),(299,240)]),
 ('Holt-Tisza parti üdülőterület',[(303,243),(317,218),(331,203),(340,201),(340,209),(336,216),(339,226),(332,246),(320,268),(320,288),(322,295),(316,293),(309,284),(304,266)]),
 ('Papírgyári lakótelep',[(219,217),(224,205),(229,206),(234,219),(229,224)]),
 ('TVM-lakótelep',[(158,307),(168,300),(173,304),(166,309)]),
 ('Szandaszőlős',[(279,331),(285,306),(293,263),(296,269),(296,282),(305,299),(319,305),(338,308),(337,316),(342,329),(345,333),(348,349),(351,365),(359,392),(355,393),(357,399),(318,393),(288,388),(285,383),(289,362),(289,333)]),
]
# Nine IVS groups from the 2008 map; the two disconnected compound groups
# are also represented by their individually labelled components.
VESZPREM_IVS=[
 ('Belváros',[(447,373),(462,392),(481,388),(492,399),(507,429),(488,444),(477,462),(464,466),(455,434),(444,413),(434,397)],'neighbourhood'),
 ('Dózsaváros',[(281,328),(315,339),(341,351),(369,337),(393,332),(445,333),(452,369),(434,392),(398,385),(371,375),(335,373),(302,354)],'neighbourhood'),
 ('Iparváros',[(255,292),(267,273),(301,265),(320,228),(343,238),(349,269),(359,245),(393,249),(410,233),(404,215),(427,198),(457,232),(448,262),(475,251),(484,235),(516,233),(521,250),(493,258),(499,306),(478,322),(448,332),(398,331),(370,337),(343,349),(308,332),(278,320)],'neighbourhood'),
 ('Jeruzsálemhegy',[(330,374),(368,378),(395,386),(434,393),(443,416),(423,443),(400,451),(353,451),(338,431),(332,405)],'neighbourhood'),
 ('Csatárhegy',[(157,342),(192,345),(209,319),(230,311),(252,320),(242,343),(226,376),(213,396),(186,381),(170,367)],'neighbourhood'),
 ('Egyetemváros',[(401,452),(424,444),(445,418),(455,436),(464,470),(477,463),(486,443),(502,461),(500,489),(520,493),(526,511),(540,518),(515,541),(501,553),(491,519),(458,523),(436,527),(412,512),(399,498)],'neighbourhood'),
 ('Cholnokyváros',[(486,443),(505,428),(502,397),(518,393),(547,377),(567,384),(576,397),(565,417),(556,452),(548,481),(548,500),(574,520),(549,543),(524,513),(505,491),(499,466)],'neighbourhood'),
 ('Jutasi úti menti lakóövezet',[(494,259),(517,253),(531,260),(544,300),(554,323),(568,340),(587,320),(598,310),(609,312),(618,341),(622,359),(594,369),(569,373),(561,382),(546,377),(521,392),(501,397),(490,377),(491,352),(484,332),(479,321),(498,306)],'planning_unit'),
 ('Kádárta',[(567,266),(575,253),(575,236),(593,219),(618,201),(635,210),(662,204),(652,190),(664,185),(665,205),(695,215),(707,230),(686,244),(687,260),(659,266),(644,259),(622,282),(609,291),(598,311),(576,291),(589,276)],'neighbourhood'),
 ('Gyulafirátót',[(594,85),(628,66),(679,49),(703,108),(683,112),(691,126),(675,126),(678,154),(658,153),(647,157),(626,166),(614,166),(606,145),(599,130),(608,119)],'neighbourhood'),
 ('Repülőtér',[(665,362),(713,346),(740,340),(768,301),(787,294),(809,307),(814,322),(780,332),(776,349),(758,354),(778,363),(785,430),(782,457),(793,481),(788,497),(747,496),(704,489),(681,484),(678,459),(666,446),(673,431),(664,410)],'local_area'),
]
# Municipal 2019 map: outer detached outlines follow blue dashes;
# central quarter divisions are coarse inferred lines following map roads,
# watercourses and the numbered-name placement, not surveyed boundaries.
VESZPREM_TAK=[
 ('Belváros',[(360,730),(400,715),(422,744),(416,781),(372,791),(349,762)]),
 ('Dózsaváros',[(200,679),(240,637),(310,641),(348,670),(372,701),(360,731),(331,747),(278,740),(250,713)]),
 ('Jeruzsálemhegy',[(331,748),(349,764),(372,791),(373,845),(346,861),(317,833),(326,815),(317,778)]),
 ('Egyetemváros',[(373,795),(415,781),(431,816),(441,852),(412,882),(367,891),(346,862),(373,845)]),
 ('Füredidomb',[(416,781),(451,789),(478,808),(469,847),(440,855),(431,816)]),
 ('Cholnokyváros',[(422,744),(478,725),(496,754),(511,796),(478,808),(451,789),(416,781)]),
 ('Újtelep',[(415,700),(476,689),(480,725),(422,744)]),
 ('Jutasi úti lakótelep',[(389,648),(450,636),(475,646),(477,690),(415,700),(390,685)]),
 ('Bakonyalja',[(384,602),(427,581),(435,612),(450,636),(389,648),(378,627)]),
 ('Jutaspuszta',[(329,569),(345,547),(369,574),(370,596),(356,604),(339,595)]),
 ('Csererdő',[(209,609),(225,575),(247,584),(236,599),(252,618),(244,634),(206,628)]),
 ('Iparváros',[(246,638),(274,615),(277,587),(303,591),(326,604),(341,603),(356,579),(380,579),(389,613),(380,642),(349,669),(308,643)]),
 ('Csatár',[(62,695),(103,696),(107,675),(134,665),(164,678),(141,707),(135,743),(115,751),(93,742)]),
 ('Szabadságpuszta',[(414,978),(439,969),(448,989),(423,1005)]),
 ('Kádárta',[(512,596),(525,566),(552,557),(564,534),(595,527),(619,549),(606,559),(624,563),(634,585),(619,598),(625,619),(593,622),(591,608),(554,609),(538,632),(512,658),(507,646),(529,618)]),
 ('Gyulafirátót',[(528,423),(560,403),(594,390),(603,410),(621,408),(637,446),(621,458),(593,471),(587,462),(575,496),(549,507),(539,502),(536,464),(545,448)]),
]

SZ_CONTROLS=[('Széchenyi-lakótelep',[240,81]),('Pletykafalu',[154,170]),('Szandaszőlős',[319,345]),('Alcsi városrész',[330,136]),('Kertváros',[314,219]),('Belváros',[269,159]),('TVM-lakótelep',[168,304])]
IVS_CONTROLS=[('Dózsaváros',[443,357]),('Iparváros',[395,288]),('Jeruzsálemhegy',[376,412]),('Egyetemváros',[443,498]),('Cholnokyváros',[535,446]),('Jutasi úti lakótelep',[517,342]),('Kádárta',[617,243]),('Gyulafirátót',[657,91]),('Csatárhegy',[210,353]),('Belváros',[471,415])]
TAK_CONTROLS=[('Gyulafirátót',[576,430]),('Kádárta',[576,587]),('Jutaspuszta',[357,575]),('Csererdő',[229,612]),('Iparváros',[316,651]),('Dózsaváros',[347,706]),('Belváros',[391,750]),('Szabadságpuszta',[428,985]),('Cholnokyváros',[466,781]),('Csatárhegy',[114,709])]
SOURCES={
 'szolnok':{'municipality':'Szolnok','mapPath':'sources/municipal-szolnok-foldi2012-next/figure9-native-pixels.png','url':'https://ktk.pte.hu/sites/ktk.pte.hu/files/images/kepzes/phd/Foldi%20Katalin%20-%20disszertacio.pdf','sourcePeriod':'KSH functional division 2003, reproduced by Földi Katalin 2012 thesis, Figure9/page72','mapSize':[441,539],'controls':SZ_CONTROLS,'features':SZOLNOK},
 'veszprem-ivs':{'municipality':'Veszprém','mapPath':'sources/municipal-veszprem-ivs2008-next/page10-native-map.jpeg','url':'https://veszprem.hu/wp-content/uploads/2023/09/VMJV-Integralt-Varosfejlesztesi-Strategia-2008.pdf','sourcePeriod':'Municipal IVS 2008-10-15, page10','mapSize':[931,662],'controls':IVS_CONTROLS,'features':VESZPREM_IVS},
 'veszprem-tak':{'municipality':'Veszprém','mapPath':'sources/municipal-veszprem-tak2019-next/page14-original.jpeg','url':'https://veszprem.hu/wp-content/uploads/2023/10/I-6_VMJV_TAK_2019_web.pdf','sourcePeriod':'Municipal TAK2019 page14 official-quarter name map','mapSize':[792,1087],'controls':TAK_CONTROLS,'features':VESZPREM_TAK},
}

def build():
 points=json.loads(gzip.decompress((DATA/'sources/country-osm/named-nodes.geojson.gz').read_bytes()))['features']
 forward=Transformer.from_crs(4326,23700,always_xy=True)
 reverse=Transformer.from_crs(23700,4326,always_xy=True)
 features=[];registrations=[];specifications=[]
 for key,source in SOURCES.items():
  matches={p['properties']['name']:p for p in points if p['properties'].get('municipality')==source['municipality']}
  anchors=[]
  for name,pixel in source['controls']:
   p=matches[name];coordinate=p['geometry']['coordinates'];metric=forward.transform(*coordinate)
   anchors.append({'name':name,'pixel':pixel,'coordinates':coordinate,'eov':metric,'osmUrl':p['properties']['source'].get('url')})
  X=np.array([[*p['pixel'],1] for p in anchors],float);Y=np.array([p['eov'] for p in anchors],float)
  matrix=np.linalg.lstsq(X,Y,rcond=None)[0]
  residuals=np.sqrt(np.sum((X@matrix-Y)**2,axis=1))
  def world(x,y,z=None):
   east=x*matrix[0,0]+y*matrix[1,0]+matrix[2,0];north=x*matrix[0,1]+y*matrix[1,1]+matrix[2,1]
   return reverse.transform(east,north)
  registrations.append({'sourceKey':key,'method':'approximate_affine_using_named_place_correspondences','anchors':anchors,'pixelToEovMatrix':matrix.tolist(),'anchorResidualsMetres':residuals.tolist(),'anchorRmsMetres':float(np.sqrt(np.mean(residuals**2))),'absoluteAccuracyMetres':None,'note':'Name locations are approximate area representatives, not physical survey controls. Residuals quantify fit to those representatives, not true boundary accuracy. Source map distortion and historical extent differences remain.'})
  for i,record in enumerate(source['features']):
   name,vertices=record[:2];kind=record[2] if len(record)>2 else 'neighbourhood'
   pixel=Polygon(vertices);fixed=not pixel.is_valid
   if fixed:pixel=make_valid(pixel)
   geo=transform(world,pixel)
   assert geo.is_valid and geo.geom_type in ['Polygon','MultiPolygon']
   assert 16<geo.bounds[0]<geo.bounds[2]<23 and 45<geo.bounds[1]<geo.bounds[3]<49
   sourceName=name;aliases=[]
   if name=='Szandaszőlős':sourceName='Szanda-szőlős';aliases=['Szanda-szőlős']
   if name=='Széchenyi-lakótelep':sourceName='Széchenyi lakótelep';aliases=['Széchenyi lakótelep']
   if name=='Csatár' and key=='veszprem-tak':aliases=['Csatárhegy']
   if name=='Alcsi':aliases=['Alcsi városrész']
   if name=='Tallinn lakótelep':aliases=['Tallinn városrész']
   if name=='József Attila úti lakótelep':aliases=['József Attila-lakótelep']
   p={'municipality':source['municipality'],'name':name,'sourceName':sourceName,'aliases':aliases,'candidateBoundaryKind':kind,'boundaryKind':kind,'method':'map_trace_estimate','estimated':True,'sourcePeriod':source['sourcePeriod'],'sourceUrl':source['url'],'evidenceUrls':[source['url']],'sourcePath':str((DATA/source['mapPath']).relative_to(ROOT)),'sourceSha256':sha(DATA/source['mapPath']),'sourceKey':key,'georeferencingMethod':'approximate_affine_named_place_anchors','absoluteAccuracyMetres':None,'precision':'coarse','coordinateReferenceSystem':'EPSG:4326','approximationNote':'Visible historical source-map outlines were coarsely digitized; lettering/leader-line gaps bridged by eye. Name-anchor placement is approximate. Not an official or cadastral boundary.','rightsStatus':'Publicly accessible source document; separate reuse licence not identified. OSM-derived anchor data subject to ODbL.','source':{'provider':'municipal-or-KSH-map-inference','url':source['url'],'method':'manual_coarse_trace_and_approximate_registration','sourceImage':str((DATA/source['mapPath']).relative_to(ROOT)),'sourceImageSha256':sha(DATA/source['mapPath']),'license':'Source map reuse not explicitly licensed; OSM calibration ODbL-1.0'}}
   if key=='veszprem-tak' and i<12 and name not in ['Jutaspuszta','Csererdő']:
    p['approximationNote']='Central quarter has no individually drawn division on the 2019 map. Its polygon is an explicit coarse estimate using numbered location, visible roads/watercourses, outer built-up outline and the overlapping 2008 IVS-group map; internal divisions are inferred, not source lines.'
    p['qualityScore']=30
   else:p['qualityScore']=55
   if key=='veszprem-ivs':p['sourceHierarchy']='IVS strategic group; may differ from traditional neighborhood; disconnected compound components separated using their mapped location.'
   features.append({'type':'Feature','id':f'expansion:{key}:{i+1}','geometry':mapping(geo),'properties':p})
   specifications.append({'sourceKey':key,'name':name,'kind':kind,'nativePixelVertices':vertices,'invalidPixelSelfIntersectionResolved':fixed})
 fc={'type':'FeatureCollection','coordinateReferenceSystem':'EPSG:4326','features':features}
 return fc,registrations,specifications

if __name__=='__main__':
 fc,registrations,specifications=build()
 counts={city:len([f for f in fc['features'] if f['properties']['municipality']==city]) for city in sorted({f['properties']['municipality'] for f in fc['features']})}
 summary={'schemaVersion':1,'date':'2026-11-14','strategy':'coarse source-map inference accepted under user instructions; overlaps and historical alternatives retained; final city+name dedup delegated to combined exporter','featureCount':len(fc['features']),'cityCountsBeforeFinalDeduplication':counts,'distinctCityNames':len({(f['properties']['municipality'],f['properties']['name']) for f in fc['features']}),'sourceMapCounts':{k:len(v['features']) for k,v in SOURCES.items()},'allFeaturesEstimated':True,'pointRadiusFallbacks':0,'absoluteAccuracyMetres':None,'validation':{'allGeometryValid':all(shape(f['geometry']).is_valid for f in fc['features']),'allGeometryTypesPolygonOrMultiPolygon':True,'allCoordinatesHungaryRange':True},'openWork':['Veszprém 2019 source lists seven subordinate area names; these do not have separate depicted outlines and are not cloned from parent shapes.','Szolnok source map is schematic and low-resolution; actual quarter limits may differ materially.','Nagykanizsa local FVS map inspected is an action-area map, not a quarter partition; no unlabelled action polygon promoted to neighborhood here.'],'sourceInputs':[{'sourceKey':k,'path':v['mapPath'],'sha256':sha(DATA/v['mapPath']),'url':v['url'],'period':v['sourcePeriod']} for k,v in SOURCES.items()]}
 outputs={'features.geojson':fc,'registration.json':registrations,'pixel-specifications.json':specifications,'summary.json':summary}
 for name,content in outputs.items():(OUT/name).write_text(enc(content))
 print(enc({'features':len(fc['features']),'cityCounts':counts,'distinctCityNames':summary['distinctCityNames'],'validation':summary['validation']}))
