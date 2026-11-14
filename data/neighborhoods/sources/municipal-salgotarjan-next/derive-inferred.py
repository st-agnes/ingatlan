"""Rebuild/check the separate Salgótarján inferred batch entirely offline.

PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-salgotarjan-next/derive-inferred.py [--check]
No geographic accuracy is asserted. This retains every native source boundary.
"""
from pathlib import Path
import argparse, hashlib, json, re, unicodedata
import numpy as np
import shapely
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj import Transformer

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
URL='https://www.salgotarjan.hu/wp-content/uploads/fejlesztesidokumentumok_20220629_its.pdf'
PDF_SHA='d0c46f2a4797517874b770da6d64dba88cf81de5170cf09e2857284644a31a25'
METHOD='Original embedded municipal profile-image color-component pixel-cell outer contours. All original components and every external pixel edge retained; only tiny fully enclosed cadastral/JPEG mask voids are interpreted as cartographic ink and filled. Native raw masks and outer outlines both archived. Similarity matching to actual corresponding overview color contours, then an unvalidated inferred overview-to-EOV affine fit against current municipality silhouette, then EPSG:4326. No source-name point controls, buffer, hull, chord, snapping, repair, image-frame closure or clipping. Registration residuals are internal diagnostics and do not establish absolute accuracy.'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name): return json.loads((P/name).read_text())
def text(v): return json.dumps(v,ensure_ascii=False,indent=2)+'\n'
def normal(v): return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',v.lower()).encode('ascii','ignore').decode())
def homogeneous(m): return np.c_[m,[0,0,1]]
def rounded(v):
    if isinstance(v,(list,tuple)): return [rounded(x) for x in v]
    return round(float(v),8)
def parts(g): return [g] if g.geom_type=='Polygon' else list(g.geoms)
def vertices(g): return sum(len(r.coords) for p in parts(g) for r in [p.exterior,*p.interiors])

parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
inventory=load('source-image-inventory.json');assert inventory['sourcePdfSha256']==PDF_SHA
for rec in inventory['records']:
    assert digest(P/rec['path'])==rec['sha256'],rec['path']
original=ROOT/'.local/neighborhoods/nationwide-docs/originals/salgotarjan-its.pdf'
if original.exists(): assert digest(original)==PDF_SHA
native=load('profile-main-correspondence-review.json')['records']
registration=load('profile-main-registration-refined.json')['records']
assert len(native)==len(registration)==8
profile_geo=load('profile-source-pixel-contours.geojson')['features']
frame=np.array(load('exploratory-frame-registration.json')['matrixPixelToEov'])
to_wgs=Transformer.from_crs(23700,4326,always_xy=True)
points=load('current-source-name-points.geojson')['features']
municipal_json=load('calibration-municipality.geojson')
municipality=shape(municipal_json['geometry'] if municipal_json['type']=='Feature' else municipal_json)
municipality_eov=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,municipality)
features=[];proof=[]
for row,reg,stored in zip(native,registration,profile_geo):
    name=row['name'];assert name==reg['name']==stored['properties']['name']
    src=shape(row['sourceOuterOutlinePixelGeometry']);raw=shape(row['rawPixelGeometry'])
    assert src.is_valid and src.equals(shape(stored['geometry']))
    # No exterior edge may be invented by the enclosed cartographic-ink interpretation.
    assert src.boundary.difference(raw.boundary).length==0
    assert not row['sourceOutlineTouchesImageEdge']
    assert not reg['targetRoiClipsComponent']
    m=np.array(reg['matrixProfilePixelsToMainPixels'])
    composite=homogeneous(m)@frame
    def eov_func(x,y,z=None):
        a=np.c_[np.atleast_1d(x),np.atleast_1d(y),np.ones(len(np.atleast_1d(x)))]@composite
        return a[:,0],a[:,1]
    eov=transform(eov_func,src)
    geographic=transform(to_wgs.transform,eov)
    geo_dict=mapping(geographic);geo_dict['coordinates']=rounded(geo_dict['coordinates']);out=shape(geo_dict)
    assert out.is_valid and not out.is_empty and len(parts(out))==len(parts(src))
    assert vertices(out)==vertices(src)
    source_image=next(v for v in inventory['records'] if v['path']==row['sourceImage'])
    point=next((v for v in points if normal(v['properties']['name'])==normal(name)),None)
    assert point is not None,('current name missing',name)
    variants={'Forgáchtelep':['Forgách-telep'],'Somlyóbánya':['Somlyóbányatelep']}.get(name,[])
    props={'name':name,'municipality':'Salgótarján','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'sourceNameIsNeighborhood':True,'sourceContourIsReal':True,'fullSourceNamePreserved':True,'sourceNameVariants':variants,'sourcePeriod':'June 2022 ITS 2021–2027; subdivision inherited from 2008 IVS / 2014 ITS; native cadastral-map date unknown','sourcePublisherIsMunicipal':True,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'primaryLayerAdmission':False,'georeferenceStatus':'inferred_georeference','georeferenceValidated':False,'geometryVerificationStatus':'native_color_pixel_outline_with_unvalidated_inferred_registration','reviewStatus':'estimated_candidate_not_verified','usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None,'absoluteAccuracyMetres':None,'independentlyAcceptedPhysicalControlCount':0,'method':METHOD,'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':source_image['pdfPageOneBased'],'printedPage':source_image['pdfPageOneBased'],'imageXref':source_image['xref'],'imageSha256':source_image['sha256']}],'overviewSourcePageOneBased':125,'sourceOriginalColorComponentId':row['sourceOriginalColorComponentId'],'sourceContourComponentCount':len(parts(src)),'sourceContourVertexCountIncludingClosure':vertices(src),'cartographicInteriorPixelsFilled':row['cartographicInteriorPixelCount'],'sourceFrameClosureUsed':False,'inferredClosingEdges':0,'constituentQuarterSplitsCreated':False,'registrationUncertainty':'The overview silhouette fit and profile/overview contour correspondence are approximate. Original raster CRS, physical controls, independent holdouts and absolute accuracy are unestablished. Forgáchtelep northwest profile/overview contours differ; Zagyvaróna and Somlyóbánya also retain local contour residuals. No mismatch is repaired or hidden.','currentNameCorroboration':{'sourceId':point['id'],'name':point['properties']['name'],'url':point['properties']['source']['url'],'objectTimestamp':point['properties']['source']['objectTimestamp'],'osmTimestamp':point['properties']['source']['osmTimestamp'],'geometryUsedForRegistration':False,'polygonBoundaryValidatedByNamePoint':False},'currentNameIndependentlyConfirmed':True,'referenceMunicipalityDiagnostic':{'provisionalOutsideAreaM2':float(eov.difference(municipality_eov).area),'provisionalOutsideFraction':float(eov.difference(municipality_eov).area/eov.area),'sourceClipped':False,'notAnAccuracyTest':True},'provisionalAreaM2':float(eov.area),'license':'Municipal-map open-reuse licence unverified; ODbL-1.0 applies to OSM reference data.','attribution':'Salgótarján MJV Integrált Településfejlesztési Stratégiája 2021–2027, June2022, pp125–137; © OpenStreetMap contributors for modern reference data.'}
    feature={'type':'Feature','properties':props,'geometry':geo_dict};features.append(feature)
    proof.append({'name':name,'sourceImage':row['sourceImage'],'sourceImageSha256':source_image['sha256'],'rawColorPixelCount':row['rawColorPixelCount'],'cartographicInteriorPixelsFilled':row['cartographicInteriorPixelCount'],'nativeRawMaskAreaPixels':raw.area,'nativeOuterContourAreaPixels':src.area,'newExternalBoundaryLengthPixels':src.boundary.difference(raw.boundary).length,'componentCount':len(parts(src)),'sourceVertexCountIncludingClosure':vertices(src),'outputVertexCountIncludingClosure':vertices(out),'matrixProfilePixelsToMainPixels':m.tolist(),'matrixProfilePixelsToEov':composite.tolist(),'profileMainResidualMainPixels':reg['residualPercentilesMainPixels'],'geographicGeometryValid':out.is_valid,'absoluteAccuracyMetres':None})
