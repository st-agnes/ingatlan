#!/usr/bin/env python3
"""Native Kaposvár raster outlines plus a separately labelled inferred registration.

There are no primary/validated geographic outputs. Two assumed image/road pairs
only define a provisional similarity. Unknown absolute accuracy stays null.
"""
import argparse,gzip,hashlib,importlib.util,itertools,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-kaposvar-raster-next'
IMAGE_SHA='54dc5dc7a697bafdc3cb662a41ed6f6cfcc21ac98ec38cffa45ac14148477676'
PDF_SHA='8dcf6a39c018d11e9b7283a263d5887f919f7c5ba7c36862a6e83c76a13f159a'
URL='https://kph.kaposvar.hu/eloterjesztesek/et20140929/documents/0301.pdf'
PINNED={'kaposvar-p18-source.jpeg':IMAGE_SHA,
 'all-city-roads-rails.geojson':'b0556317cdf5e911c95206f73a37a2f954583cb519410aec8c5f5b682290b793',
 'local-place-controls.geojson':'b3e5890dd2d3429629029e200d7073782d347e52ca91a2858bfa438a8cfa4afb',
 'provisional-georeference-anchors.json':'930a29688f7a54ab5d7ab9b056a4288cf0884b7eeb3fa5799c12605414ae1878',
 'source-extraction.json':'580dd4f15c2518975e181cb677df52e3122d6093afc1e2f90060d50151be56c8',
 'visual-review.json':'930237c14721264126d41fbf4b2150747b6f7b34314c76ba080494ac535bc5dd',
 'control-review.json':'df087606841ffc45603b2b6c1447dca3b554410a33ddf9e74b8287519a680b6d'}
NAMES={1:'Belváros',2:'Északnyugati városrész',3:'Északi városrész',
 4:'Kisgát és környéke, Cukorgyár, Pécsi utca és környéke',
 5:'Kecelhegy – Cser',6:'Donner – Rómahegy',7:'Ivánfahegy – Kaposszentjakab',
 8:'Kaposfüred',9:'Toponár – Répáspuszta – Fészerlak – Deseda',10:'Töröcske – Zselic kertváros'}
