#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
from collections import Counter
from shapely.geometry import shape
H=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
features=[];batches=[]
for p in sorted(H.glob('features-batch-*.geojson')):
 f=json.load(open(p))['features'];features+=f;batches.append({'path':p.name,'featureCount':len(f),'sha256':sha(p)})
assert len(features)==60 and len({f['properties']['originalTaskIndex'] for f in features})==60
assert all(shape(f['geometry']).is_valid for f in features)
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
byidx={f['properties']['originalTaskIndex']:f for f in features}; task=json.load(open(H/'target-selection.json'));attempts=[];i=0
for town in task['municipalities']:
 for t in town['targets']:
  f=byidx.get(i);attempts.append({'index':i,'municipality':town['municipality'],'name':t['name'],'status':'collected-low-confidence-estimate' if f else 'searched-no-defensible-whole-unit-polygon','featureId':f['id'] if f else None,'reason':f['properties']['approximationNote'] if f else 'Primary municipal ITS/HEP confirms a statistical rural-planning group (Külterületek/puszták), including five detached puszta settlements. Its complete areal limit is not established by the available text/inset map; there is no name point. Individual named settlement footprints or all remaining municipal farmland would each silently change its meaning. No arbitrary residual municipality, circle, bounding box or small unrelated parcel is substituted.'});i+=1
assert i==61
(H/'attempts.json').write_text(json.dumps(attempts,ensure_ascii=False,indent=2)+'\n')
unresolved=[a for a in attempts if a['featureId'] is None]
(H/'unresolved.json').write_text(json.dumps({'targets':unresolved,'searchedSources':['https://www.dombovar.hu/media/files/Dombovar_helyzetertekeles_0804.pdf','https://www.dombovar.hu/media/files/dombovar_koncepcio_vegso_javitott.pdf','https://www.dombovar.hu/media/files/20._Melleklet_HEP_18.06.28..pdf','https://dombovar.hu/wp-content/uploads/2022/11/11.-HEP_melleklet_22.11.30.pdf','Shared native municipality/road/area/label context and cached round-2 Dombóvár rural footprints'], 'nextAction':'Georeference the municipality ITS/HEP rural inset into its constituent settlements and determine whether the source unit is settlement-site aggregation or the complete outer administrative territory before drawing a whole-unit polygon. Existing named puszta data is preserved; its absence here does not mean every rural settlement has no footprint.'},ensure_ascii=False,indent=2)+'\n')
summary={'targetCount':61,'attemptedCount':61,'municipalityCount':len(task['municipalities']),'collectedCount':60,'unresolvedCount':1,'nativeFootprintAssociationCount':sum(bool(f['properties'].get('sourceNativeGeometry')) for f in features),'manualMapStreetFieldEstimateCount':sum(not f['properties'].get('sourceNativeGeometry') for f in features),'allInferredLowConfidence':True,'wholeQuarterAccuracyVerified':False,'batches':batches,'combinedFeatureSha256':sha(H/'features.geojson'),'byMunicipality':dict(sorted(Counter(f['properties']['municipality'] for f in features).items())),'canonicalizationCaveat':'Szuhay-domb official planning extent south of Dózsa differs from the current small Szuhajdomb street-cell north of Dózsa; review as a spelling/extent candidate, not automatically as an unrelated extra whole quarter. Source-name points are not invented for unlocated planning units.'}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
manifest={p.name:sha(p) for p in sorted(H.glob('*')) if p.is_file() and p.name!='manifest.json'}
(H/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
