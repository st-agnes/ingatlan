"""Independent, offline verification. Does not import or run producer scripts.

Run from repository root: PYTHONPATH=.local/geodata python3 <this file>
Writes only independent-review.json beside this script.
"""
from collections import deque
from pathlib import Path
import argparse
import hashlib
import json

import fitz
import numpy as np
from PIL import Image
import shapely
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union
from pyproj import Transformer

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PDF = ROOT / '.local/neighborhoods/nationwide-docs/originals/salgotarjan-its.pdf'


def read(name):
    return json.loads((P / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def largest_component(mask):
    """8-neighbour connected components, independent of scipy labeling."""
    h, w = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    best = []
    for y, x in zip(*np.where(mask)):
        if seen[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        seen[y, x] = True
        found = []
        while queue:
            cy, cx = queue.popleft()
            found.append((cy, cx))
            for ny in range(max(0, cy-1), min(h, cy+2)):
                for nx in range(max(0, cx-1), min(w, cx+2)):
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        if len(found) > len(best):
            best = found
    result = np.zeros(mask.shape, dtype=bool)
    if best:
        yy, xx = np.array(best).T
        result[yy, xx] = True
    return result


def fill_holes(mask):
    """4-neighbour exterior flood; does not add a map-frame boundary."""
    padded = np.pad(mask, 1)
    h, w = padded.shape
    outside = np.zeros(padded.shape, dtype=bool)
    outside[0, 0] = True
    queue = deque([(0, 0)])
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y-1,x), (y+1,x), (y,x-1), (y,x+1)):
            if 0 <= ny < h and 0 <= nx < w and not padded[ny,nx] and not outside[ny,nx]:
                outside[ny,nx] = True
                queue.append((ny,nx))
    return (~outside)[1:-1, 1:-1]


def pixel_geometry(mask):
    runs = []
    for y in np.flatnonzero(mask.any(axis=1)):
        changes = np.flatnonzero(np.diff(np.r_[False,mask[y],False].astype(int)))
        runs.extend(box(float(a)-.5,float(y)-.5,float(b)-.5,float(y)+.5)
                    for a,b in zip(changes[::2],changes[1::2]))
    return unary_union(runs)


def rings(geometry):
    if geometry['type'] == 'Polygon':
        return geometry['coordinates']
    assert geometry['type'] == 'MultiPolygon'
    return [ring for polygon in geometry['coordinates'] for ring in polygon]


def pixel_to_world(geometry, profile_matrix, frame_matrix, projection):
    # Keep every original vertex and ring; only arithmetic and documented rounding.
    def ring_fn(ring):
        pixels = np.asarray(ring, dtype=float)
        overview = np.column_stack((pixels, np.ones(len(pixels)))) @ profile_matrix
        eov = np.column_stack((overview, np.ones(len(overview)))) @ frame_matrix
        lon, lat = projection.transform(eov[:,0], eov[:,1])
        return np.round(np.column_stack((lon, lat)), 8).tolist()
    if geometry['type'] == 'Polygon':
        return {'type':'Polygon', 'coordinates':[ring_fn(r) for r in geometry['coordinates']]}
    return {'type':'MultiPolygon', 'coordinates':[[ring_fn(r) for r in p] for p in geometry['coordinates']]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--use-excerpt',action='store_true',help='Exercise portable archived-PDF fallback even if the full original exists')
    parser.add_argument('--output',type=Path,default=P/'independent-review.json')
    args = parser.parse_args()
    native = read('profile-main-correspondence-review.json')['records']
    refined = read('profile-main-registration-refined.json')
    frame = read('exploratory-frame-registration.json')
    exports = read('salgotarjan-inferred.geojson')
    conversion = read('conversion-proof.json')
    native_output = read('profile-source-pixel-contours.geojson')
    assert len(native) == len(refined['records']) == len(exports['features']) == 8
    assert conversion['primaryFeatureCount'] == 0 and conversion['inferredFeatureCount'] == 8
    assert conversion['physicalControlCount'] == 0 and conversion['absoluteAccuracyMetres'] is None
    assert conversion['nativeContoursUnchanged'] is True
    assert conversion['sourceNamePointsUsedForGeoreference'] is False
    assert conversion['sourceGeometryClippedToCurrentMunicipality'] is False
    assert conversion['sourceFrameClosureUsed'] is False
    assert conversion['sourcePointBufferingUsed'] is False
    assert conversion['inventedConstituentSplits'] is False
    for entry in conversion['inputFingerprints']:
        assert sha(ROOT/entry['path']) == entry['sha256'], entry['path']
    proof_by_name = {r['name']:r for r in conversion['records']}
    native_by_name = {r['name']:r for r in native}
    refined_by_name = {r['name']:r for r in refined['records']}
    assert len(native_by_name) == 8 and set(native_by_name) == set(refined_by_name)
    assert {f['properties']['name'] for f in exports['features']} == set(native_by_name)
    native_output_by_name = {f['properties']['name']:f for f in native_output['features']}
    inventory = read('source-image-inventory.json')
    images = sorted({r['sourceImage'] for r in native} | {'source-p125-xref924.jpeg'})
    full_original_verified = PDF.exists() and not args.use_excerpt
    if full_original_verified:
        assert sha(PDF) == inventory['sourcePdfSha256']
        pdf = fitz.open(PDF)
        for filename in images:
            xref = int(filename.rsplit('xref',1)[1].split('.')[0])
            assert (P/filename).read_bytes() == pdf.extract_image(xref)['image']
    else:
        pdf = fitz.open(P/'source-pages125-137.pdf')
        # Clipped PDFs may renumber xrefs, so inspect every embedded image byte stream.
        xrefs = {img[0] for page in pdf for img in page.get_images(full=True)}
        hashes = {hashlib.sha256(pdf.extract_image(xref)['image']).hexdigest() for xref in xrefs}
        assert all(sha(P/filename) in hashes for filename in images)

    main_image = np.asarray(Image.open(P/'source-p125-xref924.jpeg'),dtype=int)
    red, green, blue = np.moveaxis(main_image,-1,0)
    yellow = (red-blue>25)&(green-blue>25)&(green-blue>.65*(red-blue))
    orange = (red-blue>45)&(green-blue>15)&(red-green>25)
    strong_red = (red-green>30)&(red-blue>30)&(red-green>.68*(red-blue))&((red-blue)>.6*red)
    audits = []
    for row in native:
        name = row['name']
        src = np.asarray(Image.open(P/row['sourceImage']),dtype=int)
        r,g,b = np.moveaxis(src,-1,0)
        source_mask = ((r-g>30)&(r-b>30)) if name=='Baglyasalja' else ((r-b>45)&(g-b>15)) if name=='Beszterce lakótelep' else ((r-b>25)&(g-b>25))
        npz = np.load(P/(Path(row['sourceImage']).stem+'-color-diagnostic.npz'))
        assert np.array_equal(source_mask,npz['mask'])
        region = npz['labels']==row['sourceOriginalColorComponentId']
        # Verify that selected label is a whole original 8-connected component.
        yy,xx = np.where(region)
        y0,y1,x0,x1 = yy.min(),yy.max()+1,xx.min(),xx.max()+1
        expanded = source_mask[max(0,y0-1):min(src.shape[0],y1+1),max(0,x0-1):min(src.shape[1],x1+1)]
        selected = largest_component(expanded)
        assert np.array_equal(selected,region[max(0,y0-1):min(src.shape[0],y1+1),max(0,x0-1):min(src.shape[1],x1+1)])
        assert not (region[0].any() or region[-1].any() or region[:,0].any() or region[:,-1].any())
        filled = fill_holes(region)
        raw_geometry, outer_geometry = pixel_geometry(region), pixel_geometry(filled)
        assert raw_geometry.equals_exact(shape(row['rawPixelGeometry']),0)
        assert outer_geometry.equals_exact(shape(row['sourceOuterOutlinePixelGeometry']),0)
        assert outer_geometry.equals_exact(shape(native_output_by_name[name]['geometry']),0)
        assert outer_geometry.is_valid
        assert outer_geometry.boundary.difference(raw_geometry.boundary).length == 0
        holes = filled & ~region
        assert not (holes & (src.min(axis=2)>230)).any()
        assert int(region.sum()) == row['rawColorPixelCount']
        assert int(holes.sum()) == row['cartographicInteriorPixelCount']

        ref = refined_by_name[name]
        predicate = strong_red if name=='Baglyasalja' else orange if name=='Beszterce lakótelep' else yellow&(green-red<8) if name=='Forgáchtelep' else yellow
        x0,y0,x1,y1 = ref['mainCalibrationRoiPixels']
        cropped = largest_component(predicate[y0:y1,x0:x1])
        cy,cx = np.where(cropped)
        assert min(cx)>0 and max(cx)<x1-x0-1 and min(cy)>0 and max(cy)<y1-y0-1
        target_mask = np.zeros(predicate.shape,dtype=bool)
        target_mask[y0:y1,x0:x1] = cropped
        target = pixel_geometry(fill_holes(target_mask))
        assert target.equals_exact(shape(ref['mainCalibrationPixelGeometry']),0)
        assert int(target_mask.sum()) == ref['mainColorPixelCount']
        assert [int(cx.min()+x0),int(cy.min()+y0),int(cx.max()+x0),int(cy.max()+y0)] == ref['mainSourceComponentBbox']
        coords = shapely.get_coordinates(outer_geometry.boundary)
        matrix = np.asarray(ref['matrixProfilePixelsToMainPixels'])
        residual = shapely.distance(shapely.points(np.column_stack((coords,np.ones(len(coords))))@matrix),target.boundary)
        values = np.percentile(residual,[0,50,80,90,95,100])
        assert np.array_equal(values,ref['residualPercentilesMainPixels']['values'])
        singular_values = np.linalg.svd(matrix[:2],compute_uv=False)
        assert abs(singular_values[0]-singular_values[1])<1e-14
        audits.append({'name':name,'sourceRawPixels':int(region.sum()),'interiorInterpretationPixels':int(holes.sum()),'newExternalBoundaryLengthPixels':0,'nativeValid':True,'touchesSourceImageEdge':False,'mainRoiCutsComponent':False,'mainResidualPercentiles':{'percentiles':[0,50,80,90,95,100],'values':values.tolist()}})

    assert refined_by_name['Rónafalu']['matrixProfilePixelsToMainPixels'] == refined_by_name['Rónabánya']['matrixProfilePixelsToMainPixels']

    # Reproduce the stored frame diagnostic distances without refitting a frame.
    controls = np.asarray(frame['actualSourcePixelControls'])
    assert controls.shape == (4716,2) and np.equal(controls,np.round(controls)).all()
    assert (main_image[controls[:,1].astype(int),controls[:,0].astype(int)].min(axis=1)<248).all()
    frame_matrix = np.asarray(frame['matrixPixelToEov'])
    municipal = shape(read('calibration-municipality.geojson')['geometry'])
    to_eov = Transformer.from_crs(4326,23700,always_xy=True)
    metric = transform(to_eov.transform,municipal)
    border = max(metric.geoms,key=lambda p:p.area).exterior
    dist = shapely.distance(shapely.points(np.column_stack((controls,np.ones(len(controls))))@frame_matrix),border)
    assert np.array_equal(dist,frame['residualsMetres'])
    projection = Transformer.from_crs(23700,4326,always_xy=True)
    coordinate_count = 0
    for feature in exports['features']:
        prop = feature['properties']
        name = prop.get('registrationName',prop['name'])
        # Original source label may be preserved separately from the registration alias.
        if name not in native_by_name:
            aliases = {'Forgách-telep':'Forgáchtelep','Somlyóbányatelep':'Somlyóbánya'}
            name = aliases.get(name,name)
        row = native_by_name[name]
        expected = pixel_to_world(row['sourceOuterOutlinePixelGeometry'],np.asarray(refined_by_name[name]['matrixProfilePixelsToMainPixels']),frame_matrix,projection)
        assert feature['geometry'] == expected
        result_geometry = shape(feature['geometry'])
        assert result_geometry.is_valid
        assert prop.get('usableForAddressAssignment') is False
        assert prop['estimated'] is True and prop['boundaryKind'] == 'inferred_area'
        assert prop.get('sourceIsOfficial') is False
        assert prop.get('sourceIsHardBoundary') is False
        assert prop.get('absoluteAccuracyMetres',prop.get('absoluteAccuracy')) is None
        assert prop['primaryLayerAdmission'] is False
        assert prop['georeferenceValidated'] is False
        assert prop['sourceFrameClosureUsed'] is False
        assert prop['inferredClosingEdges'] == 0
        assert prop['constituentQuarterSplitsCreated'] is False
        assert prop['currentNameCorroboration']['geometryUsedForRegistration'] is False
        assert prop['currentNameCorroboration']['polygonBoundaryValidatedByNamePoint'] is False
        proof = proof_by_name[name]
        homogeneous_profile = np.column_stack((np.asarray(refined_by_name[name]['matrixProfilePixelsToMainPixels']),[0,0,1]))
        assert np.array_equal(homogeneous_profile@frame_matrix,proof['matrixProfilePixelsToEov'])
        assert proof['sourceVertexCountIncludingClosure'] == proof['outputVertexCountIncludingClosure'] == sum(len(ring) for ring in rings(expected))
        assert proof['newExternalBoundaryLengthPixels'] == 0
        coordinate_count += sum(len(ring) for ring in rings(expected))
        for audit in audits:
            if audit['name'] == name:
                audit['allExportCoordinatesReproducedExactly'] = True
                audit['exportValid'] = True
                audit['exportVertexCountIncludingRingClosure'] = sum(len(ring) for ring in rings(expected))

    inputs = ['source-image-inventory.json','source-pages125-137.pdf','profile-main-correspondence-review.json','profile-source-pixel-contours.geojson','profile-main-registration-refined.json','exploratory-frame-registration.json','calibration-municipality.geojson','salgotarjan-inferred.geojson','conversion-proof.json','derive-inferred.py','refine-profile-registration.py']+images
    report = {'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':'Independent review_salgotarjan agent','verdict':'eight_reproducible_source_contours_with_inferred_geographic_placement','scope':'Independent native pixels, source bytes, refined registration target/residuals, frame-distance arithmetic, and every exported geographic vertex; no producer script imported or run.','networkUsed':False,'primaryLayerApproved':False,'inferredLayerApproved':True,'absoluteAccuracyMetres':None,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'sourcePdfSha256':inventory['sourcePdfSha256'],'allImageBytesMatchOriginalPdf':True,'frameDiagnosticControlCount':4716,'frameResidualsReproducedExactly':True,'frameResidualsAreIndependentAbsoluteAccuracy':False,'everyExportCoordinateReproducedExactly':True,'exportFeatureCount':8,'exportVertexCountIncludingRingClosure':coordinate_count,'records':audits,'limits':['No independently surveyed geographic controls or known original map projection; whole-city silhouette alignment is a manual inference.','Source-to-source residuals and current municipal-edge residuals are fit diagnostics, not absolute boundary accuracy.','Forgáchtelep and Zagyvaróna retain visible overview/detail differences; no vertices were adjusted to erase these.','Tiny dark/cadastral interior mask voids are explicitly interpreted as cartographic interruptions; raw mask geometries remain archived.','Present-day name occurrence does not validate historical polygon extent; original 2008/2014 delineation reuse and 2022 document date remain separate.','No Eresztvény shape or compound source-unit copies are invented; clipped neighbouring profile fragments are excluded.','Source-map reuse licensing remains unresolved.'],'visualInspection':['profile-main-correspondence-preview.png','profile-main-registration-refined.png'],'inputFingerprints':[{'path':str((P/name).relative_to(ROOT)),'sha256':sha(P/name)} for name in inputs]}
    report['sourcePdfSha256'] = inventory['sourcePdfSha256']
    report['fullOriginalHashVerified'] = full_original_verified
    report['allImageBytesMatchOriginalPdf'] = full_original_verified
    report['allImageBytesMatchArchivedPdfEvidence'] = True
    report['pdfVerificationMode'] = 'full_original_pdf_exact_xref_bytes' if full_original_verified else 'archived_excerpt_all_embedded_image_hash_search'
    report['conversionProofInputFingerprintsVerified'] = True
    report['conversionProofMatricesAndVertexCountsVerified'] = True
    report['sourceContourInterpretation'] = 'Actual color-pixel-cell external contour; no claim that this is a literal black boundary stroke or a surveyed line.'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'review':str(args.output),'features':8,'geographicCoordinatesVerified':coordinate_count,'fullOriginalHashVerified':full_original_verified,'primaryApproved':False,'inferredApproved':True},ensure_ascii=False))


if __name__ == '__main__':
    main()