export={'type':'FeatureCollection','features':features}
input_names=['source-image-inventory.json','profile-source-pixel-contours.geojson','profile-main-correspondence-review.json','profile-main-registration-refined.json','exploratory-frame-registration.json','calibration-municipality.geojson','current-source-name-points.geojson','source-pages125-137.pdf','review-frame-scope-and-pixels.json','salgotarjan-name-semantics-review.json']
conversion={'schemaVersion':1,'status':'FROZEN_SEPARATE_INFERRED_BATCH_NOT_GEOGRAPHICALLY_VALIDATED','sourceUrl':URL,'sourceOriginalPdfSha256':PDF_SHA,'sourceDate':'2022-06','primaryFeatureCount':0,'inferredFeatureCount':8,'nativeContoursUnchanged':True,'inputFingerprints':[{ 'path':str((P/n).relative_to(ROOT)),'sha256':digest(P/n)} for n in input_names],'sourcePixelToGeographicPipeline':['Archived raw source-color component pixel cells','Actual external outlines; tiny enclosed cartographic-ink void interpretation archived separately','Refined profile→overview similarity, one shared continuous lower Róna panel','Unvalidated approximate overview→EPSG:23700 affine from municipal silhouette','EPSG:23700→EPSG:4326 using pyproj; round8 decimal places'],'overviewPixelToEovMatrix':frame.tolist(),'absoluteAccuracyMetres':None,'claimedFitResidualsAreAbsoluteAccuracy':False,'physicalControlCount':0,'sourceFrameClosureUsed':False,'sourcePointBufferingUsed':False,'sourceNamePointsUsedForGeoreference':False,'sourceGeometryClippedToCurrentMunicipality':False,'inventedConstituentSplits':False,'sourceConflictsPreserved':['Salgóbánya/Eresztvény five-name/four-body disagreement; neither emitted','Szabadságtelep/Ferenctelep disagreement; neither silently aliased','Acélgyár dual source-unit discussion; no arbitrary partition','Zagyvapálfalva full industrial legend; no fine historical footprint invented'],'omittedSourceBodies':'No cropped neighbor fragment or partially cropped Városközpont is closed; no ten-unit group is copied to constituent names. This batch contains only the eight unambiguous separately named complete profile contours.','records':proof}
outputs={'salgotarjan-inferred.geojson':text(export),'conversion-proof.json':text(conversion)}
for name,body in outputs.items():
    if args.check:
        assert (P/name).read_text()==body,('generated output differs',name)
    else: (P/name).write_text(body)
print(('Checked' if args.check else 'Wrote')+' 8 inferred source-contour features; 0 primary; absolute accuracy unknown; address assignment disabled.')
