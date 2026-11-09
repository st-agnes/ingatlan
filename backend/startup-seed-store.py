"""Read-only checks of embedded fixture resets in the disposable CI MySQL database."""
import os
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
        'mysql', '--user=otthonra', '--batch', '--skip-column-names',
        'otthonra_ci', '--execute', sql
    ], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('The disposable MySQL fixture check could not read the test database.')
    return result.stdout.strip()

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
}
values = query('SELECT ' + ','.join(expressions.values())).split('\t')
assert len(values) == len(expressions), 'Unexpected fixture-count result.'
actual = dict(zip(expressions, map(int, values)))
expected = {
    'users': 12, 'agents': 3, 'properties': 354, 'searches': 352,
    'decisions': 3 if phase == 'changed' else 1,
    'matches': 1 if phase == 'changed' else 0,
    'messages': 1 if phase == 'changed' else 0,
    'reports': 1 if phase == 'changed' else 0,
    'credit_entries': 14 if phase == 'changed' else 13,
    'sum_credits': 1197 if phase == 'changed' else 1199,
    'archived_properties': 1 if phase == 'changed' else 0,
    'payment_orders': 0,
}
for name, value in expected.items():
    assert actual[name] == value, f'Incorrect startup fixture {name}: expected {value}, received {actual[name]}.'

history = query('SELECT RevisionId,Version,(AppliedAt IS NOT NULL) FROM __OtthonraTestSeeds ORDER BY RevisionId')
rows = [row.split('\t') for row in history.splitlines()]
expected_revisions = ['ci-fixtures-a'] if phase == 'changed' else ['ci-fixtures-a', 'ci-fixtures-b']
assert [row[0] for row in rows] == expected_revisions, 'Seed history changed or ordinary Production created a marker.'
assert all(len(row) == 3 and row[1] == '20261109-test-fixtures-v3' and row[2] == '1' for row in rows), 'Invalid seed version or timestamp in history.'
print('Embedded fixture database check passed: 12 users, 3 agents, 354 properties, 352 searches; '
      + ('test changes and first revision recorded.' if phase == 'changed' else 'reset results and two-revision history preserved.'))
