#!/usr/bin/env python3
"""Independent audit of explicitly inferred caps, separate from observed contours.
No cap producer or observed-contour producer implementation is imported/invoked.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,unicodedata
os.environ['PROJ_NETWORK']='OFF'
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,shape
from pyproj import Transformer
P=Path(__file__).resolve().parent
QUANT_SHA='46e210f5e6c5c3db32f40577fb56c1bf6e55f2394fdd3d62d94943d6dfdac3b3'
OBS5_SHA='a27535ffae4e4549f76200e207fa80fc6796dfbe394740eacce57b7df7693acc'
def read(n):return json.loads((P/n).read_text())
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def enc(q):return json.dumps(q,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def jhash(q):return hashlib.sha256(json.dumps(q,separators=(',',':')).encode()).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if c.isalnum())
def length(path):return sum(math.hypot(b[0]-a[0],b[1]-a[1])for a,b in zip(path[:-1],path[1:]))
def close(a,b,tol=1e-10):assert abs(a-b)<=tol,(a,b)
def cross(a,b,c):return(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def on(a,b,p):return cross(a,b,p)==0 and min(a[0],b[0])<=p[0]<=max(a[0],b[0])and min(a[1],b[1])<=p[1]<=max(a[1],b[1])
def intersect(a,b,c,d):
 v,w,x,y=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
 if v*w<0 and x*y<0:return True
 return(v==0 and on(a,b,c))or(w==0 and on(a,b,d))or(x==0 and on(c,d,a))or(y==0 and on(c,d,b))
def ringcheck(path,unit_steps=True):
 assert path[0]==path[-1]and len({tuple(p)for p in path[:-1]})==len(path)-1
 if unit_steps:assert all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1 for a,b in zip(path[:-1],path[1:]))
 N=len(path)-1
 for i in range(N):
  for j in range(i+1,N):
   if j==i+1 or(i==0 and j==N-1):continue
   assert not intersect(path[i],path[i+1],path[j],path[j+1]),(i,j)
 twice=sum(a[0]*b[1]-a[1]*b[0]for a,b in zip(path[:-1],path[1:]));assert twice!=0
 return abs(twice)/2

def strict(features):
 program="import fs from 'node:fs';import {validateGeometry} from "+json.dumps((P/'strict-validator-snapshot.mjs').as_uri())+";let f=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(f.map(x=>({id:x.id,name:x.properties.name,...validateGeometry(x.geometry)}))));"
 r=subprocess.run(['node','--input-type=module','-e',program],input=json.dumps(features),text=True,capture_output=True,check=True,cwd=P);return json.loads(r.stdout)

def audit():
 q=read('remaining-cap-source-quantification.json');assert sha(P/'remaining-cap-source-quantification.json')==QUANT_SHA
 fc=read('reconstructed-cap-inferred.geojson');proof=read('cap-conversion-proof.json');assert len(q['records'])==len(fc['features'])==len(proof['records'])==2
 base=['remaining-cap-source-quantification.json','reconstructed-cap-inferred.geojson','cap-conversion-proof.json','independent-cap-audit.py','strict-validator-snapshot.mjs','pecs-p48-names.jpeg','pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json','first-source-inferred.geojson','remaining-source-inferred.geojson','source-inferred.geojson','first-conversion-proof.json','remaining-conversion-proof.json','conversion-proof.json','independent-final-gap-review.json','independent-manual-islands-review.json','islands-review.json']
 extra=set()
 for r in q['records']:
  extra.update([r['nativeSourceEvidence']['path'],r['bracketPreview']['path']])
  for s in r['additionalSourceSupport']:extra.update([s['originalEmbeddedJpeg'],s['nativeCrop']])
 paths=[P/n for n in sorted(set(base)|extra)];before={p:sha(p)for p in paths}
 assert sha(P/'independent-final-gap-review.json')=='f43eadb757de17ef3bccd6397ad6ebacf2381d4571cbdaafc4a10e98e35a97fc';assert sha(P/'source-inferred.geojson')==OBS5_SHA;assert sha(P/'first-source-inferred.geojson')=='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95';assert sha(P/'remaining-source-inferred.geojson')=='cfdd86a7dc73d6f6a76ebf9a2377a0e7e077992761f3b23fd675abf102c8826a'
 assert sha(P/'strict-validator-snapshot.mjs')=='abf1b564180d9b33593f9ce0d711eb996bf8f3a1d9cbb03b7527167ac515f3d7'
 assert proof['observedSourceContoursInThisFile']==0 and proof['lowConfidenceReconstructedCandidates']==2 and proof['primaryApprovedCount']==0 and proof['newGeoreferenceModelFitted']is False and proof['usableForAddressAssignment']is False and proof['claimedAbsoluteAccuracy']is None
 assert fc['claimedAbsoluteAccuracy']is None and 'reconstruct'in fc['status']
 observed=read('first-source-inferred.geojson')['features']+read('remaining-source-inferred.geojson')['features']+read('source-inferred.geojson')['features'];assert len(observed)==65 and all(f['properties']['sourceContourIsObserved']is True for f in observed)
 oldnames={norm(f['properties']['name'])for f in observed};assert not oldnames&{norm(f['properties']['name'])for f in fc['features']};oldworld=[shape(f['geometry'])for f in observed]
 A=np.c_[np.asarray(read('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels']),[0.,0.,1.]];B=np.c_[np.asarray(read('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov']),[0.,0.,1.]]
 for name in ['first-conversion-proof.json','remaining-conversion-proof.json']:
  oldhash={r['path']:r['sha256']for r in read(name)['inputs']};assert sha(P/'pecs-image-alignment.json')==oldhash['pecs-image-alignment.json']and sha(P/'pecs-registration-northwest-only-diagnostic.json')==oldhash['pecs-registration-northwest-only-diagnostic.json']
 source=Image.open(P/'pecs-p48-names.jpeg').convert('RGB');rgb=np.asarray(source);assert sha(P/'pecs-p48-names.jpeg')=='75758682472a880dee3488068f324d3feb4ba916237de33d36734696ed1d78f8';to_geo=Transformer.from_crs(23700,4326,always_xy=True)
 def project(path):
  en=np.c_[np.asarray(path),np.ones(len(path))]@B;lon,lat=to_geo.transform(en[:,0],en[:,1]);return np.c_[lon,lat],en[:,:2]
 def gridlen(path):return length((np.c_[np.asarray(path),np.ones(len(path))]@B)[:,:2])
 qby={r['sourceName']:r for r in q['records']};pby={r['name']:r for r in proof['records']};island_by={r['sourceName']:r for r in read('independent-manual-islands-review.json')['records']};cap_geoms=[];alt_geoms=[];alternative_features=[];records=[];crop_count=0
 for feature in fc['features']:
  props=feature['properties'];name=props['name'];qr=qby[name];pr=pby[name];rec=props['sourceReconstruction'];assert name in ['Árpádtető','Petőfi-akna'];assert props['sourceContourIsObserved']is False and props['reconstructionConfidence']=='low'and rec['confidence']=='low'and rec['fullRingIsFullyObserved']is False and pr['sourceContourIsObserved']is False and pr['reconstructionConfidence']=='low'
  assert qr['sourceContourIsObserved']is False and qr['wholeReconstructedRingIsFullyObserved']is False and qr['sourceQuarterFineUnitIdentitySupported']and qr['sourceWholeIslandInsideFrame'];assert props['sourceWholeFineUnitIdentitySupported']is True;assert props['sourceNameEvidence']=={'sourceLabelAnchorFigure9':qr['sourceLabelAnchorFigure9'],'sourceQuarterFineUnitIdentitySupported':True,'sourceWholeIslandInsideFrame':True,'evidence':'remaining-cap-source-quantification.json'}
  chain=[v['sourcePixel']for v in qr['visibleOuterStrokeOpenChain']];cap=[v['sourcePixel']for v in qr['uncertainCandidatePixelPath']];assert chain[0]!=chain[-1]and cap[0]==chain[-1]and cap[-1]==chain[0];assert len({tuple(v)for v in chain})==len(chain)
  for group in [qr['visibleOuterStrokeOpenChain'],qr['uncertainCandidatePixelPath']]:
   for v in group:
    x,y=v['sourcePixel'];assert 0<x<source.width-1 and 0<y<source.height-1 and v['originalRgb']==rgb[y,x].tolist()
   assert all(max(abs(a['sourcePixel'][0]-b['sourcePixel'][0]),abs(a['sourcePixel'][1]-b['sourcePixel'][1]))==1 for a,b in zip(group[:-1],group[1:]))
  assert rec['observedOpenChain']==qr['visibleOuterStrokeOpenChain']and rec['inferredCapPixelPath']==qr['uncertainCandidatePixelPath'];assert pr['sourceVisibleOpenChain']==chain and pr['sourceInferredCapPath']==cap;assert qr['visibleChainStepCount']==rec['observedChainStepCount']==len(chain)-1;assert qr['uncertainInternalPixelCount']==rec['uncertainInternalPixelCount']==len(cap)-2;assert qr['uncertainIntervalEndpointPixels']==rec['confirmedGapEndpoints']==[chain[-1],chain[0]]
  visible_length=length(chain);cap_length=length(cap);ring=chain+cap[1:];ringarea=ringcheck(ring);ringlength=length(ring);assert qr['reconstructedRingCandidate']==ring and jhash(ring)==qr['reconstructedRingCandidateSha256'];close(ringarea,qr['reconstructedRingCandidatePixelCenterArea']);close(visible_length,qr['visibleChainLengthPixels']);close(cap_length,qr['uncertainIntervalChainLengthPixels']);close(ringlength,qr['reconstructedRingLengthPixels']);close(rec['observedChainLengthPixels'],visible_length);close(rec['inferredCapLengthPixels'],cap_length);close(rec['inferredPerimeterFractionPixels'],cap_length/ringlength)
  native=pr['nativePixelGeometry'];assert native['type']=='Polygon'and native['coordinates']==[ring]and shape(native).area==ringarea;assert pr['nativeSourceAreaPixelsSquared']==ringarea;assert pr['supportQuantificationSha256']==QUANT_SHA and pr['sourceFrameSha256']==sha(P/'pecs-registration-northwest-only-diagnostic.json')and pr['geographicPlacementVerified']is False
  density=(np.c_[np.asarray(ring),np.ones(len(ring))]@A)[:,:2];assert np.max(np.abs(np.asarray(pr['densityFramePixelGeometry']['coordinates'][0])-density))<1e-12;world,en=project(ring);assert np.max(np.abs(np.asarray(feature['geometry']['coordinates'][0])-world))<1e-12;geom=shape(feature['geometry']);assert geom.is_valid and not geom.interiors;cap_geoms.append(geom)
  inferred=[];assert rec['inferredSegments']==pr['inferredSegments'];assert len(pr['inferredSegments'])==rec['inferredSegmentCount']==qr['uncertainIntervalStepCount']==len(cap)-1
  for i,(a,b)in enumerate(zip(cap[:-1],cap[1:])):
   seg=pr['inferredSegments'][i];assert seg['inferredSegmentIndex']==i and seg['sourceStartPixel']==a and seg['sourceEndPixel']==b;assert seg['quarterBoundaryInkIdentityVerified']is False and seg['segmentType']=='inferred_unverified_cap_continuation'and seg['lengthIsAbsoluteAccuracyOrErrorBound']is False;close(seg['sourceLengthPixels'],math.dist(a,b));assert seg['startOriginalRgb']==rgb[a[1],a[0]].tolist()and seg['endOriginalRgb']==rgb[b[1],b[0]].tolist();ends,grid=project([a,b]);assert np.max(np.abs(np.asarray(seg['eovGridEndpoints'])-grid))<1e-8 and np.max(np.abs(np.asarray(seg['wgs84Endpoints'])-ends))<1e-12;close(seg['lengthMetresInUnverifiedInheritedGrid'],math.dist(*grid),1e-8);inferred.append({'sourceStartPixel':a,'sourceEndPixel':b,'sourceLengthPixels':math.dist(a,b),'lengthMetresInUnverifiedInheritedGrid':math.dist(*grid),'quarterBoundaryInkIdentityVerified':False})
  mapped_cap_length=gridlen(cap);close(rec['inferredCapLengthMetresInUnverifiedInheritedGrid'],mapped_cap_length,1e-8)
  alternative=chain+[chain[0]];altarea=ringcheck(alternative,unit_steps=False);alt=pr['alternativeEndpointChord'];assert rec['alternativeEndpointChord']==alt and alt['type']=='unadopted_endpoint_chord_variant'and alt['sourceEndpoints']==[chain[-1],chain[0]]and alt['nativePixelGeometry']['coordinates']==[alternative];close(alt['sourceChordLengthPixels'],math.dist(chain[-1],chain[0]));close(alt['lengthMetresInUnverifiedInheritedGrid'],gridlen([chain[-1],chain[0]]),1e-8);close(alt['sourceAreaPixelsSquared'],altarea);close(alt['sourceAreaDifferenceFromAdoptedPixelsSquared'],abs(ringarea-altarea));altworld,_=project(alternative);assert np.max(np.abs(np.asarray(alt['worldGeometry']['coordinates'][0])-altworld))<1e-12;altgeom=shape(alt['worldGeometry']);assert altgeom.is_valid and not altgeom.interiors;alt_geoms.append(altgeom);alternative_features.append({'id':'alternative:'+feature['id'],'properties':{'name':'Unadopted endpoint chord '+name},'geometry':alt['worldGeometry']});assert qr['directChordIsMeasurementOnly']and qr['directChordAdoptedAsBoundary']is False
  # Exact original source crops and repeated-island evidence, without interfigure coordinate transfer.
  native_evidence=qr['nativeSourceEvidence'];native_crop=Image.open(P/native_evidence['path']).convert('RGB');expected=source.crop(native_evidence['sourcePixelBox']);assert native_crop.size==expected.size and native_crop.tobytes()==expected.tobytes()and sha(P/native_evidence['path'])==native_evidence['sha256'];crop_count+=1;assert sha(P/qr['bracketPreview']['path'])==qr['bracketPreview']['sha256'];assert rec['additionalOriginalFigures']==qr['additionalSourceSupport']
  for support in qr['additionalSourceSupport']:
   original=P/support['originalEmbeddedJpeg'];assert sha(original)==support['originalJpegSha256'];img=Image.open(original).convert('RGB');actual=Image.open(P/support['nativeCrop']).convert('RGB');expected=img.crop(support['cropPixelBox']);assert actual.size==expected.size and actual.tobytes()==expected.tobytes()and sha(P/support['nativeCrop'])==support['nativeCropSha256'];crop_count+=1
  if name=='Árpádtető':
   prior=island_by[name];assert prior['sourceQuarterMapWholeFineUnitIdentitySupported']and prior['sourceContourApprovedForInferredDerivation']is False and prior['pendingStrokeVertexIndices']==[7];authority='Previous literal Figure9/full-island review supports the fine-unit identity and observed surrounding chain, while explicitly withholding the pale[329,82] interval. It remains an inferred cap here.'
  else:authority='Original Figure9 literal Petofi-akna label identifies the isolated northern island above M utca/Floriantelep. The repeated complete island form in four original demographic figures supports identity and cap form; the pale cap/gray-line mixture remains unverified quarter-boundary ink.'
  assert props['boundaryKind']=='inferred_area'and props['candidateBoundaryKind']=='neighbourhood'and props['estimated']is True and props['canonicalNameIsNeighborhood']is False and props['sourceIsOfficial']is False and props['sourceIsHardBoundary']is False and props['usableForAddressAssignment']is False and props['claimedAbsoluteAccuracy']is None and props['claimedAbsoluteAccuracyMetres']is None;assert props['reviewStatus']=='low_confidence_reconstructed_candidate_not_verified'and props['georeferencingStatus']=='frozen_first_cohort_estimated_geographic_alignment_not_verified'and props['georeferencingIsApproximate']is True
  records.append({'name':name,'reconstructionConfidence':'low','fullRingSourceContourIsObserved':False,'literalObservedOpenChainRgbExact':True,'sourceFineUnitIdentityEvidence':authority,'observedChainStepCount':len(chain)-1,'observedChainLengthPixels':visible_length,'observedChainLengthMetresInUnverifiedInheritedGrid':gridlen(chain),'candidatePerimeterLengthMetresInUnverifiedInheritedGrid':gridlen(ring),'inferredPerimeterFractionInUnverifiedInheritedGrid':mapped_cap_length/gridlen(ring),'uncertainInternalPixelCount':len(cap)-2,'inferredSegmentCount':len(cap)-1,'inferredSegments':inferred,'inferredCapLengthPixels':cap_length,'inferredCapLengthMetresInUnverifiedInheritedGrid':mapped_cap_length,'inferredPerimeterFractionPixels':cap_length/ringlength,'candidateNativeSourceAreaPixelsSquared':ringarea,'alternativeChordSourceLengthPixels':math.dist(chain[-1],chain[0]),'alternativeChordLengthMetresInUnverifiedInheritedGrid':gridlen([chain[-1],chain[0]]),'alternativeNativeSourceAreaPixelsSquared':altarea,'alternativeAreaDifferencePixelsSquared':abs(ringarea-altarea),'adoptedAndAlternativeSimpleRingsIndependentlyCheckedByIntegerDeterminants':True,'unverifiedCapInkIdentityPreserved':True,'gridLengthsAreNotAbsoluteAccuracyOrErrorBounds':True,'otherThematicFigureCoordinatesTransferred':False,'claimedAbsoluteAccuracy':None})
 checks=strict(fc['features']+alternative_features);assert len(checks)==4 and all(v['valid']for v in checks)
 overlap_old=max(g.intersection(o).area for g in cap_geoms for o in oldworld);overlap_pair=cap_geoms[0].intersection(cap_geoms[1]).area;overlap_alt_old=max(g.intersection(o).area for g in alt_geoms for o in oldworld);overlap_alt_pair=alt_geoms[0].intersection(alt_geoms[1]).area;overlap_cross=max(cap_geoms[i].intersection(alt_geoms[1-i]).area for i in range(2));assert overlap_old==overlap_pair==overlap_alt_old==overlap_alt_pair==overlap_cross==0.0
 assert all(sha(p)==h for p,h in before.items());assert crop_count==10
 return {'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':'Independent remaining_pixel_audit agent','verdict':'pass_separate_low_confidence_inferred_cap_candidates_not_observed_or_verified_boundaries','scope':'Separate honest-flag, literal-source reading, topology, arithmetic and65-observed-contour nonoverlap audit for two explicitly inferred cap reconstructions. No producer code imported/invoked.','reconstructedCandidateCount':2,'observedFullSourceContoursInThisFile':0,'observedContourReferencesChecked':65,'coverageInterpretation':'65 observed source contours plus2 partially reconstructed low-confidence candidates. This is not67 verified/current boundaries. All inherited geographic placement remains unverified.','strictReconstructionValidCount':2,'strictAlternativeScenarioValidCount':2,'exactOriginalNativeSupportCropsChecked':10,'allInferredEdgesRetainUnverifiedQuarterInkIdentity':True,'allFullRingsMarkedSourceContourIsObservedFalse':True,'allCandidatesLowConfidence':True,'frozenNamesPixelToEovMatrix':B.tolist(),'newGeoreferenceModelFitted':False,'newCapsMaximumOverlapWithAll65ObservedDegreesSquared':overlap_old,'newCapPairOverlapDegreesSquared':overlap_pair,'alternativeChordMaximumOverlapWithAll65ObservedDegreesSquared':overlap_alt_old,'alternativeChordPairOverlapDegreesSquared':overlap_alt_pair,'adoptedVsOtherAlternativeMaximumOverlapDegreesSquared':overlap_cross,'observedFiveGeometrySha256Unchanged':OBS5_SHA,'observedContourPackagesOrAuditModified':False,'sourcePixelAndInheritedGridMetricsAreNotAccuracyClaims':True,'uncertainContinuationApprovedAsObservedInk':False,'primaryApprovedCount':0,'claimedAbsoluteAccuracy':None,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False,'networkUsed':False,'producerFilesModified':False,'inputFingerprints':[{'path':p.name,'sha256':h}for p,h in before.items()],'records':records,'strictValidationRecords':checks}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--write-report',action='store_true');args=ap.parse_args();result=audit();text=enc(result);target=P/'independent-cap-review.json'
 if args.check:assert target.read_text()==text
 else:target.write_text(text)
 print(enc({k:result[k]for k in ['verdict','reconstructedCandidateCount','observedFullSourceContoursInThisFile','observedContourReferencesChecked','strictReconstructionValidCount','exactOriginalNativeSupportCropsChecked','newCapsMaximumOverlapWithAll65ObservedDegreesSquared','newCapPairOverlapDegreesSquared','claimedAbsoluteAccuracy']}))
