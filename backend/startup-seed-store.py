"""Read-only checks of embedded fixture resets in the disposable CI MySQL database."""
import os
import json
from pathlib import Path
import re
import subprocess
import sys

if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in ('changed', 'reset'):
    raise SystemExit('Use only as a disposable GitHub CI startup-fixture check.')
container_id, phase = sys.argv[1:]
if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
    raise SystemExit('Invalid disposable container ID.')

def query(sql):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
        'mysql', '--user=otthonra', '--default-character-set=utf8mb4', '--batch', '--skip-column-names',
        'otthonra_ci', '--execute', sql
    ], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('The disposable MySQL fixture check could not read the test database.')
    return result.stdout.strip()

catalog = json.loads((Path(__file__).parent / 'Otthonra.Api' / 'Data' / 'test-fixtures.json').read_text())
fixture_counts = {kind: sum(row['kind'] == kind for row in catalog['fixtures']) for kind in ('property', 'search')}

# Derive the prepared activity graph from the same versioned catalog used at startup.
fixtures = {row['key']: row for row in catalog['fixtures']}
users = {row['key']: row for row in catalog['users']}
scenarios = catalog.get('activityScenarios', [])
seed_decisions = sum(len(row['actors']) for row in scenarios)
seed_matches = sum(len(row['actors']) == 2 for row in scenarios)
seed_messages = sum(bool(row.get(field)) for row in scenarios for field in ('propertyMessage', 'searchMessage'))
costs = [2 if actor == 'property' else int(users[fixtures[row['search']]['owner']].get('accountType') == 'agent')
         for row in scenarios for actor in row['actors']]
seed_charges = sum(costs)
seed_entries = len(users) + len(catalog.get('feedbackScenarios', [])) + sum(cost > 0 for cost in costs)
seed_balance = len(users) * 100 - sum(row['size'] for row in catalog.get('feedbackScenarios', [])) - seed_charges
seed_notices = len(users) + seed_decisions + 2 * seed_matches + seed_messages

expressions = {
    'users': '(SELECT COUNT(*) FROM Users)',
    'agents': "(SELECT COUNT(*) FROM Users WHERE AccountType='agent')",
    'properties': '(SELECT COUNT(*) FROM Properties)',
    'searches': '(SELECT COUNT(*) FROM SearchRequests)',
    'decisions': '(SELECT COUNT(*) FROM Decisions)',
    'matches': '(SELECT COUNT(*) FROM Matches)',
    'messages': '(SELECT COUNT(*) FROM Messages)',
    'reports': '(SELECT COUNT(*) FROM UserReports)',
    'credit_entries': '(SELECT COUNT(*) FROM CreditEntries)',
    'sum_credits': '(SELECT COALESCE(SUM(Credits),0) FROM Users)',
    'archived_properties': '(SELECT COUNT(*) FROM Properties WHERE Archived=1)',
    'payment_orders': '(SELECT COUNT(*) FROM PaymentOrders)',
    'feedback_packages': '(SELECT COUNT(*) FROM FeedbackPackages)',
    'feedback_invitations': '(SELECT COUNT(*) FROM FeedbackInvitations)',
    'feedback_ready_buyers': '(SELECT COUNT(*) FROM Users WHERE FeedbackPassCounter=19)',
    'notifications': '(SELECT COUNT(*) FROM UserNotifications)',
    'read_notifications': '(SELECT COUNT(*) FROM UserNotifications WHERE ReadAt IS NOT NULL)',
}
values = query('SELECT ' + ','.join(expressions.values())).split('\t')
assert len(values) == len(expressions), 'Unexpected fixture-count result.'
actual = dict(zip(expressions, map(int, values)))
expected = {
    'users': 17, 'agents': 4, 'properties': fixture_counts['property'], 'searches': fixture_counts['search'],
    'decisions': seed_decisions + (3 if phase == 'changed' else 1),
    'matches': seed_matches + (1 if phase == 'changed' else 0),
    'messages': seed_messages + (1 if phase == 'changed' else 0),
    'reports': 1 if phase == 'changed' else 0,
    'credit_entries': seed_entries + (2 if phase == 'changed' else 1),
    'sum_credits': seed_balance - (3 if phase == 'changed' else 1),
    'archived_properties': 1 if phase == 'changed' else 0,
    'payment_orders': 0,
    'feedback_packages': 1, 'feedback_invitations': 0, 'feedback_ready_buyers': 1,
    'notifications': seed_notices + (6 if phase == 'changed' else 1),
    # Three prepared seen events plus one explicit first-read action per activity account.
    'read_notifications': sum(len(row['actors']) for row in scenarios if row.get('readIncoming')) + 3,
}
for name, value in expected.items():
    assert actual[name] == value, f'Incorrect startup fixture {name}: expected {value}, received {actual[name]}.'

