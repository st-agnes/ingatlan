#!/usr/bin/env python3
"""Offline Kecskemét outer source-map investigation. Source-node acquisition only."""
import argparse,hashlib,json,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-kecskemet-outer-next'
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
BBOX=(19.59,46.87,19.70,46.97)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def extract():
 import osmium
 started=time.monotonic();features=[];stats={'filteredWays':0,'selectedWays':0};xmin,ymin,xmax,ymax=BBOX
 class Collector(osmium.SimpleHandler):
  def way(self,obj):
   stats['filteredWays']+=1
   if not any(n.location.valid()and xmin<=n.lon<=xmax and ymin<=n.lat<=ymax for n in obj.nodes):return
   tags=dict(obj.tags)
   if tags.get('highway') in ['construction','proposed']:return
   if any(not n.location.valid()for n in obj.nodes):raise ValueError('Incomplete actual source way')
   features.append({'type':'Feature','id':f'osm:way:{obj.id}','properties':{'name':tags.get('name:hu',tags.get('name','')),'source':{'provider':'openstreetmap','osmType':'way','osmId':obj.id,'url':f'https://www.openstreetmap.org/way/{obj.id}','tags':tags,'nodeRefs':[n.ref for n in obj.nodes],'objectVersion':obj.version,'objectTimestamp':str(obj.timestamp),'geometryUnmodified':True,'geometryProcessing':'Literal complete source-way node sequence. Rectangle is acquisition only, never a neighborhood boundary.','license':'ODbL-1.0','attribution':'©OpenStreetMap contributors'}},'geometry':{'type':'LineString','coordinates':[[n.lon,n.lat]for n in obj.nodes]}});stats['selectedWays']+=1
 with tempfile.TemporaryDirectory(prefix='otthonra-kec-outer-')as temp:
  Collector().apply_file(str(PBF),locations=True,idx='sparse_file_array,'+str(Path(temp)/'nodes.idx'),filters=[osmium.filter.KeyFilter('highway')])
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/'all-local-roads.geojson';write(p,{'type':'FeatureCollection','features':features})
 write(OUT/'extraction-proof.json',{'sourcePbfSha256':sha(PBF),'bboxAcquisitionOnly':BBOX,'statistics':stats,'outputSha256':sha(p),'nativeFilter':'KeyFilter(highway); all actual source nodes, including unnamed and motorway ways.','includesUnnamedWays':True,'elapsedSeconds':round(time.monotonic()-started,3)})
 print(json.dumps(stats))

IMAGE_SHA='8d6217e4ae20dadfd07141aaed4dff0c057166fd60f30d8a7c0eec9b9fd5079d'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
METHOD=('Manual source-black-outline interpretation on the exact original embedded2021 municipal figure79 JPEG. Manually selected source-stroke seeds guide connected dark source-pixel paths; every dense vertex is an actual source pixel(maxRGB45) and every step is an8-neighbor source-pixel step. Only strictly collinear vertices are compressed. A frozen affine transform fitted to five exact contemporary OSM-node coordinates and manually located image junctions georeferences the historical illustration. No current-road substitution, generated closing chord, gap bridge, snapping of geographic geometry, buffer, repair or inferred extent.')
def encode(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def save(p,d,check):
 b=encode(d)
 if check:
  if not p.exists() or p.read_bytes()!=b:raise ValueError('Stale or missing '+str(p))
 else:p.write_bytes(b)
def compress_collinear(ring):
 pts=list(ring[:-1]);changed=True
 while changed:
  changed=False;out=[]
  for i,b in enumerate(pts):
   a=pts[i-1];c=pts[(i+1)%len(pts)]
   if (b[0]-a[0])*(c[1]-b[1])==(b[1]-a[1])*(c[0]-b[0]) and (b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])>0:changed=True
   else:out.append(b)
  pts=out
 return pts+[pts[0]]
