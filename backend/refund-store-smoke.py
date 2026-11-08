"""CI-only MySQL fixture for refund ageing and exactly-once persistence.

Never used by deployment. This requires a disposable GitHub service container,
canonical UUIDs and the fixed CI database/user; it cannot target Cloud SQL.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in ('age', 'record', 'verify'):
    raise SystemExit('Use only as a disposable GitHub CI refund-store check.')
container_id, mode = sys.argv[1:]
if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
    raise SystemExit('Invalid disposable MySQL container ID.')
fixture_path = Path('.local/landing-refund-fixture.json')
fixture = json.loads(fixture_path.read_text())


def uid(value):
    return str(uuid.UUID(value))


def query(sql):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
        'mysql', '--default-character-set=utf8mb4', '--user=otthonra', '--batch', '--skip-column-names',
        'otthonra_ci', '--execute', sql,
    ], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise SystemExit('The disposable MySQL refund-store check failed; credentials and SQL output were not printed.')
    return result.stdout.strip()


def persist():
    fixture_path.write_text(json.dumps(fixture))
    fixture_path.chmod(0o600)


cases = fixture['cases']
assert len(cases) == 9
for name, case in cases.items():
    assert name in ('due', 'timelyPass', 'timelyLike', 'latePass', 'lateLike', 'young', 'freePass', 'agentDue', 'privateFree')
    for field in ('decisionId', 'propertyId', 'searchId'):
        case[field] = uid(case[field])
    assert case['actor'] in ('seller', 'buyer', 'agent')
    assert case['kind'] in ('property', 'search')
    assert case['expected'] in (0, 1, 2)
ids = ','.join("'" + case['decisionId'] + "'" for case in cases.values())
user_ids = {key: uid(value) for key, value in fixture['ids'].items()}
users = ','.join("'" + value + "'" for value in user_ids.values())


def snapshot():
    decisions = query(f"""SELECT Id,ActorUserId,ActorKind,Liked,Charged,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),
COALESCE(DATE_FORMAT(RefundedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL')
FROM Decisions WHERE Id IN ({ids}) ORDER BY Id""")
    charges = query(f"""SELECT Id,UserId,Amount,Description,DecisionId,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')
FROM CreditEntries WHERE DecisionId IN ({ids}) ORDER BY Id""")
    refunds = query(f"""SELECT Id,UserId,Amount,Description,RefundedDecisionId,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')
FROM CreditEntries WHERE RefundedDecisionId IN ({ids}) ORDER BY Id""")
    notifications = query(f"""SELECT Id,UserId,DecisionId,Kind,Amount,Text,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),
COALESCE(DATE_FORMAT(ReadAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL')
FROM UserNotifications WHERE UserId IN ({users}) ORDER BY Id""")
    balances = query(f'SELECT Id,Credits FROM Users WHERE Id IN ({users}) ORDER BY Id')
    return {'decisions': decisions, 'charges': charges, 'refunds': refunds,
            'notifications': notifications, 'balances': balances}


if mode == 'age':
    before = snapshot()
    assert not before['refunds'] and not before['notifications'], 'The new fixture must not already have refunds.'
    # SQL fixture time manipulation remains entirely outside the HTTP API. The
    # public interface has no client clock, ageing endpoint or test-time override.
    statements = ['START TRANSACTION', 'SET @refund_fixture_now=UTC_TIMESTAMP(6)']
    for name, case in cases.items():
        age = 13 if name == 'young' else 15
        statements.append(f"UPDATE Decisions SET CreatedAt=DATE_SUB(@refund_fixture_now,INTERVAL {age} DAY) WHERE Id='{case['decisionId']}'")
        if name in ('timelyPass', 'timelyLike'):
            statements.append(f"""UPDATE Decisions SET CreatedAt=DATE_SUB(@refund_fixture_now,INTERVAL 14 DAY)
WHERE PropertyId='{case['propertyId']}' AND SearchRequestId='{case['searchId']}'
AND ActorKind<>'{case['kind']}'""")
    statements.append('COMMIT')
    query(';'.join(statements))
    fixture['originalCharges'] = before['charges']
    persist()
    print('Refund CI fixture aged: fifteen-day paid/free decisions, thirteen-day pending like, timely and late opposite replies; original charge rows preserved.')
else:
    state = snapshot()
    assert state['charges'] == fixture['originalCharges'], 'Refund processing changed an original credit charge.'
    charges = [line.split('\t') for line in state['charges'].splitlines()]
    assert len(charges) == 7 and sum(int(row[2]) for row in charges) == -13, 'Original paid decisions lost or duplicated their charge.'
    expected = {case['decisionId']: case for case in cases.values() if case['expected']}
    decision_rows = [line.split('\t') for line in state['decisions'].splitlines()]
    assert len(decision_rows) == len(cases)
    decision_map = {uid(row[0]): row for row in decision_rows}
    for case in cases.values():
        row = decision_map[case['decisionId']]
        assert uid(row[1]) == user_ids[case['actor']] and row[2] == case['kind']
        assert (row[6] != 'NULL') == bool(case['expected']), 'The wrong decision was refunded.'
    refunds = [line.split('\t') for line in state['refunds'].splitlines()]
    notifications = [line.split('\t') for line in state['notifications'].splitlines()]
    assert len(refunds) == len(notifications) == len(expected) == 4, 'Missing or duplicate refund/notification rows.'
    assert {uid(row[4]) for row in refunds} == set(expected)
    assert {uid(row[2]) for row in notifications} == set(expected)
    for row in refunds:
        case = expected[uid(row[4])]
        assert uid(row[1]) == user_ids[case['actor']] and int(row[2]) == case['expected']
        assert row[5] == decision_map[case['decisionId']][6], 'Balance marker and ledger were not written at the same refund instant.'
    for row in notifications:
        case = expected[uid(row[2])]
        assert uid(row[1]) == user_ids[case['actor']] and row[3] == 'like_refund' and int(row[4]) == case['expected']
        assert row[6] == decision_map[case['decisionId']][6], 'Notification and refund marker differ.'
    indexes = query("""SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE()
AND TABLE_NAME IN ('CreditEntries','UserNotifications')
GROUP BY TABLE_NAME,INDEX_NAME,NON_UNIQUE ORDER BY TABLE_NAME,INDEX_NAME""")
    unique_columns = {(row[0], row[3]) for row in (line.split('\t') for line in indexes.splitlines()) if row[2] == '0'}
    assert ('CreditEntries', 'DecisionId') in unique_columns, 'The original unique charge key was removed.'
    assert ('CreditEntries', 'RefundedDecisionId') in unique_columns, 'The durable unique refund key is missing.'
    assert ('UserNotifications', 'DecisionId') in unique_columns, 'A refund can produce duplicate notifications.'
    assert query("SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='20261108-public-landing-and-like-refunds'") == '1'
    for report in fixture['reports']:
        report_id, entity_id = uid(report['id']), uid(report['entityId'])
        stored = query(f"SELECT ReporterId,EntityKind,EntityId,Reason,CreatedAt IS NOT NULL FROM UserReports WHERE Id='{report_id}'")
        assert stored.split('\t') == [user_ids['buyer'], report['entityKind'], entity_id, 'no_longer_current', '1'], 'The new report reason/source/UTC time was not persisted.'
    if mode == 'record':
        fixture['storeSnapshot'] = state
        persist()
    else:
        assert state == fixture['storeSnapshot'], 'A restart or repeated catch-up changed durable refund data.'
    print(f'Refund MySQL {mode} passed: exact credits, unique charge/refund/notification keys, common UTC instant, private read state, new report reason and additive schema marker.')
