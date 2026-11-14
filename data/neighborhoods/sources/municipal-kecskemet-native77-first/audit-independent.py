#!/usr/bin/env python3
"""Portable independent Figure 77 audit; never imports derive.py.

Default/--check need only this frozen directory plus fitz/numpy/pyproj/shapely.
--refresh-pbf-proof optionally revalidates source roads and current name nodes
against the pinned original country PBF. The resulting per-object digest proof
makes default replay independent of external work directories and the PBF.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
PBF_SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
FORM_SHA='1a572f913226e234c8862baa59118bf79468977d7f8bef079775cf4e1bb50d07'
NAMES=['Szent László város — belső forráscella','Kósafalu','Déli iparterület I.','Muszáj','Déli iparterület II.','Rendőrfalu','Nyugati iparterület']
NUM=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
POINT=re.compile(r'^('+NUM+r') ('+NUM+r') ([ml])$')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def load(filename):return json.loads((OUT/filename).read_text())
def encode(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def payload(feature):
    s=feature['properties']['source']
    return {'id':s['osmId'],'tags':s['tags'],'nodeRefs':s['nodeRefs'],'coordinates':feature['geometry']['coordinates'],'version':s['objectVersion'],'timestamp':s['objectTimestamp']}


def pbf_proof():
    import osmium
    pbf=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
    if sha(pbf)!=PBF_SHA:raise ValueError('Original country PBF fingerprint changed')
    roads={f['properties']['source']['osmId']:f for f in load('control-roads.geojson')['features']}
    names={f['properties']['source']['osmId']:f for f in load('current-name-points.geojson')['features']}
    seenways,seennodes={},{}
    class Handler(osmium.SimpleHandler):
        def way(self,obj):
            if obj.id not in roads:return
            if any(not n.location.valid()for n in obj.nodes):raise ValueError('Missing original PBF node location')
            actual={'id':obj.id,'tags':dict(obj.tags),'nodeRefs':[n.ref for n in obj.nodes],
                    'coordinates':[[n.lon,n.lat]for n in obj.nodes],'version':obj.version,'timestamp':str(obj.timestamp)}
            if actual!=payload(roads[obj.id]):raise ValueError('Changed literal control source way: '+str(obj.id))
            seenways[obj.id]={'osmWayId':obj.id,'sourceComparablePayloadSha256':digest(actual),'nodeCount':len(obj.nodes)}
        def node(self,obj):
            if obj.id not in names:return
            actual={'osmNodeId':obj.id,'coordinates':[obj.location.lon,obj.location.lat],'tags':dict(obj.tags),'version':obj.version,'timestamp':str(obj.timestamp)}
            expected=names[obj.id];s=expected['properties']['source']
            if not(actual['coordinates']==expected['geometry']['coordinates'] and actual['tags']==s['tags'] and actual['version']==s['objectVersion'] and actual['timestamp']==s['objectTimestamp']):raise ValueError('Changed current fine-name source node')
            seennodes[obj.id]=actual
    with tempfile.TemporaryDirectory(prefix='otthonra-kec77-independent-')as temporary:
        Handler().apply_file(str(pbf),locations=True,idx='sparse_file_array,'+str(Path(temporary)/'nodes.idx'),filters=[osmium.filter.IdFilter(set(roads)|set(names))])
    if set(seenways)!=set(roads)or set(seennodes)!=set(names):raise ValueError('An original PBF control/name object is missing')
    result={'schemaVersion':1,'sourcePbfSha256':PBF_SHA,'sourcePbfBytes':pbf.stat().st_size,
            'method':'Independent direct original-PBF scan by source object ID. Every complete control-way nodeRef, node coordinate, tag, version and timestamp is compared. Every current fine-name node coordinate, tag, version and timestamp is compared. No derivation code imported.',
            'controlWayCount':len(roads),'allControlWaysExactlyMatchOriginalPbf':True,
            'ways':[seenways[k]for k in sorted(seenways)],'currentNameNodes':[seennodes[k]for k in sorted(seennodes)]}
    (OUT/'independent-pbf-object-proof.json').write_bytes(encode(result))
    print(json.dumps({'directPbfValidation':'PASS','controlWays':len(roads),'currentFineNameNodes':len(names)}))


def parse_native(stream):
    marker=b'0 G\n1.8122 w\n2 J\n2 j\n'
    if stream.count(marker)!=1:raise ValueError('Native boundary block identity changed')
    paths=[];parts=[];current=None
    for raw in stream.split(marker,1)[1].splitlines():
        line=raw.decode('ascii').strip();m=POINT.fullmatch(line)
        if m:
            x,y,op=m.groups();p=(Decimal(x),Decimal(y))
            if op=='m':
                if current is not None:raise ValueError('An unclosed original source subpath')
                current=[p]
            else:
                if current is None:raise ValueError('Original lineto without moveto')
                current.append(p)
        elif line in ('h','s','S'):
            if current is None or current[-1]!=current[0]:raise ValueError('Original source path would need an extra closure edge')
            parts.append(current);current=None
            if line in ('s','S'):
                paths.append(parts);parts=[]
                if len(paths)==7:return paths
        elif line in ('q','Q','W*','n')or line.endswith(' re'):
            if current is not None:raise ValueError('Unexpected clipping operator in original source path')
        elif line:raise ValueError('Unexpected native source operator: '+line)
    raise ValueError('Missing original source boundary path')


def audit(check):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Transformer
    from shapely.geometry import MultiLineString,Polygon,shape
    from shapely.ops import polygonize_full
    pyproj.network.set_network_enabled(False)
    if check and (OUT/'manifest.json').exists():
        final_manifest=load('manifest.json')
        frozen=final_manifest['frozenFilesSha256']
        if final_manifest['frozenFileCountExcludingManifest']!=len(frozen):raise ValueError('Final manifest file count differs')
        for filename,expected in frozen.items():
            if sha(OUT/filename)!=expected:raise ValueError('Changed final frozen batch file: '+filename)
    producer=load('input-manifest.json')
    for filename,expected in producer['sha256'].items():
        if sha(OUT/filename)!=expected:raise ValueError('Changed frozen producer input: '+filename)
    generated=load('generated-manifest.json')
    for filename,expected in generated['sha256'].items():
        if sha(OUT/filename)!=expected:raise ValueError('Changed producer output: '+filename)
    doc=fitz.open(OUT/'source-pages163-164.pdf')
    forms=[x for x in doc[0].get_xobjects()if x[1]=='Meta1858']
    if len(forms)!=1:raise ValueError('Archived native source Form missing')
    native=doc.xref_stream(forms[0][0])
    if hashlib.sha256(native).hexdigest()!=FORM_SHA or native!=(OUT/'source-form188-stream.txt').read_bytes():raise ValueError('Archived original Form stream differs')
    if not any(doc.xref_stream(x)==(OUT/'source-page163-stream.txt').read_bytes()for x in doc[0].get_contents()):raise ValueError('Archived original page content stream differs')
    image_refs=[x[0]for x in doc[0].get_images()if x[2:4]==(1110,1569)]
    if len(image_refs)!=1 or doc.extract_image(image_refs[0])['image']!=(OUT/'figure77-p163-xref189.jpeg').read_bytes():raise ValueError('Original embedded JPEG bytes differ')
    text=' '.join((doc[0].get_text()+' '+doc[1].get_text()).split())
    if not all(s in text for s in ['városrész lehatárolása','három különálló lakónegyed','Rendőrfalu','Kósafalu','Muszáj']):raise ValueError('Independent historical name/scope text missing')
    raw=parse_native(native)
    polygons=[];native_counts=[];source_edges=[]
    for i,parts in enumerate(raw):
        edges=[(tuple(map(float,a)),tuple(map(float,b)))for part in parts for a,b in zip(part,part[1:])if a!=b]
        cells,cuts,dangles,invalid=polygonize_full(MultiLineString(edges))
        cells=sorted(cells.geoms,key=lambda p:-p.area)
        if len(cells)!=(3 if i==0 else 1)or len(cuts.geoms)or len(dangles.geoms)or len(invalid.geoms):raise ValueError('Native source graph topology changed')
        chosen=cells[0]
        if not chosen.is_valid or len(chosen.interiors)!=(2 if i==0 else 0):raise ValueError('Native source geometry/holes changed')
        edge_set={tuple(sorted((a,b)))for a,b in edges}
        for ring in [chosen.exterior,*chosen.interiors]:
            if any(tuple(sorted((a,b)))not in edge_set for a,b in zip(list(ring.coords),list(ring.coords)[1:])):raise ValueError('Polygonizer introduced a source edge')
        polygons.append(chosen);native_counts.append(len(edges));source_edges.append(edge_set)
    if sum(native_counts)!=497:raise ValueError('Changed literal nonzero source-edge count')
    if not all(any(Polygon(r).equals(polygons[j])for j in [1,3])for r in polygons[0].interiors):raise ValueError('Source inner-cell/hole identity changed')
    sourceproof=load('independent-pbf-object-proof.json');roads=load('control-roads.geojson')['features']
    if sourceproof['sourcePbfSha256']!=PBF_SHA or len(roads)!=20 or sourceproof['controlWayCount']!=20:raise ValueError('Original PBF proof identity changed')
    sourceway={r['osmWayId']:r for r in sourceproof['ways']}
    nodes={};membership={}
    for road in roads:
        s=road['properties']['source'];refs=s['nodeRefs'];cs=road['geometry']['coordinates']
        if digest(payload(road))!=sourceway[s['osmId']]['sourceComparablePayloadSha256']:raise ValueError('Portable original-PBF way digest changed')
        if len(refs)!=len(cs)or len(refs)!=sourceway[s['osmId']]['nodeCount']:raise ValueError('A whole source-way sequence was clipped')
        for r,c in zip(refs,cs):
            if r in nodes and nodes[r]!=c:raise ValueError('Conflicting source-node coordinates')
            nodes[r]=c;membership.setdefault(r,set()).add(road['id'])
    spec=load('control-specification.json');controls=spec['controls'];held=spec['heldOutVisualControls']
    for c in controls+held:
        if nodes[c['osmNodeId']]!=c['coordinates']or membership[c['osmNodeId']]!=set(c['sourceWayIds']):raise ValueError('A control is not the stated literal node/ways')
    if len(controls)!=6 or len(held)!=1:raise ValueError('Geographic control design changed')
    visual=load('independent-gcp-visual-review.json')
    if visual['sourceImageSha256']!=sha(OUT/'figure77-p163-xref189.jpeg'):raise ValueError('Visual evidence source changed')
    for filename,expected in visual['crops'].items():
        if sha(OUT/filename)!=expected:raise ValueError('Independent unmarked visual crop changed')
    if not visual['heldOutCandidate']['sourceFeatureIdentityUnconfirmed']:raise ValueError('Unsupported held-out identity confirmation')
    # Refit from the literal source node coordinates and original source-page
    # measurements; do not read the producer affine as an input to the fit.
    eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
    points=np.array([c['sourcePagePoint']for c in controls],dtype=float)
    metric=np.array([eov.transform(*c['coordinates'])for c in controls]);design=np.column_stack((points,np.ones(6)))
    affine=np.linalg.lstsq(design,metric,rcond=None)[0]
    reg=load('georeference.json')
    if np.max(np.abs(affine-np.array(reg['affinePagePointToEovRows'])))>1e-7:raise ValueError('Producer geographic transform differs')
    residual=np.linalg.norm(design@affine-metric,axis=1)
    if np.max(np.abs(residual-np.array(reg['controlResidualMeters'])))>1e-6:raise ValueError('Control residuals differ')
    def page_ring(ring):
        return np.array([[float(Decimal('98.15')+Decimal(str(x))*Decimal('.12108')*Decimal('5.5413')),
                          float(Decimal('841.92')-Decimal('65.172')-Decimal(str(y))*Decimal('.085555')*Decimal('7.8417'))]for x,y in ring.coords])
    all_page=np.concatenate([page_ring(r)for p in polygons for r in [p.exterior,*p.interiors]])
    all_design=np.column_stack((all_page,np.ones(len(all_page))))
    base=all_design@affine
    outputs=load('fine-inferred.geojson')['features']+load('local-units-inferred.geojson')['features']
    if len(outputs)!=7:raise ValueError('Unexpected output feature count')
    byname={f['properties']['name']:f for f in outputs};rows=[];total_vertices=0;max_error=0.
    name_nodes={n['osmNodeId']:n for n in sourceproof['currentNameNodes']}
    current=load('current-name-points.geojson')['features']
    for f in current:
        s=f['properties']['source'];e=name_nodes[s['osmId']]
        if not(f['geometry']['coordinates']==e['coordinates']and s['tags']==e['tags']and s['objectVersion']==e['version']and s['objectTimestamp']==e['timestamp']):raise ValueError('Current fine-name source node differs')
    for i,name in enumerate(NAMES):
        f=byname[name];props=f['properties'];geo=shape(f['geometry']);rawpoly=polygons[i]
        if not geo.is_valid or len(geo.interiors)!=len(rawpoly.interiors):raise ValueError('Output validity or hole count differs')
        if not(props['estimated'] is True and props['boundaryKind']=='inferred_area'and props['usableForAddressAssignment'] is False and props['absoluteAccuracyMeters'] is None):raise ValueError('Inferred-only safety/status fields changed')
        expected_rings=[]
        for r in [rawpoly.exterior,*rawpoly.interiors]:
            m=np.column_stack((page_ring(r),np.ones(len(r.coords))))@affine
            lon,lat=wgs.transform(m[:,0],m[:,1]);expected_rings.append(np.column_stack((lon,lat)))
        unmatched=list(range(len(expected_rings)));count=0
        for actual_ring in [geo.exterior,*geo.interiors]:
            actual=np.array(actual_ring.coords);match=[]
            for j in unmatched:
                expected=expected_rings[j]
                if len(actual)!=len(expected):continue
                distance=np.max(np.abs(actual[:,None,:]-expected[None,:,:]),axis=2)
                nearest=np.argmin(distance,axis=1);error=float(np.max(distance[np.arange(len(actual)),nearest]))
                if error<=1e-10:match.append((j,nearest,error))
            if len(match)!=1:raise ValueError('An output ring/vertex has no exact independently transformed source counterpart')
            j,nearest,error=match[0];unmatched.remove(j);n=len(expected_rings[j])-1
            for a,b in zip(nearest,nearest[1:]):
                a,b=int(a)%n,int(b)%n
                if (a-b)%n not in (1,n-1):raise ValueError('An output segment skips a source edge')
            max_error=max(max_error,error);count+=len(actual)
        if unmatched:raise ValueError('An original source ring is missing')
        total_vertices+=count
        evidence=next((n for n in current if n['properties']['name']==name),None)
        if i in (1,3,5)and evidence is None:raise ValueError('A fine-name point is missing')
        rows.append({'name':name,'outputVerticesIncludingRingClosures':count,'sourceHoleCount':len(rawpoly.interiors),
                     'outputHoleCount':len(geo.interiors),'everyVertexAndEdgeMatchesIndependentlyTransformedOriginalSource':True,
                     'currentNamePointCovered':geo.covers(shape(evidence['geometry']))if evidence else None,
                     'semanticScope':'separately named residential quarter'if i in (1,3,5)else 'qualified central/planning/economic source cell',
                     'inferredOnly':True})
    # Independent leave-one-control-out and reflected similarity models.
    loo=[]
    for i,c in enumerate(controls):
        keep=[j for j in range(6)if j!=i];other=np.linalg.lstsq(design[keep],metric[keep],rcond=None)[0]
        delta=np.linalg.norm(all_design@other-base,axis=1)
        row={'omittedControlId':c['id'],'omittedControlPredictionErrorMeters':float(np.linalg.norm(design[i]@other-metric[i])),
             'maximumSourceVertexDisplacementMeters':float(delta.max()),'meanSourceVertexDisplacementMeters':float(delta.mean())}
        claimed=reg['modelSensitivity']['leaveOneControlOutAffineFits'][i]
        if abs(row['maximumSourceVertexDisplacementMeters']-claimed['maximumSourceVertexDisplacementMeters'])>1e-6:raise ValueError('LOO sensitivity differs')
        loo.append(row)
    similarity_design=[];target=[]
    for (x,y),(e,n)in zip(points,metric):
        similarity_design.extend([[x,y,1,0],[-y,x,0,1]]);target.extend([e,n])
    a,b,tx,ty=np.linalg.lstsq(np.array(similarity_design),np.array(target),rcond=None)[0]
    sim=np.array([[a,b],[b,-a],[tx,ty]]);sim_delta=np.linalg.norm(all_design@sim-base,axis=1)
    if abs(float(sim_delta.max())-reg['modelSensitivity']['similarityVersusAffineMaximumSourceVertexDisplacementMeters'])>1e-5:raise ValueError('Similarity sensitivity differs')
    inverse=np.linalg.inv(np.vstack((affine.T,[0,0,1])))
    held_rows=[]
    for i,c in enumerate(held):
        predicted=(np.array([*eov.transform(*c['coordinates']),1])@inverse.T)[:2];window=c['sourcePagePointWindow']
        inside=all(window[axis][0]<=predicted[j]<=window[axis][1]for j,axis in enumerate(['x','y']))
        claim=reg['heldOutVisualChecks'][i]
        if inside!=claim['insideInspectedWindow']or np.max(np.abs(predicted-np.array(claim['predictedSourcePagePoint'])))>1e-7:raise ValueError('Held-out discrepancy not faithfully recorded')
        if inside:raise ValueError('Expected strict held-out failure was silently changed')
        held_rows.append({'osmNodeId':c['osmNodeId'],'predictedSourcePagePoint':predicted.tolist(),'insideUnchangedInspectedSourceWindow':inside,
                          'sourceFeatureIdentityUnconfirmed':True,'identityCaution':'Modern cycleway attachment versus historical road junction center. The exact historical counterpart of this modern cycleway attachment is unconfirmed.','usedInFit':False})
    provenance_files=['input-manifest.json','generated-manifest.json','control-specification.json','control-roads.geojson','independent-pbf-object-proof.json','independent-gcp-visual-review.json','fine-inferred.geojson','local-units-inferred.geojson','georeference.json','audit-independent.py']
    result={'schemaVersion':1,'status':'PASS_FOR_EXPLICIT_INFERRED_LAYER_ONLY','independentOfDerivationCode':True,
            'portableReplay':{'requiredExternalSourceDirectories':[],'sourcePdfFormReadFromFrozenBatch':True,
                              'controlWaysValidatedAgainstPortableOriginalPbfObjectDigests':True,
                              'optionalOriginalPbfDirectRevalidationCommand':'PYTHONPATH=.local/geodata python3 audit-independent.py --refresh-pbf-proof',
                              'finalManifestExcludedFromAuditFingerprintToAvoidCircularHashDependency':True},
            'provenanceSha256':{f:sha(OUT/f)for f in provenance_files},
            'nativeSource':{'originalFormStreamSha256':FORM_SHA,'archivedFormXref':forms[0][0],'nativePathCount':7,'nativeNonzeroSegmentCount':sum(native_counts),
                            'everySourceSubpathExplicitLinetoClosed':True,'additionalImplicitClosureEdges':0,'sourceFrameClosure':False,
                            'polygonizerCutsDanglesInvalidRings':0,'originalCentralCellHolesExactlyMatchMuszajAndKosafalu':True,
                            'originalPathsBeyondImageCropPreserved':['Déli iparterület II.','Nyugati iparterület']},
            'controlSourceWays':{'wayCount':len(roads),'directOriginalPbfSnapshotSha256':PBF_SHA,'allFullNodeSequencesCoordinatesTagsVersionsTimestampsVerified':True,
                                 'coordinatePairCount':sum(len(f['geometry']['coordinates'])for f in roads),'currentNameNodeCount':len(current)},
            'sourceToWorld':{'allOutputVerticesChecked':total_vertices,'maximumCoordinateDisagreementDegrees':max_error,
                             'outputFeatureCount':7,'allOriginalHolesPreserved':True,'noIntroducedOutputEdge':True,
                             'geographicAffineIndependentlyRecomputed':True,'rmsFittedControlResidualMeters':float(np.sqrt(np.mean(residual**2))),
                             'controlResidualsDoNotProveFeatureIdentityOrAbsoluteAccuracy':True},
            'gcpVisualReviewPath':'independent-gcp-visual-review.json','heldOutIndependentChecks':held_rows,
            'modelSensitivity':{'leaveOneControlOut':loo,'similarityVsAffineMaximumSourceVertexDisplacementMeters':float(sim_delta.max()),
                                'similarityVsAffineMeanSourceVertexDisplacementMeters':float(sim_delta.mean()),
                                'diagnosticNotCalibratedErrorBound':True},
            'featureChecks':rows,
            'semanticDecision':{'fineResidentialQuarters':['Kósafalu','Muszáj','Rendőrfalu'],
                                'separateQualifiedLocalCells':['Szent László város — belső forráscella','Déli iparterület I.','Déli iparterület II.','Nyugati iparterület'],
                                'centralCellNotPromotedToWholeCaptionDistrict':True,'industrialFunctionAloneNotGroundForExclusion':True,
                                'groupGeometryNotCopiedUnderFineNames':True,'currentNamesDoNotVerifyHistoricalExtent':True},
            'geographicRegistrationVerified':False,'primaryLayerApproved':False,'inferredLayerApproved':True,
            'sourceFeatureIdentityUnconfirmed':True,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
            'approvalReason':'Literal historical source contours, topology and conversion are verified. The six fitted historical junction centers are plausible visual correspondences but lack independent exact historical-to-modern point identity. The southern candidate pairs a modern cycleway attachment with a historical road junction center whose identity is unconfirmed; strict held-out-window failure remains visible. Leave-one-out/model-family sensitivity reaches tens of meters at extrapolated source vertices. These concrete registration uncertainties justify inferred-only status; unknown absolute accuracy by itself is not the rejection criterion.'}
    data=encode(result);target=OUT/'independent-review.json'
    if check:
        if not target.exists()or target.read_bytes()!=data:raise ValueError('Independent review stale or missing')
    else:target.write_bytes(data)
    print(json.dumps({'mode':'check'if check else'build','status':result['status'],'nativePaths':7,'originalControlWays':20,'allOutputVerticesChecked':total_vertices,'strictHeldoutPass':False,'maximumModelFamilyDisplacementMeters':float(sim_delta.max())},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--refresh-pbf-proof',action='store_true');a=p.parse_args()
    if a.refresh_pbf_proof:pbf_proof()
    audit(a.check)
