"""Postal catalog/import and indexed association checks in disposable CI MySQL only.

record/verify are read-only database checks. stale deliberately clears one
association and its version in the disposable service; after an API restart,
rebuilt proves that backfill changes only StreetId and runs once per version.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local/street-store-fixture.json'
PHASES = ('record', 'verify', 'stale', 'rebuilt')
FIELDS = ('id', 'city', 'district', 'name', 'type', 'streetName', 'label', 'postalCodes', 'aliases')
STREET_INDEX = 'IX_Properties_Archived_Type_StreetId'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def source_catalog():
    expected = {}
    with gzip.open(ROOT / 'dist/data/streets.json.gz', 'rt', encoding='utf-8') as runtime:
        assert runtime.readline().strip() == '[', 'Unexpected generated postal runtime format.'
        header = json.loads(runtime.readline().rstrip(',\r\n'))
        assert header['schemaVersion'] == 1 and re.fullmatch(r'[a-f0-9]{64}', header['datasetVersion'])
        for line in runtime:
            if line.strip() == ']':
                break
            row = json.loads(line.rstrip(',\r\n'))
            identifier = row['id']
            assert re.fullmatch(r'street:[a-f0-9]{24}', identifier) and identifier not in expected
            expected[identifier] = digest([row[field] for field in FIELDS])
    assert len(expected) == header['count'] > 100000, 'The full reviewed postal catalog is required.'
    assert header['stats']['unmappedSourceRows'] == 0 and header['stats']['coveredMunicipalities'] == 3155
    return header, expected


def query(container, statement, stage='postal query'):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container,
        'mysql', '--user=otthonra', '--default-character-set=utf8mb4', '--raw', '--batch',
        '--skip-column-names', 'otthonra_ci', '--execute', statement
    ], capture_output=True, text=True, encoding='utf-8', timeout=45)
    if result.returncode:
        # A bounded code and stage identify SQL failures without printing the
        # command, connection details, or any returned fixture address values.
        error = re.search(r'ERROR ([0-9]{4,5})(?: \(([A-Z0-9]{5})\))?', result.stderr)
        code = ('MySQL ' + error.group(1) + (('/' + error.group(2)) if error.group(2) else '')) if error else 'command failure'
        statement_id = hashlib.sha256(statement.encode('utf-8')).hexdigest()[:12]
        raise SystemExit(f'The disposable MySQL {stage} failed ({code}; statement {statement_id}).')
    return result.stdout.strip()


def markers(container, header):
    dataset = query(container, 'SELECT DatasetVersion,StreetCount,ImportedAt FROM __OtthonraStreetDataset WHERE Id=1', 'dataset marker').split('\t')
    association = query(container, 'SELECT DatasetVersion,ReclassifiedAt FROM __OtthonraStreetAssociation WHERE Id=1', 'association marker').split('\t')
    assert len(dataset) == 3 and dataset[0] == header['datasetVersion'] and int(dataset[1]) == header['count'] and dataset[2]
    assert len(association) == 2 and association[0] == header['datasetVersion'] and association[1]
    assert query(container, 'SELECT (SELECT COUNT(*) FROM __OtthonraStreetDataset),(SELECT COUNT(*) FROM __OtthonraStreetAssociation)') == '1\t1'
    return {'dataset': dataset, 'association': association}


def catalog(container, expected):
    # Stream the source file, retaining only one digest per identity. Read native
    # JSON values back so every imported field, including aliases/postcodes, is
    # checked against the reviewed source rather than only checking a row count.
    native = query(container, 'SELECT JSON_ARRAY(Id,City,District,Name,Type,StreetName,Label,PostalCodes,Aliases) FROM StreetCatalog ORDER BY Id', 'catalog metadata')
    seen = set()
    for line in native.splitlines():
        row = json.loads(line)
        identifier = row[0]
        assert identifier in expected and identifier not in seen, 'Native catalog has an unknown or duplicate identity.'
        assert digest(row) == expected[identifier], 'Native catalog metadata differs from the reviewed source.'
        seen.add(identifier)
    assert seen == expected.keys(), 'The native postal catalog is incomplete.'


def definitions(container, table):
    assert table in ('Properties', 'SearchLocations', 'StreetCatalog')
    rows = query(container, "SELECT INDEX_NAME,COLUMN_NAME,SEQ_IN_INDEX FROM information_schema.STATISTICS "
                 f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}' ORDER BY INDEX_NAME,SEQ_IN_INDEX", 'index definition')
    indexes = {}
    for row in rows.splitlines():
        name, column, position = row.split('\t')
        indexes.setdefault(name, []).append((int(position), column))
    return {name: [column for _, column in sorted(columns)] for name, columns in indexes.items()}


def tables_in_plan(value):
    if isinstance(value, dict):
        if 'table_name' in value:
            yield value
        for child in value.values():
            yield from tables_in_plan(child)
    elif isinstance(value, list):
        for child in value:
            yield from tables_in_plan(child)


def indexed_associations(container, expected):
    indexes = definitions(container, 'Properties')
    assert indexes.get(STREET_INDEX) == ['Archived', 'Type', 'StreetId'], 'Missing or incorrectly ordered property street index.'
    reverse = 'IX_SearchLocations_LocationId_SearchRequestId'
    assert definitions(container, 'SearchLocations').get(reverse) == ['LocationId', 'SearchRequestId']
    assert definitions(container, 'StreetCatalog').get('IX_StreetCatalog_CityDistrict') == ['City', 'District']
    column = query(container, "SELECT DATA_TYPE,IS_NULLABLE,CHARACTER_MAXIMUM_LENGTH,CHARACTER_SET_NAME,COLLATION_NAME "
                   "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='Properties' AND COLUMN_NAME='StreetId'").split('\t')
    assert column == ['varchar', 'YES', '64', 'ascii', 'ascii_bin'], 'Property street association must remain nullable and case-exact.'
    unknown = query(container, 'SELECT COUNT(*) FROM Properties p LEFT JOIN StreetCatalog s ON s.Id=p.StreetId WHERE p.StreetId IS NOT NULL AND s.Id IS NULL')
    assert unknown == '0', 'An associated property refers to an unknown postal identity.'
    mismatch = query(container, """
        SELECT COUNT(*) FROM Properties p JOIN StreetCatalog s ON s.Id=p.StreetId
        WHERE CAST(p.City AS BINARY)<>CAST(s.City AS BINARY)
          OR (p.District<>'' AND (s.District IS NULL OR CAST(p.District AS BINARY)<>CAST(s.District AS BINARY)))
          OR (p.PostalCode<>'' AND NOT JSON_CONTAINS(s.PostalCodes,JSON_QUOTE(p.PostalCode)))
          OR (p.LocationId LIKE 'city:%' AND CAST(p.LocationId AS BINARY)<>CAST(CONCAT('city:',s.City) AS BINARY))
          OR (p.LocationId LIKE 'district:Budapest:%' AND
             (s.City<>'Budapest' OR s.District IS NULL OR CAST(p.LocationId AS BINARY)<>CAST(CONCAT('district:Budapest:',
              FIELD(s.District,'I.','II.','III.','IV.','V.','VI.','VII.','VIII.','IX.','X.','XI.','XII.',
                    'XIII.','XIV.','XV.','XVI.','XVII.','XVIII.','XIX.','XX.','XXI.','XXII.','XXIII.')) AS BINARY)))
        """, 'association scope')
    assert mismatch == '0', 'An association escaped its canonical city, district or postal scope.'
    sample = next(iter(expected))
    assert re.fullmatch(r'street:[a-f0-9]{24}', sample)
    observed = []
    for statement, name, parts in [
        (f"SELECT Id FROM Properties FORCE INDEX ({STREET_INDEX}) WHERE Archived=0 AND Type='Lakás' AND StreetId='{sample}'",
         STREET_INDEX, ['Archived', 'Type', 'StreetId']),
        (f"SELECT SearchRequestId FROM SearchLocations FORCE INDEX ({reverse}) WHERE LocationId='{sample}'",
         reverse, ['LocationId'])
    ]:
        plan = json.loads(query(container, 'EXPLAIN FORMAT=JSON ' + statement, 'covering index explain'))
        tables = list(tables_in_plan(plan))
        assert len(tables) == 1 and tables[0].get('key') == name, 'The exact street predicate cannot use its covering index.'
        assert tables[0].get('used_key_parts') == parts, 'The exact street predicate did not bind the expected index prefix.'
        assert tables[0].get('access_type') in ('const', 'ref', 'range'), 'A street predicate required a full city/table scan.'
        observed.append({key: tables[0][key] for key in ('table_name', 'access_type', 'key', 'used_key_parts')})
    return observed


def protected_signature(container, identifier):
    assert re.fullmatch(r'[a-f0-9-]{36}', identifier)
    columns = ('City', 'District', 'LocationId', 'Neighborhood', 'Address', 'Street', 'HouseNumber', 'PostalCode',
               'Latitude', 'Longitude', 'GeocodedAt', 'GeocodingProvider', 'GeocodingPlaceId', 'GeocodingQuality',
               'GeocodingAddressKey', 'NeighborhoodIdsJson')
    address = query(container, 'SELECT SHA2(CAST(JSON_ARRAY(' + ','.join(columns) + ") AS CHAR),256) FROM Properties WHERE Id='" + identifier + "'")
    links = query(container, "SELECT NeighborhoodId FROM PropertyNeighborhoods WHERE PropertyId='" + identifier + "' ORDER BY NeighborhoodId")
    assert re.fullmatch(r'[a-f0-9]{64}', address), 'The stale association fixture disappeared.'
    return {'address': address, 'neighborhoodLinks': links}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    STATE.chmod(0o600)


def main():
    if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in PHASES:
        raise SystemExit('Use only as a disposable GitHub CI postal street check: CONTAINER record|verify|stale|rebuilt.')
    container, phase = sys.argv[1:]
    if not re.fullmatch(r'[a-f0-9]{12,64}', container):
        raise SystemExit('Invalid disposable MySQL container ID.')
    header, expected = source_catalog()
    if phase == 'stale':
        state = json.loads(STATE.read_text(encoding='utf-8'))
        assert markers(container, header) == state['markers'], 'Only a current, recorded association version may be made stale.'
        selected = query(container, "SELECT Id,StreetId FROM Properties WHERE StreetId IS NOT NULL ORDER BY Id LIMIT 1").split('\t')
        assert len(selected) == 2 and re.fullmatch(r'[a-f0-9-]{36}', selected[0]) and selected[1] in expected, 'Seed a canonical street property before exercising association backfill.'
        state['stale'] = {'id': selected[0], 'streetId': selected[1], 'protected': protected_signature(container, selected[0])}
        save(state)
        query(container, "START TRANSACTION; UPDATE Properties SET StreetId=NULL WHERE Id='" + selected[0]
              + "'; UPDATE __OtthonraStreetAssociation SET DatasetVersion='" + '0' * 64 + "' WHERE Id=1; COMMIT")
        print('Prepared one stale postal association in the disposable CI database.')
        return

    current = markers(container, header)
    catalog(container, expected)
    observed = indexed_associations(container, expected)
    if phase == 'record':
        save({'markers': current})
    else:
        state = json.loads(STATE.read_text(encoding='utf-8'))
        assert current['dataset'] == state['markers']['dataset'], 'Restart or fixture reset reimported the unchanged postal catalog.'
        if phase == 'rebuilt':
            stale = state['stale']
            actual = query(container, "SELECT StreetId FROM Properties WHERE Id='" + stale['id'] + "'")
            assert actual == stale['streetId'], 'Versioned address backfill did not restore the unique canonical street.'
            assert protected_signature(container, stale['id']) == stale['protected'], 'Street backfill changed address, coordinates, geocoder data or neighborhood memberships.'
            assert current['association'] != state['markers']['association'], 'Stale association version did not complete a new backfill pass.'
            state['markers'] = current
            del state['stale']
            save(state)
        else:
            assert current == state['markers'], 'A current catalog/association version must preserve import and backfill timestamps.'
    print(f'Postal MySQL {phase} passed: {header["count"]} exact source rows, preserved catalog/version markers, scoped nullable associations and covering street indexes.')
    print('Observed MySQL exact street access paths: ' + json.dumps(observed, ensure_ascii=False))


if __name__ == '__main__':
    main()
