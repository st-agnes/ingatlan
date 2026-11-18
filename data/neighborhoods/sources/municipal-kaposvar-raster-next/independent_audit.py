from pathlib import Path
import sys,argparse,itertools,fitz
sys.dont_write_bytecode=True
parser=argparse.ArgumentParser(description="Independent offline Kaposvár native-mask/model-mathematics audit; geography remains unresolved. Default and --check are read-only.")
mode=parser.add_mutually_exclusive_group()
mode.add_argument("--check",action="store_true",help="Compare recomputed frozen independent-review.json without writing.")
mode.add_argument("--write-review",action="store_true",help="Explicitly write only independent-review.json after all checks.")
cli_options=parser.parse_args()
from collections import deque,Counter
import json,hashlib,math
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,MultiPolygon,Point,LineString,shape,mapping
from shapely.ops import transform
from shapely.affinity import affine_transform
from pyproj import Transformer,Geod
import pyproj,gzip
R=Path(__file__).resolve().parents[4]
P=R/'data/neighborhoods/sources/municipal-kaposvar-raster-next'
T=json.loads((P/'source-contour-components.json').read_text());im=Image.open(P/'kaposvar-p18-source.jpeg').convert('RGB');hsv=np.asarray(im.convert('HSV'));H,W=hsv.shape[:2]
RANGES={'blue':(140,175),'green':(65,109),'red':(230,256),'lime':(35,65),'orange':(2,35),'purple':(175,230),'teal':(109,140)}
EXPECTED_IDS=['1-main','2-main','3-main','4-main','5-main','6-main','7-main','8-main','8-northwest','8-northeast','9-central','9-northern','9-north-tip','9-east','10-north','10-south']
assert [c['componentId']for c in T['components']]==EXPECTED_IDS

def decode(rows):
 mask=np.zeros((H,W),bool)
 for row in rows:
  y=row['y'];last=-1
  assert 0<=y<H
  for a,b in row['xRunsHalfOpen']:
   assert 0<=a<b<=W and a>last
   assert not mask[y,a:b].any();mask[y,a:b]=True;last=b
 return mask

def flood(seed,mask):
 # Independent explicit four-neighbor BFS; not scipy.ndimage labeling/fill_holes.
 q=deque([seed]);seen={seed}
 while q:
  y,x=q.popleft()
  for v,u in [(y-1,x),(y+1,x),(y,x-1),(y,x+1)]:
   if 0<=v<H and 0<=u<W and mask[v,u] and(v,u)not in seen:seen.add((v,u));q.append((v,u))
 return seen

def component(category,seed,saturation,value):
 lo,hi=RANGES[category];mask=(hsv[:,:,0]>=lo)&(hsv[:,:,0]<hi)&(hsv[:,:,1]>=saturation)&(hsv[:,:,2]>=value)
 x,y=seed;lookup={};candidates=[]
 for yy in range(max(0,y-5),min(H,y+6)):
  for xx in range(max(0,x-5),min(W,x+6)):
   if not mask[yy,xx]:continue
   if(yy,xx)not in lookup:
    region=flood((yy,xx),mask)
    for key in region:lookup[key]=region
   region=lookup[yy,xx]
   if len(region)>=100:candidates.append(((xx-x)**2+(yy-y)**2,yy,xx,region))
 _,yy,xx,region=min(candidates,key=lambda c:c[:3]);raw=np.zeros((H,W),bool)
 for v,u in region:raw[v,u]=True
 # Flood non-selected cells from a bounding-box outer frame to identify ONLY enclosed ink/CAD holes.
 ys,xs=np.nonzero(raw);y0,y1=int(ys.min())-1,int(ys.max())+1;x0,x1=int(xs.min())-1,int(xs.max())+1
 assert y0>=0 and x0>=0 and y1<H and x1<W
 exterior=set();q=deque()
 for v in range(y0,y1+1):
  for u in [x0,x1]:
   if not raw[v,u] and(v,u)not in exterior:exterior.add((v,u));q.append((v,u))
 for u in range(x0,x1+1):
  for v in[y0,y1]:
   if not raw[v,u] and(v,u)not in exterior:exterior.add((v,u));q.append((v,u))
 while q:
  v,u=q.popleft()
  for a,b in[(v-1,u),(v+1,u),(v,u-1),(v,u+1)]:
   if y0<=a<=y1 and x0<=b<=x1 and not raw[a,b] and(a,b)not in exterior:exterior.add((a,b));q.append((a,b))
 holes=np.zeros((H,W),bool)
 for v in range(y0,y1+1):
  for u in range(x0,x1+1):
   if not raw[v,u]and(v,u)not in exterior:holes[v,u]=True
 holesizes=[];visited=set()
 for v,u in zip(*np.nonzero(holes)):
  if(v,u)not in visited:
   region=flood((v,u),holes);visited.update(region);holesizes.append(len(region))
 return raw,holes,sorted(holesizes,reverse=True),(xx,yy)

