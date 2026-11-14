#!/usr/bin/env python3
"""Supplemental strict-import audit; never rewrites the frozen Figure77 cohort."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
SOURCE=OUT.parent/'municipal-kecskemet-native77-first'
POINT=(Decimal('207.51'),Decimal('568.81'))

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v):return(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
    from shapely.geometry import LineString,MultiLineString,Polygon,shape
    from shapely.ops import polygonize_full
    marker=b'0 G\n1.8122 w\n2 J\n2 j\n'
    stream=(SOURCE/'source-form188-stream.txt').read_bytes()
    assert hashlib.sha256(stream).hexdigest()=='1a572f913226e234c8862baa59118bf79468977d7f8bef079775cf4e1bb50d07'
    paths=[];subs=[];current=None
    for line in stream.split(marker,1)[1].decode('ascii').splitlines():
        match=re.fullmatch(r'([-+.0-9]+) ([-+.0-9]+) ([ml])',line.strip())
        if match:
            x,y,op=match.groups();point=(Decimal(x),Decimal(y))
            if op=='m':
                assert current is None
                current=[point]
            else:current.append(point)
        elif line.strip() in ['h','s','S']:
            assert current[0]==current[-1]
            subs.append(current);current=None
            if line.strip() in ['s','S']:
                paths.append(subs);subs=[]
                if len(paths)==7:break
    assert len(paths)==7
    polygons=[]
    for subs in paths:
        lines=[LineString([tuple(map(float,a)),tuple(map(float,b))])for sub in subs for a,b in zip(sub,sub[1:])if a!=b]
        geoms,cuts,dangles,invalid=polygonize_full(MultiLineString(lines))
        assert not(cuts.geoms or dangles.geoms or invalid.geoms)
        polygons.append(sorted(geoms.geoms,key=lambda g:-g.area))
    central=polygons[0][0];shell=Polygon(central.exterior);kosafalu=polygons[1][0]
    hole=next(Polygon(r)for r in central.interiors if Polygon(r).equals(kosafalu))
    touch=hole.boundary.intersection(central.exterior)
    assert touch.geom_type=='Point' and list(touch.coords)==[(207.51,568.81)]
    assert hole.difference(shell).area==0
    contexts=[]
    for subindex,sub in enumerate(paths[0]):
        for index,p in enumerate(sub):
            if p==POINT:
                contexts.append({'sourceSubpathIndexZeroBased':subindex,'vertexIndexZeroBased':index,
                                 'literalDecimalVertex':[str(t)for t in p],
                                 'adjacentSourceVertices':[[str(t)for t in q]for q in sub[index-1:index+2]]})
    assert len(contexts)==2
    features=[]
    for filename in ['fine-inferred.geojson','local-units-inferred.geojson']:
        features += json.loads((SOURCE/filename).read_text())['features']
    # Use the real application validator unchanged. JSON reaches Node via stdin,
    # and this command imports the module without invoking global build mutation.
    javascript="""import {validateGeometry} from './scripts/neighborhoods/build.mjs';
let data='';for await(const part of process.stdin)data+=part;
const features=JSON.parse(data);
console.log(JSON.stringify(features.map(f=>({id:f.id,name:f.properties.name,result:validateGeometry(f.geometry)}))));"""
    result=subprocess.run(['node','--input-type=module','-e',javascript],input=json.dumps(features),
                          text=True,capture_output=True,cwd=ROOT,check=True)
    validation=json.loads(result.stdout)
    rejected=[v for v in validation if not v['result']['valid']]
    assert len(rejected)==1 and rejected[0]['id']=='manual:kecskemet-figure77:szent-laszlo-belso-forrascella'
    assert rejected[0]['result']['reason']=='hole_outside_shell'
    exported=next(f for f in features if f['id']==rejected[0]['id'])
    world=shape(exported['geometry'])
    intersections=[Polygon(r).boundary.intersection(world.exterior)for r in world.interiors]
    nonempty=[g for g in intersections if not g.is_empty]
    assert len(nonempty)==1 and nonempty[0].geom_type=='Point'
    report={'schemaVersion':1,'status':'FROZEN_SOURCE_GEOMETRY_RETAINED_ONE_CELL_QUARANTINED_BY_STRICT_VALIDATOR',
            'originalFrozenCohortPath':str(SOURCE.relative_to(ROOT)),
            'originalFrozenManifestSha256':sha(SOURCE/'manifest.json'),
            'sourceContourCandidateCount':7,'actualAdmittedInferredFeatureCount':6,'actualPrimaryFeatureCount':0,
            'quarantinedSourceCellCount':1,'admittedFineResidentialQuarterCount':3,
            'admittedLocalEconomicCellCount':3,'sourceDataBytesModified':False,
            'strictValidatorPath':'scripts/neighborhoods/build.mjs','strictValidatorSha256':sha(ROOT/'scripts/neighborhoods/build.mjs'),
            'exactOriginalFormStreamSha256':hashlib.sha256(stream).hexdigest(),
            'nativeFinding':{'originalPathCount':7,'sourceCentralCellShapelyValid':central.is_valid,
                             'originalOuterHoleRolesConfirmed':True,'nativeTouchingCoordinate':['207.51','568.81'],
                             'originalSubpathOccurrences':contexts,
                             'touchingHoleMatchesSeparateKosafaluCellExactly':True,
                             'nativeHoleAreaOutsideShell':0.0,
                             'geographicTouchingCoordinate':list(nonempty[0].coords)[0],
                             'geometryConstructionBugFound':False},
            'actualProjectValidatorResults':validation,
            'quarantine':{'datasetId':'kecskemet-native77-local-inferred','featureId':rejected[0]['id'],
                          'reason':'hole_outside_shell','actualSourceCondition':'The original Kósafalu hole touches the central source-cell exterior at one original native vertex shared with Rendőrfalu. The project validator intentionally rejects touching holes as well as genuinely outside holes.',
                          'notAReversedShellHoleMapping':True,'noAreaActuallyOutsideShell':True,
                          'action':'Retain the exact frozen source geometry as a quarantined source cell. No hole removal, buffer, coordinate perturbation, repair or forced admission.'},
            'correctionToEarlierAdmissionClaim':'The original frozen batch contains seven archived inferred candidates. The earlier claim that all seven were import-admissible was too broad: the unchanged project validator admits six and quarantines the central touching-hole cell. Native-path preservation and Shapely validity do not override the project validator.',
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False}
    path=OUT/'admission-review.json';data=encoded(report)
    if check:
        assert path.read_bytes()==data,'Stale admission review'
        manifest=OUT/'manifest.json'
        if manifest.exists():
            m=json.loads(manifest.read_text())
            for name,value in m['frozenFilesSha256'].items():assert sha(OUT/name)==value,name
    else:path.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','admittedInferred':6,'quarantined':1,
                      'nativePointTouchConfirmed':True,'frozenBytesUnchanged':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    build(parser.parse_args().check)
