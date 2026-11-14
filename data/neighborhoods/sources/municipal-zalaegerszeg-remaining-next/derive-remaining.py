"""Offline source-pixel extraction; run from repository: PYTHONPATH=.local/geodata python PATH/derive-remaining.py."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
from shapely.geometry import box,mapping,shape,Polygon,MultiPolygon
from shapely.ops import unary_union,transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
R=P.parents[3]
def write(n,v): (P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
a=np.asarray(Image.open(P/'zalaegerszeg-p12-image0.jpeg').convert('RGB')).astype(int)
m=(a[:,:,0]<135)&(a[:,:,1]-a[:,:,0]>30)&(a[:,:,2]-a[:,:,0]>30)&(a[:,:,1]>65)
l,n=ndimage.label(~m)
def cells(mask):
 runs=[]
 for y in np.flatnonzero(mask.any(axis=1)):
  z=np.r_[False,mask[y],False].astype(int); d=np.diff(z); starts=np.flatnonzero(d==1); ends=np.flatnonzero(d==-1)
  runs.extend(box(int(s)-.5,int(y)-.5,int(e)-.5,int(y)+.5) for s,e in zip(starts,ends))
 return unary_union(runs)
def restore_label(g):
 # Only fully contained annotation holes are removed, no outward repair or bridging.
 if g.geom_type=='Polygon': return Polygon(g.exterior)
 return MultiPolygon([Polygon(x.exterior) for x in g.geoms])
M=np.array(json.loads((P/'zalaegerszeg-registration.json').read_text())['matrixPixelToEov'])
inv=Transformer.from_crs(23700,4326,always_xy=True)
def eov(x,y,z=None):
 return M[0,0]*np.array(x)+M[1,0]*np.array(y)+M[2,0],M[0,1]*np.array(x)+M[1,1]*np.array(y)+M[2,1]
def feature(g,props): return {'type':'Feature','properties':props,'geometry':mapping(g)}
base={
 'municipality':'Zalaegerszeg','boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,
 'sourcePeriod':'2014-2020 ITS approval draft dated2014-08-28; source text says areas designated for comparable 2009/2011 statistics; exact map survey date unknown',
 'evidenceUrls':['https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf'],
 'sourceDocuments':[{'url':'https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf','sha256':'4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035','pdfPageOneBased':12,'printedPage':12,'figure':1,'nameTablePdfPageOneBased':13}],
 'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'independentInteriorControlCount':0,
 'sourceDocumentIsOfficialMunicipalPublication':True,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,
 'license':'Municipal map reuse rights not independently established; ODbL applies to OSM perimeter calibration and independent name evidence.'}
# Literal enclosed source cell IDs stable for exact threshold above.
literal=[('Iparterület',6,[42,64])]
source=[]; world=[]; checks=[]
for name,number,ids in literal:
 parts=[]
 for i in ids:
  g=cells(l==i); assert g.geom_type=='Polygon' and g.is_valid
  # A full source-closed cell can have only its fully enclosed label disk restored.
  holes=[Polygon(r) for r in g.interiors]
  annotation=[h for h in holes if h.area>1500]
  assert len(annotation)==1
  other=[list(r.coords) for r in g.interiors if Polygon(r).area<=1500]
  g=Polygon(g.exterior,other)
  parts.append(g)
 g=MultiPolygon(parts)
 eg=transform(eov,g); wg=transform(inv.transform,eg)
 props=base|{'name':name,'sourceUnitNumber':number,'estimated':False,'boundaryEvidenceCategory':'literal_source_closed_contour','method':'Four-neighbor free-cell interiors at actual teal inside edge. Exact horizontal pixel-run union, removing only one fully enclosed numeric-label hole per part. No gap closure or cap reconstruction. Frozen inherited affine to EPSG:23700, then WGS84.','areaM2':eg.area,'sourcePixelArea':g.area,'sourceFreeComponentIds':ids,'componentCount':len(parts),'reviewStatus':'unregistered_source_review','georeferenceConfidence':'low_unknown_absolute_accuracy','manualReconstructedBoundaryLengthM':0}
 source.append(feature(g,props|{'coordinateSystem':'source_image_pixels_x_right_y_down','pixelCellConvention':'[x-0.5,x+0.5] × [y-0.5,y+0.5], pixel index denotes center'}));world.append(feature(wg,props))
 checks.append({'name':name,'valid':g.is_valid and wg.is_valid,'sourceAreaPixels':g.area,'areaM2':eg.area,'parts':len(parts),'vertices':sum(len(x.exterior.coords) for x in g.geoms),'literalClosed':True})
write('remaining-literal-source-pixels.geojson',{'type':'FeatureCollection','features':source})
write('remaining-literal-world.geojson',{'type':'FeatureCollection','features':world})
write('remaining-literal-checks.json',{'maskRule':'R<135; G-R>30; B-R>30; G>65. Four-neighbor free components.','sourceImageSha256':sha(P/'zalaegerszeg-p12-image0.jpeg'),'registrationSha256':sha(P/'zalaegerszeg-registration.json'),'independentInteriorControlCount':0,'absoluteAccuracyM':None,'features':checks})
# Overlay literal source boundaries, green. Source pixels preserved.
im=Image.open(P/'zalaegerszeg-p12-image0.jpeg').convert('RGB');d=ImageDraw.Draw(im)
for f in source:
 for g in shape(f['geometry']).geoms: d.line(list(g.exterior.coords),fill=(255,0,0),width=2)
im.save(P/'remaining-literal-overlay.png')
print(json.dumps(checks,ensure_ascii=False))
# Explicit source-bounded manual reconstructions. Numeric circles occlude the local
# quarter edge; source lobes outside the stated window are left exactly unchanged.
# The shortest convex connection of the visible interior entry intervals is one
# interpretation, not a claim that the unseen edge was straight.
from shapely.geometry import MultiPoint,LineString,Point
manual=[
 ('Zalabesenyő',10,[77],[918,1483,980,1545]),
 ('Botfa',11,[83,87],[1052,1625,1114,1687]),
 ('Bazita',12,[80,91],[371,1648,433,1710]),
 ('Ebergény',13,[60,68,70],[353,1198,415,1260]),
 ('Szenterzsébethegy',14,[44,47],[234,1067,296,1129]),
]
ms=[];mw=[];proof=[];caps=[];alts=[]
for name,number,ids,bounds in manual:
 original=cells(np.isin(l,ids)); cx=(bounds[0]+bounds[2])/2; cy=(bounds[1]+bounds[3])/2; window=Point(cx,cy).buffer(31,quad_segs=16)
 entries=original.intersection(window.boundary)
 patch=entries.convex_hull
 assert patch.geom_type=='Polygon' and not patch.is_empty
 outside=original.difference(window)
 g=unary_union([outside,patch]); assert g.is_valid
 newedge=g.boundary.difference(original.boundary)
 lines=list(newedge.geoms) if newedge.geom_type=='MultiLineString' else [newedge]
 lines=[x for x in lines if x.geom_type=='LineString' and x.length>1e-6]
 # Keep only new cap portions; visible edge segments inside window were deliberately
 # removed together with the annotation and are conservatively counted inferred.
 eg=transform(eov,g);wg=transform(inv.transform,eg)
 caplen=sum(transform(eov,x).length for x in lines)
 props=base|{'name':name,'sourceUnitNumber':number,'estimated':True,'boundaryEvidenceCategory':'source_contour_with_manual_label_occlusion_caps','method':'Observed source free-cell lobes outside explicit annotation disc window, exact pixel-run union. Inside the window, shortest convex connection of source-interior entry intervals; reconstructed caps remain uncertain. No use of present-day roads/name points as boundary controls. Frozen inherited affine EOV then WGS84.','areaM2':eg.area,'sourcePixelArea':g.area,'sourceFreeComponentIds':ids,'reviewStatus':'unregistered_manual_inference_candidate','georeferenceConfidence':'low_unknown_absolute_accuracy','boundaryReconstructionConfidence':'low','annotationReconstructionWindowPixels':bounds,'annotationWindowGeometry':mapping(window),'manualReconstructedBoundaryLengthM':caplen,'manualReconstructedBoundaryLengthPixels':sum(x.length for x in lines),'manualReconstructedPerimeterFraction':caplen/eg.length,'claimedAbsoluteAccuracyMetres':None,'uncertaintyNotes':['Observed pixels outside the annotation window retain the source contour. Reconstructed cap location inside the window is inferred and may differ from the unseen original line.','Alternatives displace each cap midpoint by up to ±3 source pixels, bounded by the annotation window; these illustrate local ambiguity and are not a statistical confidence interval.','The inherited affine has zero independent interior controls; perimeter fit residuals do not measure absolute interior accuracy.']}
 ms.append(feature(g,props|{'coordinateSystem':'source_image_pixels_x_right_y_down'}));mw.append(feature(wg,props))
 for k,line in enumerate(lines):
  capprops={'name':name,'sourceUnitNumber':number,'capIndex':k,'observed':False,'confidence':'low','lengthPixels':line.length,'lengthM':transform(eov,line).length}
  caps.append(feature(line,capprops))
  cc=list(line.coords);start=np.array(cc[0]);end=np.array(cc[-1]);v=end-start; normal=np.array([-v[1],v[0]])/np.linalg.norm(v);mid=(start+end)/2
  for sign in [-1,1]:
   proposed=mid+sign*3*normal; factor=1.0
   while factor>1e-6 and not window.covers(Point(proposed)):
    factor*=.5;proposed=mid+sign*3*factor*normal
   alt=LineString([start,proposed,end]);alts.append(feature(alt,capprops|{'alternativeMidpointDisplacementPixels':sign*3*factor,'meaning':'Illustration of alternative hidden-edge curvature; not probability limits.'}))
 proof.append({'name':name,'sourceUnitNumber':number,'sourceComponents':ids,'windowPixels':bounds,'windowGeometry':mapping(window),'removedObservedBoundaryLengthPixels':original.boundary.intersection(window).length,'removedObservedBoundaryLengthM':transform(eov,original.boundary.intersection(window)).length,'pixelCellGeometry':mapping(g),'observedOutsideWindowGeometry':mapping(outside),'inferredPatchGeometry':mapping(patch),'entryIntervalsGeometry':mapping(entries),'capGeometry':mapping(newedge),'capLengthPixels':sum(x.length for x in lines),'capLengthM':caplen,'outsideWindowSymmetricDifferencePixelsSquared':g.difference(window).symmetric_difference(original.difference(window)).area,'sourceRasterPreservedOutsideWindow':g.difference(window).symmetric_difference(original.difference(window)).area<1e-9,'isValid':g.is_valid,'geometryType':g.geom_type,'excludedUnlabelledCells':[92] if number==12 else []})
write('remaining-manual-source-pixels.geojson',{'type':'FeatureCollection','features':ms})
write('remaining-manual-world.geojson',{'type':'FeatureCollection','features':mw})
write('remaining-manual-caps-source-pixels.geojson',{'type':'FeatureCollection','features':caps})
write('remaining-manual-cap-alternatives-source-pixels.geojson',{'type':'FeatureCollection','features':alts})
write('remaining-manual-reconstruction-proof.json',{'schemaVersion':1,'status':'provisional_manual_interpretation_low_confidence','annotationWindowMeaning':'A radius31px 64-segment annotation disc window contains the numeric label and merged stroke. Local convex connection is inferred; no observed-edge claim inside window. The window itself is never a quarter polygon.','records':proof})
# Raw pre-interpretation source lobes retained for independent inspection.
write('remaining-raw-manual-lobes-source-pixels.geojson',{'type':'FeatureCollection','features':[feature(cells(np.isin(l,ids)),{'name':name,'sourceUnitNumber':num,'sourceComponents':ids}) for name,num,ids,b in manual]})
im=Image.open(P/'zalaegerszeg-p12-image0.jpeg').convert('RGB');d=ImageDraw.Draw(im)
for f in ms:
 geom=shape(f['geometry']);ps=[geom] if geom.geom_type=='Polygon' else list(geom.geoms)
 for part in ps:d.line(list(part.exterior.coords),fill=(255,0,0),width=2)
for f in caps:d.line(list(shape(f['geometry']).coords),fill=(255,220,0),width=3)
im.save(P/'remaining-manual-overlay.png')
print(json.dumps([{'name':x['name'],'valid':x['isValid'],'type':x['geometryType'],'capPixels':x['capLengthPixels'],'capM':x['capLengthM'],'outsidePreserved':x['sourceRasterPreservedOutsideWindow']} for x in proof],ensure_ascii=False))
# Preserve the unnumbered closed Bazita-adjacent source cell without assigning it.
unassigned=cells(l==92)
write('remaining-unassigned-source-pixels.geojson',{'type':'FeatureCollection','features':[feature(unassigned,{'sourceFreeComponentId':92,'provisionalNearbyName':'Bazita','assigned':False,'reason':'An independently closed unnumbered cell is separated from labelled unit12 by an uncoloured strip. Number12 does not establish assignment to this detached cell.'})]})
# Semantic alternative for unit13: omit the southwest lobe70, whose attribution is
# inferred from its ends meeting the same annotation circle rather than an own label.
original=cells(np.isin(l,[60,68]));window=Point(384,1229).buffer(31,quad_segs=16)
alt=unary_union([original.difference(window),original.intersection(window.boundary).convex_hull])
write('remaining-ebergeny-omit-lobe70-source-pixels.geojson',{'type':'FeatureCollection','features':[feature(alt,{'name':'Ebergény','sourceUnitNumber':13,'estimated':True,'alternativeTo':'remaining-manual-source-pixels.geojson','sourceComponents':[60,68],'omittedUnlabelledLobe':70,'confidence':'low','reason':'Alternative semantic assignment omitting southwest lobe70; number13 bridges components only through annotation region.'})]})
# Strict-validator-compatible interpretation of one ambiguous raster pixel. The
# literal source remains separate and quarantined; no source correction is hidden.
raw=shape(source[0]['geometry']);parts=list(raw.geoms);p=parts[1];kept=[];removed=[]
for r in p.interiors:
 h=Polygon(r)
 if h.area==1 and h.boundary.distance(p.exterior)==0:removed.append(h)
 else:kept.append(list(r.coords))
assert len(removed)==1
parts[1]=Polygon(p.exterior,kept);g=MultiPolygon(parts);eg=transform(eov,g);wg=transform(inv.transform,eg)
props=world[0]['properties']|{'estimated':True,'boundaryEvidenceCategory':'literal_source_contour_with_explicit_one_pixel_ambiguity_fill','reviewStatus':'unregistered_manual_raster_ambiguity_candidate','method':'Same literal two-part Iparterület contour, with one explicitly recorded1px source-mask hole touching exterior at a corner interpreted as raster ambiguity and filled. Another fully interior1px hole remains. Original literal source is preserved separately. Frozen inherited affine, no current-name or road fitting.','manualReconstructedBoundaryLengthM':transform(eov,removed[0].boundary).length,'manualReconstructedBoundaryLengthPixels':4,'manualReconstructionAreaPixels':1,'manualReconstructionAreaM2':transform(eov,removed[0]).area,'areaM2':eg.area,'sourcePixelArea':g.area,'boundaryReconstructionConfidence':'low_for_single_pixel','inferredPixelBounds':list(removed[0].bounds),'sourceNameStatus':'official_historical_source_table_name; current_exact_OSM_name_not_observed'}
write('remaining-iparterulet-one-pixel-inferred-source-pixels.geojson',{'type':'FeatureCollection','features':[feature(g,props|{'coordinateSystem':'source_image_pixels_x_right_y_down'})]})
write('remaining-iparterulet-one-pixel-inferred-world.geojson',{'type':'FeatureCollection','features':[feature(wg,props)]})
write('remaining-iparterulet-one-pixel-inference-proof.json',{'status':'explicit_inference_not_literal_source','removedSourceMaskHolePixels':mapping(removed[0]),'areaDifferencePixels':g.area-raw.area,'areaDifferenceM2':eg.area-transform(eov,raw).area,'unchangedExteriorRings':all(a.exterior.equals(b.exterior) for a,b in zip(raw.geoms,g.geoms)),'remainingInteriorHoles':[len(p.interiors) for p in g.geoms],'reason':'Original1px hole touches exterior at one point and fails project hole_outside_shell; this explicit estimated interpretation fills it. Literal contour remains retained with failure recorded.','alternative':'Keep the literal source contour quarantined; do not use this inferred interpretation.'})