def boundary(mask):
 # Pixel-cell boundary is independently reconstructed by exposed cell sides.
 edges={}
 for y,x in zip(*np.nonzero(mask)):
  x,y=int(x),int(y);a=(2*x-1,2*y-1);b=(2*x+1,2*y-1);c=(2*x+1,2*y+1);d=(2*x-1,2*y+1)
  for neighbor,start,end in [((y-1,x),a,b),((y,x+1),b,c),((y+1,x),c,d),((y,x-1),d,a)]:
   yy,xx=neighbor
   if not(0<=yy<H and 0<=xx<W and mask[yy,xx]):
    assert start not in edges,'non-simple exposed cell edge graph'
    edges[start]=end
 start=min(edges);ring=[start];current=edges[start]
 while current!=start:
  ring.append(current);current=edges[current];assert len(ring)<=len(edges)
 assert len(ring)==len(edges)
 kept=[]
 for k,b in enumerate(ring):
  a=ring[k-1];c=ring[(k+1)%len(ring)]
  if(b[0]-a[0])*(c[1]-b[1])!=(b[1]-a[1])*(c[0]-b[0]):kept.append((b[0]/2,b[1]/2))
 kept.append(kept[0]);p=Polygon(kept);assert p.is_valid and not p.interiors and p.area==int(mask.sum())
 return p


def read(name):
 return json.loads((P/name).read_text())

def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def need(condition,message):
 if not condition:raise AssertionError(message)

pyproj.network.set_network_enabled(False)
manifest=read('generated-manifest.json');manifest_digest=sha(P/'generated-manifest.json')
extraction=read('source-extraction.json');pdf=R/extraction['pdfPath'];document=fitz.open(pdf)
need(sha(pdf)==extraction['pdfSha256']==T['sourcePdfSha256'] if 'sourcePdfSha256'in T else sha(pdf)==extraction['pdfSha256'],'PDF hash')
need(document.extract_image(124)['image']==(P/'kaposvar-p18-source.jpeg').read_bytes(),'original xref124 JPEG bytes')
need(124 in [v[0]for v in document[17].get_images(full=True)],'actual page18 xref identity')
need(document[17].get_text()==extraction['sourcePage18Text'],'original source legend text')
need(im.size==(625,883)and sha(P/'kaposvar-p18-source.jpeg')==T['sourceImageSha256']==extraction['originalImageSha256'],'native source identity')
need('10 városrészre' in document[17].get_text() and '2014. szeptember'in document[0].get_text(),'historical source semantics/date')
need(T['baselineHsvThresholds']=={'saturation':35,'value':80,'hueCategories':{k:list(v)for k,v in RANGES.items()}},'documented HSV classes')
visual=read('visual-review.json');control=read('control-review.json')
need(control['registrationAssessment']['additionalCandidatesAccepted']==0 and control['registrationAssessment']['independentlyConfirmedPhysicalPixelControls']==0,'source controls falsely accepted')
need(sha(P/'visual-review.json')==manifest['inputSha256']['visual-review.json']and sha(P/'control-review.json')==manifest['inputSha256']['control-review.json'],'frozen reviews changed')

