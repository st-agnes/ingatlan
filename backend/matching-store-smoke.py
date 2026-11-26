"""Read-only normalized location-index checks in the disposable CI MySQL database."""
import gzip
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
with gzip.open(ROOT / 'dist/data/neighborhoods.json.gz', 'rt', encoding='utf-8') as runtime:
    assert runtime.readline().strip() == '[', 'Unexpected generated neighborhood runtime format.'
    NEIGHBORHOODS = json.loads(runtime.readline().rstrip(',\r\n'))['areas']
assert len(NEIGHBORHOODS) == 4308, 'The location-index verifier requires the full generated neighborhood catalog.'
with gzip.open(ROOT / 'dist/data/streets.json.gz', 'rt', encoding='utf-8') as runtime:
    assert runtime.readline().strip() == '[', 'Unexpected generated street runtime format.'
    street_header = json.loads(runtime.readline().rstrip(',\r\n'))
    STREET_IDS = set()
    for line in runtime:
        if line.strip() == ']':
            break
        identifier = json.loads(line.rstrip(',\r\n'))['id']
        assert re.fullmatch(r'street:[a-f0-9]{24}', identifier), 'Invalid canonical street identity.'
        assert identifier not in STREET_IDS, 'Duplicate canonical street identity.'
        STREET_IDS.add(identifier)
assert len(STREET_IDS) == street_header['count'] > 100000, 'The location-index verifier requires the full generated postal street catalog.'
KNOWN_IDS = ({'city:' + city for city in SETTLEMENTS}
             | {'district:Budapest:' + str(index) for index in range(1, 24)}
             | {area['id'] for area in AREAS}
             | {area['id'] for area in NEIGHBORHOODS}
             | STREET_IDS)


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

    geography_counts = query(container_id, """
        SELECT
          (SELECT COUNT(*) FROM MatchingLocationAreas WHERE Kind='city'),
          (SELECT COUNT(*) FROM MatchingLocationAreas WHERE Kind='neighborhood'),
          (SELECT COUNT(*) FROM MatchingLocationAreas WHERE Kind='district'),
          (SELECT COUNT(*) FROM MatchingLocationMembers WHERE SelectionId LIKE 'street:%')
        """)
    assert geography_counts == '3155\t4308\t23\t0', \
        'Distance matching requires every original municipality, neighborhood and district boundary, without street proximity anchors.'
    spatial_indexes = query(container_id, """
        SELECT TABLE_NAME,INDEX_NAME,INDEX_TYPE FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA=DATABASE() AND (
          TABLE_NAME='MatchingPropertyPoints' AND INDEX_NAME='SX_MatchingPropertyPoints_Position'
          OR TABLE_NAME='MatchingLocationAreas' AND INDEX_NAME='SX_MatchingLocationAreas_Boundary')
        ORDER BY TABLE_NAME
        """)
    assert spatial_indexes.splitlines() == [
        'MatchingLocationAreas\tSX_MatchingLocationAreas_Boundary\tSPATIAL',
        'MatchingPropertyPoints\tSX_MatchingPropertyPoints_Position\tSPATIAL'
    ], 'Distance matching must retain both property-point and original-boundary spatial indexes.'
    point_consistency = query(container_id, """
        SELECT
          (SELECT COUNT(*) FROM Properties p LEFT JOIN MatchingPropertyPoints g ON g.PropertyId=p.Id
           WHERE p.Latitude IS NOT NULL AND p.Longitude IS NOT NULL AND g.PropertyId IS NULL),
          (SELECT COUNT(*) FROM MatchingPropertyPoints g LEFT JOIN Properties p ON p.Id=g.PropertyId
           WHERE p.Id IS NULL OR p.Latitude IS NULL OR p.Longitude IS NULL
             OR ST_SRID(g.Position)<>4326
             OR ABS(ST_Longitude(g.Position)-p.Longitude)>0.0000000001
             OR ABS(ST_Latitude(g.Position)-p.Latitude)>0.0000000001),
          (SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
           WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='MatchingPropertyPoints'
             AND COLUMN_NAME='PropertyId' AND REFERENCED_TABLE_NAME='Properties')
        """)
    assert point_consistency == '0\t0\t1', \
        'Spatial property points must stay synchronized with authoritative saved coordinates and retain their parent foreign key.'
    # Exercise the actual MySQL 8.0/8.4 geographic point-to-polygon operation.
    # The outside point is close to the eastern edge, far from the center.
    boundary_distance = query(container_id, """
        SELECT
          ST_Distance(ST_GeomFromText('POINT(19.9 47.5)',4326,'axis-order=long-lat'),
            ST_GeomFromText('POLYGON((19 47,20 47,20 48,19 48,19 47))',4326,'axis-order=long-lat')),
          ST_Distance(ST_GeomFromText('POINT(20.1 47.5)',4326,'axis-order=long-lat'),
            ST_GeomFromText('POLYGON((19 47,20 47,20 48,19 48,19 47))',4326,'axis-order=long-lat'))
        """)
    inside, outside = map(float, boundary_distance.split('\t'))
    assert inside == 0 and 7000 < outside < 8000, \
        'Geographic matching must use distance to the selected area, zero inside and about7.5km outside this edge.'
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
