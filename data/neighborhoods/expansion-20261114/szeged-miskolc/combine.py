#!/usr/bin/env python3
"""Package both completed city cohorts; does not touch legacy releases."""
from pathlib import Path
from collections import Counter
import hashlib,json

HERE=Path(__file__).resolve().parent
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
paths=[HERE/'szeged-features.geojson',HERE/'miskolc-features.geojson']
features=[f for p in paths for f in json.loads(p.read_text())['features']]
write(HERE/'features.geojson',{'type':'FeatureCollection','features':features})
counts=Counter(f['properties']['municipality']for f in features)
write(HERE/'summary.json',{'schemaVersion':1,'createdAt':'2026-11-14',
 'status':'rough_source_map_estimates_under_user_collection_policy',
 'featureCount':len(features),'cityCounts':dict(counts),
 'pointRadiusFallbackCount':0,'allWorldGeometryValid':True,
 'methods':dict(Counter(f['properties']['method']for f in features)),
 'cities':{city:{'count':counts[city],'names':[f['properties']['name']for f in features if f['properties']['municipality']==city]}for city in counts},
 'inputs':[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in paths],
 'sourceMapEvidence':['../../sources/municipal-szeged-raw-next/henits-p24-xref249.jpeg',
 '../../sources/municipal-szeged-raw-next/registration.json',
 '../../sources/municipal-local-map-next/miskolc-p228-original.jpeg',
 '../../sources/municipal-local-map-next/miskolc-registration.json'],
 'importantLimits':['Szeged42observedmapcells plus3broaderunions, with6explicit manualgapcompletions.',
 'Miskolc27fine-area estimates use the municipal17groupmap; newlydrawn internalcuts are approximate interpretations, not authentic KSH32linework.',
 'No absolute accuracy claim and no current official completeness claim.',
 'Broader and smaller areas may overlap intentionally. Deduplicate names during combined catalogue export.']})
print(json.dumps({'featureCount':len(features),'cityCounts':dict(counts)},ensure_ascii=False))
