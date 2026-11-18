#!/usr/bin/env python3
"""Stream actual nationwide major-road, railway and river/canal OSM way geometry.

Requires osmium==4.1.1. A native key filter runs after node-location caching;
Python never receives the country's untagged nodes or unrelated building ways.
This produces source linework only, not inferred neighbourhood boundaries.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
import tempfile
import time

ROAD_CLASSES = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary'}
ROAD_CLASSES |= {value + '_link' for value in tuple(ROAD_CLASSES)}


def select_barrier(tags, include_streams=False):
    kinds = []
    if tags.get('highway') in ROAD_CLASSES:
        kinds.append('road')
    if tags.get('railway') == 'rail':
        kinds.append('railway')
    if tags.get('waterway') in ({'river', 'canal', 'stream'} if include_streams else {'river', 'canal'}):
        kinds.append('waterway')
    return kinds


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def extract(input_path, output_path, include_streams=False, index_type='sparse_file_array'):
    import osmium
    input_path, output_path = Path(input_path), Path(output_path)
    if output_path.exists():
        raise FileExistsError('Output directory already exists')
    if not input_path.is_file():
        raise ValueError('Input PBF does not exist')
    if index_type not in {'sparse_file_array', 'flex_mem'}:
        raise ValueError('Unsupported node index type')
    pbf_sha = file_hash(input_path)
    acquisition_path = input_path.with_name(input_path.name + '.source.json')
    acquisition = json.loads(acquisition_path.read_text(encoding='utf-8')) if acquisition_path.exists() else None
    if acquisition and (acquisition.get('sha256') != pbf_sha or acquisition.get('bytes') != input_path.stat().st_size):
        raise ValueError('Input PBF differs from its acquisition manifest')
    with osmium.io.Reader(str(input_path), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header = reader.header()
        header_metadata = {key: header.get(key) for key in (
            'generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number',
            'osmosis_replication_base_url') if header.get(key)}
    output_path.mkdir(parents=True)
    temporary_lines = output_path / 'barriers.ndjson.part'
    temporary_audit = output_path / 'audit.ndjson.part'
    stats = Counter({'wayCallbacks': 0, 'selectedWays': 0, 'rejectedWays': 0})
    kind_counts = Counter()
    started = time.monotonic()
    line_sha, audit_sha = hashlib.sha256(), hashlib.sha256()

    def progress(stage):
        print(f'OSM barriers {stage}: {stats["wayCallbacks"]:,} filtered ways; '
              f'{stats["selectedWays"]:,} selected; {stats["rejectedWays"]:,} rejected; '
              f'{time.monotonic() - started:.1f}s', file=sys.stderr, flush=True)

    try:
        with temporary_lines.open('xb') as lines, temporary_audit.open('xb') as audit:
            class Collector(osmium.SimpleHandler):
                # Deliberately no node/area/relation methods: NodeLocationsForWays
                # caches every actual node before the native filter, then only
                # tagged ways reach Python. No building-area assembly is needed.
                def way(self, obj):
                    stats['wayCallbacks'] += 1
                    if stats['wayCallbacks'] % 100_000 == 0:
                        progress('way pass')
                    kinds = select_barrier(obj.tags, include_streams)
                    if not kinds:
                        return
                    tags = dict(obj.tags)
                    source = {'provider': 'openstreetmap', 'osmType': 'way', 'osmId': obj.id,
                              'url': f'https://www.openstreetmap.org/way/{obj.id}',
                              'tags': tags, 'nodeRefs': [node.ref for node in obj.nodes],
                              'objectVersion': obj.version, 'objectTimestamp': str(obj.timestamp),
                              'changeset': obj.changeset, 'pbfSha256': pbf_sha,
                              'osmTimestamp': header_metadata.get('osmosis_replication_timestamp'),
                              'geometryUnmodified': True,
                              'geometryProcessing': 'Actual complete OSM way node sequence; no clipping, snapping, simplification, interpolation, buffering or polygon inference.',
                              'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
                              'attributionUrl': 'https://www.openstreetmap.org/copyright'}
                    try:
                        coordinates = [[node.lon, node.lat] for node in obj.nodes]
                        if len(coordinates) < 2:
                            raise ValueError('source_way_has_fewer_than_two_nodes')
                        if not all(math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90
                                   for lon, lat in coordinates):
                            raise ValueError('invalid_source_node_coordinate')
                        if len({tuple(point) for point in coordinates}) < 2:
                            raise ValueError('degenerate_source_line')
                    except (RuntimeError, ValueError) as exc:
                        stats['rejectedWays'] += 1
                        record = encode({'id': f'osm:way:{obj.id}', 'reason': type(exc).__name__ + ': ' + str(exc)[:120],
                                         'source': source})
                        audit.write(record)
                        audit_sha.update(record)
                        return
                    geometry = {'type': 'LineString', 'coordinates': coordinates}
                    source['geometrySha256'] = hashlib.sha256(encode(geometry).rstrip(b'\n')).hexdigest()
                    feature = {'type': 'Feature', 'id': f'osm:way:{obj.id}',
                               'properties': {'name': (tags.get('name:hu') or tags.get('name') or '').strip(),
                                              'barrierKinds': kinds, 'reviewStatus': 'unreviewed',
                                              'sourceIsOfficial': False, 'source': source}, 'geometry': geometry}
                    record = encode(feature)
                    lines.write(record)
                    line_sha.update(record)
                    stats['selectedWays'] += 1
                    kind_counts.update(kinds)

            print('OSM barriers: native node-location pass started; only highway/railway/waterway ways enter Python.',
                  file=sys.stderr, flush=True)
            with tempfile.TemporaryDirectory(prefix='otthonra-barrier-index-') as temporary:
                index = ('sparse_file_array,' + str(Path(temporary) / 'nodes.idx')) if index_type == 'sparse_file_array' else index_type
                Collector().apply_file(str(input_path), locations=True, idx=index,
                                       filters=[osmium.filter.KeyFilter('highway', 'railway', 'waterway')])
        progress('complete')
        lines_path, audit_path = output_path / 'barriers.ndjson', output_path / 'audit.ndjson'
        temporary_lines.rename(lines_path)
        temporary_audit.rename(audit_path)
        manifest = {
            'version': 1, 'scope': 'entire Geofabrik Hungary PBF; actual source ways only',
            'generatedAt': datetime.now(timezone.utc).isoformat(),
            'input': {'file': input_path.name, 'bytes': input_path.stat().st_size, 'sha256': pbf_sha,
                      'header': header_metadata, 'acquisition': acquisition},
            'dependencies': {'osmium': version('osmium')}, 'nodeIndex': index_type,
            'nativeFilter': 'KeyFilter(highway,railway,waterway) after NodeLocationsForWays; way-only Python handler',
            'selection': {'highway': sorted(ROAD_CLASSES), 'railway': ['rail'],
                          'waterway': ['river', 'canal'] + (['stream'] if include_streams else [])},
            'stats': {**stats, 'barrierKinds': dict(kind_counts)},
            'outputs': [{'file': lines_path.name, 'bytes': lines_path.stat().st_size, 'sha256': line_sha.hexdigest()},
                        {'file': audit_path.name, 'bytes': audit_path.stat().st_size, 'sha256': audit_sha.hexdigest()}],
            'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
            'attributionUrl': 'https://www.openstreetmap.org/copyright',
            'notes': ['No estimated polygons are generated.',
                      'Whole source ways are retained, including ways that cross the extract boundary.',
                      'OSM tags and bridge/tunnel/layer/access metadata are preserved; suitability as a neighbourhood barrier is not assessed.',
                      'NDJSON is streamed; the disk-backed default node index bounds memory use.']}
        (output_path / 'manifest.json').write_bytes(encode(manifest))
    except BaseException:
        temporary_lines.unlink(missing_ok=True)
        temporary_audit.unlink(missing_ok=True)
        # Final files without a success manifest are never a completed dataset.
        raise
    print(json.dumps(manifest['stats'], ensure_ascii=False))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New output directory for streamed NDJSON and manifest')
    parser.add_argument('--include-streams', action='store_true', help='Also retain actual waterway=stream ways')
    parser.add_argument('--index', choices=['sparse_file_array', 'flex_mem'], default='sparse_file_array',
                        help='Disk-backed index by default; flex_mem is opt-in and may use more memory')
    args = parser.parse_args()
    try:
        extract(args.input, args.output, args.include_streams, args.index)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f'Barrier extraction failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
