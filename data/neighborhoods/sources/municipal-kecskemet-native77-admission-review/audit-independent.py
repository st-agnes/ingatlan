#!/usr/bin/env python3
"""Independent project-admission correction; original native77 batch read-only.

Reparse original PDF Form bytes; compare native and exported point contacts;
call the project's actual validateGeometry export, without altering any shape.
All output is confined to this separate supplemental admission-review cohort.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
FROZEN=ROOT/'data/neighborhoods/sources/municipal-kecskemet-native77-first'
FORM_SHA='1a572f913226e234c8862baa59118bf79468977d7f8bef079775cf4e1bb50d07'
TOUCH=(Decimal('207.51'),Decimal('568.81'))
NUM=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
POINT=re.compile(r'^('+NUM+r') ('+NUM+r') ([ml])$')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encode(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def frozen_hashes():return {str(p.relative_to(FROZEN)):sha(p)for p in sorted(FROZEN.rglob('*'))if p.is_file()}


def parse(stream):
    marker=b'0 G\n1.8122 w\n2 J\n2 j\n'
    if stream.count(marker)!=1:raise ValueError('Original native stroke block changed')
    paths=[];parts=[];current=None
    for raw in stream.split(marker,1)[1].splitlines():
        line=raw.decode('ascii').strip();match=POINT.fullmatch(line)
        if match:
            x,y,op=match.groups();p=(Decimal(x),Decimal(y))
            if op=='m':
                if current is not None:raise ValueError('Unclosed source subpath')
                current=[p]
            else:
                if current is None:raise ValueError('Source line without moveto')
                current.append(p)
        elif line in ('h','s','S'):
            if current is None or current[-1]!=current[0]:raise ValueError('Original path needs an extra closing edge')
            parts.append(current);current=None
            if line in ('s','S'):
                paths.append(parts);parts=[]
                if len(paths)==7:return paths
        elif line in ('q','Q','W*','n')or line.endswith(' re'):
            if current is not None:raise ValueError('Unexpected source graphics operation')
        elif line:raise ValueError('Unexpected native operation '+line)
    raise ValueError('Missing source paths')


def main(check):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Transformer
    from shapely.geometry import MultiLineString,Polygon,shape,Point
    from shapely.ops import polygonize_full
    from shapely.validation import explain_validity
    pyproj.network.set_network_enabled(False)
    before=frozen_hashes()
    stream=(FROZEN/'source-form188-stream.txt').read_bytes()
    if hashlib.sha256(stream).hexdigest()!=FORM_SHA:raise ValueError('Original source Form bytes changed')
    doc=fitz.open(FROZEN/'source-pages163-164.pdf')
    form=next(x[0]for x in doc[0].get_xobjects()if x[1]=='Meta1858')
    if doc.xref_stream(form)!=stream:raise ValueError('Archived PDF does not preserve the original Form stream')
    paths=parse(stream)
    occurrences=[i for i,p in enumerate(paths[0][0])if p==TOUCH]
    if occurrences!=[15,54]:raise ValueError('Native exact point contact identity differs')
    polygons=[]
    for i,parts in enumerate(paths):
        segments=[(tuple(map(float,a)),tuple(map(float,b)))for part in parts for a,b in zip(part,part[1:])if a!=b]
        cells,cuts,dangles,invalid=polygonize_full(MultiLineString(segments))
        if cuts.geoms or dangles.geoms or invalid.geoms:raise ValueError('Original source graph is incomplete')
        cells=sorted(cells.geoms,key=lambda p:-p.area)
        if len(cells)!=(3 if i==0 else 1):raise ValueError('Original source-cell count differs')
        polygons.append(cells[0])
    central=polygons[0]
    if not central.is_valid or len(central.interiors)!=2:raise ValueError('Expected original central-cell representation differs')
    hole_records=[]
    for i,hole in enumerate(central.interiors):
        match=[name for j,name in [(1,'Kósafalu'),(3,'Muszáj')]if Polygon(hole).equals(polygons[j])]
        if len(match)!=1:raise ValueError('A native hole has no independent named-cell counterpart')
        intersection=central.exterior.intersection(hole)
        hole_records.append({'holeIndexZeroBased':i,'separateSourceCellName':match[0],
                             'shellIntersectionWkt':intersection.wkt,'shellIntersectionEmpty':intersection.is_empty})
    kosa=next(r for r in hole_records if r['separateSourceCellName']=='Kósafalu')
    muszaj=next(r for r in hole_records if r['separateSourceCellName']=='Muszáj')
    if kosa['shellIntersectionWkt']!='POINT (207.51 568.81)'or not muszaj['shellIntersectionEmpty']:raise ValueError('Native exact touch differs')
    if not polygons[5].boundary.covers(Point(float(TOUCH[0]),float(TOUCH[1]))):raise ValueError('Rendőrfalu original contour does not meet the same source point')
    registration=json.loads((FROZEN/'georeference.json').read_text());affine=np.array(registration['affinePagePointToEovRows'])
    page=[float(Decimal('98.15')+TOUCH[0]*Decimal('.12108')*Decimal('5.5413')),
          float(Decimal('841.92')-Decimal('65.172')-TOUCH[1]*Decimal('.085555')*Decimal('7.8417'))]
    metric=np.array([*page,1])@affine
    wgs=Transformer.from_crs(23700,4326,always_xy=True).transform(*metric)
    local=json.loads((FROZEN/'local-units-inferred.geojson').read_text())['features']
    fine=json.loads((FROZEN/'fine-inferred.geojson').read_text())['features']
    exported=next(f for f in local if f['properties']['name']=='Szent László város — belső forráscella')
    world=shape(exported['geometry']);world_contact=[]
    for i,ring in enumerate(world.interiors):
        intersection=world.exterior.intersection(ring)
        if not intersection.is_empty:world_contact.append({'holeIndexZeroBased':i,'shellIntersectionWkt':intersection.wkt})
    if len(world_contact)!=1 or not world.exterior.intersection(world.interiors[0]).equals(Point(*wgs)):raise ValueError('Exported point contact differs from independently transformed native point')
    # Importing the actual repository validator has no build side effect: its
    # CLI guard runs only when build.mjs itself is the process entry point.
    js="""
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const root=process.argv[1];
const {validateGeometry}=await import(pathToFileURL(root+'/scripts/neighborhoods/build.mjs'));
const folder=root+'/data/neighborhoods/sources/municipal-kecskemet-native77-first/';
const rows=[];
for(const filename of ['fine-inferred.geojson','local-units-inferred.geojson']){
 const data=JSON.parse(await readFile(folder+filename,'utf8'));
 for(const feature of data.features){
  const verdict=validateGeometry(feature.geometry,feature.bbox);
  rows.push({sourceFile:filename,id:feature.id,name:feature.properties.name,valid:verdict.valid,reason:verdict.reason??null});
 }
}
process.stdout.write(JSON.stringify(rows));
"""
    process=subprocess.run(['node','--input-type=module','-e',js,str(ROOT)],capture_output=True,text=True,check=True)
    actual=json.loads(process.stdout)
    rejected=[r for r in actual if not r['valid']];accepted=[r for r in actual if r['valid']]
    if len(rejected)!=1 or rejected[0]['id']!=exported['id']or rejected[0]['reason']!='hole_outside_shell'or len(accepted)!=6:raise ValueError('Actual repository admission results differ')
    build=ROOT/'scripts/neighborhoods/build.mjs';code=build.read_text()
    if "if (onSegment(a, b, point)) return false;"not in code or 'ringsIntersect(checkedRings[i], checkedRings[0])'not in code:raise ValueError('Expected strict contact policy changed')
    after=frozen_hashes()
    if before!=after:raise ValueError('Frozen native77 directory changed during read-only audit')
    result={'schemaVersion':1,'status':'CONFIRMED_CENTRAL_CELL_REJECTED_BY_PROJECT_VALIDATOR',
            'scope':'Independent supplemental project-admission correction. The existing frozen native77-first batch is read-only and remains byte-identical. No source geometry, ring role, export, validator or registry is modified.',
            'frozenBatchPath':str(FROZEN.relative_to(ROOT)),'frozenBatchFileCountReadOnlyVerified':len(before),
            'allFrozenFilesSha256UnchangedDuringAudit':True,
            'inputsSha256':{str(p.relative_to(ROOT)):sha(p)for p in [FROZEN/'source-form188-stream.txt',FROZEN/'source-pages163-164.pdf',FROZEN/'fine-inferred.geojson',FROZEN/'local-units-inferred.geojson',FROZEN/'georeference.json',build,Path(__file__).resolve()]},
            'rawNativeFinding':{'sourceFormStreamSha256':FORM_SHA,'archivedSourceFormXref':form,'drawingIndexZeroBased':6,
                                'subpathIndexZeroBased':0,'literalDecimalPoint':list(map(str,TOUCH)),
                                'literalRepeatedVertexIndicesZeroBased':occurrences,
                                'sourceFirstSubpathVertexCountIncludingMovetoAndRepeatedLineReturns':len(paths[0][0]),
                                'pointContactAlreadyPresentInOriginalSource':True,'namedHoleContacts':hole_records,
                                'rendőrfaluOriginalBoundaryMeetsSamePoint':True,'shapelyCentralPolygonValid':central.is_valid,
                                'shapelyValidityExplanation':explain_validity(central)},
            'exportedFinding':{'independentlyTransformedPagePoint':page,'independentlyTransformedWgs84Point':list(wgs),
                               'exportedShellHoleContacts':world_contact,'shapelyWorldPolygonValid':world.is_valid,
                               'introducedByGeoreferencingRoundingOrRepair':False},
            'actualProjectValidator':{'modulePath':'scripts/neighborhoods/build.mjs','sha256':sha(build),
                                      'actualExportedValidateGeometryFunctionCalled':True,'validationResults':actual,
                                      'acceptedCount':len(accepted),'rejectedCount':len(rejected),
                                      'strictPolicy':'pointInside returns false on shell boundary, and ringsIntersect treats any shell-hole point contact as intersection. Either condition rejects with hole_outside_shell. This exact name does not mean the hole has positive area outside the shell.',
                                      'ringRotationOrOrientationDoesNotRemoveContact':True},
            'correctionToEarlierIndependentReview':'The frozen earlier independent review verified Shapely validity and source-preserving geometry, but did not invoke the actual project validateGeometry admission function. Its all-seven inferred-layer approval therefore exceeds the project admission result. Preserve it as historical evidence and apply this supplemental correction: six records pass project geometry validation; the central two-hole source cell does not.',
            'safeAdmissionDecision':{'fineInferredRecordsPassingGeometry':3,'localInferredRecordsPassingGeometry':3,
                                     'centralSourceCellAdmitted':False,'centralSourceCellMustRemainQuarantined':True,
                                     'allOtherSixRecordsStillRequireTheirDocumentedInferredOnlyStatus':True,
                                     'sourceGeometryPreserved':True,'noRepairHoleDeletionRingRoleChangeOrForceAdmission':True},
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False}
    output=OUT/'native77-admission-independent.json';data=encode(result)
    if check:
        if not output.exists()or output.read_bytes()!=data:raise ValueError('Supplemental admission review is stale')
    else:output.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','confirmed':True,'actualProjectAccepted':len(accepted),'actualProjectRejected':len(rejected),'reason':rejected[0]['reason'],'sourceContact':list(map(str,TOUCH)),'frozenFilesUnchanged':True},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');main(p.parse_args().check)