component_records=[];final_components=[];raw_masks=[];filled_masks=[];raw_variants={};dark_checks=[]
for component_document in T['components']:
 identifier=component_document['componentId']
 raw,holes,sizes,chosen_seed=component(component_document['colorCategory'],component_document['requestedSourceSeed'],35,80)
 need(np.array_equal(raw,decode(component_document['sourceColorMaskRle'])),identifier+' original RGB-HSV four-neighbor component membership')
 need(np.array_equal(holes,decode(component_document['filledGraphicOverlayPixelsRle'])),identifier+' exterior flood and enclosed graphic-hole membership')
 need(sizes==component_document['graphicOverlayHoleAreasPixels'] and tuple(component_document['actualClassifiedSourceSeed'])==chosen_seed,identifier+' hole sizes/seed choice')
 need(int(raw.sum())==component_document['sourceColorPixelCount'] and int(holes.sum())==component_document['filledGraphicOverlayPixelCount'],'pixel counts')
 need(not sizes or max(sizes)<=130,'large unexplained inner source hole')
 filled=raw|holes;mask_polygon=boundary(filled);archived_mask=shape(component_document['maskGeometry'])
 need(mask_polygon.symmetric_difference(archived_mask).area==0 and mask_polygon.area==component_document['pixelCellArea'],'independent exposed-cell-edge contour versus archived raw mask')
 need(all(float(x*2).is_integer() and int(x*2)%2!=0 for xy in archived_mask.exterior.coords for x in xy),'mask half-integer cell-edge convention')
 output=shape(component_document['geometry']);override=component_document['darkSourceOutlineOverride']
 if override is None:
  need(identifier not in ['8-northeast','9-north-tip'] and component_document['contourMethod']=='color_mask_pixel_cell_boundary_estimate','mask mode')
  need(output.symmetric_difference(mask_polygon).area==0,'14 final contours must equal independently rebuilt pixel-cell geometry')
 else:
  need(identifier in ['8-northeast','9-north-tip'] and component_document['contourMethod']=='actual_dark_source_pixel_cycle','two dark override modes only')
  ring=override['denseSourceDarkRing'];pixel_paths=override['sourceDarkPixelPaths'];rgb=np.asarray(im)
  need(override['maximumAllowedSourceRgb']==165 and override['searchCorridorPixels']==3,'actual DARK threshold/search corridor')
  need(ring[0]==ring[-1]and all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1 for a,b in zip(ring,ring[1:])),'actual dark source8-neighbor closure')
  need(all(type(v)is int for xy in ring for v in xy),'dark integer source-pixel centres')
  need(all(max(rgb[y,x])<=165 for x,y in ring),'dark trace leaves actual dark source pixels')
  need(len(override['sourcePixelColourEvidence'])==len(ring),'dense actual RGB evidence size')
  for xy,evidence in zip(ring,override['sourcePixelColourEvidence']):
   x,y=xy;need(xy==evidence['pixel']and list(map(int,rgb[y,x]))==evidence['rgb'],'actual original JPEG RGB evidence')
  # Independently recompute dark-pixel snap ranking. Corridor is only a search condition.
  snapped=[]
  for x,y in override['manualSeeds']:
   candidates=[]
   for yy in range(y-3,y+4):
    for xx in range(x-3,x+4):
     value=int(max(rgb[yy,xx]))
     if value<=165:candidates.append(((xx-x)**2+(yy-y)**2+value*.01,(xx,yy)))
   snapped.append(list(min(candidates)[1]))
  need(snapped==override['actualSourceDarkSeeds'],'actual source-dark seed selection')
  joined=[]
  for a,b,path in zip(snapped,snapped[1:],pixel_paths):
   need(path[0]==a and path[-1]==b,'dark path endpoints')
   segment=LineString([a,b])
   need(all(segment.distance(Point(q))<=3+1e-12 for q in path),'dark path outside bounded source-stroke search corridor')
   joined+=path if not joined else path[1:]
  need(joined==ring,'dense cycle not exact concatenation of actual source paths')
  dense_polygon=Polygon(ring)
  need(dense_polygon.is_valid and not dense_polygon.interiors and dense_polygon.area==override['sourcePolygonAreaPixels'],'dark source polygon')
  need(output.symmetric_difference(dense_polygon).area==0,'dark collinear compression area changed')
  dense_unique=[tuple(q)for q in ring[:-1]];compressed=[tuple(q)for q in output.exterior.coords]
  need(set(compressed)<=set(dense_unique),'dark compression invents vertices')
  offset=dense_unique.index(compressed[0]);rotated=dense_unique[offset:]+dense_unique[:offset]+[compressed[0]];index=0
  for endpoint in compressed[1:]:
   j=index+1
   while rotated[j]!=endpoint:j+=1
   a=rotated[index];dx=endpoint[0]-a[0];dy=endpoint[1]-a[1]
   need(all((q[0]-a[0])*dy==(q[1]-a[1])*dx for q in rotated[index:j+1]),'dark compression replaces noncollinear source route')
   index=j
  need(index==len(rotated)-1,'compressed dark ring lost source path segment')
  dark_checks.append({'componentId':identifier,'darkThresholdMaxRgb':165,'searchCorridorPixels':3,'denseActualSourcePixelCount':len(ring),'compressedActualSourcePixelCount':len(compressed),'actualMaximumRgbOnPath':int(max(max(rgb[y,x])for x,y in ring)),'denseCycleAreaPixels':dense_polygon.area,'compressionSymmetricDifferencePixelArea':0,'allDenseStepsActual8Neighbor':True,'allDenseRgbEvidenceMatchesOriginal':True,'noGapInterpolationOrChord':True,'notLiteralBlack45Threshold':True})
 need(output.is_valid and not output.interiors and output.area==component_document['outputContourAreaPixels'],'valid no-hole final native contour')
 need(output.bounds[0]>1 and output.bounds[1]>1 and output.bounds[2]<W-2 and output.bounds[3]<H-2,'source frame contact')
 threshold_record=next(d for d in T['thresholdSensitivity']if d['componentId']==identifier)
 need(threshold_record['measuresRawColorMaskOnly']is True and threshold_record['applicableToFinalContour']==(override is None),'threshold applicability distinction')
 variant_records={}
 for variant,saturation,value in [('looser',25,70),('tighter',45,95)]:
  other_raw,other_holes,_,_=component(component_document['colorCategory'],component_document['requestedSourceSeed'],saturation,value);other=boundary(other_raw|other_holes)
  values={'pixelCellArea':other.area,'symmetricDifferencePixelArea':int(np.logical_xor(filled,other_raw|other_holes).sum()),'boundaryHausdorffPixels':mask_polygon.boundary.hausdorff_distance(other.boundary)}
  claimed=threshold_record['variants'][variant]
  need(all(abs(v-claimed[key])<1e-12 for key,v in values.items())and claimed['doesNotMeasureTrueBoundaryError']is True,'raw HSV sensitivity differs')
  variant_records[variant]=values
 component_records.append({'componentId':identifier,'quarterNumber':component_document['quarterNumber'],'sourceColorPixels':int(raw.sum()),'filledEnclosedGraphicPixels':int(holes.sum()),'largestEnclosedGraphicHolePixels':max(sizes)if sizes else 0,'maskPixelCellArea':mask_polygon.area,'finalContourMethod':component_document['contourMethod'],'finalContourAreaPixels':output.area,'rawMaskVersusFinalContourSymmetricDifferencePixelArea':mask_polygon.symmetric_difference(output).area,'rawThresholdSensitivity':variant_records,'thresholdSensitivityAppliesToFinalContour':override is None,'nativeGeometryValidNoHoles':True,'touchesSourceImageFrame':False})
 raw_masks.append(raw);filled_masks.append(filled);final_components.append(output)
