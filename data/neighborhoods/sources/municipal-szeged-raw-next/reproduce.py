"""Check the frozen cohort from selected native raster, source cells and actual roads.

This check needs no network, full publication PDF or national PBF. Full-raw checks
remain separate optional provenance checks while those local originals are present.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from PIL import Image
from scipy.ndimage import label
from shapely import contains_xy
from shapely.geometry import MultiPoint,Point,shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
T=Transformer.from_crs(4326,23700,always_xy=True);W=Transformer.from_crs(23700,4326,always_xy=True)
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');args=pa.parse_args()
manifest=read('artifact-manifest.json')
for row in manifest['files']:assert sha(P/row['path'])==row['sha256'],row['path']+' changed'
root=read('root-independent-proposal-review.json');assert root['accepted'] and root['featureCount']==4
for n,h in root['pinnedInputs'].items():assert sha(P/n)==h,'Root proposal pin changed: '+n
raw=np.array(Image.open(P/'henits-p24-xref249.jpeg').convert('RGB'));assert raw.shape==(1018,1174,3)
main_sources=read('henits-five-black60-source-pixels-working.geojson')['features'];assert {f['properties']['number'] for f in main_sources}=={19,20,28,11}
for cutoff in [50,60,70]:
 ids,count=label(raw.max(2)<cutoff,structure=np.ones((3,3),dtype='uint8'));sizes=np.bincount(ids.ravel());chosen=np.flatnonzero(sizes>=1000);chosen=chosen[chosen!=0];stroke=np.isin(ids,chosen)
 free,_=label(~stroke,structure=np.array([[0,1,0],[1,1,1],[0,1,0]],dtype='uint8'))
 sources=read(f'henits-five-black{cutoff}-source-pixels-working.geojson')['features']
 assert len(sources)==4
 for f in sources:
  sx,sy=f['properties']['seedXY'];mask=free==free[sy,sx];assert not(mask[0].any()or mask[-1].any()or mask[:,0].any()or mask[:,-1].any())
  g=shape(f['geometry']);assert g.is_valid and g.geom_type=='Polygon' and len(g.interiors)==0 and g.area==int(mask.sum())
  x0,y0,x1,y1=map(int,g.bounds);xx,yy=np.meshgrid(np.arange(x0,x1)+.5,np.arange(y0,y1)+.5);assert np.array_equal(contains_xy(g,xx,yy),mask[y0:y1,x0:x1])
 # Unit27's genuine source key is not permission to add a closing edge over its label.
 sx,sy=850,605;mask=free==free[sy,sx];assert mask[0].any()or mask[-1].any()or mask[:,0].any()or mask[:,-1].any()
reg=read('registration.json');roads={f['id']:f for f in read('registration-road-controls.geojson')['features']};A=[];v=[]
for c in reg['controls']:
 found=[]
 for id in c['sourceWays']:
  f=roads[id];s=f['properties']['source'];found.append(f['geometry']['coordinates'][s['nodeRefs'].index(c['osmNodeId'])])
 assert found and all(q==c['wgs84'] for q in found) and not c['sourcePlacePointUsedForFit']
 x,y=c['pixel'];e,n=T.transform(*c['wgs84']);A.extend([[x,y,1,0],[-y,x,0,1]]);v.extend([e,n])
a,b,ex,ny=np.linalg.lstsq(A,v,rcond=None)[0];m=np.array([[a,b],[b,-a]]);o=np.array([ex,ny]);assert np.max(abs(m-np.array(reg['pixelToEovMatrix'])))<1e-8 and np.max(abs(o-np.array(reg['pixelToEovOffset'])))<1e-6
sources={f['properties']['number']:f for f in main_sources};oldproposal={f['properties']['sourceUnitNumber']:f for f in read('henits-four-main-world-working.geojson')['features']};municipality=shape(read('municipality-check-reference.geojson')['features'][0]['geometry']);prior=read('prior-szeged-comparison-reference.geojson')['features'];hull=MultiPoint([c['pixel']for c in reg['controls']]).convex_hull
for file,model in [('szeged-four-inferred-import.geojson',reg),('szeged-four-placement-alternative.geojson',reg['alternatives']['threeJunctionSimilarity'])]:
 fs=read(file)['features'];assert len(fs)==4;geoms=[]
 for f in fs:
  p=f['properties'];number=p['sourceUnitNumber'];src=shape(sources[number]['geometry']);g=shape(f['geometry']);assert g.is_valid and g.geom_type=='Polygon' and len(g.interiors)==0 and municipality.covers(g)
  mm=np.array(model['pixelToEovMatrix']);off=np.array(model['pixelToEovOffset']);expected=[]
  for px in src.exterior.coords:expected.append(W.transform(*(mm@np.array(px)+off)))
  assert np.max(abs(np.array(g.exterior.coords)-np.array(expected)))<1e-11
  assert src.difference(hull).area==src.area and p['controlHullCoverageFraction']==0 and p['placementConfidence']=='low'
  assert p['estimated'] and p['estimatedPlacement'] and not p['estimatedContour'] and p['sourceContourObserved'] and not p['canonicalNameIsNeighborhood'] and not p['usableForAddressAssignment'] and p['claimedAbsoluteAccuracyMetres'] is None
  assert all(g.covers(Point(*z['coordinates']))==z['insideCandidate'] and not z['usedForFit'] for z in p['sourceLabelEvidence'])
  assert all(g.intersection(shape(z['geometry'])).area==0 for z in prior)
  if file=='szeged-four-inferred-import.geojson':assert f['geometry']==oldproposal[number]['geometry'],'Final coordinates differ from root proposal'
  geoms.append(g)
 assert all(a.intersection(b).area==0 for i,a in enumerate(geoms)for b in geoms[i+1:])
print(json.dumps({'check':True,'selectedNativeRasterCutoffsRecomputed':3,'sourceContoursPerCutoff':4,'ujszoregQuarantinesReproduced':3,'actualRoadControls':6,'mainWorldCandidates':4,'placementAlternativesNotAdditionalQuarters':4,'finalCoordinatesExactlyEqualRootProposal':True,'filePinsChecked':len(manifest['files']),'networkUsed':False,'globalRegistryModified':False}))
