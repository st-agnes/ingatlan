#!/usr/bin/env python3
"""Independent original-PDF and frozen Eger geometry readback; never edits sources."""
from pathlib import Path
import argparse,hashlib,json
import fitz,numpy as np
from shapely import set_precision
from shapely.geometry import shape,LineString,Point
from shapely.ops import unary_union,polygonize,transform,nearest_points
from pyproj import Transformer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=ROOT/'data/neighborhoods/sources/municipal-east'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def audit():
    pdf=OLD/'eger-map-2016.pdf'
    assert sha(pdf)=='7db28b2b5922e6dea7bde9dc3263087534b26e9cd1e52b63335249265df6febe'
    doc=fitz.open(pdf);assert len(doc)==1
    drawings=doc[0].get_drawings()
    saved=json.loads((OLD/'eger-pdf-vector-paths.json').read_text())
    world=json.loads((OLD/'eger-planning-units.geojson').read_text())
    native={};records=[]
    for row in saved['paths']:
        idx=row['pdfDrawingIndex'];items=drawings[idx]['items']
        assert items and all(item[0]=='l' for item in items),idx
        segments=[set_precision(LineString([tuple(it[1]),tuple(it[2])]),.001) for it in items]
        result=unary_union(list(polygonize(unary_union(segments))))
        reference=shape(row['pdfGeometry'])
        area=result.symmetric_difference(reference).area
        distance=result.hausdorff_distance(reference)
        assert area<1e-7 and distance<1e-7,(idx,area,distance)
        native[idx]=result
        records.append({'pdfDrawingIndex':idx,'nativeLineCount':len(items),
                        'nativeAndArchivedSymmetricDifferencePdfPointsSquared':area,
                        'nativeAndArchivedHausdorffPdfPoints':distance})
    assert len(native)==33
    native[165659]=native[165659].difference(unary_union([native[i] for i in [164816,164817,165658]]))
    mat=np.asarray(saved['affineToEov']['matrix']);offset=np.asarray(saved['affineToEov']['offset'])
    reverse=Transformer.from_crs(23700,4326,always_xy=True)
    def mapped(x,y,z=None):
        return reverse.transform(mat[0,0]*np.asarray(x)+mat[0,1]*np.asarray(y)+offset[0],
                                 mat[1,0]*np.asarray(x)+mat[1,1]*np.asarray(y)+offset[1])
    by_idx={r['pdfDrawingIndex']:r for r in records}
    for f in world['features']:
        idx=f['properties']['sourcePdfDrawingIndex'];expected=transform(mapped,native[idx]);actual=shape(f['geometry'])
        delta=expected.symmetric_difference(actual).area;dist=expected.hausdorff_distance(actual)
        assert actual.is_valid and delta<1e-12 and dist<1e-9,(idx,delta,dist)
        by_idx[idx].update({'outputName':f['properties']['name'],'outputValid':True,
                          'nativeToFrozenWorldSymmetricDifferenceDegreesSquared':delta,
                          'nativeToFrozenWorldHausdorffDegrees':dist})
    assert len(world['features'])==32
    outlines=[]
    for idx in range(164771,164780):
        assert all(item[0]=='l' for item in drawings[idx]['items'])
        outlines.extend(LineString([tuple(item[1]),tuple(item[2])]) for item in drawings[idx]['items'])
    outline=unary_union(outlines)
    samples=np.asarray([outline.interpolate(t,normalized=True).coords[0] for t in np.linspace(0,1,1200,endpoint=False)])
    municipal_file=HERE/'calibration-municipality.geojson'
    municipal=next(f for f in json.loads(municipal_file.read_text())['features'] if f['properties']['name']=='Eger')
    assert municipal['id']=='osm:relation:1418156'
    assert municipal['properties']['source']['osmType']=='relation'
    assert municipal['properties']['source']['osmId']==1418156
    assert municipal['properties']['source']['pbfSha256']=='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
    forward=Transformer.from_crs(4326,23700,always_xy=True)
    target=transform(forward.transform,shape(municipal['geometry'])).boundary
    x0,y0,x1,y1=target.bounds;p0,q0,p1,q1=outline.bounds
    fit=np.diag([(x1-x0)/(p1-p0),-(y1-y0)/(q1-q0)])
    shift=np.array([x0-fit[0,0]*p0,y1-fit[1,1]*q0])
    for _ in range(35):
        projected=samples@fit.T+shift
        nearest=np.asarray([nearest_points(Point(*v),target)[1].coords[0] for v in projected])
        distances=np.linalg.norm(nearest-projected,axis=1)
        select=distances<np.percentile(distances,90)
        beta=np.linalg.lstsq(np.column_stack([samples[select],np.ones(select.sum())]),nearest[select],rcond=None)[0]
        fit=beta[:2].T;shift=beta[2]
    coefficient_difference=max(float(np.abs(fit-mat).max()),float(np.abs(shift-offset).max()))
    assert coefficient_difference<1e-6,coefficient_difference
    final_distances=np.asarray([Point(*v).distance(target) for v in samples@fit.T+shift])
    return {'schemaVersion':1,'checkedAt':'2026-11-14','status':'original_native_paths_and_frozen_geographic_transform_verified',
            'sourcePdfSha256':sha(pdf),'actualNativeSourcePathsChecked':33,'frozenWorldFeaturesChecked':32,
            'originalPathsOrWorldFeaturesChanged':False,'independentInteriorControlCount':0,
            'semanticAdmissionDecisionMadeByThisAudit':False,'primaryCoverageCredit':0,
            'calibration':{'method':'Independently read actual native perimeter linework and rerun 35 trimmed closest-boundary affine fits; bounding box is only the initial estimate, not the resulting fit.',
                           'sourcePerimeterDrawingIndices':list(range(164771,164780)),
                           'sampleCount':1200,'trimmedPerIteration':.10,'coefficientMaximumDifference':coefficient_difference,
                           'reportedLastPrefitMedianP95MaximumMetres':list(map(float,np.percentile(distances,[50,95,100]))),
                           'recomputedFinalMatrixMedianP95MaximumMetres':list(map(float,np.percentile(final_distances,[50,95,100]))),
                           'residualsAreIndependentAccuracyBounds':False,
                           'municipalityInputPath':str(municipal_file.relative_to(ROOT)),
                           'municipalityInputSha256':sha(municipal_file)},
            'nativeAndWorldRecords':records,'absoluteAccuracyMetres':None,'usableForAddressAssignment':False,
            'limitations':['This verifies source geometry and transformation arithmetic; it does not establish that a regulatory plan unit is a full current ordinary quarter.',
                           'The initial municipal bounds are followed by actual perimeter fitting. Neither perimeter agreement nor a printed scale validates the interior independently.',
                           'Frozen reported residuals use the final prefit iteration; the final-matrix distances are reported separately, without changing any frozen source.'],
            'inputFingerprints':[{'path':str((OLD/n).relative_to(ROOT)),'sha256':sha(OLD/n)}for n in ['eger-map-2016.pdf','eger-pdf-vector-paths.json','eger-planning-units.geojson']]}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=audit();text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n';out=HERE/'root-native-geometry-audit.json'
    if args.check:assert out.read_text()==text
    else:out.write_text(text)
    print(json.dumps({k:v for k,v in result.items() if k in ['status','actualNativeSourcePathsChecked','frozenWorldFeaturesChecked','primaryCoverageCredit','independentInteriorControlCount']}))