need(len(dark_checks)==2 and len(final_components)==16,'native hybrid contour counts')
for a,b in itertools.combinations(final_components,2):need(a.intersection(b).area==0,'native source component interior overlap')

# Derive the reflected similarity by independent complex division, not the converter linear solve.
roads=read('all-city-roads-rails.geojson')['features'];places=read('local-place-controls.geojson')['features'];nodes={};node_ways={}
for road in roads:
 refs=road['properties']['source']['nodeRefs'];coords=road['geometry']['coordinates'];need(len(refs)==len(coords),'OSM node sequence count')
 for node,coordinate in zip(refs,coords):
  need(node not in nodes or nodes[node]==coordinate,'inconsistent literal OSM node');nodes[node]=coordinate;node_ways.setdefault(node,set()).add(road['id'])
anchors=read('provisional-georeference-anchors.json');georef=read('provisional-georeference.json');sensitivity=read('registration-sensitivity.json')
need([a['osmNodeId']for a in anchors['anchors']]==[325221618,5907787634],'literal provisional node IDs')
need([a['assumedSourcePixel']for a in anchors['anchors']]==[[252,478],[259,550]],'provisional source assumptions')
for anchor in anchors['anchors']:
 need(nodes[anchor['osmNodeId']]==anchor['coordinates']and set(anchor['sourceWayIds'])<=node_ways[anchor['osmNodeId']],'literal provisional modern node data')
 need(anchor['imageCorrespondenceIndependentlyConfirmed']is False,'assumed image correspondence promoted to accepted control')
