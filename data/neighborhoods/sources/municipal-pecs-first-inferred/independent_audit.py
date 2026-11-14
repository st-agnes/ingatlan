#!/usr/bin/env python3
"""Independent, read-only-by-default audit of the frozen first Pecs inferred batch.
No producer union or transform implementation is imported.
"""
from pathlib import Path
import argparse,hashlib,json,math,subprocess
import fitz
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Point,Polygon,shape
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
REPORT=HERE/'independent-review.json'
SOURCE_PDF_SHA='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1'
FROZEN_SOURCE_SHA='3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95'
VALIDATOR_SOURCE_SHA='7d234a3c4750b6a735483befd02661c6ba199491fec102bd2d301dabf4cb216c'
VALIDATOR_SNAPSHOT_SHA='abf1b564180d9b33593f9ce0d711eb996bf8f3a1d9cbb03b7527167ac515f3d7'
VALIDATOR_LITERAL_SNIPPET_SHA='76dc7e7e6647bf98e5a1c6dc18c21acdd4fe57db8a33a96235cefd3d35541a81'
EXPECTED_IMAGES={'pecs-p63-density.jpeg':'08ec2a2ffe63222113424c7353ab502399b20b4e8d41f7262545ee4483283788','pecs-p48-names.jpeg':'75758682472a880dee3488068f324d3feb4ba916237de33d36734696ed1d78f8'}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value):return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def pixel_hash(points):return hashlib.sha256(json.dumps(sorted(points),separators=(',',':')).encode()).hexdigest()
def canonical_edge(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int, int, int]:
    """Endpoints use doubled pixel coordinates to preserve half-integers exactly."""
    if b < a:
        a, b = b, a
    return (*a, *b)


def independently_exposed_faces(included: np.ndarray, stroke: np.ndarray):
    """Enumerate raw cell faces, without polygon construction or geometric union."""
    h, w = included.shape
    edges = set()
    missing_adjacent_stroke = 0
    touches_edge = False
    y_values, x_values = np.nonzero(included)
    for y, x in zip(y_values.tolist(), x_values.tolist()):
        # Outside-cell neighbor plus its corresponding unit edge endpoints.
        faces = (
            (x, y - 1, (2*x - 1, 2*y - 1), (2*x + 1, 2*y - 1)),
            (x + 1, y, (2*x + 1, 2*y - 1), (2*x + 1, 2*y + 1)),
            (x, y + 1, (2*x - 1, 2*y + 1), (2*x + 1, 2*y + 1)),
            (x - 1, y, (2*x - 1, 2*y - 1), (2*x - 1, 2*y + 1)),
        )
        for nx, ny, a, b in faces:
            in_raster = 0 <= nx < w and 0 <= ny < h
            if in_raster and included[ny, nx]:
                continue
            edges.add(canonical_edge(a, b))
            touches_edge |= not in_raster
            if not in_raster or not stroke[ny, nx]:
                missing_adjacent_stroke += 1
    return edges, missing_adjacent_stroke, touches_edge


