#!/usr/bin/env python3
"""Reassociate preserved country geometries without rescanning or changing PBF vertices.

All input output-file hashes are verified. The new output retains every source
geometry and construction file, changing only municipality association metadata.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys

SPEC = importlib.util.spec_from_file_location('country_extractor', Path(__file__).with_name('extract-country.py'))
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)
ASSOCIATION_KEYS = {'municipality', 'municipalityId', 'municipalityOsmId', 'municipalityEvidence',
                    'coveringMunicipalityOsmIds', 'hierarchyMunicipalityOsmIds'}


def reassociate(input_dir, output, settlements):
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    if output.exists():
        raise FileExistsError('Output directory already exists')
    manifest_path = input_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for entry in manifest['outputs']:
        if Path(entry['file']).name != entry['file']:
            raise ValueError('Invalid source output path')
        path = input_dir / entry['file']
        if path.stat().st_size != entry['bytes'] or extractor.file_hash(path) != entry['sha256']:
            raise ValueError('Source output hash mismatch: ' + entry['file'])
    canonical = set(json.loads(settlements.read_text(encoding='utf-8'))['settlements'])
    documents = {name: json.loads((input_dir / name).read_text(encoding='utf-8')) for name in
                 ['polygons.geojson', 'named-nodes.geojson', 'municipalities.geojson', 'audit.json']}
    municipal_features = documents['municipalities.geojson']['features']
    records = [{'key': feature['id'], 'canonicalName': feature['properties']['name'],
                'source': feature['properties']['source']} for feature in municipal_features]
    polygons = {feature['id']: shape(feature['geometry']) for feature in municipal_features}
    selected, selection_audit = extractor.select_municipality_boundaries(records, polygons, canonical)
    selected_keys = {record['key'] for record in selected}
    municipal_shapes = [polygons[record['key']] for record in selected]
    index = STRtree(municipal_shapes)
    for feature in municipal_features:
        feature['properties']['usedForAssociation'] = feature['id'] in selected_keys
    for filename in ['polygons.geojson', 'named-nodes.geojson']:
        for feature in documents[filename]['features']:
            properties = feature['properties']
            parents = {feature['id']: set(properties.get('hierarchyMunicipalityOsmIds', []))}
            association = extractor.associate(shape(feature['geometry']), feature['id'], index,
                                               municipal_shapes, selected, parents)
            for key in ASSOCIATION_KEYS:
                properties.pop(key, None)
            properties.update(association)
            if filename == 'polygons.geojson':
                tags = properties['source']['tags']
                kind = extractor.classification(tags)
                if properties.get('municipality') == 'Budapest' and tags.get('admin_level') == '9':
                    kind = {'boundaryKind': 'district', 'classificationReason': 'budapest_admin_9'}
                properties.update(kind)
    documents['audit.json']['municipalitySelection'] = selection_audit
    documents['audit.json']['missingCanonicalMunicipalities'] = sorted(canonical - {record['canonicalName'] for record in selected})
    output.mkdir(parents=True)
    original_outputs = manifest['outputs']
    outputs = []
    for entry in original_outputs:
        path = output / entry['file']
        if entry['file'] in documents:
            extractor.write_json(path, documents[entry['file']])
        else:
            shutil.copyfile(input_dir / entry['file'], path)
        outputs.append({'file': entry['file'], 'bytes': path.stat().st_size, 'sha256': extractor.file_hash(path)})
    features = documents['polygons.geojson']['features']
    manifest['outputs'] = outputs
    manifest['counts'].update({
        'municipalityAssociationPolygons': len(selected),
        'municipalitiesWithPolygons': len({feature['properties']['municipality'] for feature in features if feature['properties']['municipality']}),
        'unresolvedPolygonMunicipalities': sum(feature['properties']['municipality'] is None for feature in features)})
    manifest['polygonClassifications'] = dict(Counter(feature['properties']['classificationReason'] for feature in features))
    manifest['associationCorrection'] = {
        'processedAt': datetime.now(timezone.utc).isoformat(), 'script': Path(__file__).name,
        'scriptSha256': extractor.file_hash(Path(__file__)), 'inputManifestSha256': extractor.file_hash(manifest_path),
        'inputOutputs': original_outputs,
        'processing': 'Primary canonical municipality names only; Budapest admin6; exact-equal duplicate outer-way/relation identities canonicalized to relation. Source geometry and construction bytes unchanged.'}
    extractor.write_json(output / 'manifest.json', manifest)
    print(json.dumps(manifest['counts'], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--settlements', type=Path, default=extractor.ROOT / 'dist/data/settlements.json')
    args = parser.parse_args()
    try:
        reassociate(args.input_dir, args.output, args.settlements)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f'Country reassociation failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
