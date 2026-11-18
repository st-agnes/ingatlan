#!/usr/bin/env python3
"""Spatial integrity and offline reproduction checks; not an accuracy audit."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,subprocess,sys,unicodedata
from shapely.geometry import Point,shape
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out=HERE/'features.geojson';before=sha(out)
subprocess.run([sys.executable,str(HERE/'build.py')],check=True)
assert sha(out)==before,'Rebuild changed frozen output'
fs=json.loads(out.read_text())['features'];sel=json.loads((HERE/'selection.json').read_text())
seen=set();city=Counter();methods=Counter()
for f in fs:
 p=f['properties'];g=shape(f['geometry']);key=(norm(p['municipality']),norm(p['name']))
 assert key not in seen,key
 seen.add(key);city[p['municipality']]+=1;methods[p['method']]+=1
 assert p['name'] in sel['missingNames'],p['name']
 assert g.is_valid and g.geom_type in ['Polygon','MultiPolygon'] and not g.is_empty,p['name']
 assert g.covers(Point(p['namePoint']['coordinates'])),p['name']
 assert p['estimated'] is True and p['lowConfidence'] is True,p['name']
 assert 'circle' not in p['method'] and 'voronoi' not in p['method'],p['name']
sourcechecks=[]
for p in sorted(HERE.glob('*-source-roads.geojson.gz')):
 raw=gzip.open(p,'rb').read();src=json.loads(raw)['features']
 assert len(raw)<95_000_000,p.name
 sourcechecks.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p),'compressedBytes':p.stat().st_size,'uncompressedBytes':len(raw),'featureCount':len(src)})
remaining=[n for n in sel['missingNames'] if norm(n) not in {x[1] for x in seen}]
summary={'featureCount':len(fs),'cities':dict(city),'methods':dict(methods),'allValidPolygonal':True,'allSavedNamePointsInside':True,'noNormalizedCityNameDuplicates':True,
 'circleCount':0,'voronoiCount':0,'reproducesByteIdenticallyOffline':True,'requiresCountryPbfToRebuildFinalFeatures':False,
 'finalInput':{'path':str(out.relative_to(ROOT)),'sha256':before},'savedContextSourceWays':sum(x['featureCount'] for x in sourcechecks),'sourceFiles':sourcechecks,
 'initialKnownNameCount':sel['knownNameCount'],'initialNamesWithCollectedPolygon':sel['namesWithCollectedPolygon'],
 'newKnownNameCoveragePercent':round((sel['namesWithCollectedPolygon']+len(fs))/sel['knownNameCount']*100,1),'remainingInitialBacklogNames':remaining,
 'completeCityCoverageEstablished':False,'absoluteAccuracyEstablished':False,
 'limits':'Manual rings and corridor splits are low-confidence inferences from saved mapped street context. Spatial validity, point inclusion, size safeguards and successful reproduction do not validate exact neighborhood borders.'}
(HERE/'packet-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(fs),'sha256':before,'remaining':len(remaining),'offlineReproduction':'byte-identical','sourceWays':summary['savedContextSourceWays']},ensure_ascii=False))