# Coordinates are synthetic fixture points in their own municipality, never
# Google-validated addresses. Zero quarter memberships are valid where the
# source has no neighborhood coverage (for example Abádszalók).
assert query("SELECT COUNT(*) FROM Properties WHERE (Street='OTTHONRA TEST' OR (StreetId IN ('street:aae22ff8e2d0fa698c0291dc','street:6cd1dbc01d7aec3be234b7ba') AND HouseNumber='99999')) AND HouseNumber<>'' AND Latitude IS NOT NULL AND Longitude IS NOT NULL AND GeocodedAt IS NOT NULL AND GeocodingProvider='synthetic-test-fixture' AND GeocodingQuality='SYNTHETIC' AND GeocodingPlaceId LIKE 'synthetic:%' AND GeocodingAddressKey<>''") == str(fixture_counts['property']), 'Every startup property must carry explicitly synthetic owner-scoped point metadata.'
assert query('SELECT COUNT(*) FROM Properties WHERE StreetId IS NOT NULL') == '2', 'Exactly two dedicated fictional fixture cases must exercise real source streets.'
assert query('SELECT COUNT(*) FROM NeighborhoodSearchAreas') == '4308', 'A fixture reset must preserve the imported search boundaries.'
assert query('SELECT COUNT(*) FROM __OtthonraNeighborhoodDataset WHERE Id=1 AND FeatureCount=4308') == '1', 'A fixture reset must preserve the single dataset marker.'
assert query('SELECT COUNT(*) FROM Properties p WHERE JSON_LENGTH(p.NeighborhoodIdsJson)<>(SELECT COUNT(*) FROM PropertyNeighborhoods pn WHERE pn.PropertyId=p.Id)') == '0', 'Fixture membership JSON and indexed links must remain synchronized.'
for title, included, excluded in [
    ('Teszt · Vénkerti lakás · szintetikus címpont', 'neighborhood:e8c749e1fc0a306c717ad312', 'neighborhood:f22df415c7b5ea79925e8886'),
    ('Teszt · Sestakerti lakás · szintetikus címpont', 'neighborhood:f22df415c7b5ea79925e8886', 'neighborhood:e8c749e1fc0a306c717ad312'),
]:
    positive = query(f"SELECT COUNT(*) FROM Properties p JOIN PropertyNeighborhoods pn ON pn.PropertyId=p.Id WHERE p.Title='{title}' AND pn.NeighborhoodId='{included}'")
    negative = query(f"SELECT COUNT(*) FROM Properties p JOIN PropertyNeighborhoods pn ON pn.PropertyId=p.Id WHERE p.Title='{title}' AND pn.NeighborhoodId='{excluded}'")
    assert positive == '1', f'Seeded positive polygon membership for {title}: expected 1, received {positive}.'
    assert negative == '0', f'Seeded negative polygon membership for {title}: expected 0, received {negative}.'

history = query('SELECT RevisionId,Version,(AppliedAt IS NOT NULL) FROM __OtthonraTestSeeds ORDER BY RevisionId')
rows = [row.split('\t') for row in history.splitlines()]
expected_revisions = ['ci-fixtures-a'] if phase == 'changed' else ['ci-fixtures-a', 'ci-fixtures-b']
assert [row[0] for row in rows] == expected_revisions, 'Seed history changed or ordinary Production created a marker.'
assert all(len(row) == 3 and row[1] == catalog['version'] and row[2] == '1' for row in rows), 'Invalid seed version or timestamp in history.'
print(f"Embedded fixture database check passed: 17 users, 4 agents, {fixture_counts['property']} properties, {fixture_counts['search']} searches; "
      + ('test changes and first revision recorded.' if phase == 'changed' else 'reset results and two-revision history preserved.'))
