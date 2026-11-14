#!/usr/bin/env python3
"""Package the current selected polygons, import and explicitly separate fallbacks."""
from pathlib import Path
import argparse,hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/neighborhoods'
OUTPUT=ROOT/'downloads/neighborhoods/otthonra-keresheto-varosreszek.zip'
FILES=['search-areas.geojson','search-area-names.json','search-areas-report.csv','search-areas-report.json',
       'search-areas-deduplication.json','search-areas.mysql.sql.gz','search-area-identities.json','search-area-identities.README.md',
       'expansion-20261114/STRATEGY.md','expansion-20261114/WORK-STATE.json','expansion-20261114/technical-validation.json',
       'expansion-20261114/inventory/priority-cities.csv','expansion-20261114/inventory/reference-benchmarks.json',
       'expansion-20261114/inventory/provisional-fallback-features.geojson',
       'expansion-20261114/inventory/provisional-fallback-summary.json']

def contents():
    files={'data/neighborhoods/'+name:(DATA/name).read_bytes() for name in FILES}
    next_state=DATA/'expansion-20261114-next/WORK-STATE.json'
    if next_state.exists():files['data/neighborhoods/expansion-20261114-next/WORK-STATE.json']=next_state.read_bytes()
    files['docs/NEIGHBORHOOD-SEARCH-DATA.md']=(ROOT/'docs/NEIGHBORHOOD-SEARCH-DATA.md').read_bytes()
    report=json.loads(files['data/neighborhoods/search-areas-report.json'])
    note=f'''Otthonra – kereshető városrészek és területek

Kiválasztott poligonok: {report['featureCount']}; települések: {report['municipalityCount']}.
Fő adat: data/neighborhoods/search-areas.geojson (WGS84, hosszúság/szélesség).
Név szerinti lista: data/neighborhoods/search-area-names.json.
MySQL 8 import: data/neighborhoods/search-areas.mysql.sql.gz.

A pontokból képzett tartalékkörök külön fájlban maradnak az inventory könyvtárban.
Nem részei a fő katalógusnak és nem igazolnak térképi lefedettséget.
A különböző nevű szülő- és részterületek szándékosan átfedhetnek.
Az országos teljes városrészszám és az országos lefedettség továbbra sem ismert.

A részletes importálás és módszertan: docs/NEIGHBORHOOD-SEARCH-DATA.md.
Ez az adatcsomag önmagában nem módosítja és nem telepíti az alkalmazást.

A nyers források és a teljes, folytatható munkafolyamat GitHubon:
https://github.com/st-agnes/ingatlan/tree/codex/neighborhood-research-506-191
'''
    files['OLVASS-EL.txt']=note.encode()
    manifest={'schemaVersion':1,'featureCount':report['featureCount'],'municipalityCount':report['municipalityCount'],
              'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(files.items())}}
    files['MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    return files,manifest

def run(check=False):
    files,manifest=contents()
    if check:
        with zipfile.ZipFile(OUTPUT) as archive:
            assert set(archive.namelist())==set(files),'Package file list differs'
            assert archive.testzip() is None,'Corrupt ZIP member'
            for name,raw in files.items():assert archive.read(name)==raw,'Stale package member: '+name
        expected=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()+'  '+OUTPUT.name+'\n'
        assert OUTPUT.with_suffix('.zip.sha256').read_text()==expected,'Package SHA-256 differs'
        return manifest
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,14,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16;archive.writestr(info,raw)
    (OUTPUT.with_suffix('.zip.sha256')).write_text(hashlib.sha256(OUTPUT.read_bytes()).hexdigest()+'  '+OUTPUT.name+'\n')
    run(check=True)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=run(args.check);print(json.dumps({'checked':args.check,'featureCount':result['featureCount'],
        'municipalityCount':result['municipalityCount'],'zipBytes':OUTPUT.stat().st_size}))