to_metric=Transformer.from_crs(4326,23700,always_xy=True);to_world=Transformer.from_crs(23700,4326,always_xy=True);geod=Geod(ellps='WGS84')
image_pairs=np.array([a['assumedSourcePixel']for a in anchors['anchors']],float);target=np.array([to_metric.transform(*a['coordinates'])for a in anchors['anchors']])
def independent_similarity(pairs):
 delta=pairs[1]-pairs[0];world_delta=target[1]-target[0];ratio=complex(*world_delta)/complex(delta[0],-delta[1]);a,b=ratio.real,ratio.imag
 translation=complex(*target[0])-ratio*complex(pairs[0,0],-pairs[0,1])
 return np.array([[a,b,translation.real],[b,-a,translation.imag],[0,0,1]])
matrix=independent_similarity(image_pairs);archived_matrix=np.array(georef['matrixPixelColumnToEov']);matrix_delta=float(abs(matrix-archived_matrix).max())
need(matrix_delta<2e-9,'independent complex similarity mismatch')
fit_residuals=np.linalg.norm((np.c_[image_pairs,np.ones(2)]@matrix.T)[:,:2]-target,axis=1)
need(max(fit_residuals)<1e-7 and georef['independentlyAcceptedPhysicalControlCount']==0 and georef['independentPhysicalHoldoutCount']==0 and georef['sourceImageCorrespondencesIndependentlyVerified']is False,'unresolved control status')
need(georef['claimedAbsoluteAccuracyMetres']is None and georef['sourceProjectionKnown']is False and georef['noReviewRadiusOrAccuracyBoundAssigned']is True,'false source accuracy/CRS claim')
vertices=[np.array(g.exterior.coords)for g in final_components];base=[(np.c_[v,np.ones(len(v))]@matrix.T)[:,:2]for v in vertices]
need(sensitivity['scenarioCount']==16 and sensitivity['assumedIndependentPerCoordinateAnchorPerturbationPixels']==3 and sensitivity['assumedPerturbationWasMeasured']is False,'scenario assumption')
need('NOT_accuracy'in sensitivity['status']and sensitivity['claimedAbsoluteAccuracyMetres']is None,'scenario promoted to accuracy')
scenario_records=[]
for shifts,claimed in zip(itertools.product([-3,3],repeat=4),sensitivity['scenarios']):
 need(list(shifts)==claimed['assumedAnchorPixelCoordinateShifts'],'independent per-coordinate scenario enumeration')
 perturbed=image_pairs+np.array(shifts).reshape(2,2);m=independent_similarity(perturbed);need(abs(m-np.array(claimed['matrixPixelColumnToEov'])).max()<2e-9,'scenario complex-division matrix')
 maxima=[float(np.linalg.norm((np.c_[v,np.ones(len(v))]@m.T)[:,:2]-baseline,axis=1).max())for v,baseline in zip(vertices,base)]
 for c,value in zip(T['components'],maxima):need(abs(value-claimed['maximumModeledDisplacementMByComponent'][c['componentId']])<2e-7,'scenario maximum modeled vertex displacement')
 scenario_records.append({'assumedAnchorCoordinateShifts':list(shifts),'maximumModeledDisplacementAcrossComponentsM':max(maxima),'notAccuracyOrErrorBound':True})

