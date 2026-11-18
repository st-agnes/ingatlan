#!/usr/bin/env python3
"""Freeze/verify this rejected, reproducible Pécs control experiment only."""
import argparse
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    decision = json.loads((P / 'decision.json').read_text())
    audit = json.loads((P / 'independent-review.json').read_text())
    assert decision['automaticPrimaryApproval'] is False
    assert decision['usableForAddressAssignment'] is False
    assert decision['quarterGeometriesGeneratedOrChanged'] is False
    assert audit
    paths = sorted(p for p in P.iterdir() if p.is_file() and p.name != 'manifest.json')
    record = {
        'schemaVersion': 1,
        'frozenDate': '2026-11-14',
        'scope': 'Rejected five-pair georeferencing experiment and source-link audit; no quarter polygons, first inferred snapshot, primary records or registries changed.',
        'modelStatus': decision['status'],
        'networkUsed': False,
        'primaryRecordsAdded': 0,
        'quarterPolygonCount': 0,
        'absoluteBoundaryAccuracyMetres': None,
        'files': [{'path': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths],
    }
    text = encoded(record)
    if args.check:
        assert (P / 'manifest.json').read_text() == text, 'Frozen file inventory/content changed'
    else:
        (P / 'manifest.json').write_text(text)
    print(json.dumps({'check': args.check, 'files': len(paths), 'primaryRecordsAdded': 0, 'modelStatus': record['modelStatus']}))


if __name__ == '__main__':
    main()
