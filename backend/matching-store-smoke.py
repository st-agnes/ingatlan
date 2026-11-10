"""Read-only normalized location-index checks in the disposable CI MySQL database."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
ROMANS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII',
          'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI', 'XXII', 'XXIII']
SETTLEMENTS = json.loads((ROOT / 'dist/data/settlements.json').read_text(encoding='utf-8'))['settlements']
AREAS = json.loads((ROOT / 'dist/data/agglomerations.json').read_text(encoding='utf-8'))['areas']
KNOWN_IDS = ({'city:' + city for city in SETTLEMENTS}
             | {'district:Budapest:' + str(index) for index in range(1, 24)}
             | {area['id'] for area in AREAS})


def normalize(value):
    return ''.join(character for character in unicodedata.normalize('NFD', value or '')
                   if unicodedata.category(character) != 'Mn').upper().strip()


CITIES = {normalize(city): city for city in SETTLEMENTS}
DISTRICTS = {normalize('Budapest ' + roman + '. kerület'): index
             for index, roman in enumerate(ROMANS, 1)}


def strings(value):
    if value is None or not value.strip():
        return []
    parsed = json.loads(value)
    if parsed is None:
        return []
    if not isinstance(parsed, list) or any(item is not None and not isinstance(item, str) for item in parsed):
        raise ValueError('Invalid persisted string-array JSON.')
    return parsed


def district_number(value):
    clean = normalize(value).replace('BUDAPEST', '').replace('KERULET', '').replace('.', '').strip()
    if re.fullmatch(r'[0-9]+', clean):
        number = int(clean)
        return number if 1 <= number <= 23 else None
    return ROMANS.index(clean) + 1 if clean in ROMANS else None


def expected_ids(search):
    """Resolve the same canonical selections/legacy fallback as the source catalog."""
    try:
        explicit = strings(search['locationIdsJson'])
        if explicit:
            if any(item not in KNOWN_IDS for item in explicit):
                return ['@invalid']
            result = sorted(set(explicit))
            return result if 0 < len(result) <= 50 else ['@invalid']
        districts = strings(search['districtsJson'])
        city = normalize(search['city'])
        direct = DISTRICTS.get(city)
        if direct is not None:
            return ['district:Budapest:' + str(direct)]
        if city.startswith('BUDAPEST '):
            number = district_number(city)
            return ['district:Budapest:' + str(number)] if number is not None else ['@invalid']
        canonical = CITIES.get(city)
        if canonical is None:
            return ['@invalid']
        if canonical != 'Budapest':
            return ['city:' + canonical]
        selected = [value for value in districts if value is not None and value.strip()]
        if not selected:
            return ['city:Budapest']
        numbers = [district_number(value) for value in selected]
        if any(number is None for number in numbers):
            return ['@invalid']
        result = sorted({'district:Budapest:' + str(number) for number in numbers})
        return result if 0 < len(result) <= 50 else ['@invalid']
    except (ValueError, TypeError):
        return ['@invalid']


def query(container_id, sql):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
        'mysql', '--user=otthonra', '--default-character-set=utf8mb4', '--raw', '--batch',
        '--skip-column-names', 'otthonra_ci', '--execute', sql
    ], capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode:
        raise SystemExit('The disposable MySQL location-index check could not read the database.')
    return result.stdout.strip()


def main():
    if os.environ.get('CI') != 'true' or len(sys.argv) != 2:
        raise SystemExit('Use only as a disposable GitHub CI location-index check.')
    container_id = sys.argv[1]
    if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
        raise SystemExit('Invalid disposable MySQL container ID.')
    indexes = query(container_id, """
        SELECT INDEX_NAME,COLUMN_NAME,SEQ_IN_INDEX
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='SearchLocations'
        ORDER BY INDEX_NAME,SEQ_IN_INDEX
        """)
    definitions = {}
    for row in indexes.splitlines():
        name, column, position = row.split('\t')
        definitions.setdefault(name, []).append((int(position), column))
    columns = lambda name: [column for _, column in sorted(definitions.get(name, []))]
    assert columns('PRIMARY') == ['SearchRequestId', 'LocationId'], 'Missing or incorrectly ordered composite location primary key.'
    reverse = 'IX_SearchLocations_LocationId_SearchRequestId'
    assert columns(reverse) == ['LocationId', 'SearchRequestId'], 'The reverse-location covering index is unavailable or incorrectly ordered.'
    foreign_keys = query(container_id, """
        SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='SearchLocations'
          AND COLUMN_NAME='SearchRequestId' AND REFERENCED_TABLE_NAME='SearchRequests'
          AND REFERENCED_COLUMN_NAME='Id'
        """)
    assert foreign_keys == '1', 'Location links must retain their search foreign key.'
    invalid_counts = query(container_id, """
        SELECT
          (SELECT COUNT(*) FROM SearchRequests s WHERE NOT EXISTS
             (SELECT 1 FROM SearchLocations l WHERE l.SearchRequestId=s.Id)),
          (SELECT COUNT(*) FROM SearchLocations l LEFT JOIN SearchRequests s
             ON s.Id=l.SearchRequestId WHERE s.Id IS NULL),
          (SELECT COUNT(*) FROM (SELECT SearchRequestId FROM SearchLocations
             GROUP BY SearchRequestId HAVING COUNT(*)>50) excessive)
        """)
    assert invalid_counts == '0\t0\t0', 'Missing, orphaned or excessively expanded location links.'
    searches = query(container_id, """
        SELECT JSON_OBJECT('id',Id,'city',City,'districtsJson',DistrictsJson,'locationIdsJson',LocationIdsJson)
        FROM SearchRequests ORDER BY Id
        """)
    links = query(container_id, """
        SELECT JSON_OBJECT('searchId',SearchRequestId,'locationId',LocationId)
        FROM SearchLocations ORDER BY SearchRequestId,LocationId
        """)
    actual = {}
    for row in links.splitlines():
        value = json.loads(row)
        actual.setdefault(value['searchId'].lower(), []).append(value['locationId'])
    checked = 0
    for row in searches.splitlines():
        search = json.loads(row)
        assert sorted(actual.get(search['id'].lower(), [])) == expected_ids(search), \
            'Indexed locations differ from the canonical persisted selection or legacy fallback.'
        checked += 1

    # Observe the provider's real optimizer decision. A small fixture may make a
    # table scan cheaper; assert index availability above rather than force a plan.
    plan = json.loads(query(container_id, """
        EXPLAIN FORMAT=JSON SELECT DISTINCT SearchRequestId FROM SearchLocations
        WHERE LocationId IN ('city:Solymár','area:Budapest')
        """))
    assert isinstance(plan.get('query_block'), dict), 'MySQL did not return an actual JSON query plan.'
    observed = []

    def visit(value):
        if isinstance(value, dict):
            if 'table_name' in value:
                observed.append({name: value[name] for name in
                                 ['table_name', 'access_type', 'key', 'possible_keys', 'used_key_parts'] if name in value})
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(plan)
    print(f'Location-index database check passed: {checked} canonical search selections; '
          'correct covering-index order, foreign key, no missing/orphaned/expanded links.')
    print('Observed MySQL reverse-location access paths: ' + json.dumps(observed, ensure_ascii=False))


if __name__ == '__main__':
    main()
