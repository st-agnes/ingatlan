from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;fw=Transformer.from_crs(4326,23700,always_xy=True).transform
T=json.load(open(P/'targets.json'));F=json.load(open(P/'features.geojson'))['features'];S=json.load(open(P/'selection.json'));expected={(m['municipality'],t['name']) for m in T['municipalities'] for t in m['targets']};actual={(f['properties']['municipality'],f['properties']['name']) for f in F};assert actual==expected and len(F)==len(expected)==66
pointDeviations=[];duplicates=defaultdict(list);parentDeviations=[]
for f,s in zip(F,S):
 p=f['properties'];g=shape(f['geometry']);assert g.geom_type in ['Polygon','MultiPolygon'] and g.is_valid and not g.is_empty;assert 16<g.bounds[0]<g.bounds[2]<23 and 45<g.bounds[1]<g.bounds[3]<49;assert p['estimated'] and p['lowConfidence'] and p['sourceUrl'] and p['approximationNote']
 duplicates[hashlib.sha256(json.dumps(f['geometry'],sort_keys=True).encode()).hexdigest()].append(p['municipality']+'/'+p['name']);m=transform(fw,g);parent=transform(fw,shape(json.load(open(P/'source-inputs'/s['contextKey']/'municipality.geojson'))['features'][0]['geometry']));outside=m.difference(parent).area/m.area
 if outside>.01:parentDeviations.append({'municipality':p['municipality'],'name':p['name'],'outsideMunicipalityFraction':round(outside,4)})
 if s.get('pointSource'):
  d=m.distance(transform(fw,Point(s['pointSource']['coordinates'])))
  if d>20:pointDeviations.append({'municipality':p['municipality'],'name':p['name'],'distanceMetres':round(d),'interpretation':'Source label coordinate is outside the selected physical outline; retain low confidence and do not treat the point as a surveyed boundary anchor.'})
assert all(len(v)==1 for v in duplicates.values())
B=[];rebuilt=[]
for p in sorted((P/'batches').glob('batch-*.geojson')):
 fs=json.load(open(p))['features'];rebuilt+=fs;B.append({'path':str(p.relative_to(P)),'count':len(fs),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert rebuilt==F
result={'featureCount':len(F),'expectedCount':len(expected),'allTargetNamesCovered':True,'validWgs84Polygons':True,'identicalGeometryDuplicates':[],'batchFilesMatchCumulativeFeatures':True,'batches':B,'namePointDeviationsOver20Metres':pointDeviations,'municipalityOutsideFractionOver1Percent':parentDeviations,'allEstimatedLowConfidence':True,'featuresSha256':hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest()}
(P/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
