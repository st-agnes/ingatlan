#!/usr/bin/env python3
"""Frozen, offline Figure 77 native-path batch. Run with PYTHONPATH=.local/geodata."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
URL = 'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
PDF_SHA = '83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
FORM_SHA = '1a572f913226e234c8862baa59118bf79468977d7f8bef079775cf4e1bb50d07'
NAMES = ['Szent László város — belső forráscella', 'Kósafalu', 'Déli iparterület I.',
         'Muszáj', 'Déli iparterület II.', 'Rendőrfalu', 'Nyugati iparterület']
SLUGS = ['szent-laszlo-belso-forrascella', 'kosafalu', 'deli-iparterulet-1',
         'muszaj', 'deli-iparterulet-2', 'rendorfalu', 'nyugati-iparterulet']
FINE = {1, 3, 5}
METHOD = ('Literal decimal m/l paths from the original municipal PDF Figure 77 Form stream. '
          'Only original nonzero line segments are polygonized, independently per source stroke object; '
          'no noding, buffer, repair, snap, simplification, image-frame closure or invented connecting edge. '
          'The central source cell retains both original holes. Six manually interpreted historical-map '
          'road junctions and literal current OSM-node coordinates fit an affine transform in EOV/EPSG:23700; '
          'a candidate southern road-junction/cycleway attachment is held out, with physical identity unconfirmed. '
          'Geographic placement is an explicit unverified estimate. '
          'Source contours are transformed to WGS84 without replacing them by current roads.')
LICENSE = 'Municipal source-map reuse rights unverified; ODbL-1.0 for OSM geographical controls and name points.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def build(check=False):
    import fitz
    import numpy as np
    import pyproj
    from pyproj import Geod, Transformer
    from shapely.geometry import MultiLineString, Polygon, mapping, shape
    from shapely.ops import polygonize_full
    from PIL import Image, ImageDraw
    pyproj.network.set_network_enabled(False)
    generated = {}

    def save(filename, value):
        payload = encode(value)
        generated[filename] = hashlib.sha256(payload).hexdigest()
        if check:
            if not (OUT / filename).exists() or (OUT / filename).read_bytes() != payload:
                raise ValueError('Missing or stale artifact: ' + filename)
        else:
            (OUT / filename).write_bytes(payload)

    frozen = json.loads((OUT / 'input-manifest.json').read_text())
    for filename, expected in frozen['sha256'].items():
        if sha(OUT / filename) != expected:
            raise ValueError('Frozen source changed: ' + filename)
    doc = fitz.open(OUT / 'source-pages163-164.pdf')
    source_form = next(x[0] for x in doc[0].get_xobjects() if x[1] == 'Meta1858')
    if hashlib.sha256(doc.xref_stream(source_form)).hexdigest() != FORM_SHA:
        raise ValueError('Archived page does not preserve original Form stream')
    if sha(OUT / 'source-form188-stream.txt') != FORM_SHA:
        raise ValueError('Changed native Form stream')
    raw = json.loads((OUT / 'figure77-native-source-decimal-paths.json').read_text())
    if raw['sourcePdfSha256'] != PDF_SHA or len(raw['paths']) != 7:
        raise ValueError('Changed native path identity')
    # Exact decimal source operations remain the authority. Zero-length source
    # instructions are ignored by the polygonizer because they are not edges.
    native_polygons, source_records = [], []
    for index, path in enumerate(raw['paths']):
        segments = []
        for sub in path['subpaths']:
            vertices = [[Decimal(x), Decimal(y)] for x, y in sub['decimalVertices']]
            if vertices[0] != vertices[-1] or not sub['explicitLineReturnBeforeClose']:
                raise ValueError('A source subpath needs an invented closing edge')
            segments.extend([[list(map(float, a)), list(map(float, b))]
                             for a, b in zip(vertices, vertices[1:]) if a != b])
        polygons, cuts, dangles, invalid = polygonize_full(MultiLineString(segments))
        polys = sorted(polygons.geoms, key=lambda p: -p.area)
        if len(polys) != (3 if index == 0 else 1) or any(len(g.geoms) for g in [cuts, dangles, invalid]):
            raise ValueError('Unexpected native source topology')
        chosen = polys[0]
        if not chosen.is_valid or len(chosen.interiors) != (2 if index == 0 else 0):
            raise ValueError('Changed valid native cell or holes')
        source_edges = {tuple(sorted((tuple(a), tuple(b)))) for a, b in segments}
        for ring in [chosen.exterior, *chosen.interiors]:
            if any(tuple(sorted((tuple(a), tuple(b)))) not in source_edges
                   for a, b in zip(ring.coords, list(ring.coords)[1:])):
                raise ValueError('Output source ring contains a non-source edge')
        native_polygons.append(chosen)
        source_records.append({'name': NAMES[index], 'fitzDrawingIndexZeroBased': index + 6,
                               'sourceNonzeroSegmentCount': len(segments),
                               'selectedNativePolygon': mapping(chosen),
                               'allOutputEdgesMatchLiteralSourceSegments': True,
                               'originalInteriorCount': len(chosen.interiors),
                               'sourceNativeContinuationBeyondDisplayedCrop': index in (4, 6),
                               'closureEdgesAdded': 0})
    for ring in native_polygons[0].interiors:
        if not any(Polygon(ring).equals(native_polygons[i]) for i in (1, 3)):
            raise ValueError('A source central-cell hole lost its separate named-cell identity')

    controls = json.loads((OUT / 'control-specification.json').read_text())
    roads = json.loads((OUT / 'control-roads.geojson').read_text())['features']
    nodes, membership = {}, {}
    for road in roads:
        source = road['properties']['source']
        refs, coords = source['nodeRefs'], road['geometry']['coordinates']
        if len(refs) != len(coords) or not source['geometryUnmodified']:
            raise ValueError('Changed literal control-way sequence')
        for node, coord in zip(refs, coords):
            if node in nodes and nodes[node] != coord:
                raise ValueError('Inconsistent literal road-node coordinate')
            nodes[node] = coord
            membership.setdefault(node, set()).add(road['id'])
    for control in controls['controls'] + controls['heldOutVisualControls']:
        node = control['osmNodeId']
        if nodes[node] != control['coordinates'] or set(control['sourceWayIds']) != membership[node]:
            raise ValueError('Control is not its stated literal road-junction node')
    to_eov = Transformer.from_crs(4326, 23700, always_xy=True)
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    points = np.array([c['sourcePagePoint'] for c in controls['controls']])
    metric = np.array([to_eov.transform(*c['coordinates']) for c in controls['controls']])
    design = np.c_[points, np.ones(len(points))]
    affine = np.linalg.lstsq(design, metric, rcond=None)[0]
    residuals = np.linalg.norm(design @ affine - metric, axis=1)
    if len(points) != 6 or max(residuals) > 25:
        raise ValueError('Unexpected geographic-control fit')
    inverse = np.linalg.inv(np.vstack([affine.T, [0, 0, 1]]))
    held_out = []
    for control in controls['heldOutVisualControls']:
        metric_control = to_eov.transform(*control['coordinates'])
        fitted_pixel = (np.array([*metric_control, 1]) @ inverse.T)[:2]
        window = control['sourcePagePointWindow']
        inside = all(window[axis][0] <= fitted_pixel[i] <= window[axis][1]
                     for i, axis in enumerate(['x', 'y']))
        held_out.append({'id': control['id'], 'osmNodeId': control['osmNodeId'],
                         'predictedSourcePagePoint': fitted_pixel.tolist(),
                         'independentlyInspectedSourcePageWindow': window,
                         'insideInspectedWindow': inside, 'usedInFit': False,
                         'sourceFeatureIdentityVerified': control.get('sourceFeatureIdentityVerified', False),
                         'identityCaution': control.get('identityCaution'),
                         'registrationValidationEstablished': False})
        # A failed visual window is evidence, not a reason to widen the window
        # or force the transformation. Keep the conservative inferred batch.

    def page_points(ring):
        # These are literal publisher matrices, not a fitted inter-figure relation.
        return np.array([[float(Decimal('98.15') + Decimal(str(x)) * Decimal('.12108') * Decimal('5.5413')),
                          float(Decimal('841.92') - (Decimal('65.172') + Decimal(str(y)) * Decimal('.085555') * Decimal('7.8417')))]
                         for x, y in ring.coords])

    def world_ring(ring):
        m = np.c_[page_points(ring), np.ones(len(ring.coords))] @ affine
        lon, lat = to_wgs.transform(m[:, 0], m[:, 1])
        return np.c_[lon, lat].tolist()

    all_page_vertices = np.concatenate([page_points(ring) for polygon in native_polygons
                                        for ring in [polygon.exterior, *polygon.interiors]])
    all_design = np.c_[all_page_vertices, np.ones(len(all_page_vertices))]
    full_fit_vertices = all_design @ affine
    leave_one_out = []
    for omitted, control in enumerate(controls['controls']):
        keep = [i for i in range(len(points)) if i != omitted]
        other = np.linalg.lstsq(design[keep], metric[keep], rcond=None)[0]
        changes = np.linalg.norm(all_design @ other - full_fit_vertices, axis=1)
        omitted_error = float(np.linalg.norm(design[omitted] @ other - metric[omitted]))
        leave_one_out.append({'omittedControlId': control['id'],
                              'omittedControlPredictionErrorMeters': omitted_error,
                              'maximumSourceVertexDisplacementMeters': float(max(changes)),
                              'meanSourceVertexDisplacementMeters': float(np.mean(changes))})
    similarity_design, similarity_target = [], []
    for (x, y), (east, north) in zip(points, metric):
        similarity_design += [[x, y, 1, 0], [-y, x, 0, 1]]
        similarity_target += [east, north]
    aa, bb, tx, ty = np.linalg.lstsq(np.array(similarity_design), np.array(similarity_target), rcond=None)[0]
    similarity = np.array([[aa, bb], [bb, -aa], [tx, ty]])
    similarity_change = np.linalg.norm(all_design @ similarity - full_fit_vertices, axis=1)
    sensitivity = {'leaveOneControlOutAffineFits': leave_one_out,
                   'similarityFitPagePointToEovRows': similarity.tolist(),
                   'similarityVersusAffineMaximumSourceVertexDisplacementMeters': float(max(similarity_change)),
                   'similarityVersusAffineMeanSourceVertexDisplacementMeters': float(np.mean(similarity_change)),
                   'interpretation': 'Model changes diagnose sensitivity to chosen controls and transform family; they do not bound actual boundary error.'}

    names = json.loads((OUT / 'current-name-points.geojson').read_text())['features']
    fine, local, world_polygons, geod = [], [], [], Geod(ellps='WGS84')
    for index, polygon in enumerate(native_polygons):
        geo = Polygon(world_ring(polygon.exterior), [world_ring(r) for r in polygon.interiors])
        if not geo.is_valid or len(geo.interiors) != len(polygon.interiors):
            raise ValueError('Invalid transformed original source geometry')
        world_polygons.append(geo)
        area, perimeter = geod.geometry_area_perimeter(geo)
        name_point = next((p for p in names if p['properties']['name'] == NAMES[index]), None)
        if index in FINE and name_point is None:
            raise ValueError('Missing independently archived current fine-name point')
        scope = ('Separately named residential quarter expressly identified in PDF164 prose.' if index in FINE
                 else 'Separately labelled industrial/economic source cell within the broader Szent László Város district; fine-neighborhood status is not established.')
        if index == 0:
            scope = ('The two-hole CENTRAL source cell labelled Szent László város, excluding the separate Muszáj and Kósafalu cells. '
                     'It is not the complete Szent László Város district named in the caption and prose; no independent fine-neighborhood scope is asserted.')
        props = {'name': NAMES[index], 'sourceLabel': 'Szent László város' if index == 0 else NAMES[index],
                 'municipality': 'Kecskemét', 'boundaryKind': 'inferred_area',
                 'candidateBoundaryKind': 'neighbourhood' if index in FINE else 'local_area',
                 'sourceSemanticKind': 'distinct_residential_quarter' if index in FINE else 'named_local_planning_or_economic_cell',
                 'canonicalNameIsNeighborhood': False, 'estimated': True,
                 'sourceNativeContourVerified': True, 'sourceScopeNote': scope,
                 'method': METHOD, 'evidenceUrls': [URL], 'license': LICENSE,
                 'sourcePeriod': '2021 May municipal consultation draft; underlying orthophoto date unknown.',
                 'sourceDocuments': [{'url': URL, 'sha256': PDF_SHA, 'pdfPageOneBased': 163, 'printedPage': 161,
                                      'figure': 77, 'originalSourceFormXref': 188,
                                      'sourceFormStreamSha256': FORM_SHA}],
                 'sourceIsOfficial': False, 'sourceIsHardBoundary': False,
                 'claimedAbsoluteAccuracyMetres': None, 'absoluteAccuracyMeters': None,
                 'usableForAddressAssignment': False,
                 'geometryVerificationStatus': 'native_source_contour_verified_geographic_placement_inferred',
                 'reviewStatus': 'estimated_candidate_not_verified',
                 'sourcePathContinuesBeyondDisplayedImageCrop': index in (4, 6),
                 'currentNameEvidence': {'status': 'exact_current_osm_name_point' if name_point else 'historical_municipal_source_label_only',
                                         'currentNameIndependentlyConfirmed': name_point is not None,
                                         'osmPointId': name_point['id'] if name_point else None,
                                         'currentOsmPointCoveredByHistoricalEstimatedPolygon': geo.covers(shape(name_point['geometry'])) if name_point else None,
                                         'namePointDoesNotVerifyBoundaryExtent': True},
                 'areaM2': abs(area), 'perimeterM': perimeter,
                 'attribution': 'Source: Kecskemét MJV Megalapozó Vizsgálat II, May 2021 consultation draft, Figure 77; geographical controls ©OpenStreetMap contributors.',
                 'reviewNotes': ['Every contour edge is an original native PDF line segment, including original portions beyond the displayed map crop.',
                                 'Map registration uses manual source junction interpretation. Residuals and a held-out visual match do not calibrate absolute boundary accuracy.',
                                 'Industrial function alone is not grounds for discarding a source-named cell; its documented local/economic scope is retained.',
                                 'The source-map reuse license, current exact boundary extent, legal status and address assignment remain unverified.']}
        feature = {'type': 'Feature', 'id': 'manual:kecskemet-figure77:' + SLUGS[index],
                   'properties': props, 'geometry': mapping(geo)}
        (fine if index in FINE else local).append(feature)
    save('fine-inferred.geojson', {'type': 'FeatureCollection', 'features': fine})
    save('local-units-inferred.geojson', {'type': 'FeatureCollection', 'features': local})
    registration = {'schemaVersion': 1, 'sourcePageCoordinateSystem': 'PDF page points, top-left origin; x right, y down',
                    'geographicFitCrs': 'EPSG:23700', 'outputCrs': 'EPSG:4326',
                    'affinePagePointToEovRows': affine.tolist(), 'controlCount': len(points),
                    'controlResidualMeters': residuals.tolist(), 'maximumControlResidualMeters': float(max(residuals)),
                    'rmsControlResidualMeters': float(np.sqrt(np.mean(residuals**2))),
                    'heldOutVisualChecks': held_out,
                    'modelSensitivity': sensitivity,
                    'geoPdfDictionarySearch': {'keysSearchedAcrossOriginalPdfXrefObjects': ['/VP','/Measure','/LGIDict','/GPTS','/LPTS','/GCS'], 'matches': 0},
                    'printedCoordinatesScaleOrNorthArrowFound': False,
                    'otherFigureControlsReused': False, 'geographicRegistrationVerified': False,
                    'absoluteAccuracyMeters': None, 'usableForAddressAssignment': False,
                    'limitation': 'Manual historical image correspondences and modern road centers are uncalibrated; southern extent is largely extrapolated. A native closed contour is proved separately from approximate placement.'}
    save('georeference.json', registration)
    save('native-contour-proof.json', {'schemaVersion': 1, 'sourcePdfSha256': PDF_SHA,
                                     'sourceNativeFormStreamSha256': FORM_SHA,
                                     'nativeCoordinateSystem': 'Original Form coordinates; see source matrices in independent-source review.',
                                     'records': source_records, 'totalNonzeroSourceSegmentCount': sum(r['sourceNonzeroSegmentCount'] for r in source_records),
                                     'allOutputEdgesMatchLiteralSourceSegments': True,
                                     'geometryRepairSnapBufferClipOrInventedClosingEdge': False})
    save('conversion-proof.json', {'schemaVersion': 1, 'allGeometriesValid': True, 'featureCount': 7,
                                  'fineResidentialNameCount': 3, 'separateLocalSourceCellCount': 4,
                                  'nativeHoleCounts': [len(p.interiors) for p in native_polygons],
                                  'worldHoleCounts': [len(p.interiors) for p in world_polygons],
                                  'allOutputEdgesMatchLiteralSourceSegments': True,
                                  'centralCellIsNotWholeCaptionDistrict': True,
                                  'absoluteAccuracyMeters': None, 'usableForAddressAssignment': False})
    for filename, identifier, count in [('fine-inferred.geojson', 'kecskemet-native77-fine-inferred', 3),
                                        ('local-units-inferred.geojson', 'kecskemet-native77-local-inferred', 4)]:
        save(filename.replace('.geojson', '-registry-entry.json'),
             {'id': identifier, 'path': str((OUT / filename).relative_to(ROOT)), 'sha256': generated[filename],
              'municipality': 'Kecskemét', 'featureCount': count, 'method': METHOD, 'evidenceUrls': [URL],
              'license': LICENSE, 'reviewPath': str((OUT / 'independent-review.json').relative_to(ROOT)),
              'propertyOverrides': {'boundaryKind': 'inferred_area',
                                    'candidateBoundaryKind': 'neighbourhood' if count == 3 else 'local_area',
                                    'estimated': True, 'canonicalNameIsNeighborhood': False,
                                    'usableForAddressAssignment': False},
              'rightsStatus': 'Publicly published municipal consultation draft; open reuse rights not independently established.'})
    # Human review image: literal source contours, source junction measurements,
    # and current OSM controls projected onto the historical page.
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    preview = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(preview)
    palette = ['#e730a7','#00d5ff','#ffbb00','#00ff66','#ff5f40','#a17aff','#ffff00']
    for index, polygon in enumerate(native_polygons):
        for ring in [polygon.exterior, *polygon.interiors]:
            draw.line([tuple(p * 2) for p in page_points(ring)], fill=palette[index], width=2)
    for control in controls['controls'] + controls['heldOutVisualControls']:
        x, y = [v * 2 for v in control['sourcePagePoint']]
        draw.line((x-6,y,x+6,y),fill='red',width=2)
        draw.line((x,y-6,x,y+6),fill='red',width=2)
    if not check:
        preview.save(OUT / 'native-contour-control-preview.png')
    save('generated-manifest.json', {'schemaVersion': 1, 'sha256': generated.copy()})
    print(json.dumps({'mode': 'check' if check else 'build', 'fineInferred': len(fine), 'localInferred': len(local),
                      'nativeSourceSegments': sum(r['sourceNonzeroSegmentCount'] for r in source_records),
                      'maximumControlResidualMeters': float(max(residuals)), 'heldOutChecks': held_out,
                      'allSourceEdgesProved': True}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
