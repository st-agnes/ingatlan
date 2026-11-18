"""Verify and pin the unregistered Hatház source-contour/estimated-placement subset."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def load(name):return json.loads((P/name).read_text())
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def build():
 src=load('hathaz-observed-source-pixels.geojson')['features'][0]
 f=load('hathaz-inferred-import.geojson')['features'][0]
 a=load('hathaz-placement-alternative.geojson')['features'][0]
 reg=load('hathaz-registration.json');s=shape(src['geometry']);g=shape(f['geometry']);ag=shape(a['geometry'])
 T=Transformer.from_crs(4326,23700,always_xy=True);W=Transformer.from_crs(23700,4326,always_xy=True)
 M=np.array(reg['pixelToEovMatrix']);off=np.array(reg['pixelToEovOffset']);inv=np.linalg.inv(M)
 expected=[];back=[]
 for x,y in s.exterior.coords:
  xy=M@np.array([x,y])+off;ll=W.transform(*xy);expected.append(ll)
 for x,y in g.exterior.coords:
  xy=np.array(T.transform(x,y));back.append(tuple(inv@(xy-off)))
 actual=np.array(g.exterior.coords);srcp=np.array(s.exterior.coords)
 assert actual.shape==np.array(expected).shape
 assert np.max(np.abs(actual-np.array(expected)))<1e-10
 assert s.is_valid and g.is_valid and ag.is_valid
 assert len(g.interiors)==len(s.interiors)==0 and g.geom_type=='Polygon'
 assert f['properties']['estimated'] and f['properties']['estimatedPlacement'] and not f['properties']['estimatedContour']
 eov=transform(T.transform,g);aeov=transform(T.transform,ag)
 municipality_path=ROOT/'data/neighborhoods/sources/municipal-local-map-next/zalaegerszeg-calibration-municipality.geojson'
 muni=shape(json.loads(municipality_path.read_text())['geometry']);meov=transform(T.transform,muni)
 outside=eov.difference(meov).area
 frozen_names=[]
 for folder,file in [('municipal-local-map-next','zalaegerszeg-import.geojson'),('municipal-local-map-next','zalaegerszeg-quarantine.geojson'),('municipal-zalaegerszeg-remaining-next','remaining-inferred-import.geojson')]:
  x=json.loads((ROOT/'data/neighborhoods/sources'/folder/file).read_text());frozen_names += [z['properties']['name'] for z in x['features']]
 assert 'Hatház' not in frozen_names
 proof={'schemaVersion':1,'status':'frozen_first_useful_subset_unregistered','counts':{'newEstimatedNeighborhoodCandidates':1,'observedRasterContours':1,'primaryFeatures':0,'placementAlternativesNotCountedAsAdditionalQuarters':1},'sourceGeometry':{'sourceImage':'p141-xref778.jpeg','sourceAreaPixels':s.area,'sourceVerticesIncludingClosure':len(s.exterior.coords),'type':s.geom_type,'holes':len(s.interiors),'valid':s.is_valid,'sourceClosureWasInvented':False,'sourceClippingOrRepair':False},'conversion':{'worldType':g.geom_type,'worldValid':g.is_valid,'worldHoles':len(g.interiors),'worldVertexCountIncludingClosure':len(g.exterior.coords),'coordinateArrayExactlyMatchesPinnedSimilarityInverseProjection':bool(np.max(np.abs(actual-np.array(expected)))<1e-10),'maximumInverseRoundtripDiagnosticPixels':float(np.max(np.abs(np.array(back)-srcp))),'roundtripMeaning':'Numerical conversion consistency only; not georeferencing accuracy.'},'geographicDiagnostics':{'areaM2':eov.area,'municipalityOverlapFraction':1-outside/eov.area,'outsideArchivedCurrentMunicipalityAreaM2':outside,'namePointInsideCandidate':g.covers(Point(16.7935476,46.8873239)),'namePointUsedForFit':False,'municipalityPath':str(municipality_path.relative_to(ROOT)),'municipalitySha256':sha(municipality_path)},'alternative':{'file':'hathaz-placement-alternative.geojson','sameObservedSourceContour':True,'areaM2':aeov.area,'symmetricDifferenceM2':eov.symmetric_difference(aeov).area,'hausdorffDistanceMetres':eov.hausdorff_distance(aeov),'meaning':'Variation between two plausible sparse-reference placements of the same raster contour, not a confidence envelope or an absolute accuracy bound.'},'identity':{'exactCurrentName':'Hatház','exactOsmPlaceId':'osm:node:1110266803','alreadyFrozenNamesCompared':frozen_names,'duplicateExistingFrozenQuarterName':False,'notAliasOfHistoricalUnit17':'2014 ITS unit17 was Nyugati külterület;2025 chapter3.4 unit17 is Hatház.'},'limitations':['All world placement is estimated. Absolute positional accuracy is unknown.','Source is a municipal consultation-draft study; no statutory neighborhood boundary or cadastral status established.','Municipal map reuse rights not independently established. OSM calibration/name evidence is ODbL.','Unregistered source-local package; national coverage remains incomplete and address assignment is not approved.'],'globalRegistriesModified':False,'usableForAddressAssignment':False}
 original=ROOT/'.local/neighborhoods/supplement-originals/zalaegerszeg-ziffa2025.pdf'
 assert sha(original)=='b132fd75d6c95538023ced5eda3ad8ac7f7131c6e27f889ed7206c23e4a44745'
 inp={'schemaVersion':1,'status':'frozen_source_inputs_for_one_estimated_neighborhood','originalPdf':{'path':str(original.relative_to(ROOT)),'sha256':sha(original),'sourceUrl':'https://zalaegerszeg.hu/wp-content/uploads/2025/09/ZEG_ZIFFA_egyeztetesi-valt.pdf','fullOriginalRemainsLocal':True,'pageCount':229},'sourcePdfPagesOneBased':[63,99,141,142],'sourceImageXref':778,'sourceImageSizePixels':[355,451],'pinnedOsmPbf':{'path':'.local/neighborhoods/hungary-latest.osm.pbf','sha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','osmSnapshotTimestamp':'2026-11-12T21:23:05Z','networkUsedForExtraction':False},'inputs':[{'path':n,'sha256':sha(P/n)} for n in ['source-map-only-p141.pdf','source-page-facts.json','p141-xref773.jpeg','p141-xref778.jpeg','hathaz-geographic-reference.geojson','current-name-evidence.geojson']],'export':'hathaz-inferred-import.geojson','estimatedFeatureCount':1,'sourcePixelGeometry':'hathaz-observed-source-pixels.geojson','placementAlternative':'hathaz-placement-alternative.geojson','registeredGlobally':False,'sourcePointsUsedForGeoreferencing':False,'claimedAbsoluteAccuracyMetres':None}
 return {'conversion-proof.json':enc(proof),'input-manifest.json':enc(inp)}
if __name__=='__main__':
 pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');args=pa.parse_args()
 outputs=build()
 for name,content in outputs.items():
  if args.check:assert (P/name).read_text()==content,name+' differs'
  else:(P/name).write_text(content)
 excluded={'artifact-manifest.json'}
 artifact={'schemaVersion':1,'status':'frozen_unregistered_first_hathaz_subset','estimatedFeatureCount':1,'primaryFeatureCount':0,'files':[{'path':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(P.iterdir()) if f.is_file() and f.name not in excluded]}
 path=P/'artifact-manifest.json';content=enc(artifact)
 if args.check:assert path.read_text()==content,'artifact-manifest.json differs'
 else:path.write_text(content)
 print(json.dumps({'check':args.check,'filesPinned':len(artifact['files']),'newEstimatedNeighborhoodCandidates':1}))