EXPECTED_PARTS={1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:3,9:4,10:2}
METHOD=('Native625×883 original2014 municipal JPEG color-mask extraction. Manually identified '
 'source-colored components use documented HSV classes and4-neighbour connectivity. Small enclosed '
 'source-number/CAD-ink mask holes are filled after source review; white exterior/rural gaps and '
 'separate components are not bridged. Every native contour edge follows actual classified pixel-cell '
 'boundaries; only exactly collinear cell-edge vertices are omitted. Fourteen components retain '
 'raster-color estimates of the drawn outline. Two specifically reviewed CAD/digit-occluded silhouettes '
 '(northeast8 and northernmost9) instead follow closed8-neighbour cycles of actual dark source pixels '
 '(maxRGB165) within3px manually identified outer-stroke corridors; their full RGB/pixel paths are archived. '
 'No missing dark-pixel gap is bridged. WGS84 positions use an INFERRED, unvalidated '
 'EOV similarity from two assumed source-image/modern-road-node correspondences. Literal modern '
 'node coordinates are verified, but no image correspondence or independent physical holdout is '
 'established. No hull, image-frame closure, arbitrary closing chord, buffering, repair, current-road '
 'boundary substitution or clipping to current municipal limits. Unknown absolute accuracy remains null.')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(d):return(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
 import numpy as np,pyproj
 from PIL import Image,ImageDraw
 from pyproj import Transformer,Geod
 from shapely.geometry import Polygon,MultiPolygon,shape,mapping,Point
 from shapely.ops import transform,unary_union
 pyproj.network.set_network_enabled(False)
 artifacts={}
 def save(name,data):
  b=encode(data);artifacts[name]=hashlib.sha256(b).hexdigest();p=OUT/name
  if check:
   if not p.exists()or p.read_bytes()!=b:raise ValueError('Stale or missing '+str(p))
  else:p.write_bytes(b)
 for name,digest in PINNED.items():
  if sha(OUT/name)!=digest:raise ValueError('Changed frozen source input '+name)
 helper=OUT/'extract_source_masks.py';spec=importlib.util.spec_from_file_location('kaposvar_native_color_masks',helper)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 components=module.extract();variants={n:module.extract(*v)for n,v in [('looser',(25,70)),('tighter',(45,95))]}
 if len(components)!=16:raise ValueError('Expected16 actual source-colored components')
 component_geometries=[shape(c['geometry'])for c in components]
 for i,g in enumerate(component_geometries):
  for h in component_geometries[i+1:]:
   if g.intersection(h).area!=0:raise ValueError('Source component pixel-cell interiors overlap')
 roads=json.loads((OUT/'all-city-roads-rails.geojson').read_text())['features'];nodes={};node_ways={}
 for road in roads:
  for node,c in zip(road['properties']['source']['nodeRefs'],road['geometry']['coordinates']):
   if node in nodes and nodes[node]!=c:raise ValueError('Inconsistent actual control node coordinates')
   nodes[node]=c;node_ways.setdefault(node,set()).add(road['id'])
 anchors=json.loads((OUT/'provisional-georeference-anchors.json').read_text())
 for anchor in anchors['anchors']:
  node=anchor['osmNodeId']
  if nodes.get(node)!=anchor['coordinates']or not set(anchor['sourceWayIds']).issubset(node_ways[node]):
   raise ValueError('Provisional world reference is not a literal archived OSM node')
  if anchor['imageCorrespondenceIndependentlyConfirmed']is not False:raise ValueError('Unvalidated image association promoted to observed control')
 to_metric=Transformer.from_crs(4326,23700,always_xy=True);to_world=Transformer.from_crs(23700,4326,always_xy=True)
 image_pairs=np.array([a['assumedSourcePixel']for a in anchors['anchors']],dtype=float)
 geographic_pairs=np.array([to_metric.transform(*a['coordinates'])for a in anchors['anchors']])
 def similarity(pixels):
  dx,dy=pixels[1]-pixels[0];de,dn=geographic_pairs[1]-geographic_pairs[0]
  a,b=np.linalg.solve([[dx,dy],[-dy,dx]],[de,dn]);e,f=geographic_pairs[0]-np.array([[a,b],[b,-a]])@pixels[0]
  return np.array([[a,b,e],[b,-a,f],[0,0,1]])
 matrix=similarity(image_pairs);inverse=np.linalg.inv(matrix);residuals=np.linalg.norm((np.c_[image_pairs,np.ones(2)]@matrix.T)[:,:2]-geographic_pairs,axis=1)
 def metric_function(x,y,z=None):
  x,y=np.array(x),np.array(y)
  return(matrix[0,0]*x+matrix[0,1]*y+matrix[0,2],matrix[1,0]*x+matrix[1,1]*y+matrix[1,2])
 def world_polygon(g):
  metric=transform(metric_function,g)
  return transform(to_world.transform,metric)
 threshold_diagnostics=[]
 for i,(component,g)in enumerate(zip(components,component_geometries)):
  mask_g=shape(component['maskGeometry'])
  diag={'componentId':component['componentId'],'baselineThresholds':{'minimumSaturation':35,'minimumValue':80},
    'measuresRawColorMaskOnly':True,'applicableToFinalContour':component['darkSourceOutlineOverride']is None,'variants':{}}
  for variant_name,other in variants.items():
   h=shape(other[i]['maskGeometry'])
   diag['variants'][variant_name]={'pixelCellArea':h.area,'symmetricDifferencePixelArea':mask_g.symmetric_difference(h).area,
    'boundaryHausdorffPixels':mask_g.boundary.hausdorff_distance(h.boundary),'doesNotMeasureTrueBoundaryError':True}
  threshold_diagnostics.append(diag)
 # Exact scenario computations only. ±3px is an assumed input, not a measured
 # placement error and not an absolute accuracy/confidence interval.
 native_vertices=[np.array(g.exterior.coords)for g in component_geometries]
 base_metric=[(np.c_[v,np.ones(len(v))]@matrix.T)[:,:2]for v in native_vertices]
 scenarios=[]
 for shifts in itertools.product([-3,3],repeat=4):
  perturbed=image_pairs+np.array(shifts).reshape(2,2);m=similarity(perturbed)
  maxima=[float(np.linalg.norm((np.c_[v,np.ones(len(v))]@m.T)[:,:2]-base,axis=1).max())
          for v,base in zip(native_vertices,base_metric)]
  scenarios.append({'assumedAnchorPixelCoordinateShifts':list(shifts),'matrixPixelColumnToEov':m.tolist(),
   'maximumModeledDisplacementMByComponent':dict(zip([c['componentId']for c in components],maxima))})
 save('source-contour-components.json',{'schemaVersion':1,'coordinateReference':'native_JPEG_pixel_centres_and_pixel_cell_edges_NOT_WGS84',
  'sourceImageSha256':IMAGE_SHA,'sourceSizePixels':[625,883],
  'pixelConvention':'MaskGeometry uses occupied pixel-cell edges[x-.5,x+.5]×[y-.5,y+.5]; the two dark-source overrides instead follow integer JPEG-pixel centres. Every component declares its outputCoordinateConvention.',
  'method':METHOD,'literalBlackOutlineTracedForAllComponents':False,'actualDarkSourcePixelOverrides':2,
  'baselineHsvThresholds':{'saturation':35,'value':80,'hueCategories':module.RANGES},
  'sourceComponentCount':16,'fullLegendUnitCount':10,'components':components,
  'smallEnclosedGraphicMaskHolesFilledOnly':True,'trueSourceGeographicHoleEstablished':False,
  'whiteExteriorGapsAndSeparateComponentsBridged':False,'frameClosureUsed':False,'sourcePixelCellInteriorOverlapArea':0,
  'sourceMaskHelperSha256':sha(helper),'darkOverrideHelperSha256':sha(OUT/'trace_dark_overrides.py'),
  'thresholdSensitivity':threshold_diagnostics})
 save('registration-sensitivity.json',{'schemaVersion':1,'status':'hypothetical_model_sensitivity_NOT_accuracy',
  'assumedIndependentPerCoordinateAnchorPerturbationPixels':3,'assumedPerturbationWasMeasured':False,
  'scenarioCount':16,'meaning':'Exact changes in the provisional similarity under16corner cases of assumed ±3px shifts in each of4anchor coordinates. Not an observed error, statistical confidence interval, guaranteed boundary or accuracy radius.',
  'scenarios':scenarios,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False})
 save('provisional-georeference.json',{'schemaVersion':1,'status':'inferred_georeference',
  'provisionalAnchorSpecification':anchors,'literalWorldCoordinatesVerified':True,
  'sourceImageCorrespondencesIndependentlyVerified':False,'independentlyAcceptedPhysicalControlCount':0,
  'independentPhysicalHoldoutCount':0,'matrixPixelColumnToEov':matrix.tolist(),
  'internalTwoAnchorFitResidualM':residuals.tolist(),'fitResidualMeaning':'Two pairs exactly determine the similarity; tiny residuals are algebraic closure, not evidence that assumed source correspondences are correct.',
  'provisionalModelMetresPerPixel':float(np.hypot(matrix[0,0],matrix[0,1])),
  'sourceProjectionKnown':False,'metricCrs':'EPSG:23700','outputCrs':'EPSG:4326',
  'inverseProjectionPipeline':to_world.get_last_used_operation().definition if to_world.description!='unavailable until proj_trans is called'else None,
  'pyprojVersion':pyproj.__version__,'projVersion':pyproj.proj_version_str,'projNetworkDisabled':True,
  'claimedAbsoluteAccuracyMetres':None,'noReviewRadiusOrAccuracyBoundAssigned':True,
  'unresolvedReason':'Two source-image/road pairs remain manual assumptions; faint CAD topology did not permit independent validation of six further candidate junctions. See control-review.json.',
  'usableForAddressAssignment':False})
 parent_path=ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
 parent=shape(next(f for f in json.loads(gzip.decompress(parent_path.read_bytes()))['features']
                   if f['properties']['name']=='Kaposvár'and f['properties'].get('usedForAssociation'))['geometry'])
 parent_metric=transform(to_metric.transform,parent);geod=Geod(ellps='WGS84');features=[];native_quarters={};world_quarters={}
 for number,name in NAMES.items():
  subset=[(c,g)for c,g in zip(components,component_geometries)if c['quarterNumber']==number]
  if len(subset)!=EXPECTED_PARTS[number]:raise ValueError('Wrong source component count for quarter'+str(number))
  g=subset[0][1]if len(subset)==1 else MultiPolygon([v for c,v in subset])
  if not g.is_valid:raise ValueError('Invalid assembled native legend unit')
  world=world_polygon(g);metric=transform(metric_function,g)
  if not world.is_valid:raise ValueError('Invalid provisionally registered quarter')
  area,perimeter=geod.geometry_area_perimeter(world);outside=metric.difference(parent_metric)
  native_quarters[number]=g;world_quarters[number]=world
  props={'name':name,'municipality':'Kaposvár','boundaryKind':'inferred_area','estimated':True,
   'candidateBoundaryKind':'neighbourhood'if number in [1,2,3,8]else'planning_unit',
   'canonicalNameIsNeighborhood':False,'georeferenceStatus':'inferred_georeference',
   'sourceLegendNumber':number,'fullLegendNamePreserved':True,'sourceComponentCount':len(subset),
   'sourceComponentIds':[c['componentId']for c,g in subset],'constituentQuarterSplitsCreated':False,
   'sourceSemantics':'Original municipality defined10városrészek; multi-name legend units remain whole and are not independent constituent-name boundaries.',
   'method':METHOD,'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':18,'printedPage':18,'imageXref':124,'imageSha256':IMAGE_SHA}],
   'sourcePeriod':'September2014; underlying cadastral-map date unknown.',
   'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,
   'claimedAbsoluteAccuracyMetres':None,'georeferenceValidated':False,'independentlyAcceptedPhysicalControlCount':0,
   'geometryVerificationStatus':'native_color_mask_with_unvalidated_inferred_georeference',
   'reviewStatus':'estimated_candidate_not_verified','currentNameIndependentlyConfirmed':False,
   'literalBlackStrokeOutlineClaimed':False,'sourceFrameClosureUsed':False,
   'referenceMunicipalityDiagnostic':{'provisionalOutsideAreaM2':outside.area,'provisionalOutsideFraction':outside.area/metric.area,
      'sourceClipped':False,'notAnAccuracyTest':True},
   'provisionalAreaM2':abs(area),'provisionalPerimeterM':perimeter,
   'license':'Municipal-map open-reuse licence unverified; ODbL-1.0 applies to OSM geographical references.',
   'attribution':'Kaposvár2014Integrált Településfejlesztési Stratégia,page18; geographical reference ©OpenStreetMap contributors.'}
  if number==8:props['unnumberedComponentAssociation']='Two detached cyan footprints assigned to8 by the unique same source color and visual map context; neither has its own numeral. This remains an inferred association.'
  features.append({'type':'Feature','id':'manual:kaposvar-raster-unit:'+str(number),'properties':props,'geometry':mapping(world)})
 save('inferred-georeference.geojson',{'type':'FeatureCollection','status':'inferred_georeference_only','primaryFeatureCount':0,
  'usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None,'features':features})
 save('native-legend-unit-contours.json',{'schemaVersion':1,'coordinateReference':'native_JPEG_pixels_NOT_WGS84',
  'sourceImageSha256':IMAGE_SHA,'units':[{'number':n,'name':NAMES[n],'geometry':mapping(g)}for n,g in native_quarters.items()],
  'sourceLegendUnitCount':10,'sourceColoredComponentCount':16,'geographicRegistrationValidated':False})
 # Place points are only coarse semantic checks, never source junction controls.
 associations={'Belváros':1,'Kisgát':4,'Kecelhegy':5,'Cser':5,'Donner':6,'Rómahegy':6,
  'Ivánfahegy':7,'Kaposszentjakab':7,'Kaposfüred':8,'Toponár':9,'Répáspuszta':9,'Fészerlakpuszta':9,'Töröcske':10,'Zselic-kertváros':10}
 place_checks=[]
 for place in json.loads((OUT/'local-place-controls.geojson').read_text())['features']:
  name=place['properties']['name']
  if name not in associations:continue
  coord=place['geometry']['coordinates'];eov=np.array([*to_metric.transform(*coord),1]);pixel=(inverse@eov)[:2];n=associations[name]
  place_checks.append({'sourceFeatureId':place['id'],'name':name,'literalCoordinates':coord,'sourceLegendNumber':n,
   'provisionalImagePixel':pixel.tolist(),'insideInferredSourceFamily':native_quarters[n].covers(Point(pixel)),
   'distanceToInferredSourceFamilyM':transform(metric_function,native_quarters[n]).distance(Point(eov[:2])),
   'usedAsRegistrationControl':False,'notAPhysicalHoldoutOrAccuracyResidual':True})
 save('coarse-place-diagnostics.json',{'schemaVersion':1,'diagnostics':place_checks,
  'meaning':'Contemporary OSM area-name points versus provisional historic colored footprints; these are NOT actual source-pixel point correspondences or a geographic accuracy test.',
  'claimedAbsoluteAccuracyMetres':None})
 # Projection was now exercised; preserve the actual pipeline separately.
 save('projection-provenance.json',{'metricCrs':'EPSG:23700','outputCrs':'EPSG:4326',
  'actualInverseProjectionPipeline':to_world.get_last_used_operation().definition,
  'libraryDatumOperationAccuracyMetadataM':to_world.get_last_used_operation().accuracy,
  'metadataNotSourceBoundaryAccuracy':True,'claimedAbsoluteAccuracyMetres':None})
 save('conversion-proof.json',{'schemaVersion':1,'method':METHOD,'sourceImageSha256':IMAGE_SHA,'sourcePdfSha256':PDF_SHA,
  'nativeLegendUnits':10,'nativeColoredComponents':16,'provisionalGeographicFeatures':10,'primaryFeatures':0,
  'allRawNativeMasksConvertedWithExactPixelCellArea':True,'colorMaskEstimatedContours':14,
  'actualDarkSourcePixelOverrideContours':2,'sourceFrameClosureUsed':False,
  'separateComponentsConnectedOrWhiteRuralGapsFilled':False,'allOutputFeaturesInferredGeoreference':True,
  'independentlyAcceptedPhysicalControlCount':0,'claimedAbsoluteAccuracyMetres':None,
  'sourceMaskHelperSha256':sha(helper),'inferredOutputSha256':artifacts['inferred-georeference.geojson'],
  'currentMunicipalityArchiveSha256':sha(parent_path),'usableForAddressAssignment':False,
  'reproduce':'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kaposvar-raster-next.py --check'})
 save('inferred-registry-entry.json',{'id':'kaposvar-raster-inferred-georeference',
  'path':str((OUT/'inferred-georeference.geojson').relative_to(ROOT)),'sha256':artifacts['inferred-georeference.geojson'],
  'municipality':'Kaposvár','method':METHOD,'evidenceUrls':[URL],
  'license':'Municipal source-map reuse rights unverified; ODbL-1.0 for OSM reference data.',
  'propertyOverrides':{'estimated':True,'boundaryKind':'inferred_area','canonicalNameIsNeighborhood':False,
    'georeferenceStatus':'inferred_georeference','usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None},
  'reviewPath':str((OUT/'independent-review.json').relative_to(ROOT)),
  'rightsStatus':'Public municipal publication; open-map reuse licence not independently established.'})
 save('generated-manifest.json',{'schemaVersion':1,'status':'separate_inferred_batch_not_primary',
  'inputSha256':PINNED,'converterPath':str(Path(__file__).relative_to(ROOT)),'converterSha256':sha(Path(__file__)),
  'maskHelperSha256':sha(helper),'darkOverrideHelperSha256':sha(OUT/'trace_dark_overrides.py'),
  'artifactsSha256':dict(artifacts),'primaryFeatures':0,
  'inferredFeatures':10,'sourceComponents':16,'claimedAbsoluteAccuracyMetres':None,'usableForAddressAssignment':False})
 if not check:
  preview=Image.open(OUT/'kaposvar-p18-source.jpeg').convert('RGB');scale=4;preview=preview.resize((625*scale,883*scale));draw=ImageDraw.Draw(preview)
  for c,g in zip(components,component_geometries):
   draw.line([(x*scale,y*scale)for x,y in g.exterior.coords],fill='black',width=1)
  preview.save(OUT/'native-mask-contour-preview.png')
 print(json.dumps({'nativeSourceComponents':16,'nativeFullLegendUnits':10,'inferredGeoreferenceFeatures':10,
  'primaryFeatures':0,'independentlyAcceptedPhysicalControls':0,'claimedAbsoluteAccuracyMetres':None,
  'inferredSha256':artifacts['inferred-georeference.geojson'],'check':check},ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');build(p.parse_args().check)
