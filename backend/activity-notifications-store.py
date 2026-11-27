"""Actual disposable CI MySQL activity receipts and additive notification migration."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

MODES = {'--prepare-feedback', '--prepare-upgrade', '--verify'}
if (os.environ.get('CI') != 'true' or len(sys.argv) not in (2, 3)
        or not re.fullmatch(r'[a-f0-9]{12,64}', sys.argv[1])
        or len(sys.argv) == 3 and sys.argv[2] not in MODES):
    raise SystemExit('Use only a disposable GitHub CI MySQL container.')
mode = sys.argv[2] if len(sys.argv) == 3 else '--verify'
path = Path('.local/activity-notifications-fixture.json')
fixture = json.loads(path.read_text())


def guid(value):
    return str(uuid.UUID(value))


def query(sql):
    result = subprocess.run(['docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', sys.argv[1],
                             'mysql', '--user=otthonra', '--batch', '--skip-column-names',
                             'otthonra_ci', '--execute', sql], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('The disposable activity database assertion failed; SQL and credentials were not printed.')
    return result.stdout.strip().splitlines()


sender, recipient = guid(fixture['sender']['id']), guid(fixture['recipient']['id'])
owners = [guid(owner['id']) for owner in fixture['owners']]
owner_sql = ','.join("'" + owner + "'" for owner in owners)
version = '20261119-account-activity-notifications'
visits_version = '20261127-notification-menu-visits'

if mode == '--prepare-feedback':
    p2, search = guid(fixture['p2']['id']), guid(fixture['searchC']['id'])
    rows = query(f"SELECT Id FROM Decisions WHERE ActorUserId='{sender}' AND ActorKind='property' AND PropertyId='{p2}' AND SearchRequestId='{search}' AND Liked=TRUE AND Charged=2")
    assert len(rows) == 1, 'Only the known disposable unanswered paid like may be aged.'
    decision = guid(rows[0])
    query(f"UPDATE Users SET FeedbackPassCounter=19 WHERE Id='{sender}'; UPDATE Decisions SET CreatedAt=UTC_TIMESTAMP(6)-INTERVAL 15 DAY WHERE Id='{decision}'")
    fixture['deletedDecisionId'] = decision
    path.write_text(json.dumps(fixture))
    os.chmod(path, 0o600)
    print('Prepared one disposable feedback sample and one known 14-day unanswered paid like.')
    raise SystemExit(0)

if mode == '--prepare-upgrade':
    # Stop the owned CI API before this destructive, immediately-previous-schema fixture.
    # The actual legacy refund keeps its ID, text, first ReadAt, FK and unique receipt.
    query("DELETE FROM UserNotifications WHERE Kind NOT IN ('like_refund','feedback_refund'); "
          "ALTER TABLE UserNotifications DROP INDEX IX_UserNotifications_UserId_EventKey, "
          "DROP INDEX IX_UserNotifications_UserId_ReadAt_CreatedAt, "
          "DROP COLUMN EventKey, DROP COLUMN EntityKind, DROP COLUMN EntityId, "
          "DROP COLUMN PropertyId, DROP COLUMN SearchRequestId, DROP COLUMN MatchId; "
          "ALTER TABLE Users DROP COLUMN NotificationLastVisitAt; "
          "DROP TABLE IF EXISTS __OtthonraNotificationBackfills; "
          f"DELETE FROM __OtthonraSchemaVersions WHERE Version IN ('{version}','{visits_version}')")
    legacy = fixture['legacyRefund']
    rows = query(f"SELECT Id,DecisionId,DATE_FORMAT(ReadAt,'%Y-%m-%dT%H:%i:%s.%f') FROM UserNotifications WHERE Id='{guid(legacy['id'])}' AND UserId='{sender}'")
    assert len(rows) == 1 and rows[0].split('\t')[1] == guid(legacy['decisionId'])
    assert rows[0].split('\t')[2] != 'NULL', 'Previous-schema fixture must retain a read legacy refund.'
    print('Prepared previous notification schema without menu visits while preserving legacy refund ID, foreign key and first-read timestamp.')
    raise SystemExit(0)

columns = query("SELECT COLUMN_NAME,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND COLUMN_NAME IN ('EventKey','EntityKind','EntityId','PropertyId','SearchRequestId','MatchId') ORDER BY COLUMN_NAME")
assert columns == [name + '\tYES' for name in ['EntityId', 'EntityKind', 'EventKey', 'MatchId', 'PropertyId', 'SearchRequestId']]
for name, expected in [
    ('IX_UserNotifications_UserId_EventKey', '0\tUserId,EventKey'),
    ('IX_UserNotifications_UserId_ReadAt_CreatedAt', '1\tUserId,ReadAt,CreatedAt'),
    ('IX_UserNotifications_UserId_CreatedAt', '1\tUserId,CreatedAt'),
]:
    assert query(f"SELECT NON_UNIQUE,GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserNotifications' AND INDEX_NAME='{name}' GROUP BY NON_UNIQUE") == [expected]
assert query(f"SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='{version}'") == ['1']
assert query(f"SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='{visits_version}'") == ['1']
assert query("SELECT COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='Users' AND COLUMN_NAME='NotificationLastVisitAt'") == ['datetime(6)\tYES']
for owner in owners:
    rows = query(f"SELECT COUNT(*) FROM UserNotifications n JOIN Users u ON u.Id=n.UserId WHERE u.Id='{owner}' AND (u.NotificationLastVisitAt IS NULL OR n.CreatedAt>u.NotificationLastVisitAt)")
    assert rows == [str(fixture['snapshots'][owner]['newCount'])], 'The menu badge must reflect the persisted visit boundary, independently of ReadAt.'
if 'persistedVisit' in fixture:
    receipt = fixture['persistedVisit']
    rows = query(f"SELECT DATE_FORMAT(NotificationLastVisitAt,'%Y-%m-%dT%H:%i:%s.%f') FROM Users WHERE Id='{guid(receipt['ownerId'])}'")
    assert len(rows) == 1 and rows[0].rstrip('0').rstrip('.') == receipt['visitedAt'].rstrip('Z').rstrip('0').rstrip('.'), 'An ordinary restart must not reset the last menu visit.'
assert query(f"SELECT COUNT(*) FROM __OtthonraNotificationBackfills WHERE Version LIKE '{version}:%'")[0] != '0'
assert query("SELECT COUNT(*) FROM (SELECT UserId,EventKey FROM UserNotifications WHERE EventKey IS NOT NULL GROUP BY UserId,EventKey HAVING COUNT(*)<>1) duplicates") == ['0']
assert query(f"SELECT COUNT(*) FROM UserNotifications WHERE UserId IN ({owner_sql}) AND Kind NOT IN ('like_refund','feedback_refund') AND (DecisionId IS NOT NULL OR FeedbackPackageId IS NOT NULL)") == ['0'], 'Generic activities cannot consume unique legacy refund source keys.'

# Derive receipts from their real source rows, independent of notification paging/order/IDs.
expected = []
for row in query(f"SELECT d.Id,CASE WHEN d.ActorKind='property' THEN s.OwnerId ELSE p.OwnerId END FROM Decisions d JOIN Properties p ON p.Id=d.PropertyId JOIN SearchRequests s ON s.Id=d.SearchRequestId WHERE d.Liked=TRUE AND (p.OwnerId IN ({owner_sql}) OR s.OwnerId IN ({owner_sql}))"):
    source, owner = row.split('\t')
    if owner in owners:
        expected.append((owner, 'incoming_like:' + source))
for row in query(f"SELECT m.Id,p.OwnerId,s.OwnerId FROM Matches m JOIN Properties p ON p.Id=m.PropertyId JOIN SearchRequests s ON s.Id=m.SearchRequestId WHERE p.OwnerId IN ({owner_sql}) OR s.OwnerId IN ({owner_sql})"):
    source, seller, buyer = row.split('\t')
    expected.extend((owner, 'match_created:' + source) for owner in [seller, buyer] if owner in owners)
for row in query(f"SELECT msg.Id,CASE WHEN msg.SenderId=p.OwnerId THEN s.OwnerId ELSE p.OwnerId END FROM Messages msg JOIN Matches m ON m.Id=msg.MatchId JOIN Properties p ON p.Id=m.PropertyId JOIN SearchRequests s ON s.Id=m.SearchRequestId WHERE p.OwnerId IN ({owner_sql}) OR s.OwnerId IN ({owner_sql})"):
    source, owner = row.split('\t')
    if owner in owners:
        expected.append((owner, 'message_received:' + source))
for row in query(f"SELECT i.Id,p.OwnerId FROM FeedbackInvitations i JOIN FeedbackPackages p ON p.Id=i.PackageId WHERE p.OwnerId IN ({owner_sql}) AND i.AnsweredAt IS NOT NULL AND i.Reason IS NOT NULL AND i.Reason<>'decline'"):
    source, owner = row.split('\t')
    expected.append((owner, 'feedback_received:' + source))
for row in query(f"SELECT Id,UserId FROM CreditEntries WHERE UserId IN ({owner_sql}) AND Amount>0 AND RefundedDecisionId IS NULL AND RefundedFeedbackPackageId IS NULL"):
    source, owner = row.split('\t')
    expected.append((owner, 'credit_added:' + source))
for row in query(f"SELECT Id,OwnerId,ReceivedCount>=Size,RefundedAt IS NOT NULL FROM FeedbackPackages WHERE OwnerId IN ({owner_sql})"):
    source, owner, complete, expired = row.split('\t')
    if complete == '1':
        expected.append((owner, 'feedback_completed:' + source))
    if expired == '1':
        expected.append((owner, 'feedback_expired:' + source))
for row in query(f"SELECT Id,ActorUserId FROM Decisions WHERE ActorUserId IN ({owner_sql}) AND RefundedAt IS NOT NULL"):
    source, owner = row.split('\t')
    expected.append((owner, 'like_refund:' + source))
for row in query(f"SELECT Id,OwnerId FROM FeedbackPackages WHERE OwnerId IN ({owner_sql}) AND RefundedCredits>0"):
    source, owner = row.split('\t')
    expected.append((owner, 'feedback_refund:' + source))
actual = [tuple(row.split('\t')) for row in query(f"SELECT UserId,EventKey FROM UserNotifications WHERE UserId IN ({owner_sql})")]
assert sorted(actual) == sorted(expected), 'Every source event needs exactly one receipt for each eligible owner, including deleted-profile history.'
assert len(expected) >= 10, 'Integration scenario must exercise multiple event families.'

legacy = fixture['legacyRefund']
read = query(f"SELECT DATE_FORMAT(ReadAt,'%Y-%m-%dT%H:%i:%s.%f'),DecisionId,EventKey FROM UserNotifications WHERE Id='{guid(legacy['id'])}' AND UserId='{sender}'")
assert len(read) == 1
at, source, key = read[0].split('\t')
assert at.rstrip('0').rstrip('.') == legacy['readAt'].rstrip('Z').rstrip('0').rstrip('.')
assert source == guid(legacy['decisionId']) and key == 'like_refund:' + source
print('Activity MySQL store: owner/source unique receipts, privacy-safe target columns, read index, bounded backfill marker and preserved legacy refund/read state passed.')
