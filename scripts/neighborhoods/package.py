#!/usr/bin/env python3
"""Package existing neighborhood data and its offline rebuild tools, without fetching or rebuilding."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
ZIP_NAME = 'otthonra-ingyenes-varosreszhatarok.zip'
MANIFEST_NAME = 'SHA256SUMS.txt'
README_NAME = 'README-kezdes.txt'
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
COPIES = {
    'data/neighborhoods/neighborhoods.geojson': 'varosreszhatarok.geojson',
    'data/neighborhoods/nationwide-report.csv': 'varosreszhatarok-lefedettseg.csv',
    'data/neighborhoods/nationwide-report.md': 'varosreszhatarok-hianyok.md',
    'data/neighborhoods/review.html': 'varosreszhatarok-nezegeto.html',
    'data/neighborhoods/planning-units.geojson': 'varosresz-tervezesi-egysegek.geojson',
    'data/neighborhoods/estimated-candidates.geojson': 'varosresz-becsult-jeloltek.geojson',
    'data/neighborhoods/estimated-report.csv': 'varosresz-becsult-statisztika.csv',
}
REQUIRED = [
    'data/neighborhoods/catalog.geojson', 'data/neighborhoods/catalog.geojson.gz',
    'data/neighborhoods/neighborhoods.geojson', 'data/neighborhoods/neighborhoods.geojson.gz',
    'data/neighborhoods/report.json', 'data/neighborhoods/report.csv',
    'data/neighborhoods/report.md', 'data/neighborhoods/review.html',
    'data/neighborhoods/coverage.json', 'docs/NEIGHBORHOOD-DATA.md',
    'dist/data/settlements.json',
    'data/neighborhoods/nationwide-report.json', 'data/neighborhoods/nationwide-report.csv',
    'data/neighborhoods/nationwide-report.md', 'data/neighborhoods/planning-units.geojson',
    'data/neighborhoods/estimated-candidates.geojson',
    'data/neighborhoods/estimated-report.json', 'data/neighborhoods/estimated-report.csv',
]

README = '''OTTHONRA – INGYENES MAGYAR VÁROSRÉSZHATÁROK

Kezdés
------
A ZIP-et bontsd ki egy tetszőleges könyvtárba. A könyvtárszerkezetet tartsd meg.

Egységes határvonalak (GeoJSON, WGS84/EPSG:4326):
  data/neighborhoods/neighborhoods.geojson
  data/neighborhoods/neighborhoods.geojson.gz

Városonkénti statisztikák és hiányok:
  data/neighborhoods/nationwide-report.csv
  data/neighborhoods/nationwide-report.md
  data/neighborhoods/nationwide-report.json

Külön kezelt tágabb tervezési egységek és nem hitelesített becsült jelöltek:
  data/neighborhoods/planning-units.geojson
  data/neighborhoods/estimated-candidates.geojson
  data/neighborhoods/estimated-report.csv
  data/neighborhoods/estimated-report.json

A becsült jelöltek városonkénti statisztikája külön mutatja a geometriai
rekordokat és a forrásneveket. Egy több részből álló alakzat egy rekord;
a történeti alternatívák és tágabb csoportok nem új, igazolt városrészek.

Külön kutatási forrásfelületek (nem városrészhatárok):
  data/neighborhoods/sources/extra-osm-candidates/landuse-proxies.geojson
  data/neighborhoods/sources/public-vector-next/wof-alt/

Az országos leltár 3155 települése nem jelenti az összes városrész ismeretét.
A forrásalapú, a tervezési és a becsült rétegek nem összeadhatók teljes
városrész-lefedettségként; a becslések nem zárják le a hiánylistát.

Önálló, internet nélkül is megnyitható alakzatnézegető:
  data/neighborhoods/review.html

Részletes dokumentáció, módszertan, licencek:
  docs/NEIGHBORHOOD-DATA.md
  data/neighborhoods/sources/

A források, forrásdátumok, névellenőrzések és hiányok megmaradnak az adatok
mellett. Az adatgyűjtemény nem teljes országos városrésznyilvántartás.

Offline újraépítés
-----------------
A kibontott könyvtár gyökerében futtasd. Node.js 22 vagy újabb és Python 3 szükséges;
Git, MySQL, backend, npm-telepítés és hálózati hozzáférés nem szükséges.

  node scripts/neighborhoods/build.mjs
  node scripts/neighborhoods/report.mjs
  node scripts/neighborhoods/export.mjs
  node scripts/neighborhoods/export-secondary.mjs
  node scripts/neighborhoods/nationwide-report.mjs
  python3 scripts/neighborhoods/combined-report.py
  node scripts/neighborhoods/preview.mjs

Ellenőrzés:

  node scripts/neighborhoods/build.mjs --check
  node scripts/neighborhoods/report.mjs --check
  node scripts/neighborhoods/export.mjs --check
  node tests/neighborhoods.test.mjs
  node tests/neighborhoods-osm.test.mjs
  node tests/neighborhoods-national.test.mjs
  node tests/neighborhoods-report.test.mjs
  node tests/neighborhoods-fetch.test.mjs
  node tests/neighborhoods-manual.test.mjs
  node tests/neighborhoods-semantic.test.mjs
  node tests/neighborhoods-country.test.mjs
  node tests/neighborhoods-nationwide-report.test.mjs

Az eredeti budapesti shapefile-ok köztes konverziója külön, Python 3-mal:

  python3 data/neighborhoods/sources/national-osm/convert.py
  python3 data/neighborhoods/sources/national-osm-2025/convert.py

Újracsomagolás Python 3-mal (nem építi újra és nem tölti le az adatokat):

  python3 scripts/neighborhoods/package.py --output csomag

Integritás
----------
A SHA256SUMS.txt a csomag minden más fájljának SHA256-lenyomatát tartalmazza.
Linuxon ellenőrizhető a kibontás után: sha256sum -c SHA256SUMS.txt
macOS-en: shasum -a 256 -c SHA256SUMS.txt
A csomagoló minden ZIP-bejegyzést visszaolvas, ellenőrzi a CRC-t és az SHA256-ot.
A böngészős automatizált teszt külön Playwright-környezetet igényel; az adatok
megtekintéséhez és a fenti offline ellenőrzésekhez nem szükséges.
'''


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def included_files(root):
    paths = []
    for relative in ['data/neighborhoods', 'scripts/neighborhoods']:
        for path in (root/relative).rglob('*'):
            relative_path = path.relative_to(root)
            name = relative_path.as_posix()
            if (any(part in {'__pycache__', '.local', '.git', 'artifacts'} for part in relative_path.parts)
                    or path.suffix in {'.pyc', '.zip'}
                    or name.startswith('data/neighborhoods/sources/budapest/')):
                continue
            if path.is_symlink():
                raise ValueError(f'Symlinks are not package inputs: {name}')
            if path.is_file():
                paths.append(path)
    paths.extend(path for path in (root/'tests').glob('neighborhood*.test.*') if path.is_file())
    paths.extend(root/name for name in ['docs/NEIGHBORHOOD-DATA.md', 'dist/data/settlements.json'])
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())


def stamp(path):
    if path.is_symlink():
        raise ValueError('Package inputs must be ordinary files')
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def snapshot(root):
    # Refuse a mixed read if a collector or builder changes any selected input.
    paths = included_files(root)
    before = {path: stamp(path) for path in paths}
    files = {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}
    if included_files(root) != paths or any(stamp(path) != state for path, state in before.items()):
        raise ValueError('Package inputs changed while reading; rerun after all collectors/builders finish')
    missing = [name for name in REQUIRED if name not in files]
    if missing:
        raise ValueError('Built package inputs are missing: '+', '.join(missing))
    for plain in ['data/neighborhoods/catalog.geojson', 'data/neighborhoods/neighborhoods.geojson']:
        if gzip.decompress(files[plain+'.gz']) != files[plain]:
            raise ValueError(f'Plain/gzip package inputs differ: {plain}')
        document = json.loads(files[plain])
        if document.get('type') != 'FeatureCollection' or not isinstance(document.get('features'), list):
            raise ValueError(f'Invalid built GeoJSON: {plain}')
    files[README_NAME] = README.encode('utf-8')
    manifest = ''.join(f'{sha256(data)}  {name}\n' for name, data in sorted(files.items()))
    files[MANIFEST_NAME] = manifest.encode('utf-8')
    return files


def write_atomic(path, data):
    temporary = path.with_name(path.name+'.part')
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def package(output, root=ROOT):
    output = output.resolve()
    root = root.resolve()
    for selected in ['data', 'scripts', 'tests', 'docs', 'dist']:
        if output == root/selected or (root/selected) in output.parents:
            raise ValueError('Output must be outside the packaged input directories')
    files = snapshot(root)
    output.mkdir(parents=True, exist_ok=True)
    temporary = output/(ZIP_NAME+'.part')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(files):
                raise ValueError('ZIP readback/CRC verification failed')
            for name, data in files.items():
                if sha256(archive.read(name)) != sha256(data):
                    raise ValueError(f'ZIP SHA256 readback mismatch: {name}')
        temporary.replace(output/ZIP_NAME)
    finally:
        temporary.unlink(missing_ok=True)
    for source, destination in COPIES.items():
        write_atomic(output/destination, files[source])
    write_atomic(output/README_NAME, files[README_NAME])
    write_atomic(output/MANIFEST_NAME, files[MANIFEST_NAME])
    archive_data = (output/ZIP_NAME).read_bytes()
    write_atomic(output/(ZIP_NAME+'.sha256'), f'{sha256(archive_data)}  {ZIP_NAME}\n'.encode('ascii'))
    result = {'archive': str(output/ZIP_NAME), 'bytes': len(archive_data),
              'sha256': sha256(archive_data), 'files': len(files), 'crcVerified': True}
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        package(args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f'Packaging failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
