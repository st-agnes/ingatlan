"""Place only Neszele using actual road junctions; never georeference from names."""
from pathlib import Path
import json,numpy as np
from PIL import Image,ImageDraw
from pyproj import Transformer
from shapely.geometry import shape,mapping,Point
from shapely.ops import transform
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
T=Transformer.from_crs(4326,23700,always_xy=True);W=Transformer.from_crs(23700,4326,always_xy=True)
refs=json.loads((P/'road-geographic-reference.geojson').read_text());byid={f['id']:f for f in refs['features']}
controls=[{'id':'irinyi_jedlik','pixel':[216,200],'wgs84':[16.8283727,46.8564648],'osmWayIds':[33754364,33754361],'description':'Visible Irinyi János/Jedlik Ányos road-center junction.'},{'id':'kiraly_jedlik','pixel':[268,202],'wgs84':[16.830206,46.8564452],'osmWayIds':[149157493,33754361],'description':'Visible Király/Jedlik Ányos road-center junction.'},{'id':'ilosvai_bukkfa','pixel':[169.5,157.5],'wgs84':[16.826764,46.857424],'osmWayIds':[209371097,209329533],'description':'Visible Bükkfa/Ilosvai road-center junction, north of quarter label.'},{'id':'gebarti_jedlik','pixel':[280,165.5],'wgs84':[16.8306148,46.8572548],'osmWayIds':[33754359,148822704],'description':'Visible Jedlik Ányos/Gébárti road-center junction at the eastern curve.'}]
for c in controls:
 c['eov']=list(T.transform(*c['wgs84']));c['sourcePixelPickingIsManual']=True;c['approximatePixelPickingUncertainty']=3
 for ident in c['osmWayIds']:
  coords=byid[f'osm:way:{ident}']['geometry']['coordinates'];assert any(np.linalg.norm(np.array(ll)-np.array(c['wgs84']))<1e-9 for ll in coords)
def fit(cs):
 A=[];v=[]
 for c in cs:
  u,y=c['pixel'];e,n=c['eov'];A.extend([[u,y,1,0],[-y,u,0,1]]);v.extend([e,n])
 a,b,ex,ny=np.linalg.lstsq(A,v,rcond=None)[0];return np.array([[a,b],[b,-a]]),np.array([ex,ny])