native=read('native-legend-unit-contours.json');output=read('inferred-georeference.geojson');features=output['features'];by_number={f['properties']['sourceLegendNumber']:f for f in features};native_by_number={v['number']:v for v in native['units']};names=visual['sourceTextEvidence']['fullSourceNamesByNumber'];expected_parts={1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:3,9:4,10:2}
need(len(features)==len(native['units'])==10 and output['primaryFeatureCount']==0 and output['status']=='inferred_georeference_only','inferred only ten whole legends')
need(not(P/'registry-entry.json').exists(),'primary registry must not exist')
parentpath=R/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz';parent=shape(next(f['geometry']for f in json.loads(gzip.decompress(parentpath.read_bytes()))['features']if f['properties']['name']=='Kaposvár'and f['properties'].get('usedForAssociation')));parent_metric=transform(to_metric.transform,parent)
# Preserve archived matrix operation order for exact serialized WGS84 reconstruction,
# after independently verifying its mathematical construction above.
def metric_function(x,y,z=None):
 x,y=np.array(x),np.array(y);return(archived_matrix[0,0]*x+archived_matrix[0,1]*y+archived_matrix[0,2],archived_matrix[1,0]*x+archived_matrix[1,1]*y+archived_matrix[1,2])
unit_records=[];native_units={};metric_units={}
for number in range(1,11):
 indices=[i for i,c in enumerate(T['components'])if c['quarterNumber']==number];need(len(indices)==expected_parts[number],'full legend component count')
 family=final_components[indices[0]]if len(indices)==1 else MultiPolygon([final_components[i]for i in indices]);need(family.is_valid and family.equals_exact(shape(native_by_number[number]['geometry']),0),'whole native legend assembly')
 f=by_number[number];props=f['properties'];need(props['name']==native_by_number[number]['name']==names[str(number)],'full source name preservation')
 metric=transform(metric_function,family);world=transform(to_world.transform,metric);need(world.is_valid and world.equals_exact(shape(f['geometry']),0),'exact WGS84 construction after matrix check')
 need(props['estimated']is True and props['boundaryKind']=='inferred_area'and props['canonicalNameIsNeighborhood']is False and props['georeferenceStatus']=='inferred_georeference'and props['georeferenceValidated']is False,'inferred classification')
 need(props['claimedAbsoluteAccuracyMetres']is None and props['usableForAddressAssignment']is False and props['sourceIsOfficial']is False and props['sourceIsHardBoundary']is False and props['currentNameIndependentlyConfirmed']is False and props['independentlyAcceptedPhysicalControlCount']==0,'unproved accuracy/current name/cadastral/address claim')
 need(props['constituentQuarterSplitsCreated']is False and props['fullLegendNamePreserved']is True and props['sourceComponentCount']==len(indices),'fine subdivision or component loss')
 if number==8:need('inferred association'in props['unnumberedComponentAssociation'],'two unnumbered cyan islands association must remain inferred')
 area,perimeter=geod.geometry_area_perimeter(world);need(abs(abs(area)-props['provisionalAreaM2'])<1e-6 and abs(perimeter-props['provisionalPerimeterM'])<1e-6,'provisional area/perimeter arithmetic')
 outside=metric.difference(parent_metric);diagnostic=props['referenceMunicipalityDiagnostic'];need(abs(outside.area-diagnostic['provisionalOutsideAreaM2'])<1e-6 and abs(outside.area/metric.area-diagnostic['provisionalOutsideFraction'])<1e-12 and diagnostic['sourceClipped']is False and diagnostic['notAnAccuracyTest']is True,'unclipped provisional reference diagnostic')
 native_units[number]=family;metric_units[number]=metric;unit_records.append({'number':number,'name':props['name'],'sourceParts':len(indices),'nativeGeometryAndGroupingExactlyReproduced':True,'worldCoordinateConstructionExactlyReproduced':True,'geographicCorrectnessValidated':False,'provisionalAreaM2':abs(area),'provisionalOutsideCurrentMunicipalityFraction':outside.area/metric.area,'sourceClipped':False})