def expand_saved_grid_edges(pixel_geometry: dict):
    """Expand saved ring segments to unit faces; do not derive a new footprint."""
    assert pixel_geometry['type'] == 'Polygon'
    edges = set()
    duplicates = 0
    for ring in pixel_geometry['coordinates']:
        doubled = np.asarray(ring, dtype=float) * 2
        assert np.array_equal(doubled, np.rint(doubled)), 'Non-half-integer pixel vertex'
        xy = np.rint(doubled).astype(np.int64)
        assert np.array_equal(xy[0], xy[-1]), 'Open saved pixel ring'
        assert np.all(xy % 2 == 1), 'Pixel-cell corners must have odd doubled coordinates'
        for a, b in zip(xy[:-1], xy[1:]):
            delta = b - a
            assert (delta[0] == 0) != (delta[1] == 0), 'Non-grid or duplicate saved edge'
            length = int(abs(delta[0]) + abs(delta[1]))
            assert length % 2 == 0 and length > 0
            step = np.sign(delta) * 2
            for index in range(length // 2):
                v0 = tuple((a + index*step).tolist())
                v1 = tuple((a + (index + 1)*step).tolist())
                edge = canonical_edge(v0, v1)
                duplicates += edge in edges
                edges.add(edge)
    return edges, duplicates


def independently_project_rings(pixel_geometry: dict, names_to_density: np.ndarray,
                                names_to_eov: np.ndarray):
    """Use homogeneous matrices rather than the producer's scalar transform."""
    first = np.c_[names_to_density, np.array([0., 0., 1.])]
    second = np.c_[names_to_eov, np.array([0., 0., 1.])]
    density_to_eov = np.linalg.inv(first) @ second
    to_geographic = Transformer.from_crs('EPSG:23700', 'EPSG:4326', always_xy=True)
    rings = []
    for ring in pixel_geometry['coordinates']:
        points = np.asarray(ring, dtype=float)
        east_north = np.c_[points, np.ones(len(points))] @ density_to_eov
        lon, lat = to_geographic.transform(east_north[:, 0], east_north[:, 1])
        rings.append(np.c_[lon, lat].tolist())
    return {'type': 'Polygon', 'coordinates': rings}, density_to_eov.tolist()


def existing_js_validation(collection: dict):
    module = (HERE / 'strict-validator-snapshot.mjs').as_uri()
    program = f"""
import fs from 'node:fs';
import {{validateGeometry}} from {json.dumps(module)};
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(source.features.map(f => ({{
  id:f.id, name:f.properties.name, ...validateGeometry(f.geometry)
}}))));
"""
    result = subprocess.run(['node', '--input-type=module', '-e', program],
                            input=json.dumps(collection), text=True,
                            cwd=HERE, capture_output=True, check=True)
    return json.loads(result.stdout)


def verify_snapshot_images():
    provenance=json.loads((HERE/'pecs-source-extraction-proof.json').read_text())
    assert provenance['originalPdfSha256']==SOURCE_PDF_SHA
    subset_path=HERE/provenance['subsetPath']
    assert digest(subset_path)==provenance['subsetSha256']
    excerpt=fitz.open(subset_path)
    records=[]
    for page_number,image_name in ((48,'pecs-p48-names.jpeg'),(63,'pecs-p63-density.jpeg')):
        local=(HERE/image_name).read_bytes()
        assert hashlib.sha256(local).hexdigest()==EXPECTED_IMAGES[image_name]
        page=excerpt[provenance['subsetOriginalPagesOneBased'].index(page_number)]
        embedded=[excerpt.extract_image(image[0])['image'] for image in page.get_images(full=True)]
        assert local in embedded
        records.append({'originalPdfPageOneBased':page_number,'image':image_name,
          'matchesPreviouslyIndependentlyVerifiedOriginalImageSha256':True,
          'excerptEmbeddedImageByteIdentical':True,'sha256':EXPECTED_IMAGES[image_name]})
    return records


def audit():
    filenames=['source-inferred.geojson','conversion-proof.json','raw-pixel-cells.json',
      'assignments.json','derive.py','pecs-p63-density.jpeg','pecs-p48-names.jpeg',
      'pecs-cartographic-hole-decisions.json','pecs-cartographic-hole-review.json',
      'pecs-image-alignment.json','pecs-registration-northwest-only-diagnostic.json',
      'pecs-independent-name-cell-review.json','pecs-review-gray-heldout-diagnostic.json',
      'pecs-source-extraction-proof.json','pecs-source-selected-pages.pdf','independent_audit.py',
      'strict-validator-snapshot.mjs','strict-validator-source-proof.json']
    paths=[HERE/name for name in filenames]
    hashes_before={path:digest(path) for path in paths}
    load=lambda name:json.loads((HERE/name).read_text())
    assert digest(HERE/'source-inferred.geojson')==FROZEN_SOURCE_SHA
    validator_proof=load('strict-validator-source-proof.json')
    assert validator_proof['originalSha256']==VALIDATOR_SOURCE_SHA
    assert validator_proof['snapshotSha256']==digest(HERE/'strict-validator-snapshot.mjs')==VALIDATOR_SNAPSHOT_SHA
    validator_text=(HERE/'strict-validator-snapshot.mjs').read_text()
    literal=validator_text[validator_text.index('const EPSILON'):].rstrip('\n')
    assert hashlib.sha256(literal.encode()).hexdigest()==VALIDATOR_LITERAL_SNIPPET_SHA
    source,proof,raw,assignments=map(load,('source-inferred.geojson','conversion-proof.json',
      'raw-pixel-cells.json','assignments.json'))
    decisions=load('pecs-cartographic-hole-decisions.json')
    name_review=load('pecs-independent-name-cell-review.json')
    assert assignments['sourceNameReviewSnapshotSha256']==digest(HERE/'pecs-independent-name-cell-review.json')
    assert source['status']=='estimated_geographic_placement_only'
    assert proof['frozenBatch'] and proof['primaryApprovedCount']==0
    assert proof['placementVerified'] is False and proof['usableForAddressAssignment'] is False
    assert len(source['features'])==len(proof['records'])==len(raw['records'])==len(assignments['records'])==33
    for item in proof['inputs']:
        assert Path(item['path']).name==item['path']
        assert digest(HERE/item['path'])==item['sha256']
    original_images=verify_snapshot_images()
    rgb=np.asarray(Image.open(HERE/'pecs-p63-density.jpeg').convert('RGB'),dtype=np.int64)
    stroke=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|\
      (rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],size=7)-16)
    free,free_count=ndimage.label(~stroke,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
    assert free_count==proof['allSourceCellCount']==221
    assert decisions['sourceImageSha256']==digest(HERE/'pecs-p63-density.jpeg')
    approved={row['sourcePixelSetSha256']:row for row in decisions['records']}
    assert len(approved)==86 and all(row['restorationApproved'] for row in approved.values())
    raw_by_id={row['sourceComponentId']:row for row in raw['records']}
    proof_by_id={row['sourceCellId']:row for row in proof['records']}
    assignment_by_id={row['reviewedSourceComponentId']:row for row in assignments['records']}
    assert len(raw_by_id)==len(proof_by_id)==len(assignment_by_id)==33
    names_to_density=np.asarray(load('pecs-image-alignment.json')['matrixNamesPixelsToDensityPixels'])
    names_to_eov=np.asarray(load('pecs-registration-northwest-only-diagnostic.json')['matrixPixelToEov'])
    validations=existing_js_validation(source)
    assert len(validations)==33 and all(row['valid'] for row in validations)
    validations_by_id={row['id']:row for row in validations}
    output_records=[];world_geometries=[];used_restored=set();used_decisions=set()
    interpreted_stroke=stroke.copy();total_raw_faces=total_interpreted_faces=0
    composite_matrix=None
    for feature in source['features']:
        p=feature['properties'];cid=p['sourceCellId'];record=proof_by_id[cid];assignment=assignment_by_id[cid]
        assert p['name']==record['name']==assignment['sourceName']
        reviewed=[r for r in name_review['records'] if r['sourceName']==p['name']]
        assert len(reviewed)==1 and reviewed[0]['reviewedSourceComponentId']==cid
        assert reviewed[0]['canUseUnchangedSourceCell']
        assert reviewed[0]['verifiedDensityInteriorPixel']==assignment['verifiedDensityInteriorPixel']
        seed=assignment['verifiedDensityInteriorPixel']
        assert int(free[seed[1],seed[0]])==cid
        included=free==cid
        assert not(included[0].any() or included[-1].any() or included[:,0].any() or included[:,-1].any())
        raw_geometry=raw_by_id[cid]['pixelCellGeometry']
        assert raw_geometry==record['rawPixelCellGeometry']
        raw_polygon=shape(raw_geometry)
        original_faces,missing,touches=independently_exposed_faces(included,stroke)
        saved_raw_faces,duplicates=expand_saved_grid_edges(raw_geometry)
        assert original_faces==saved_raw_faces and not missing and not touches and not duplicates
        assert raw_polygon.area==int(included.sum())==record['rawPixelCount']
        restored=included.copy();removed_faces=set();restoration_records=[]
        producer_restorations={r['sourcePixelSetSha256']:r for r in record['restorations']}
        for ring in raw_polygon.interiors:
            hole=Polygon(ring);x0,y0,x1,y1=hole.bounds
            pixels=[[x,y] for y in range(math.ceil(y0),math.floor(y1)+1)
              for x in range(math.ceil(x0),math.floor(x1)+1) if hole.contains(Point(x,y))]
            assert len(pixels)==hole.area
            signature=pixel_hash(pixels)
            decision=approved[signature];reported=producer_restorations[signature]
            assert decision['sourceComponentId']==cid and decision['restorationApproved']
            assert sorted(reported['pixels'])==sorted(pixels)
            assert reported['classification']==decision['classification']
            assert signature not in used_decisions;used_decisions.add(signature)
            for x,y in pixels:
                assert stroke[y,x] and free[y,x]==0 and (x,y) not in used_restored
                assert all(int(free[ny,nx]) in (0,cid) for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
                restored[y,x]=True;interpreted_stroke[y,x]=False;used_restored.add((x,y))
            faces,_=expand_saved_grid_edges({'type':'Polygon','coordinates':[list(ring.coords)]})
            removed_faces|=faces
            restoration_records.append({'sourcePixelSetSha256':signature,'originalSourcePixels':len(pixels),
              'allOriginalMask':True,'otherFreeSourceCellContainedOrTouched':False,
              'explicitIndependentDecisionMatched':True,'classification':decision['classification']})
        assert len(producer_restorations)==len(restoration_records)
        interpreted_faces,missing,touches=independently_exposed_faces(restored,stroke)
        interpreted_geometry=record['interpretedPixelCellGeometry']
        saved_interpreted_faces,duplicates=expand_saved_grid_edges(interpreted_geometry)
        assert interpreted_faces==saved_interpreted_faces==original_faces-removed_faces
        assert not missing and not touches and not duplicates
        original_outer_faces,_=expand_saved_grid_edges({'type':'Polygon','coordinates':[raw_geometry['coordinates'][0]]})
        assert interpreted_faces==original_outer_faces
        interpreted_polygon=shape(interpreted_geometry)
        assert interpreted_polygon.is_valid and not interpreted_polygon.interiors
        assert interpreted_polygon.area==int(restored.sum())
        assert int(restored.sum()-included.sum())==record['restoredSourcePixelCount']==p['cartographicRestoredPixelCount']
        rebuilt,composite_matrix=independently_project_rings(interpreted_geometry,names_to_density,names_to_eov)
        actual=feature['geometry'];assert actual['type']==rebuilt['type']=='Polygon'
        assert len(actual['coordinates'])==len(rebuilt['coordinates'])==1
        left,right=np.asarray(actual['coordinates'][0]),np.asarray(rebuilt['coordinates'][0])
        assert left.shape==right.shape
        error=float(np.max(np.abs(left-right)));assert error<=1e-12
        world=shape(actual);assert world.is_valid and not world.interiors;world_geometries.append(world)
        assert p['boundaryKind']=='inferred_area' and p['estimated'] is True
        assert p['canonicalNameIsNeighborhood'] is False and p['usableForAddressAssignment'] is False
        assert p['claimedAbsoluteAccuracyMetres'] is None and p['sourceIsHardBoundary'] is False
        assert p['georeferencingStatus']=='estimated_geographic_alignment_not_verified'
        assert record['geographicPlacementVerified'] is False
        assert p['externalSourceOutlineChanged'] is False
        assert record['sourceImageEdgeClosureInvented'] is False
        total_raw_faces+=len(original_faces);total_interpreted_faces+=len(interpreted_faces)
        output_records.append({'id':feature['id'],'name':p['name'],'sourceCellId':cid,
          'independentFrozenNameReviewAssignmentMatched':True,'rawOriginalPixelCount':int(included.sum()),
          'independentRawExposedFaceCount':len(original_faces),'rawFaceMismatchCount':0,
          'restoredOriginalPixelCount':int(restored.sum()-included.sum()),'restorations':restoration_records,
          'interpretedPixelCount':int(restored.sum()),'independentInterpretedFaceCount':len(interpreted_faces),
          'interpretedFaceMismatchCount':0,'externalSourceFacesChanged':0,'holesAfterInterpretation':0,
          'geosValid':True,'existingStrictJsValidation':validations_by_id[feature['id']],
          'worldProjectionMaximumVertexErrorDegrees':error,'geographicPlacementVerified':False,
          'estimatedOnly':True,'primaryApproval':False,'usableForAddressAssignment':False})
    assert len(used_restored)==proof['cartographicRestorationPixelCount']==1076
    assert len(used_decisions)==86
    interpreted_free,interpreted_count=ndimage.label(~interpreted_stroke,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
    assert interpreted_count==free_count
    pairs=np.unique(free[free>0]*(interpreted_count+1)+interpreted_free[free>0])
    old_ids,new_ids=np.divmod(pairs,interpreted_count+1)
    assert len(old_ids)==len(np.unique(old_ids))==free_count
    assert len(new_ids)==len(np.unique(new_ids))==interpreted_count
    max_overlap=0.
    for i,world in enumerate(world_geometries):
        for other in world_geometries[:i]:max_overlap=max(max_overlap,world.intersection(other).area)
    assert max_overlap<1e-16
    reproduction=subprocess.run(['python3',str(HERE/'derive.py'),'--check'],cwd=Path.cwd(),text=True,
      capture_output=True,check=True)
    for path,sha in hashes_before.items():assert digest(path)==sha,'Frozen producer input changed during audit'
    counts={'neighbourhood':sum(f['properties']['candidateBoundaryKind']=='neighbourhood' for f in source['features']),
      'planning_unit':sum(f['properties']['candidateBoundaryKind']=='planning_unit' for f in source['features'])}
    assert counts=={'neighbourhood':32,'planning_unit':1}
    return {'schemaVersion':1,'reviewDate':'2026-11-14',
      'reviewer':'independent local_pdf_expand/pecs_pixel_review agent',
      'verdict':'pass_inferred_only_33_records_zero_primary',
      'scope':'Frozen first snapshot only: original raw source cells, explicit cartographic pixel restoration, unchanged exterior edges, projection arithmetic, strict topology and retained inferred-only status. Geographic placement is unverified.',
      'sourceRecordCount':33,'inferredCandidateCount':33,'candidateFineNames':32,'candidatePlanningUnits':1,
      'primaryApprovedCount':0,'geographicPlacementVerified':False,'usableForAddressAssignment':False,
      'sourceImages':original_images,'originalPdfSha256Provenance':SOURCE_PDF_SHA,
      'allRawSourceCellExposedFaceSetsIndependentlyVerified':True,'totalRawExposedFaces':total_raw_faces,
      'allInterpretedExposedFaceSetsIndependentlyVerified':True,'totalInterpretedExposedFaces':total_interpreted_faces,
      'explicitlyReviewedRestoredHoleCount':86,'restoredOriginalSourcePixelCount':1076,
      'externalSourcePixelFacesChanged':0,'originalFreeSourceCellCount':int(free_count),
      'freeSourceCellCountAfterRestoration':int(interpreted_count),'freeSourceCellMappingRemainsOneToOne':True,
      'sourceImageEdgeClosureInvented':False,'holesInExportedGeometries':0,
      'strictJsValidCount':33,'strictJsRejectedCount':0,'maximumPairwiseOverlapDegreesSquared':max_overlap,
      'strictValidatorSnapshotLiteralOriginIndependentlyComparedAtFreeze':True,
      'strictValidatorSnapshotSha256':VALIDATOR_SNAPSHOT_SHA,
      'allAuditDataAndValidatorInputsAreLocalSnapshotFiles':True,
      'independentHomogeneousDensityToEovMatrix':composite_matrix,
      'producerReadOnlyReproductionCheckPassed':reproduction.returncode==0,
      'producerUnionOrTransformCodeImportedForIndependentCalculations':False,
      'placementLimits':'Northwestern-only calibration is retained as estimated. Later perimeter controls disagree by up to approximately 350 m. This audit does not certify location, source age/current validity, legal boundary, licence or address assignment.',
      'networkUsed':False,'producerFilesModified':False,
      'inputFingerprints':[{'path':str(path.relative_to(HERE)),'sha256':sha} for path,sha in hashes_before.items()],
      'records':output_records}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args();report=audit();text=encoded(report)
    if args.check:assert REPORT.read_text()==text,'Frozen independent audit report changed'
    if args.write_report:REPORT.write_text(text)
    print(encoded({k:report[k] for k in ('verdict','inferredCandidateCount','primaryApprovedCount',
      'restoredOriginalSourcePixelCount','externalSourcePixelFacesChanged','strictJsValidCount')}))


if __name__=='__main__':main()


