#!/usr/bin/env python3
"""Reproduce a bounded, explicitly low-confidence raster-source proposal offline."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,math,re,zlib
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,shape
from shapely.ops import transform
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
DATASET='vac-hep2023-marialiget-estimated';URL='https://www.vac.hu/docs/VacVarosOnkormanyzatHEP20232028.pdf'
PDF_SHA='f6120b4782812f17894cbebbaacbb3390892e98fbd673a2faaadfb1577164285';PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def objsha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def source_map():
 raw=gzip.decompress((P/'source-map-inline-commands.bin.gz').read_bytes());proof=read('map-extraction-proof.json');assert hashlib.sha256(raw).hexdigest()==proof['selectedOriginalDecodedPdfContentSha256']
 pat=rb'q 3103\.2 0 0 7\.2 640\.8 ([0-9.]+) cm\nBI\n/CS/RGB\n/W 431\n/H 1\n/BPC 8\n/F/Fl\n/DP<</Predictor 15\n/Columns 431\n/Colors 3>>\nID (.*?)\nEI Q'
 chunks=list(re.finditer(pat,raw,re.S));assert len(chunks)==523
 rows=[]
 for i,m in enumerate(chunks):
  assert abs(float(m[1])-(7145.6-7.2*i))<.02
  data=zlib.decompress(m[2]);assert len(data)==1294;kind=data[0];assert kind in range(5);row=bytearray(data[1:])
  for j in range(len(row)):
   left=row[j-3]if j>=3 else 0
   if kind in [1,4]:row[j]=(row[j]+left)%256
   elif kind==3:row[j]=(row[j]+left//2)%256
  rows.append(bytes(row))
 rgb=b''.join(rows);assert hashlib.sha256(rgb).hexdigest()==proof['nativeMapRgbSha256'];im=Image.frombytes('RGB',(431,523),rgb);im.save(P/'source-map-native.png');return im

def controls():
 roads=read('selected-actual-osm-ways.geojson');by={f['id']:f for f in roads['features']};spec=read('registration-control-specification.json');to=Transformer.from_crs(4326,23700,always_xy=True).transform
 xy=[];pixels=[];rows=[]
 for c in spec['controls']:
  a,b=[by[i]for i in c['actualWayIds']];g=transform(to,shape(a['geometry'])).intersection(transform(to,shape(b['geometry'])));assert g.geom_type=='Point'
  ground=[g.x,g.y];assert max(abs(v-w)for v,w in zip(ground,c['expectedIntersectionEov']))<1e-7
  pixels.append([*c['sourcePixel'],1]);xy.append(ground);rows.append({**c,'recomputedActualIntersectionEov':ground,'groundCoordinateMethod':'Analytical intersection of literal source-way segments after EPSG4326→23700; not a place node and not an inferred boundary edge.'})
 x=np.array(pixels,dtype=float);y=np.array(xy);assert np.linalg.matrix_rank(x)==3;m=np.linalg.lstsq(x,y,rcond=None)[0];res=np.linalg.norm(x@m-y,axis=1)
 assert len(rows)==3 and max(res)<1e-6
 return m,x,y,rows

def geometry(ring,m):
 assert len(ring)>=4 and ring[0]==ring[-1] and all(0<=x<431 and 0<=y<523 for x,y in ring)
 g=Polygon(np.c_[np.array(ring),np.ones(len(ring))]@m);assert g.is_valid and g.area>0
 inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
 coords=[list(inverse(*c))for c in g.exterior.coords];return g,{'type':'Polygon','coordinates':[coords]}

def verify_originals():
 import fitz,osmium,tempfile
 pdf=ROOT/'.local/neighborhoods/next-towns/vac-hep2023.pdf';pbf=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
 assert sha(pdf)==PDF_SHA and sha(pbf)==PBF_SHA
 d=fitz.open(pdf);assert len(d)==168;raw=d[6].read_contents();start=raw.index(b'q\n638.398 3383.61 3111.6 3771.6 re W* n\n');selected=raw[start:];assert selected==gzip.decompress((P/'source-map-inline-commands.bin.gz').read_bytes())
 assert len(d[6].get_drawings())==0;strips=[b for b in d[6].get_text('dict')['blocks']if b.get('type')==1 and b.get('width')==431 and b.get('height')==1];assert len(strips)==523
 rgb=b''.join(Image.open(io.BytesIO(b['image'])).convert('RGB').tobytes()for b in strips);assert hashlib.sha256(rgb).hexdigest()==read('map-extraction-proof.json')['nativeMapRgbSha256']
 for n in ['Márialiget','Kisderecske','Csatamező','Liget']:
  assert n in d[5].get_text()or n in d[8].get_text()
 expected={int(f['id'].split(':')[-1]):f for f in read('selected-actual-osm-ways.geojson')['features']};pt={int(f['id'].split(':')[-1]):f for f in read('identity-points.geojson')['features']};got={};ngot={}
 class H(osmium.SimpleHandler):
  def node(self,n):
   if n.id in pt:ngot[n.id]={'tags':dict(n.tags),'version':n.version,'timestamp':str(n.timestamp),'coordinates':[n.lon,n.lat]}
  def way(self,w):
   if w.id in expected:got[w.id]={'tags':dict(w.tags),'version':w.version,'timestamp':str(w.timestamp),'refs':[n.ref for n in w.nodes],'coordinates':[[n.lon,n.lat]for n in w.nodes]}
 with tempfile.TemporaryDirectory(prefix='vac-source-check-')as t:H().apply_file(str(pbf),locations=True,idx='sparse_file_array,'+str(Path(t)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway','railway','waterway','place')])
 assert set(got)==set(expected)and set(ngot)==set(pt)
 for i,f in expected.items():
  s=f['properties']['source'];a=got[i];assert a['tags']==s['tags']and a['version']==s['objectVersion']and a['timestamp']==s['objectTimestamp']and a['refs']==s['nodeRefs']and a['coordinates']==f['geometry']['coordinates']
 for i,f in pt.items():
  s=f['properties']['source'];a=ngot[i];assert a['tags']==s['tags']and a['version']==s['objectVersion']and a['timestamp']==s['objectTimestamp']and a['coordinates']==f['geometry']['coordinates']
 return {'originalPdfSha256Verified':True,'originalPbfSha256Verified':True,'exactOriginalMapInlineCommandsVerified':True,'nativeMapRowsIndependentlyDecodedByMuPdf':523,'literalSelectedWaysVerified':len(got),'literalIdentityNodesVerified':len(ngot)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify-originals',action='store_true');args=ap.parse_args();source_map();m,x,y,crows=controls();traces=read('native-contour-traces.json')['features'];to=Transformer.from_crs(4326,23700,always_xy=True).transform
 city=read('vac-municipality-reference.geojson')['features'][0];cg=transform(to,shape(city['geometry']));pts={f['properties']['name']:f for f in read('identity-points.geojson')['features']};features=[];scouts=[];summary=[];world={}
 method='Manual trace of the observed closed dashed Mária-liget perimeter in the original431×523municipal raster, preserving selected source-pixel vertices. Affine source-pixel→EPSG23700 registration uses three physical road/rail crossings from literal same-PBF ways, then EPSG23700→4326. No place points are fit controls; no Voronoi, hull, parcel clone, parent clone, snapping, buffering, repair or clipping. Placement is LOW-CONFIDENCE and extrapolated south of calibration controls. Raster tracing and conventional dash-gap interpolation are explicit estimates, not native geographic source geometry.'
 uncertainty='Source map reference year, survey lineage, CRS, present whole-quarter extent and unrestricted map reuse rights are unknown. HEP horizon2023–2028and PDF creation metadataNovember2022do not date the map or certify adoption. Only three manually read noncollinear controls define an exact affine fit with no independently selected holdout; zero training residual is an algebraic result, not ground accuracy. Both southern scout footprints extrapolate beyond the calibration triangle. Pixel perturbation alternatives are sensitivity scenarios, not confidence limits or extra quarters. Absolute accuracy is unclaimed.'
 for t in traces:
  name=t['name'];eg,g=geometry(t['sourcePixels'],m);world[name]=eg;point=pts[t['currentIdentityName']];pg=transform(to,shape(point['geometry']));outside=eg.difference(cg).area;pointinside=eg.covers(pg);pointdistance=eg.distance(pg)
  entry={'name':name,'nativeTraceId':t['id'],'nativeVerticesIncludingClosure':len(t['sourcePixels']),'valid':True,'areaM2Epsg23700':eg.area,'outsideVacM2':outside,'wholePolygonWithinVac':cg.covers(eg),'identityNodeId':point['id'],'identityPointInside':pointinside,'identityPointOutsideDistanceM':pointdistance,'identityPointUsedForFit':False,'sourceFrameCaveat':t['frameCaveat'],'registrationExtrapolatedSouth':True}
  if name=='Mária-liget':
   assert outside==0
   p={'name':name,'municipality':'Vác','municipalityId':'city:Vác','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_low_confidence_source_raster_candidate','sourceContourIsObserved':True,'sourceGeometryIsPublishedNative':False,'literalSourceMapName':'Mária-liget','literalSourceTextName':'Márialiget','sourceNameVariantsMeaning':'The same source map uses the hyphenated label and its municipal prose uses Márialiget. Current exact map-name PBF point corroborates identity only; no automatic alias or current Máriaudvar merge.','sourceNameEvidence':{'exactMapLabelNamePointId':point['id'],'exactMapLabelNamePointInside':pointinside,'namePointOutsideDistanceM':pointdistance,'pointDisagreementNotCorrected':True,'placePointsUsedForFit':False,'historicalTextFormerName':'Máriaudvar','currentMáriaudvarPointElsewhereNotMerged':True},'georeferencingIsApproximate':True,'georeferenceFitPerformed':True,'georeferencingStatus':'three_physical_control_affine_low_confidence_southern_extrapolation','claimedAbsoluteAccuracyMetres':None,'absoluteBoundaryAccuracyM':None,'wholeOrdinaryQuarterExtentVerified':False,'sourcePeriod':'HEP2023–2028; PDF creation metadata2022-11-30; original map reference year and current extent unknown','method':method,'placementUncertainty':uncertainty,'nativeContourPath':'native-contour-traces.json','nativeTraceId':t['id'],'registrationPath':'registration-control-specification.json','nativeTraceCanonicalSha256':objsha(t['sourcePixels']),'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':7,'selectedMapPath':'source-map-native.png','selectedOriginalInlineMapCommandsPath':'source-map-inline-commands.bin.gz','identityFactsPath':'hierarchy-and-source-facts.json'}],'license':'Public municipal PDF access; unrestricted map reuse rights unestablished. OSM control and identity evidence ODbL-1.0.','rightsStatus':'Public access is not a map reuse licence; original map provider/reference year unknown.'}
   features.append({'type':'Feature','id':'manual:vac-hep2023-marialiget-estimated:marialiget','properties':p,'geometry':g});entry['disposition']='proposed_low_confidence_estimated_only'
  else:
   assert outside>0
   scouts.append({'type':'Feature','id':'scout:vac-hep2023:kisderecske','properties':{'name':name,'municipality':'Vác','researchOnly':True,'admitted':False,'rejectionReason':'Source-frame/closure interpretation and extrapolated registration unresolved; literal scout has positive outside-municipality area. No clipping or fitted shift.','sourcePixelsPath':'native-contour-traces.json','frameCaveat':t['frameCaveat'],'outsideVacM2':outside,'usableForAddressAssignment':False},'geometry':g});entry['disposition']='unadmitted_scout'
  summary.append(entry)
 assert len(features)==len(scouts)==1
 write('marialiget-estimated-proposal.geojson',{'type':'FeatureCollection','scope':'One LOW-CONFIDENCE historical-source fine-neighborhood candidate only, no parent/fine-child completeness claim','features':features})
 write('kisderecske-unadmitted-scout.geojson',{'type':'FeatureCollection','researchOnly':True,'registryAdmissionAllowed':False,'features':scouts})
 # Deterministic manual-pixel perturbations measure instability; none are admitted.
 sensitivity=[];alternatives=[];base=world['Mária-liget'];ring=next(t['sourcePixels']for t in traces if t['name']=='Mária-liget')
 for i in range(3):
  for axis in range(2):
   for delta in [-2,-1,1,2]:
    vx=x.copy();vx[i,axis]+=delta;vm=np.linalg.lstsq(vx,y,rcond=None)[0];vg,vgeo=geometry(ring,vm);sid=f'control{i+1}-'+('x'if axis==0 else'y')+f'{delta:+d}'
    sensitivity.append({'scenario':sid,'controlIndexOneBased':i+1,'axis':'x'if axis==0 else'y','deltaNativePixels':delta,'centroidDisplacementM':base.centroid.distance(vg.centroid),'hausdorffDisplacementM':base.hausdorff_distance(vg),'areaM2Epsg23700':vg.area,'outsideVacM2':vg.difference(cg).area,'alternativeAdmitted':False})
    alternatives.append({'type':'Feature','id':'sensitivity:'+sid,'properties':{'scenario':sid,'name':'Mária-liget registration sensitivity','researchOnly':True,'admitted':False,'notAdditionalQuarter':True,'usableForAddressAssignment':False},'geometry':vgeo})
 write('unadmitted-registration-variants.geojson',{'type':'FeatureCollection','researchOnly':True,'registryAdmissionAllowed':False,'scope':'24sensitivity placements of one same source contour; not24quarters','features':alternatives})
 write('registration-proof.json',{'schemaVersion':1,'controls':crows,'controlCount':3,'placePointFitControls':0,'sourcePixelBasis':'Original431×523stitched raster; x right/y down; continuous pixel coordinates are approximate manual line-center readings, not subpixel accuracy.','metricCrs':'EPSG:23700','outputCrs':'EPSG:4326','affinePixelToEovRows':m.tolist(),'trainingResidualM':np.linalg.norm(x@m-y,axis=1).tolist(),'trainingResidualIsAccuracyEstimate':False,'independentlySelectedHoldoutCount':0,'calibrationTriangleSourcePixels':x[:,:2].tolist(),'candidateExtrapolatedBeyondTriangle':True,'relativeScaleSingularValuesMPerPixel':np.linalg.svd(m[:2,:])[1].tolist(),'scaleIsAccuracyBound':False,'sensitivityScenarios':sensitivity,'sensitivityMeaning':'Each control x/y manually perturbed by±1and±2native pixels independently, refitting all three pairs; scenarios are unadmitted diagnostics, not confidence bounds.'})
 write('proposal-review.json',{'schemaVersion':1,'datasetId':DATASET,'proposedFeatureCount':1,'primaryAdmissions':0,'classification':'LOW-CONFIDENCE estimated source-raster placement; historical map extent, not current hard boundary','candidateBoundaryKind':'neighbourhood','method':method,'placementUncertainty':uncertainty,'sourceMapIsRaster':True,'nativeQuarterVectorsAvailable':False,'parentSourceGroups':5,'parentGroupsPromotedToFineChildren':0,'placePointsUsedForFit':0,'wholeCurrentExtentVerified':False,'absoluteAccuracyEstablished':False,'sourceOfficialBoundaryStatusClaimed':False,'addressAssignmentApproved':False,'features':summary,'variantCount':24,'variantsAdmitted':0,'kisderecskeAdmitted':False,'sourceFrameOrOutsideCityDisagreementNotRepaired':True,'sourceHierarchyPath':'hierarchy-and-source-facts.json','registrationProofPath':'registration-proof.json','noGlobalWrites':True})
 write('registry-entry-proposal.json',{'id':DATASET,'path':str((P/'marialiget-estimated-proposal.geojson').relative_to(ROOT)),'sha256':sha(P/'marialiget-estimated-proposal.geojson'),'municipality':'Vác','method':method,'evidenceUrls':[URL],'license':'Public municipal map reuse rights unestablished; ODbL-1.0 for actual OSM controls/identity evidence','propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None},'reviewPath':str((P/'proposal-review.json').relative_to(ROOT)),'independentReviewPath':str((P/'independent-review.json').relative_to(ROOT)),'uncertaintyPath':str((P/'proposal-review.json').relative_to(ROOT)),'uncertainties':[uncertainty,'Manual raster trace follows a conventional dashed perimeter; source pixel readings and southern extrapolation are uncertain. Kisderecske, broader parents and24registration alternatives are not admitted.'],'frozenFeatureCount':1,'globalRegistryAdmissionPerformed':False})
 if args.verify_originals:write('original-source-revalidation.json',{'schemaVersion':1,**verify_originals()})
 manifest={'schemaVersion':1,'selfContainedReproduction':True,'networkCalls':0,'globalWrites':False,'files':[]}
 for f in sorted(P.iterdir()):
  if f.is_file()and f.name not in ['artifact-manifest.json','reproduction-check.json']:manifest['files'].append({'path':f.name,'bytes':f.stat().st_size,'sha256':sha(f)})
 write('artifact-manifest.json',manifest)
 print(json.dumps({'proposedEstimatedFeatures':1,'unadmittedScoutFeatures':1,'unadmittedRegistrationVariants':24,'sourceMapPixels':[431,523],'geographicFitControls':3,'placeFitControls':0,'networkCalls':0,'globalWrites':False}))
if __name__=='__main__':main()
