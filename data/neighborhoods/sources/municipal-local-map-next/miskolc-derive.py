#!/usr/bin/env python3
"""Exact raster-cell source construction for Miskolc's 17 actually mapped units.
Source groups remain groups; no copying their footprint onto contained names.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,unicodedata
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
spec=importlib.util.spec_from_file_location('raster_cell_tools',ROOT/'scripts/neighborhoods/derive-local-map-next.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
SEEDS=[(1,695,92),(2,779,125),(3,793,274),(4,684,331),(5,700,203),(6,601,104),(7,676,167),(8,667,229),(9,641,257),(10,568,343),(11,549,245),(12,573,191),(13,516,65),(14,443,75),(15,447,168),(16,471,298),(17,210,199)]

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if c.isalnum())
def encoded(o):return json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n'

def build():
 sem=json.loads((P/'miskolc-source-semantics.json').read_text());reg=json.loads((P/'miskolc-registration.json').read_text());mat=np.array(reg['matrixPixelToEov']);rgb=np.array(Image.open(P/'miskolc-p228-original.jpeg').convert('RGB')).astype(int)
 blue=(rgb[:,:,2]-rgb[:,:,0]>40)&(rgb[:,:,1]-rgb[:,:,0]>24)&(rgb[:,:,2]>70);free,n=ndimage.label(~blue)
 geo=Transformer.from_crs(23700,4326,always_xy=True);metric=Transformer.from_crs(4326,23700,always_xy=True).transform;parent=shape(json.loads((P/'miskolc-calibration-municipality.geojson').read_text())['geometry']);points=json.loads((P/'miskolc-source-name-points.geojson').read_text())['features']
 def project(x,y,z=None):return geo.transform(x*mat[0,0]+y*mat[1,0]+mat[2,0],x*mat[0,1]+y*mat[1,1]+mat[2,1])
 feats=[];proof=[];used=[]
 for (number,x,y),s in zip(SEEDS,sem['records']):
  assert number==s['sourceUnitNumber'];cid=int(free[y,x]);assert cid and cid not in used;used.append(cid);mask=free==cid
  if mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any():raise ValueError('Open/cropped source cell')
  pixel=helper.pixel_geometry(mask);edges=helper.boundary_blue_test(pixel,blue);world=transform(project,pixel);assert world.is_valid
  fine=s['canSupplyIndividualNamedNeighbourhoodCandidate'];name=s['sourceFvsTableLabel'];name='Miskolc-Tapolca' if number==10 else name
  evidence=[{'id':p['id'],'name':p['properties']['name'],'coordinates':p['geometry']['coordinates'],'insideHistoricalSourceArea':world.covers(shape(p['geometry'])),'distanceFromHistoricalSourceAreaMetres':transform(metric,world).distance(transform(metric,shape(p['geometry']))),'sourceUrl':p['properties']['source']['url']} for p in points if norm(p['properties']['name'])==norm(name)]
  outside=transform(metric,world.difference(parent)).area;area=transform(metric,world).area
  props={'name':name,'sourceName':s['sourceFvsTableLabel'],'municipality':'Miskolc','boundaryKind':'neighbourhood' if fine else 'planning_unit','canonicalNameIsNeighborhood':fine,'sourceUnitNumber':number,'sourceKshConstituents':s['kshConstituents'],'sourceSemanticType':s['semanticType'],'constituentFootprintsInvented':False,'sourcePeriod':'2014 ITS boundary illustration, republished in the 2021–2027 FVS (2023 resolution annex); imagery acquisition date unknown','method':'Exact four-neighbor non-cyan raster cell inside the original cyan boundary band, with manually identified numbered interior seed. All residual holes preserved. Exact source-cell run union; every exposed edge adjacent to original cyan. No raster-edge closing, numeric label boundary inference, gap bridging, buffers, road substitution, geometry repair or clipping. Frozen approximate affine source outer-stroke registration to archived current municipality in EOV; inverse projection to EPSG:4326.','evidenceUrls':[sem['source']['url']],'sourceDocuments':[{'url':sem['source']['url'],'sha256':sem['source']['sha256'],'pdfPageOneBased':228,'figure':23,'table':58}],'estimated':False,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,'sourceDocumentIsOfficialMunicipalPublication':True,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'historical_source_raster_review_required','sourceLabelEvidence':evidence,'currentNameStatus':'same_city_exact_osm_name_observed' if evidence else 'not_independently_confirmed','areaM2':abs(Geod(ellps='WGS84').geometry_area_perimeter(world)[0]),'municipalityOverlapFraction':1-outside/area,'outsideCurrentMunicipalityAreaM2':outside,'reviewNotes':['Five individually named statistical units and twelve whole planning groups; never copy a group footprint to constituent names.','Inside edge of a thick raster stroke; excluded cartographic bands leave gaps. Unknown absolute accuracy, historical source age and imagery date.','Perimeter fitting diagnostics are not independent interior accuracy. Source topmost outer stroke reaches the raster edge, so top-edge pixels were excluded from calibration; no exported interior touches any image edge.','Municipal publication does not itself establish unrestricted reuse rights or current legal/cadastral validity.'],'license':'Municipal map reuse rights unverified; ODbL for OSM municipality/name evidence.'}
  feats.append({'type':'Feature','id':f'manual:miskolc-source-raster:{number}','geometry':mapping(world),'properties':props})
  proof.append({'name':name,'sourceUnitNumber':number,'interiorSeedPixel':[x,y],'sourceFreeComponentId':cid,'includedSourcePixelCount':int(mask.sum()),'pixelCellGeometry':mapping(pixel),'sourcePixelBoundaryEdges':edges,'missingOriginalCyanAdjacentEdges':0,'allResidualSourceHolesRetained':True,'residualHoleAreasPixels':[abs(shape({'type':'Polygon','coordinates':[list(h.coords)]}).area) for h in pixel.interiors],'geosValid':world.is_valid,'sourceCellTouchesRasterEdge':False,'outsideCurrentMunicipalityAreaM2':outside,'sourceSemantics':s,'sourceNameEvidence':evidence})
 for i,f in enumerate(feats):
  for o in feats[:i]:assert shape(f['geometry']).intersection(shape(o['geometry'])).area<=1e-16
 inputs=[{'path':str(f.relative_to(ROOT)),'sha256':sha(f)} for f in [P/'miskolc-p228-original.jpeg',P/'miskolc-registration.json',P/'miskolc-source-semantics.json',P/'miskolc-calibration-municipality.geojson',P/'miskolc-source-name-points.geojson',ROOT/'scripts/neighborhoods/derive-local-map-next.py']]
 return {'type':'FeatureCollection','features':feats},{'schemaVersion':1,'inputs':inputs,'sourceImageSizePixels':[884,557],'sourceEmbeddedImageXref':3691,'sourcePdfPageOneBased':228,'sourcePdfSha256':sem['source']['sha256'],'sourceMask':'B-R>40,G-R>24,B>70, original JPEG','interpretation':'Exact source non-cyan cell union at inside edge of original cyan stroke; no hole filling at all.','registration':reg,'absoluteAccuracyMetres':None,'records':proof}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();fc,pr=build();outputs={'miskolc-source-raster.geojson':encoded(fc),'miskolc-conversion-proof.json':encoded(pr)}
 for n,t in outputs.items():
  if a.check:assert (P/n).read_text()==t,n
  else:(P/n).write_text(t)
 print(json.dumps({'features':len(fc['features']),'fine':sum(f['properties']['boundaryKind']=='neighbourhood' for f in fc['features']),'planning':sum(f['properties']['boundaryKind']=='planning_unit' for f in fc['features']),'holes':[len(f['geometry']['coordinates'])-1 for f in fc['features']],'check':a.check}))
if __name__=='__main__':main()
