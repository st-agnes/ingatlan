#!/usr/bin/env python3
"""Combine completed source alternatives and compare with a fixed saved baseline."""
import json,collections,hashlib,unicodedata
from pathlib import Path
from shapely.geometry import shape
OUT=Path(__file__).resolve().parent
SOURCES=['street-block-features.geojson','fehervar-native-features.geojson','fehervar-subarea-features.geojson','nyir-character-features.geojson']
norm=lambda s:''.join(c for c in unicodedata.normalize('NFC',s).casefold() if c.isalnum())
features=[];datasets={}
for name in SOURCES:
 raw=(OUT/name).read_bytes();rows=json.loads(raw)['features'];features+=rows;datasets[name]={'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}
for i,f in enumerate(features):
 f.setdefault('id','next-fehervar-nyir:'+str(i));g=shape(f['geometry']);assert g.is_valid and not g.is_empty
 assert 15.5<g.bounds[0]<23.5 and 45<g.bounds[1]<49.5
keys=[(f['properties']['municipality'],norm(f['properties']['name'])) for f in features];assert len(keys)==len(set(keys))
raw=(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n').encode();(OUT/'features.geojson').write_bytes(raw)
baseline=json.loads((OUT/'baseline-name-index.json').read_text());known={tuple(x) for x in baseline['knownKeys']};circles={tuple(x) for x in baseline['circleKeys']};new=set(keys)-known
querykeys={(f['properties']['municipality'],norm(n)) for f in features for n in [f['properties']['name']]+f['properties'].get('aliases',[])};matched=querykeys&circles
summary={'featureCount':len(features),'municipalities':dict(collections.Counter(f['properties']['municipality'] for f in features)),'sourceDatasets':datasets,'featureSha256':hashlib.sha256(raw).hexdigest(),'distinctNewNameKeysBeforeFinalAliases':len(new),'newNameKeysByMunicipality':dict(collections.Counter(k[0] for k in new)),'validGeometryCount':len(features),'circleOrVoronoiCount':0,'countryCoverageClaimed':False,'comparisonBaselineCommit':baseline['commit'],'baselineCircleNamesMatched':len(matched),'baselineCirclesMatchedByMunicipality':dict(collections.Counter(k[0] for k in sorted(matched)))}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'newNameKeys':len(new),'baselineCirclesMatched':len(matched)},ensure_ascii=False))
