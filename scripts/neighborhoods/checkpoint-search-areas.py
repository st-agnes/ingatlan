#!/usr/bin/env python3
"""Validate a collection checkpoint and refresh its resumable state and package."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,unicodedata
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/neighborhoods'
OLD=DATA/'expansion-20261114'
NEXT=DATA/'expansion-20261114-next'

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def key(value):return ''.join(c for c in unicodedata.normalize('NFKC',value).casefold() if c.isalnum())

def main(status):
    raw=(DATA/'search-areas.geojson').read_bytes();document=json.loads(raw)
    features=document['features'];fallback=json.loads((OLD/'inventory/provisional-fallback-features.geojson').read_text())['features']
    names=set();ids=set();canonical=set()
    for feature in features:
        p=feature['properties'];geometry=shape(feature['geometry'])
        assert geometry.is_valid and not geometry.is_empty,p['label']
        assert feature['id'] not in ids;ids.add(feature['id'])
        k=(p['municipality'],p['canonicalNameKey']);assert k not in canonical;canonical.add(k)
        names.update((p['municipality'],key(value)) for value in [p['name']]+p['aliases'])
    for feature in fallback:
        p=feature['properties'];assert shape(feature['geometry']).is_valid
        assert (p['municipality'],key(p['name'])) not in names,p['name']
    tests=len(re.findall(r'^    def test_', (ROOT/'tests/neighborhoods-search-areas.test.py').read_text(),re.M))
    validation={'schemaVersion':1,'scope':'technical_not_geographic_accuracy_review',
       'geojsonSha256':hashlib.sha256(raw).hexdigest(),'featureCount':len(features),
       'validGeometryCount':len(features),'duplicateCanonicalNameCount':0,'duplicateIdCount':0,
       'optionalFallbackCount':len(fallback),'optionalFallbackDuplicatesWithCore':0,
       'realMySqlExecutionPerformed':False,'regressionTests':tests}
    dump(OLD/'technical-validation.json',validation)
    report=json.loads((DATA/'search-areas-report.json').read_text())
    inventory=json.loads((OLD/'inventory/priority-cities.json').read_text())
    state=json.loads((OLD/'WORK-STATE.json').read_text())
    state['latestCheckpoint']={k:report[k] for k in ['featureCount','municipalityCount','methods','duplicateVariantsPreserved']}
    state['knownNameInventory']=inventory['summary'];state['retiredIdentityRedirects']=report['retiredIdentityCount']
    state['completedSourcePackets']=json.loads((OLD/'input-registry.json').read_text())['datasets']
    state['nextPriorityCities']=sorted([{'municipality':x['municipality'],'knownNames':x['knownNameCount'],
       'mappedNames':x['namesWithCollectedPolygon'],'remainingNames':len(x['missingNames'])}
       for x in inventory['cities']],key=lambda x:-x['remainingNames'])[:12]
    state['currentCollectionState']='data/neighborhoods/expansion-20261114-next/WORK-STATE.json'
    dump(OLD/'WORK-STATE.json',state)
    current=json.loads((NEXT/'WORK-STATE.json').read_text());current['status']=status
    current['latestCheckpoint']=state['latestCheckpoint'];current['knownNameInventory']=inventory['summary']
    current['newAreasNet']=len(features)-current['baseline']['coreAreas']
    current['fallbackCircleReduction']=current['baseline']['fallbackCircles']-len(fallback)
    current['baselineCommit']='50988ce52abd3bbd010f1383d94c03f08b3f4c87'
    current['nextPriorityCities']=state['nextPriorityCities'];dump(NEXT/'WORK-STATE.json',current)
    readme=DATA/'README.md';text=readme.read_text()
    text=re.sub(r'\*\*Legutóbbi mentés: \d+ kereshető terület \d+ településről\*\*, kör alapú pótlás nélkül\. Külön tartalékrétegben \d+ pontból becsült kör marad\.',
       f"**Legutóbbi mentés: {len(features)} kereshető terület {report['municipalityCount']} településről**, kör alapú pótlás nélkül. Külön tartalékrétegben {len(fallback)} pontból becsült kör marad.",text)
    readme.write_text(text)
    subprocess.run(['python3',str(ROOT/'scripts/neighborhoods/package-search-areas.py')],check=True,cwd=ROOT)
    print(json.dumps({'areas':len(features),'fallbacks':len(fallback),'addedNet':current['newAreasNet'],
                     'circlesReplaced':current['fallbackCircleReduction'],'nationalCoverageComplete':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--status',default='collecting_and_checkpointing')
    args=parser.parse_args();main(args.status)
