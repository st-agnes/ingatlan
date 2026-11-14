#!/usr/bin/env python3
"""Reproduce core outputs in a temporary isolated tree; leave source files intact."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUTPUTS = ['source-map-p25-xref365.jpeg', 'source-pixel-contours.geojson',
           'petofi-cap-alternative-source-pixels.geojson', 'source-segmentation.npz',
           'petofi-cap-evidence.json', 'source-facts.json', 'source-extraction-proof.json',
           'source-contours-preview.png', 'petofi-label-gap-preview.png',
           'road-registration.json', 'kiskunfelegyhaza-inferred-import.geojson',
           'outlying-world-scouts.geojson', 'placement-similarity-alternative.geojson',
           'petofi-contour-alternative-world.geojson', 'name-and-model-diagnostics.json',
           'inferred-registry-entry.json', 'registration-road-overlay.png']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix='kiskun-reproduction-') as temporary:
    task_root = Path(temporary)
    target = task_root / HERE.relative_to(ROOT)
    target.mkdir(parents=True)
    pdf = task_root / '.local/neighborhoods/next-towns/kiskunfelegyhaza-its2016.pdf'
    pdf.parent.mkdir(parents=True)
    pdf.symlink_to(ROOT / '.local/neighborhoods/next-towns/kiskunfelegyhaza-its2016.pdf')
    for name in ['extract-source.py', 'register.py', 'source-road-rail-reference.geojson',
                 'source-name-points.geojson']:
        shutil.copy2(HERE / name, target / name)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / '.local/geodata')
    for name in ['extract-source.py', 'register.py']:
        subprocess.run([sys.executable, str(target / name)], cwd=task_root,
                       env=env, check=True, capture_output=True, text=True)
    checks = [{'path': name, 'frozenSha256': sha(HERE / name),
               'reproducedSha256': sha(target / name),
               'byteIdentical': sha(HERE / name) == sha(target / name)} for name in OUTPUTS]
    assert all(c['byteIdentical'] for c in checks)
    report = {'schemaVersion': 1, 'status': 'PASS', 'outputsCompared': len(checks),
              'allByteIdentical': True, 'temporaryTreeUsed': True,
              'sourcePacketOrGlobalOutputsRewritten': False, 'checks': checks}
if '--write-report' in sys.argv:
    (HERE / 'reproduction-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