place_by_id={f['id']:f for f in places};coarse=read('coarse-place-diagnostics.json');inverse=np.linalg.inv(archived_matrix)
for diagnostic in coarse['diagnostics']:
 original=place_by_id[diagnostic['sourceFeatureId']];need(original['geometry']['coordinates']==diagnostic['literalCoordinates'],'literal area-place coordinate');X,Y=to_metric.transform(*original['geometry']['coordinates']);pixel=(inverse@np.array([X,Y,1]))[:2];number=diagnostic['sourceLegendNumber']
 need(np.allclose(pixel,diagnostic['provisionalImagePixel'],rtol=0,atol=1e-10),'coarse place transform')
 need(native_units[number].covers(Point(pixel))==diagnostic['insideInferredSourceFamily']and abs(metric_units[number].distance(Point(X,Y))-diagnostic['distanceToInferredSourceFamilyM'])<1e-7,'coarse place-region arithmetic')
 need(diagnostic['usedAsRegistrationControl']is False and diagnostic['notAPhysicalHoldoutOrAccuracyResidual']is True,'place labels promoted to geographic controls')

for name,digest in manifest['inputSha256'].items():need(sha(P/name)==digest,'final input hash '+name)
for name,digest in manifest['artifactsSha256'].items():need(sha(P/name)==digest,'final generated hash '+name)
need(sha(R/manifest['converterPath'])==manifest['converterSha256']and sha(P/'extract_source_masks.py')==manifest['maskHelperSha256']and sha(P/'trace_dark_overrides.py')==manifest['darkOverrideHelperSha256'],'final converter/helper hashes')
need(sha(P/'generated-manifest.json')==manifest_digest,'artifacts changed during audit')
registry=read('inferred-registry-entry.json');need(sha(R/registry['path'])==registry['sha256'],'inferred registry hash')
need(registry['propertyOverrides']['boundaryKind']=='inferred_area'and registry['propertyOverrides']['estimated']is True and registry['propertyOverrides']['canonicalNameIsNeighborhood']is False and registry['propertyOverrides']['claimedAbsoluteAccuracyMetres']is None,'registry inferred-only override')
report={'schemaVersion':1,'reviewer':'independent fig81_visual agent; offline native-source and model-mathematics QA','independentAuditorPath':str(Path(__file__).resolve().relative_to(R)),'independentAuditorSha256':sha(Path(__file__)),'verdict':'PASS_SOURCE_CONSTRUCTION_AND_PROVISIONAL_MODEL_MATHEMATICS_ONLY; GEOGRAPHIC_VALIDITY_UNRESOLVED','scope':'Native source-mask/dark-stroke construction and calculations are reproducible. No source-image/geographic correspondence, absolute position, current boundary, legal status or address assignment is validated. All ten outputs remain separate inferred candidates; primary0.','sourceIdentity':{'pdfSha256':sha(pdf),'actualPdfPage':18,'imageXref':124,'archivedJpegBytesEqualActualPdfImage':True,'imageSha256':sha(P/'kaposvar-p18-source.jpeg'),'nativeSize':[625,883],'period':'September2014; source-map projection and underlying data date unknown.'},'independentMethods':['Direct original JPEG RGB to PillowHSV; explicit four-neighbor BFS independently selects each nearest substantial manually seeded color component.','Independent exterior-background flood determines only enclosed graphic-mask holes. Every raw/filled RLE pixel and hole count is reproduced.','Exposed directed pixel-cell sides reconstruct cell polygons without the converter row-rectangle union; all area-preserving collinear compression/geometry checks pass.','Two dark source-centre cycles independently checked against original RGB, documented snap choices,3px search corridor, every actual8-neighbor step and exact collinear compression;165 is a dark threshold, not literal-black45.','Provisional reflected similarity independently derived by complex division from literal modern node data and unvalidated image assumptions. All sixteen independent per-coordinate±3px scenarios and displacements recomputed.','Ten whole source legend groups and all WGS84 coordinate construction, area and place/reference diagnostics reproduced; arithmetic checks are not geographic verification.'],'sourceConstruction':{'components':component_records,'darkSourceCycleChecks':dark_checks,'sourceComponentCount':16,'wholeLegendUnitCount':10,'maskCellFinalContourCount':14,'actualDarkSourceCentreCycleCount':2,'allOutputNativeContoursValidNoHoles':True,'allSourceComponentsAwayFromImageFrame':True,'pairwiseNativeContourInteriorOverlapArea':0,'noHullBufferFrameClosureOrInventedRuralBridge':True,'actualDrawnOutlineAccuracyCertified':False,'twoUnnumberedCyanComponentAssociationsRemainInferred':True},'visualInspection':{'originalNativeSourceAndFinalOverlayInspected':True,'twoEnlargedDarkCycleOverlaysInspected':True,'observations':['Final contours preserve all sixteen separate colored areas and ten complete legend names.','Two corrected outer dark-source cycles follow the small northeast cyan8 and northern orange9 outlines across CAD/digit-occluded color notches. Neither is closed through a missing source-pixel gap.','Fourteen color-mask contours remain explicit estimates of drawn borders, subject to color/JPEG/line-overlay classification; raw HSV threshold sensitivity is not boundary error.','Enclosed graphic ink/CAD holes are filled; external white countryside, component gaps and source-frame edges are not used as invented bridges.','No independently identified physical geographic holdout junction has been established.']},'provisionalRegistration':{'status':'inferred_georeference','geographicValidity':'UNRESOLVED','independentlyAcceptedPhysicalControls':0,'independentPhysicalHoldouts':0,'literalModernNodeIds':[325221618,5907787634],'assumedSourcePixels':image_pairs.tolist(),'independentComplexDivisionMatrixPixelColumnToEov':matrix.tolist(),'maximumDifferenceFromArchivedMatrix':matrix_delta,'internalTwoReferenceAlgebraicResidualsM':fit_residuals.tolist(),'twoReferenceClosureDoesNotProveGeographicCorrectness':True,'sourceProjectionKnown':False,'claimedAbsoluteAccuracyMetres':None,'noReviewRadiusAccuracyBoundOrConfidenceIntervalAssigned':True,'pyprojVersion':pyproj.__version__,'projVersion':pyproj.proj_version_str,'projNetworkDisabled':True},'registrationSensitivity':{'scenarioCount':16,'eachOfFourAnchorCoordinatesIndependentlyPerturbedByPixels':[-3,3],'allScenarioMatricesAndPerComponentDisplacementsReproduced':True,'notSameAsEarlierRadial3pxThoughtExperiment':True,'scenarios':scenario_records,'assumedPerturbationsAreNotMeasuredErrors':True,'notAccuracyErrorOrConfidenceBounds':True},'inferredLegendOutputs':unit_records,'coarsePlaceDiagnostics':{'literalPlaceRecordsRecomputed':len(coarse['diagnostics']),'usedAsPhysicalControls':False,'notGeographicAccuracyResiduals':True},'classification':{'inferredOnlyFeatures':10,'primaryFeatures':0,'primaryRegistryCreated':False,'unsupportedConstituentFineSplits':False,'currentNamesIndependentlyConfirmed':False,'currentLegalOrCadastralBoundaryVerified':False,'sourceReuseRightsIndependentlyEstablished':False,'usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None},'frozenArtifactHashesSha256':{name:sha(P/name)for name in list(manifest['artifactsSha256'])+['generated-manifest.json','visual-review.json','control-review.json']},'limitations':['All world geometry has unresolved inferred georeferencing. Correct transformation arithmetic cannot establish that assumed road/image associations are true.','Native raster color classification and dark165 stroke-centre selection are historical-map digitization choices, not surveyed or current cadastral boundaries.','Two unnumbered cyan islands are associated with Kaposfüred by same-color/context inference.','Raw HSV threshold changes and hypothetical anchor perturbations measure model sensitivity only; no observed true error, accuracy radius or confidence interval is assigned.','Unknown source projection, underlying cadastral-map date, current fine-name validity and municipal-map open-reuse license.','Not usable for automatic address assignment.']}
review_path=P/'independent-review.json';payload=(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
if cli_options.write_review:review_path.write_bytes(payload)
elif cli_options.check:need(review_path.exists()and review_path.read_bytes()==payload,'frozen independent review differs')
print(json.dumps({'verdict':report['verdict'],'sourceComponents':16,'wholeLegendUnits':10,'inferredFeatures':10,'primaryFeatures':0,'acceptedPhysicalControls':0,'geographicValidity':'UNRESOLVED','sourceDarkCycles':2,'independentScenarios':16,'reviewWritten':cli_options.write_review,'readOnlyCheck':not cli_options.write_review,'reviewSha256':hashlib.sha256(payload).hexdigest()},ensure_ascii=False))