def build(check=False):
 import importlib.util,gzip
 import numpy as np
 from PIL import Image,ImageDraw
 from shapely.geometry import Polygon,shape,mapping
 from pyproj import Geod
 image=OUT/'figure79-source.jpeg'
 if sha(image)!=IMAGE_SHA:raise ValueError('Changed original publisher image')
 review=json.loads((OUT/'fine-map-review.json').read_text());calibration=review['comparisonMethod'];M=np.array(calibration['matrixOriginalJpegColumnToWgs84'])
 if len(calibration['controls'])!=5 or M.shape!=(3,3) or not np.isfinite(M).all():raise ValueError('Invalid frozen source controls')
 roads_path=OUT/'all-local-roads.geojson';extraction=json.loads((OUT/'extraction-proof.json').read_text())
 if sha(roads_path)!=extraction['outputSha256']:raise ValueError('Changed literal control-road source')
 actual_nodes={}
 for road in json.loads(roads_path.read_text())['features']:
  for node,coord in zip(road['properties']['source']['nodeRefs'],road['geometry']['coordinates']):
   if node in actual_nodes and actual_nodes[node]!=coord:raise ValueError('Conflicting literal node coordinates')
   actual_nodes[node]=coord
 for control in calibration['controls']:
  if actual_nodes.get(control['osmNodeId'])!=control['coordinates']:raise ValueError('Control is not an actual literal OSM node')
 world_controls=np.c_[np.array([c['coordinates']for c in calibration['controls']]),np.ones(5)]
 pixel_controls=np.array([c['renderedPage2xPixels']for c in calibration['controls']])
 fitted_world_to_render=np.vstack([np.linalg.lstsq(world_controls,pixel_controls,rcond=None)[0].T,[0,0,1]])
 native_to_render=np.array(calibration['matrixOriginalJpegColumnToRenderedPage2x'])
 if not np.allclose(np.linalg.inv(fitted_world_to_render)@native_to_render,M,rtol=0,atol=1e-11):raise ValueError('Affine matrix does not reproduce literal controls')
 helper=OUT/'trace-figure79-pixels.py';spec=importlib.util.spec_from_file_location('otthonra_figure79_pixel_trace',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 rgb=np.asarray(Image.open(image).convert('RGB'));values=rgb.max(axis=2)
 country=ROOT/'data/neighborhoods/sources/country-osm';parents=json.loads(gzip.decompress((country/'municipalities.geojson.gz').read_bytes()))['features'];parent=shape(next(f for f in parents if f['properties']['name']=='Kecskemét' and f['properties'].get('usedForAssociation'))['geometry'])
 geod=Geod(ellps='WGS84');features=[];records=[];rings={'Petőfiváros I.':module.I,'Petőfiváros II.':module.II};pixel_polygons=[]
 for index,(name,ring) in enumerate(rings.items(),1):
  if ring[0]!=ring[-1] or any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):raise ValueError('Source-pixel chain is open or contains a gap')
  if any(values[y,x]>45 for x,y in ring):raise ValueError('Trace leaves actual source-black pixels')
  original=Polygon(ring);simple=compress_collinear(ring);pg=Polygon(simple)
  if not original.is_valid or not pg.is_valid or original.symmetric_difference(pg).area!=0:raise ValueError('Nonvalid source trace or non-collinear simplification')
  pixel_polygons.append(pg);world=(np.c_[np.array(simple),np.ones(len(simple))]@M.T)[:,:2];g=Polygon(world)
  if not g.is_valid or not parent.covers(g):raise ValueError('Invalid/outside-canonical-parent georeferenced trace')
  area,perimeter=geod.geometry_area_perimeter(g)
  props={'name':name,'municipality':'Kecskemét','boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,'method':METHOD,'evidenceUrls':[URL],
   'sourceDocuments':[{'url':URL,'sha256':PDF_SHA,'pdfPageOneBased':169,'printedPage':167,'figure':79,'imageXref':208,'originalImageSha256':IMAGE_SHA}],
   'sourcePeriod':'Municipal publication2021May; underlying orthophoto acquisition date unknown.',
   'sourceRaster':{'path':str(image.relative_to(ROOT)),'sha256':IMAGE_SHA,'width':1694,'height':1202,'pixelCoordinateConvention':'integer PIL source-pixel indices, x right/y down, top-left index0; no halfpixel offset added','denseSourcePixelCount':len(ring),'collinearCompressedPixelCount':len(simple)},
   'estimated':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'claimedAbsoluteAccuracyMetres':None,
   'geometryVerificationStatus':'historical_source_raster_outline_reproduced_georeferencing_accuracy_unknown','reviewStatus':'source_based_historical_boundary_review_required',
   'currentNameEvidence':{'status':'municipal2021fine_label_only','matchingExactCurrentOsmLabelVerified':False,'currentNameIndependentlyConfirmed':False},
   'reviewNotes':['These are the actual separately labelled fine outlines on figure79, not the broad combined Petőfiváros–Felsőszéktó planning extent.',
      'Every dense trace vertex is a black pixel in the unmodified original JPEG. Geographic vertices derive from image georeferencing and MUST NOT be described as original OSM vertices.',
      'Contemporary OSM nodes only supply geographical control coordinates; the manually placed old-image junction locations and the map line width have unknown positional uncertainty.',
      'The current Vízmű arterial is displaced from part of the historical source outline; it is not substituted for the black source line.',
      'Fit residuals describe chosen control consistency, not absolute map/boundary accuracy. No official/current/legal/cadastral or address assignment is established.'],
   'areaM2':abs(area),'perimeterM':perimeter,'license':'Municipal source-map reuse rights not independently established; ODbL applies to OSM geographical controls.','attribution':'Source: Kecskemét MJV Megalapozó VizsgálatII2021, figure79; geographical controls ©OpenStreetMap contributors.'}
  features.append({'type':'Feature','id':'manual:kecskemet-figure79-petofi:'+str(index),'properties':props,'geometry':mapping(g)})
  records.append({'name':name,'valid':True,'literalSourcePixelClosure':True,'allDensePixelsMaxRgbAtMost45':True,'allDenseSteps8Neighbor':True,'densePixelCount':len(ring),'compressedPixelCount':len(simple),'sourcePixelArea':original.area,'simplificationSymmetricDifferencePixelArea':0,'absoluteBoundaryAccuracyMetres':None,'canonicalParentContained':True,'areaM2':abs(area),'geographicCoordinatesAreOsmVertices':False})
 if pixel_polygons[0].intersection(pixel_polygons[1]).area!=0:raise ValueError('Traced adjacent source quarters overlap internally')
 save(OUT/'petofi-source-raster.geojson',{'type':'FeatureCollection','features':features},check)
 save(OUT/'raster-pixel-trace.json',{'sourceImageSha256':IMAGE_SHA,'manualSeeds':module.SECTIONS,'snappedManualSeeds':[{'manualPixel':a,'sourceBlackPixel':b}for a,b in module.snaps.items()],'blackPixelThresholdMaxRgb':45,'manualSearchCorridorPixels':module.PAD,'interpretation':'Search corridor only constrains source-stroke digitization; it never becomes an inferred geographic extent. No missing source-pixel connection is bridged.','sourceBlackPixelPaths':module.paths,'denseClosedPixelRings':rings,'compressedClosedPixelRings':{name:compress_collinear(ring)for name,ring in rings.items()}},check)
 save(OUT/'raster-georeference.json',{'sourceImageSha256':IMAGE_SHA,'actualControlRoadInputSha256':extraction['outputSha256'],'allControlCoordinatesMatchLiteralOsmNodes':True,'affineMatrixReproducesControlFit':True,'controls':calibration['controls'],'matrixOriginalJpegColumnToWgs84':M.tolist(),'fitResidualRenderedPixels':calibration['residualRenderedPixels'],'controlInterpretation':'Literal geographical OSM node coordinates with manually selected approximate image-junction locations, not surveyed black-boundary control positions.','absoluteBoundaryAccuracyMetres':None,'sourceMapProjectionKnown':False,'outputCrs':'EPSG:4326'},check)
 payload=encode({'type':'FeatureCollection','features':features});digest=hashlib.sha256(payload).hexdigest()
 save(OUT/'conversion-proof.json',{'schemaVersion':1,'method':METHOD,'sourceImageSha256':IMAGE_SHA,'sourcePublisherPdfSha256':PDF_SHA,'pixelTraceHelperSha256':sha(helper),'georeferenceControlSubsetSha256':hashlib.sha256(encode({'controls':calibration['controls'],'matrix':M.tolist()})).hexdigest(),'records':records,'sharedSourceSplitUsedIdentically':True,'interiorOverlapPixelArea':0,'outputSha256':digest,'reproduce':'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kecskemet-outer-next.py --check','usableForAddressAssignment':False},check)
 save(OUT/'registry-entry.json',{'id':'kecskemet-petofi-source-raster','path':str((OUT/'petofi-source-raster.geojson').relative_to(ROOT)),'sha256':digest,'municipality':'Kecskemét','method':METHOD,'evidenceUrls':[URL],'license':'Source municipal map reuse rights unverified; ODbL for OSM georeferencing controls.','propertyOverrides':{'boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,'usableForAddressAssignment':False},'reviewPath':str((OUT/'raster-independent-review.json').relative_to(ROOT)),'rightsStatus':'Municipal map public publication, open-reuse licence not independently established.'},check)
 if not check:
  preview=Image.open(image).convert('RGB');draw=ImageDraw.Draw(preview)
  for color,ring in zip(['red','yellow'],rings.values()):draw.line(ring,fill=color,width=2)
  preview.save(OUT/'raster-trace-preview.png')
 print(json.dumps({'fineQuarterSourceTraces':2,'features':[{'name':f['properties']['name'],'vertices':len(f['geometry']['coordinates'][0]),'areaM2':round(f['properties']['areaM2'])}for f in features],'sha256':digest,'check':check},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.extract:extract()
 else:build(a.check)
