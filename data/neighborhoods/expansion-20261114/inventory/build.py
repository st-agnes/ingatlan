#!/usr/bin/env python3
"""Known-name worklist; these counts are deliberately not a nationwide denominator."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'data/neighborhoods'
OUT = Path(__file__).resolve().parent
PRIORITY = ['Budapest','Debrecen','Szeged','Miskolc','Pécs','Győr','Nyíregyháza',
 'Kecskemét','Székesfehérvár','Szombathely','Szolnok','Érd','Tatabánya','Sopron',
 'Kaposvár','Veszprém','Békéscsaba','Zalaegerszeg','Eger','Nagykanizsa','Dunaújváros',
 'Hódmezővásárhely','Dunakeszi','Szigetszentmiklós','Cegléd','Baja','Salgótarján',
 'Ózd','Vác','Gödöllő','Szekszárd','Hajdúböszörmény','Pápa','Budaörs','Gyula',
 'Kiskunfélegyháza','Esztergom','Ajka','Orosháza','Szentes']

def key(s):
    # Accents matter. Only case, whitespace and punctuation variants collapse.
    return ''.join(c for c in unicodedata.normalize('NFC', str(s)).casefold() if c.isalnum())

def load(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)

def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--catalog',type=Path,help='Optional final deduplicated application catalogue')
    args=ap.parse_args()
    inv=load(BASE/'nationwide-inventory.json')
    municipalities={r['municipality']:r for r in inv['municipalities']}
    points=load(BASE/'sources/country-osm/named-nodes.geojson.gz')['features']
    names={}
    files=[args.catalog] if args.catalog else [BASE/'neighborhoods.geojson',BASE/'estimated-candidates.geojson',BASE/'planning-units.geojson']
    geometries=[(path,f) for path in files for f in load(path)['features']]
    alias_targets={}
    canonical_keys=set()
    for path,f in geometries:
        p=f['properties']; city=p.get('municipality'); name=p.get('name')
        if city not in municipalities or not name: continue
        canonical_keys.add((city,key(name)))
        for alias in [name]+p.get('aliases',[]):
            if isinstance(alias,str): alias_targets.setdefault((city,key(alias)),set()).add(name)

    def ensure(city,name):
        if city not in municipalities or not name or not key(name): return None
        original_name=name
        targets=alias_targets.get((city,key(name)),set())
        if (city,key(name)) not in canonical_keys and len(targets)==1:
            name=next(iter(targets))
        k=(city,key(name))
        if k not in names:
            names[k]={'municipality':city,'name':name,'nameKey':key(name),
              'sourceNames':[],'pointCandidates':[],'nameReferences':[],
              'collectedGeometries':[]}
        row=names[k]
        for source_name in [name,original_name]:
            if source_name not in row['sourceNames']: row['sourceNames'].append(source_name)
        return row

    for p in points:
        a=p['properties']; row=ensure(a.get('municipality'),a.get('name'))
        if row is None: continue
        row['pointCandidates'].append({'sourceId':p.get('id'),
          'coordinates':p['geometry']['coordinates'],'placeKind':a['place'],
          'sourceUrl':a['source']['url'],'snapshotDate':a['source'].get('osmTimestamp')})
        # OSM alt_name and old_name aid dedup/search but do not invent new areas.
        for field in ['alt_name','short_name','official_name','name:hu']:
            for alias in a['source'].get('tags',{}).get(field,'').split(';'):
                alias=alias.strip()
                if alias and alias not in row['sourceNames']: row['sourceNames'].append(alias)

    for city,meta in municipalities.items():
        for ref in meta.get('nameReferences',[]):
            for name in ref.get('names',[]):
                row=ensure(city,name)
                if row is None: continue
                row['nameReferences'].append({'sourceId':ref.get('id'),'sourceUrl':ref.get('sourceUrl'),
                  'title':ref.get('title'),'category':ref.get('category'),
                  'referencePeriod':ref.get('referencePeriod'),
                  'completeForReferencePeriod':ref.get('completeForReferencePeriod',False),
                  'currentCompletenessVerified':ref.get('currentCompletenessVerified',False)})

    for path,f in geometries:
        p=f['properties']; row=ensure(p.get('municipality'),p.get('name'))
        if row is None: continue
        for alias in p.get('aliases',[]):
            if isinstance(alias,str) and alias not in row['sourceNames']: row['sourceNames'].append(alias)
        row['collectedGeometries'].append({'sourceId':f.get('id',p.get('id')),
          'sourceFile':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
          'method':p.get('method',p.get('source',{}).get('method')),
          'estimated':p.get('estimated',False)})

    ordered=sorted(names.values(),key=lambda r:(r['municipality'],r['nameKey']))
    for row in ordered:
        row['hasCollectedPolygon']=bool(row['collectedGeometries'])
        row['hasKnownPoint']=bool(row['pointCandidates'])
        row['nextAction']='collected' if row['hasCollectedPolygon'] else 'find_map_or_polygon_before_radius_fallback' if row['hasKnownPoint'] else 'find_boundary_or_location'
    groups=collections.defaultdict(list)
    for r in ordered: groups[r['municipality']].append(r)
    def summary(city):
        rows=groups[city]; refnames=[r for r in rows if r['nameReferences']]
        return {'municipality':city,'county':municipalities[city]['county'],
          'knownNameCount':len(rows),'namesWithCollectedPolygon':sum(r['hasCollectedPolygon'] for r in rows),
          'namesWithPointOnly':sum(r['hasKnownPoint'] and not r['hasCollectedPolygon'] for r in rows),
          'namesWithoutPointOrPolygon':sum(not r['hasKnownPoint'] and not r['hasCollectedPolygon'] for r in rows),
          'referenceNameCount':len(refnames),
          'referenceNamesWithCollectedPolygon':sum(r['hasCollectedPolygon'] for r in refnames),
          'knownNameCoveragePercent':round(sum(r['hasCollectedPolygon'] for r in rows)/len(rows)*100,1) if rows else None,
          'completeCityCoverageEstablished':False,
          'missingNames':[r['name'] for r in rows if not r['hasCollectedPolygon']]}
    priority=[summary(c) for c in PRIORITY]
    global_summary={'knownNameCount':len(ordered),'municipalitiesWithKnownNames':len(groups),
      'namesWithCollectedPolygon':sum(r['hasCollectedPolygon'] for r in ordered),
      'namesWithKnownPoint':sum(r['hasKnownPoint'] for r in ordered),
      'pointOnlyNames':sum(r['hasKnownPoint'] and not r['hasCollectedPolygon'] for r in ordered),
      'unlocatedUncollectedNames':sum(not r['hasKnownPoint'] and not r['hasCollectedPolygon'] for r in ordered),
      'nationalCompletionPercent':None,'targetNationalCoveragePercent':[80,90]}
    note=('Worklist of currently known names from OSM suburb/neighbourhood/quarter points, municipal reference lists and collected polygons. '
      'Name coverage measures this finite worklist only. It is not a count of every Hungarian neighbourhood, '
      'and neither point-only names nor urban planning groups establish official neighbourhood boundaries. '
      'Names, aliases, historical schemes and overlapping areas are retained under the user-authorized broad search-area policy. '
      'No point was converted into a circle by this script.')
    inputs=['nationwide-inventory.json','sources/country-osm/named-nodes.geojson.gz']
    metadata={'schemaVersion':1,'date':'2026-11-14','scope':note,'summary':global_summary,
       'inputs':{s:hashlib.sha256((BASE/s).read_bytes()).hexdigest() for s in inputs},
       'geometryInputs':[str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p) for p in files]}
    reference_benchmarks=[]
    covered_keys={(r['municipality'],r['nameKey']) for r in ordered if r['hasCollectedPolygon']}
    for city,meta in municipalities.items():
        for ref in meta.get('nameReferences',[]):
            raw_names=ref.get('names',[]); ref_names={key(n):n for n in raw_names}
            def represented(n):
                targets=alias_targets.get((city,key(n)),set())
                return (city,key(n)) in covered_keys or any((city,key(t)) in covered_keys for t in targets)
            missing=[n for k,n in sorted(ref_names.items()) if not represented(n)]
            identities=ref.get('identities',[])
            reference_benchmarks.append({'municipality':city,'sourceId':ref.get('id'),
              'title':ref.get('title'),'sourceUrl':ref.get('sourceUrl'),'category':ref.get('category'),
              'referencePeriod':ref.get('referencePeriod'),
              'completeForReferencePeriod':ref.get('completeForReferencePeriod',False),
              'currentCompleteCityReferenceEstablished':bool(ref.get('sourceIsOfficial') and ref.get('currentCompletenessVerified') and ref.get('completeForReferencePeriod') and ref.get('category')=='urban_neighborhood'),
              'sourceNameEntries':len(raw_names),'distinctNameKeys':len(ref_names),
              'sourceIdentityCount':len(identities) if identities else None,
              'namesWithCollectedPolygon':len(ref_names)-len(missing),'missingNames':missing,
              'knownReferenceNameCoveragePercent':round((len(ref_names)-len(missing))/len(ref_names)*100,1) if ref_names else None,
              'allSourceIdentitiesCovered':None,
              'note':'Name/alias coverage only. Same literal name may denote distinct district-qualified identities; historical/planning references are useful alternate search-area schemes, not a current-city-completeness assertion.'})
    dump(OUT/'known-names.json',{**metadata,'names':ordered})
    dump(OUT/'priority-cities.json',{**metadata,'cities':priority})
    dump(OUT/'municipality-backlog.json',{**metadata,'municipalities':[summary(c) for c in sorted(groups)]})
    dump(OUT/'reference-benchmarks.json',{**metadata,'references':reference_benchmarks})
    with (OUT/'priority-cities.csv').open('w',newline='') as fh:
        fields=['municipality','knownNameCount','namesWithCollectedPolygon','namesWithPointOnly','namesWithoutPointOrPolygon','referenceNameCount','referenceNamesWithCollectedPolygon','knownNameCoveragePercent','missingNames']
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction='ignore'); w.writeheader()
        for c in priority: w.writerow({**c,'missingNames':' | '.join(c['missingNames'])})
    print(json.dumps(global_summary,ensure_ascii=False))

if __name__=='__main__': main()