M,off=fit(controls);AM,ao=fit(controls[:2]);inv=np.linalg.inv(M)
for c in controls:c['fitResidualMetresDiagnosticOnly']=float(np.linalg.norm(M@np.array(c['pixel'])+off-np.array(c['eov'])))
reg={'schemaVersion':1,'status':'frozen_estimated_registration','sourceImage':'p138-xref768.jpeg','sourcePixelSpace':'Native image pixel corners, x right/y down','worldCrs':'EPSG:23700 EOV, inverse projected to WGS84','model':'Four-parameter similarity with reflected pixel-y, least squares from four actual road junctions. No shear or name-point controls.','controls':controls,'pixelToEovMatrix':M.tolist(),'pixelToEovOffset':off.tolist(),'scaleMetresPerSourcePixel':float(np.sqrt(abs(np.linalg.det(M)))),'rmsFitResidualMetresDiagnosticOnly':float(np.sqrt(np.mean([c['fitResidualMetresDiagnosticOnly']**2 for c in controls]))),'residualMeaning':'Internal manual road-correspondence consistency only, not surveyed accuracy or an absolute positional bound.','twoJunctionAlternative':{'pixelToEovMatrix':AM.tolist(),'pixelToEovOffset':ao.tolist(),'controlIds':[c['id'] for c in controls[:2]],'meaning':'Preliminary two-junction fit preserved as another plausible placement of the same source contour; zero residual degrees of freedom cannot measure accuracy.'},'estimatedPlacement':True,'sourceNamePointsUsedForFit':False,'claimedAbsoluteAccuracyMetres':None,'limitations':['Native387×329 raster; thick boundary band and manually picked road centerlines leave unknown positional uncertainty.','Source map projection/background age are unknown; isotropic EOV similarity is an explicit placement assumption.','The source label obscures part of the central Gébárti/Ilosvai junction, so that location is excluded from fitting.','Current road geometry may differ from the source backdrop. Main/alternative differences illustrate ambiguity and are not a confidence envelope.']}
(P/'neszele-registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
sf=json.loads((P/'neszele-literal-source-pixels.geojson').read_text())['features'][0];s=shape(sf['geometry'])
def placed(m,o):
 def fun(xx,yy,z=None):
  ar=np.array([xx,yy]);ans=m@ar+o[:,None] if ar.ndim>1 else m@ar+o;return ans[0],ans[1]
 return transform(fun,s)
eov=placed(M,off);aeov=placed(AM,ao);world=transform(W.transform,eov);aw=transform(W.transform,aeov)
assert world.is_valid and aw.is_valid
pr={'name':'Neszele','municipality':'Zalaegerszeg','boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,'candidateBoundaryKind':'neighbourhood','sourceUnitNumber':16,'sourceSchemaId':'zalaegerszeg-ziffa2025-chapter3.4-unit16-map-neszele','sourceSchemaIdentityNotes':'Neszele and Ságod have separately labeled observed map contours in shared chapter unit16. This is Neszele only, not an alias or clone of the grouped parent.','sourcePeriod':'2025-08-30 ZIFFA consultation draft; adoption not independently established; backdrop date unknown','estimated':True,'sourceContourObserved':True,'estimatedContour':False,'estimatedPlacement':True,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'sourceDocumentIsOfficialMunicipalPublication':True,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'sourceDocuments':[{'url':'https://zalaegerszeg.hu/wp-content/uploads/2025/09/ZEG_ZIFFA_egyeztetesi-valt.pdf','sha256':'b132fd75d6c95538023ced5eda3ad8ac7f7131c6e27f889ed7206c23e4a44745','date':'2025-08-30','status':'consultation_draft','pdfPageOneBased':138,'semanticsPagesOneBased':[63,139],'figure':53,'imageXref':768}],'evidenceUrls':['https://zalaegerszeg.hu/wp-content/uploads/2025/09/ZEG_ZIFFA_egyeztetesi-valt.pdf'],'method':sf['properties']['method']+' Explicit estimated placement using four road-center junctions and a similarity transform in EOV, then inverse projection to WGS84.','currentNameStatus':'same_city_exact_osm_name_observed','sourceLabelEvidence':[{'id':'osm:node:347301131','name':'Neszele','coordinates':[16.827674,46.8570588],'usedForGeoreferencing':False,'insideCandidate':world.covers(Point(16.827674,46.8570588))}],'areaM2':eov.area,'sourcePixelArea':s.area,'reviewStatus':'frozen_source_contour_and_estimated_placement','reviewNotes':['Observed native source interior is preserved exactly; source contour observation and world placement are separate claims.','Grouped chapter indicators do not merge Neszele and Ságod map identities. No group-parent polygon was copied into either child.','Source consultation study does not establish statutory, legal, cadastral or surveyed quarter boundaries.','Separate two-junction placement is retained as an alternative hypothesis, not another quarter or accuracy bound.'],'license':'Municipal map redistribution rights unknown; ODbL applies to OSM road reference and name evidence.'}
f={'type':'Feature','id':'manual:zalaegerszeg-ziffa2025:unit16-neszele-estimated-placement','properties':pr,'geometry':mapping(world)}
af={'type':'Feature','id':'alternative:zalaegerszeg-ziffa2025:neszele-two-junction-placement','properties':{**pr,'alternativeOnly':True,'areaM2':aeov.area,'method':sf['properties']['method']+' Estimated placement alternative using only Irinyi/Jedlik and Király/Jedlik junctions; not an additional quarter.'},'geometry':mapping(aw)}
(P/'neszele-inferred-import.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n');(P/'neszele-placement-alternative.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[af]},ensure_ascii=False,indent=2)+'\n')
im=Image.open(P/'p138-xref768.jpeg').convert('RGB').resize((1161,987));draw=ImageDraw.Draw(im)
def px(ll):return tuple((inv@(np.array(T.transform(*ll))-off))*3)
for rf in refs['features']:draw.line([px(ll) for ll in rf['geometry']['coordinates']],fill=(255,0,0),width=2)
for c in controls:
 xx,yy=np.array(c['pixel'])*3;draw.ellipse((xx-5,yy-5,xx+5,yy+5),outline=(0,0,255),width=2);draw.text((xx+5,yy),c['id'],fill=(0,0,255))
im.save(P/'neszele-registration-preview.png')
print(json.dumps({'valid':world.is_valid,'vertices':len(world.exterior.coords),'areaM2':eov.area,'fitResidualsDiagnosticOnly':[c['fitResidualMetresDiagnosticOnly'] for c in controls],'alternativeSymmetricDifferenceM2':eov.symmetric_difference(aeov).area,'alternativeHausdorffMetres':eov.hausdorff_distance(aeov)}))
