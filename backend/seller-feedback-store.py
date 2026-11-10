"""Disposable-CI-only feedback fixtures and persisted financial invariants.

The script accepts only a local Docker service ID, fixed CI MySQL database and
private fixture files. It is never part of deployment and cannot target Cloud SQL.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

MODES = ('legacy-notification', 'upgraded-notification', 'prime', 'capacity', 'age', 'record', 'verify')
if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in MODES:
    raise SystemExit('Use only as a disposable GitHub CI seller-feedback store check.')
container_id, mode = sys.argv[1:]
if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
    raise SystemExit('Invalid disposable MySQL container ID.')
fixture_path = Path('.local/seller-feedback-fixture.json')
legacy_path = Path('.local/seller-feedback-notification-upgrade.json')


def uid(value):
    return str(uuid.UUID(value))


def query(sql):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
        'mysql', '--default-character-set=utf8mb4', '--user=otthonra', '--batch', '--raw', '--skip-column-names',
        'otthonra_ci', '--execute', sql,
    ], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise SystemExit('The disposable MySQL seller-feedback check failed; SQL, credentials and raw database output were not printed.')
    return result.stdout.strip()


def persist(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    path.chmod(0o600)


def literal(value):
    # Fixture text is generated locally; escape as SQL data, never identifiers.
    return "'" + str(value).replace('\\', '\\\\').replace("'", "''") + "'"


def notification_row(notification_id):
    return query(f"""SELECT Id,UserId,DecisionId,Kind,Amount,Text,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),COALESCE(DATE_FORMAT(ReadAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL')
FROM UserNotifications WHERE Id='{uid(notification_id)}'""")


if mode == 'legacy-notification':
    # The API is stopped by CI before altering this owned disposable table.
    assert query('SELECT COUNT(*) FROM FeedbackPackages') == '0', 'Legacy fixture must precede feedback package creation.'
    assert query('SELECT COUNT(*) FROM UserNotifications WHERE DecisionId IS NULL') == '0'
    row = query('SELECT Id,ActorUserId FROM Decisions ORDER BY CreatedAt,Id LIMIT 1').split('\t')
    assert len(row) == 2
    decision_id, user_id = map(uid, row)
    notification_id = str(uuid.uuid4())
    query("""ALTER TABLE UserNotifications DROP FOREIGN KEY FK_UserNotifications_FeedbackPackages_FeedbackPackageId;
ALTER TABLE UserNotifications DROP INDEX IX_UserNotifications_FeedbackPackageId;
ALTER TABLE UserNotifications DROP COLUMN FeedbackPackageId;
ALTER TABLE UserNotifications DROP FOREIGN KEY FK_UserNotifications_Decisions_DecisionId;
ALTER TABLE UserNotifications MODIFY COLUMN DecisionId char(36) COLLATE ascii_general_ci NOT NULL;
ALTER TABLE UserNotifications ADD CONSTRAINT FK_UserNotifications_Decisions_DecisionId FOREIGN KEY (DecisionId) REFERENCES Decisions(Id) ON DELETE RESTRICT;
DELETE FROM __OtthonraSchemaVersions WHERE Version='20261110-seller-feedback-and-insights';""")
    query(f"""INSERT INTO UserNotifications(Id,UserId,DecisionId,Kind,Amount,Text,CreatedAt,ReadAt)
VALUES('{notification_id}','{user_id}','{decision_id}','migration_fixture',0,'Legacy notification preservation',UTC_TIMESTAMP(6),NULL)""")
    persist(legacy_path, {'id': notification_id, 'row': notification_row(notification_id)})
    assert query("SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND COLUMN_NAME='DecisionId'") == 'NO'
    print('Legacy notification fixture prepared: original non-null DecisionId schema, real decision foreign key and one immutable notification receipt.')
    raise SystemExit(0)

if mode == 'upgraded-notification':
    fixture = json.loads(legacy_path.read_text())
    assert query("SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND COLUMN_NAME='DecisionId'") == 'YES'
    assert query("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND COLUMN_NAME='FeedbackPackageId'") == '1'
    assert query("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND CONSTRAINT_NAME='FK_UserNotifications_Decisions_DecisionId' AND CONSTRAINT_TYPE='FOREIGN KEY'") == '1'
    assert query("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND CONSTRAINT_NAME='FK_UserNotifications_FeedbackPackages_FeedbackPackageId' AND CONSTRAINT_TYPE='FOREIGN KEY'") == '1'
    assert notification_row(fixture['id']) == fixture['row'], 'Additive notification upgrade changed an original receipt.'
    assert query("SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='20261110-seller-feedback-and-insights'") == '1'
    query(f"DELETE FROM UserNotifications WHERE Id='{uid(fixture['id'])}' AND Kind='migration_fixture'")
    print('Legacy notification upgrade passed: nullable decision link, package link, both foreign keys and original notification fields/timestamp preserved.')
    raise SystemExit(0)

fixture = json.loads(fixture_path.read_text())
users = {key: uid(value) for key, value in fixture['ids'].items()}
packages = {key: uid(value['id']) for key, value in fixture['packages'].items()}
properties = {key: uid(value['id']) for key, value in fixture['properties'].items()}


def rows(table, columns, where, order='Id'):
    return query(f'SELECT {columns} FROM `{table}` WHERE {where} ORDER BY {order}')


def snapshot():
    package_ids = ','.join(literal(value) for value in packages.values())
    if fixture.get('newMainPackage'):
        package_ids += ',' + literal(uid(fixture['newMainPackage']['id']))
    owner_ids = ','.join(literal(value) for value in users.values())
    return {
        'packages': rows('FeedbackPackages', "Id,PropertyId,OwnerId,RequestId,Size,ReceivedCount,Enabled,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),DATE_FORMAT(ExpiresAt,'%Y-%m-%dT%H:%i:%s.%fZ'),COALESCE(DATE_FORMAT(RefundedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL'),RefundedCredits", f'Id IN ({package_ids})'),
        'answers': rows('FeedbackInvitations', "Id,PackageId,PropertyId,BuyerId,DecisionId,Reason,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),DATE_FORMAT(ExpiresAt,'%Y-%m-%dT%H:%i:%s.%fZ'),COALESCE(DATE_FORMAT(AnsweredAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL')", f'PackageId IN ({package_ids})'),
        'charges': rows('CreditEntries', "Id,UserId,Amount,FeedbackPackageId,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')", f'FeedbackPackageId IN ({package_ids})'),
        'refunds': rows('CreditEntries', "Id,UserId,Amount,RefundedFeedbackPackageId,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')", f'RefundedFeedbackPackageId IN ({package_ids})'),
        'notifications': rows('UserNotifications', "Id,UserId,FeedbackPackageId,DecisionId,Kind,Amount,Text,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ'),COALESCE(DATE_FORMAT(ReadAt,'%Y-%m-%dT%H:%i:%s.%fZ'),'NULL')", f'FeedbackPackageId IN ({package_ids})'),
        'balances': rows('Users', 'Id,Credits', f'Id IN ({owner_ids})'),
        'impressions': rows('PropertyImpressions', "Id,PropertyId,ViewerUserId,SearchRequestId,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')", f"PropertyId='{properties['main']}'"),
    }


if mode == 'prime':
    assert query(f"SELECT FeedbackPassCounter FROM Users WHERE Id='{users['buyer']}'").isdigit()
    query(f"UPDATE Users SET FeedbackPassCounter=19 WHERE Id='{users['buyer']}'")
    # Required account/index relationships exist before exercising the service.
    for table, index in [('PropertyImpressions', 'IX_PropertyImpressions_PropertyId_ViewerUserId'), ('FeedbackInvitations', 'IX_FeedbackInvitations_PackageId_BuyerId')]:
        result = query(f"SELECT NON_UNIQUE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}' AND INDEX_NAME='{index}' LIMIT 1")
        assert result == '0', f'{table} requires its durable uniqueness index.'
    print('Feedback CI boundary prepared: next new pass reaches the cadence threshold; unique people/impression and person/campaign indexes verified.')
elif mode == 'capacity':
    # Boundary fixtures are complete relational rows, not a fabricated count:
    # nine distinct people, canonical searches, real pass decisions and answers.
    # They never authenticate or consume the public login rate limit.
    package_id, property_id = packages['capacity'], properties['capacity']
    assert query(f"SELECT ReceivedCount FROM FeedbackPackages WHERE Id='{package_id}'") == '0'
    source_search = uid(fixture['capacityDecisions'][0])
    source_decision = uid(query(f"SELECT Id FROM Decisions WHERE PropertyId='{property_id}' AND SearchRequestId='{source_search}' AND ActorKind='search'"))

    def clone(table, source_id, override):
        columns = query(f"SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}' ORDER BY ORDINAL_POSITION").splitlines()
        assert columns and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', column) for column in columns)
        names = ','.join('`' + column + '`' for column in columns)
        values = ','.join(override.get(column, '`' + column + '`') for column in columns)
        return f"INSERT INTO `{table}` ({names}) SELECT {values} FROM `{table}` WHERE Id='{source_id}'"

    statements = ['START TRANSACTION']
    synthetic = []
    for number in range(9):
        user_id, search_id, decision_id, invitation_id = [str(uuid.uuid4()) for _ in range(4)]
        synthetic.append({'userId': user_id, 'searchId': search_id, 'decisionId': decision_id, 'invitationId': invitation_id})
        statements.append(clone('Users', users['buyer'], {'Id': literal(user_id), 'Name': literal('Határ Teszt'), 'Email': literal(f'feedback-boundary-{user_id}@example.test'), 'Phone': "''", 'Credits': '0', 'ActiveKind': 'NULL', 'ActiveEntityId': 'NULL', 'FeedbackPassCounter': '0'}))
        statements.append(clone('SearchRequests', source_search, {'Id': literal(search_id), 'OwnerId': literal(user_id)}))
        statements.append(f"INSERT INTO SearchLocations(SearchRequestId,LocationId) SELECT '{search_id}',LocationId FROM SearchLocations WHERE SearchRequestId='{source_search}'")
        statements.append(clone('Decisions', source_decision, {'Id': literal(decision_id), 'ActorUserId': literal(user_id), 'SearchRequestId': literal(search_id), 'Liked': '0', 'Charged': '0', 'RefundedAt': 'NULL'}))
        statements.append(f"""INSERT INTO FeedbackInvitations(Id,PackageId,PropertyId,DecisionId,BuyerId,CreatedAt,ExpiresAt,AnsweredAt,Reason)
VALUES('{invitation_id}','{package_id}','{property_id}','{decision_id}','{user_id}',UTC_TIMESTAMP(6),DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 15 MINUTE),UTC_TIMESTAMP(6),'layout')""")
    statements.extend([f"UPDATE FeedbackPackages SET ReceivedCount=9 WHERE Id='{package_id}'", f"UPDATE Users SET FeedbackPassCounter=19 WHERE Id IN ('{users['buyer']}','{users['other']}')", 'COMMIT'])
    query(';'.join(statements))
    fixture['syntheticCapacity'] = synthetic
    persist(fixture_path, fixture)
    assert query(f"SELECT COUNT(DISTINCT BuyerId) FROM FeedbackInvitations WHERE PackageId='{package_id}' AND AnsweredAt IS NOT NULL AND Reason<>'decline'") == '9'
    print('Capacity boundary prepared: nine distinct, fully linked fixture responses leave exactly one reservable slot; both real buyers are cadence-eligible.')
elif mode == 'age':
    before = snapshot()
    assert not before['refunds'] and not before['notifications']
    assert query(f"SELECT ReceivedCount FROM FeedbackPackages WHERE Id='{packages['main']}'") == '1'
    assert query(f"SELECT ReceivedCount FROM FeedbackPackages WHERE Id='{packages['pendingExpiry']}'") == '0'
    assert query(f"SELECT ReceivedCount FROM FeedbackPackages WHERE Id='{packages['capacity']}'") == '10'
    aged = ','.join(literal(packages[key]) for key in ('main', 'pendingExpiry', 'capacity'))
    query(f"""START TRANSACTION;
SET @feedback_fixture_now=UTC_TIMESTAMP(6);
UPDATE FeedbackPackages SET CreatedAt=DATE_SUB(@feedback_fixture_now,INTERVAL 15 DAY),ExpiresAt=DATE_SUB(@feedback_fixture_now,INTERVAL 1 DAY) WHERE Id IN ({aged});
UPDATE FeedbackInvitations SET CreatedAt=DATE_ADD(DATE_SUB(@feedback_fixture_now,INTERVAL 15 DAY),INTERVAL 1 HOUR),ExpiresAt=DATE_ADD(DATE_SUB(@feedback_fixture_now,INTERVAL 15 DAY),INTERVAL 75 MINUTE),AnsweredAt=IF(AnsweredAt IS NULL,NULL,DATE_ADD(DATE_SUB(@feedback_fixture_now,INTERVAL 15 DAY),INTERVAL 65 MINUTE)) WHERE PackageId IN ({aged});
UPDATE Decisions d JOIN FeedbackInvitations i ON i.DecisionId=d.Id SET d.CreatedAt=DATE_SUB(i.CreatedAt,INTERVAL 1 MINUTE) WHERE i.PackageId IN ({aged});
COMMIT;""")
    fixture['originalPackageCharges'] = before['charges']
    persist(fixture_path, fixture)
    print('Feedback expiry fixture aged: partial, unanswered and fully delivered campaigns, preserving original charges and a consistent fourteen-day timeline.')
else:
    state = snapshot()
    package_ids = ','.join(literal(value) for value in packages.values())
    original = rows('CreditEntries', "Id,UserId,Amount,FeedbackPackageId,DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')", f'FeedbackPackageId IN ({package_ids})')
    assert original == fixture['originalPackageCharges'], 'Expiration changed or duplicated an original charge.'
    refund_rows = [row.split('\t') for row in state['refunds'].splitlines()]
    notification_rows = [row.split('\t') for row in state['notifications'].splitlines()]
    expected = {packages['main']: 9, packages['pendingExpiry']: 10}
    assert len(refund_rows) == len(notification_rows) == 2
    assert {uid(row[3]): int(row[2]) for row in refund_rows} == expected
    assert {uid(row[2]): int(row[5]) for row in notification_rows} == expected
    assert all(row[1] == users['seller'] for row in refund_rows + notification_rows)
    assert all(row[3] == 'NULL' and row[4] == 'feedback_refund' for row in notification_rows)
    assert len(state['impressions'].splitlines()) == 2
    # Every campaign counts only accepted categorical answers from distinct people.
    counts = query(f"""SELECT p.Id,p.ReceivedCount,COUNT(i.Id),COUNT(DISTINCT i.BuyerId)
FROM FeedbackPackages p LEFT JOIN FeedbackInvitations i ON i.PackageId=p.Id AND i.AnsweredAt IS NOT NULL AND i.Reason<>'decline'
WHERE p.Id IN ({package_ids}) GROUP BY p.Id,p.ReceivedCount""")
    for row in counts.splitlines():
        _, recorded, received, people = row.split('\t')
        assert int(recorded) == int(received) == int(people)
    assert query('SELECT COUNT(*) FROM FeedbackPackages WHERE ReceivedCount>Size OR ReceivedCount<0 OR RefundedCredits>Size OR RefundedCredits<0') == '0'
    assert query('SELECT COUNT(*) FROM PropertyImpressions GROUP BY PropertyId,ViewerUserId HAVING COUNT(*)>1') == ''
    if mode == 'record':
        fixture['databaseSnapshot'] = state
        persist(fixture_path, fixture)
        print('Feedback database record passed: unique people, exact answer counts, immutable charges,9/10credit refunds, nullable decision notifications and one receipt per expired campaign.')
    else:
        assert state == fixture['databaseSnapshot'], 'A restart or repeated read changed persisted financial or feedback state.'
        print('Feedback database restart verification passed: package/answer/impression rows, charge/refund keys, balances and original notification timestamps unchanged.')
