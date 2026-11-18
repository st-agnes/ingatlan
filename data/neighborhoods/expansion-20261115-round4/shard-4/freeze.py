from pathlib import Path
import json,hashlib,math,collections
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
R=Path(__file__).resolve().parent
D=lambda p:json.loads(p.read_text())
def dump(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
T=Transformer.from_crs(4326,23700,always_xy=True).transform
fc=D(R/'features.geojson');ev=D(R/'source-evidence.json');ss=D(R/'selections.json');task=D(R/'source-inputs/task.json');targets={(m['municipality'],t['name']):t for m in task['municipalities'] for t in m['targets']}
seen=set();valid=[]
for f,e in zip(fc['features'],ev['records']):
 p=f['properties'];key=(p['municipality'],p['name']);assert key in targets and key not in seen;seen.add(key);g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'];assert e['whollyWithinMunicipality'];assert p['estimated'] is True and p['confidence']=='low' and p['lowConfidence'] is True and p['radiusFallback'] is False
 a,b,c,d=g.bounds;assert -180<=a<=c<=180 and -90<=b<=d<=90
 for point in targets[key]['pointCandidates']:assert transform(T,g).buffer(.01).covers(transform(T,Point(point['coordinates'])))
 valid.append({'municipality':key[0],'name':key[1],'geometryType':g.geom_type,'valid':True,'areaKm2':e['areaKm2'],'knownPointsInside':e['knownPointsInside'],'withinMunicipality':True,'partialExtent':p.get('partialExtent',False)})
assert seen==set(targets) and len(seen)==63
p=R/'build.py';s=p.read_text().replace("'labelControlsGeometrySize':False","'targetPointGeneratesShapeOrSize':False,'registrationUsesOtherSettlementLabelCorrespondences':s['kind']=='raster-map'");p.write_text(s)
for e in ev['records']:
 e.pop('labelControlsGeometrySize',None);e['targetPointGeneratesShapeOrSize']=False;e['registrationUsesOtherSettlementLabelCorrespondences']=e['kind']=='raster-map'
dump(R/'source-evidence.json',ev)
for num,start,end in [(3,32,52),(4,52,63)]:
 b=R/f'batch-{num:02}';b.mkdir(exist_ok=True);obj={'type':'FeatureCollection','features':fc['features'][start:end]};e=dict(ev);e['records']=ev['records'][start:end];dump(b/'features.geojson',obj);dump(b/'source-evidence.json',e);dump(b/'selections.json',ss[start:end]);dump(b/'manifest.json',{'status':'FROZEN','featureCount':end-start,'featuresSha256':hashlib.sha256((b/'features.geojson').read_bytes()).hexdigest(),'offlineBuild':'../build.py and ../source-inputs; this selection list is a fixed subset of ../selections.json','filesSha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(b.iterdir()) if p.name!='manifest.json'}})
summary=D(R/'summary.json');summary.update({'status':'FROZEN','attemptedTargetCount':63,'knownPointCount':sum(len(t['pointCandidates']) for t in targets.values()),'validFeatureCount':63,'municipalityContainedFeatureCount':63,'knownPointContainedFeatureCount':56,'methodCounts':dict(collections.Counter(e['kind'] for e in ev['records'])),'partialExtentFeatureCount':sum(v['partialExtent'] for v in valid),'sourceIdentityReview':'alias-review.json','batches':[{**D(R/f'batch-{i:02}'/'manifest.json'),'path':f'batch-{i:02}/features.geojson'} for i in range(1,5)]});dump(R/'summary.json',summary)
dump(R/'validation.json',{'featureCount':63,'uniqueTargetIdentityCount':63,'targetCount':63,'missingTargets':[],'invalidFeatures':[],'outOfMunicipalityFeatures':[],'uncoveredKnownPoints':[],'coordinateSystem':'WGS84 EPSG:4326','allEstimatedLowConfidence':True,'radiusFallbackCount':0,'sourceConstruction':'52 explicit actual road/landscape block selections;6 actual municipal raster traces;2 literal farmyard enclosures;1 manual road-map whole thermal district;1 native Bög corridor plus adjoining physical compartment;1 municipal rural complement.','records':valid})
dump(R/'unresolved.json',{'allAssignedTargetsAttempted':True,'assignedTargetCount':63,'missingGeometryTargets':[],'fullyVerifiedModernQuarterBoundaries':0,'remainingBoundaryUncertainty':'All63 outputs remain approximate search areas. Physical compartments need not coincide with traditional/legal boundaries. No modern cadastral accuracy is claimed.','sourceIdentityAmbiguities':D(R/'alias-review.json')['proposals'],'partialOrSpecialCases':[{'municipality':e['municipality'],'name':e['name'],'note':e['selection']['note']} for e in ev['records'] if e['selection'].get('partial') or e['kind']=='rural-remainder'],'searchesAndReviewedInputs':['All31 shared parent country-extraction contexts: actual native roads, waterways, railways, closed surfaces, municipal polygons and place/address records. No separate PBF scan.','All30 point-bearing town source-road maps rendered in inspection/; dense-quarter grouping recorded in manual-quarter-mask-review.json.','Full cached Kecskemét2021municipalPDF reviewed pp138–140,175,178, six named overview traces and three source-road block groups. Source subset and image archived in kecskemet/.','Cached Salgótarján2022ITS reviewed p139(sectionIII.3.1.10) and existing Eresztvény source estimate archived in salgotarjan/.','Primary municipal web text checked for Tiszaföldvár2021Homok circuit, municipal geography, Pásztó Plathi-negyed and Csongrád historic names; see primary-web-source-facts.json. No new binary downloads or shell network.'],'aliasMutationsPerformed':False})
(R/'README.md').write_text('''# Round 4, shard 4 — 63 low-confidence neighborhood polygons

All 63 assigned names in 31 municipalities were attempted and have source-informed WGS84 geometry. The 56 known place points are covered. Every feature is valid, lies within its municipality and is explicitly estimated with low confidence. No circle, point buffer, point rectangle or Voronoi construction is used.

Import only `features.geojson` (63 features). Alternatively the immutable `batch-01` through `batch-04` feature files contain disjoint batches of12,20,20,11names. Do not import both approaches: checkpoint files duplicate the full packet identities. Diagnostic/source GeoJSON files are inputs, not extra neighborhoods.

Most shapes follow explicitly selected groups of actual road, stream, railway, mapped land-use and municipal compartments. Rural surrounding land is retained. Dense estates/quarters use broader groups of neighboring blocks. Native farmyard enclosures represent two small rural settlements. Kecskemét has six actual municipal overview-map traces, registered coarsely from nine other settlement/label correspondences (162m fit residual; no accuracy guarantee), plus three road-block groups. Zsóry-fürdő includes the whole holiday/bath road district. Óbög uses the mapped Bög settlement corridor with adjoining physical land and may overlap Újbög. Salgótarján’s explicitly rural planning unit is approximated by the municipality remainder after mapped continuous built-up surfaces and the prior Eresztvény estimate are excluded.

These are approximate address-search areas, not authoritative or fully verified modern neighborhood boundaries. Some source compartments or literal settlement footprints are partial. `unresolved.json` and per-feature approximation notes preserve those limitations. In particular only42%of the coarse Bödögsor map trace remains inside the modern municipality. The map spellings Bordás/Borbás and northern industrial/logistical name alignment need identity handling; `alias-review.json` proposes review without changing global aliases. Parent/child quarters and their overlaps are retained.

Offline rebuild from this directory:

`PYTHONPATH=/workspace/ingatlan/.local/geodata python build.py`

Requires Python with Shapely, pyproj and NumPy. All geometry inputs, source object versions/URLs, original PBF hash and place/address source records are in `source-inputs/`; no PBF scan, network or PDF download is needed. `selections.json` stores the explicit geometry recipe. `source-evidence.json` records boundary/source anchors and selection limitations. Municipal source-page subsets and map registration are archived in `kecskemet/` and `salgotarjan/`; primary web facts are paraphrased in `primary-web-source-facts.json`. `features-preview.pdf` provides31town map pages. `inspection/`, source map crops and candidate cell files are diagnostic material.

The executable full-packet build is `build.py`. A copied initial recipe in `batch-01/build.py` is historical checkpoint evidence; to replay that subset separately, put its `selections.json` beside a copy of the full-packet build and the archived source-inputs, or filter the full rebuilt output by the checkpoint names.

OSM snapshot2026-11-12T21:23:05Z; PBF SHA256224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a. © OpenStreetMap contributors, ODbL-1.0. The parent performed one shared country extraction; this shard did not scan the PBF or mutate any older/global packets.
''')
print('FROZEN',summary['featuresSha256']);print('BATCHES',[(i,D(R/f'batch-{i:02}'/'manifest.json')['featuresSha256']) for i in range(1,5)])
