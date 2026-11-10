"""Report-reason persistence and legacy-index upgrade checks in disposable CI MySQL only.

The ``legacy`` phase deliberately removes other CI report rows and restores the
old unique index. Stop the disposable API before invoking it. No deployment runs
this fixture, and it cannot connect to a hosted database.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

MODES = ('record', 'verify', 'legacy', 'upgraded')
OLD_INDEX = 'IX_UserReports_ReporterId_ReportedUserId'
NEW_INDEX = 'IX_UserReports_ReporterId_EntityKind_EntityId_Reason'
VERSION = '20261107-interactions-and-report-reasons'
REASONS = {'suspected_agent', 'misleading_content', 'no_longer_current', 'duplicate_listing', 'other_violation'}
NEW_COLUMNS = ['ReporterId', 'EntityKind', 'EntityId', 'Reason']
OLD_COLUMNS = ['ReporterId', 'ReportedUserId']

if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in MODES:
    raise SystemExit('Use only as a disposable GitHub CI interaction-store check.')
container_id, mode = sys.argv[1:]
if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
    raise SystemExit('Invalid disposable MySQL container ID.')
fixture_path = Path('.local/interaction-fixture.json')
fixture = json.loads(fixture_path.read_text())


def canonical_uuid(value):
    return str(uuid.UUID(value))


def expected_report(value):
    result = {field: canonical_uuid(value[field]) for field in
              ('id', 'reporterId', 'reportedUserId', 'entityId')}
    result['entityKind'] = value['entityKind']
    result['reason'] = value['reason']
    assert result['entityKind'] in ('property', 'search'), 'Invalid report source kind in CI fixture.'
    assert result['reason'] in REASONS, 'Invalid report reason in CI fixture.'
    return result


def query(sql):
    result = subprocess.run([
        'docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
        'mysql', '--user=otthonra', '--batch', '--skip-column-names',
        'otthonra_ci', '--execute', sql,
    ], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('The disposable MySQL interaction-store check failed; no credentials or SQL output were printed.')
    return result.stdout.strip()


def persist():
    fixture_path.write_text(json.dumps(fixture))
    fixture_path.chmod(0o600)


def read_reports(reports):
    normalized = [expected_report(report) for report in reports]
    expected = {report['id']: report for report in normalized}
    assert expected and len(expected) == len(normalized), 'CI report IDs must be nonempty and distinct.'
    # All interpolated IDs have been parsed and canonicalized as UUIDs.
    ids = ','.join("'" + report_id + "'" for report_id in expected)
    raw = query(f"""SELECT Id,ReporterId,ReportedUserId,EntityKind,EntityId,Reason,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ')
FROM UserReports WHERE Id IN ({ids}) ORDER BY Id""")
    rows = [row.split('\t') for row in raw.splitlines()] if raw else []
    assert len(rows) == len(expected), 'A report row was lost or duplicated.'
    timestamps = {}
    for row in rows:
        assert len(row) == 7, 'Unexpected report-store result shape.'
        report_id, reporter, reported, kind, entity, reason, timestamp = row
        report_id = canonical_uuid(report_id)
        stored = {
            'id': report_id, 'reporterId': canonical_uuid(reporter),
            'reportedUserId': canonical_uuid(reported), 'entityKind': kind,
            'entityId': canonical_uuid(entity), 'reason': reason,
        }
        assert stored == expected[report_id], 'The persisted report source, owner or selected reason changed.'
        instant = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert instant.tzinfo is not None, 'The stored report timestamp must be interpreted as UTC.'
        timestamps[report_id] = timestamp
    return timestamps


def indexes():
    raw = query(f"""SELECT INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='UserReports'
AND INDEX_NAME IN ('{OLD_INDEX}','{NEW_INDEX}')
ORDER BY INDEX_NAME,SEQ_IN_INDEX""")
    result = {}
    for row in raw.splitlines() if raw else []:
        name, non_unique, sequence, column = row.split('\t')
        assert non_unique == '0', 'The report deduplication index must be unique.'
        columns = result.setdefault(name, [])
        assert int(sequence) == len(columns) + 1, 'Unexpected unique-index column order.'
        columns.append(column)
    return result


if mode in ('record', 'verify'):
    timestamps = read_reports(fixture['reports'])
    if mode == 'record':
        start = dt.datetime.fromisoformat(fixture['reportStart'].replace('Z', '+00:00')) - dt.timedelta(seconds=5)
        end = dt.datetime.fromisoformat(fixture['reportEnd'].replace('Z', '+00:00')) + dt.timedelta(seconds=5)
        for timestamp in timestamps.values():
            instant = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            assert start <= instant <= end, 'Report time is missing or is not the original UTC creation time.'
        fixture['reportTimestamps'] = timestamps
        persist()
    else:
        assert timestamps == fixture['reportTimestamps'], 'A duplicate request or restart changed a report timestamp.'
    print(f'Interaction report-store {mode} passed: {len(timestamps)} selected reasons and source ownership persist with original UTC timestamps.')
elif mode == 'legacy':
    reports = [expected_report(report) for report in fixture['reports']]
    anchor = next((report for report in reports
                   if report['reason'] == 'suspected_agent' and report['entityKind'] == 'property'), None)
    assert anchor is not None, 'The legacy upgrade needs one suspected-agent property report.'
    timestamps = read_reports([anchor])
    timestamp = timestamps[anchor['id']]
    assert timestamp == fixture['reportTimestamps'][anchor['id']], 'The legacy anchor was already modified.'
    fixture['legacy'] = {'report': anchor, 'timestamp': timestamp}
    persist()
    # CI-only representation of the previous report schema. Preserve the anchor
    # row/ID/time, and retain an index usable by the ReporterId foreign key at
    # every DDL step: ADD the old prefix index BEFORE dropping the new one.
    query("DELETE FROM UserReports WHERE Id <> '" + anchor['id'] + "'")
    current = indexes()
    assert current.get(NEW_INDEX) == NEW_COLUMNS, 'The current report-context index is missing.'
    if OLD_INDEX not in current:
        query(f'ALTER TABLE UserReports ADD UNIQUE INDEX `{OLD_INDEX}` (`ReporterId`,`ReportedUserId`)')
    else:
        assert current[OLD_INDEX] == OLD_COLUMNS, 'The legacy index has unexpected columns.'
    query(f'ALTER TABLE UserReports DROP INDEX `{NEW_INDEX}`')
    query(f"DELETE FROM __OtthonraSchemaVersions WHERE Version='{VERSION}'")
    assert indexes() == {OLD_INDEX: OLD_COLUMNS}, 'Could not establish the previous report uniqueness rule.'
    assert read_reports([anchor])[anchor['id']] == timestamp, 'Preparing the legacy schema rewrote the retained report.'
    print('Legacy report-index fixture prepared in disposable CI: one original report and its UTC timestamp retained.')
else:
    legacy = fixture['legacy']
    anchor = expected_report(legacy['report'])
    new_reports = [expected_report(report) for report in legacy['newReports']]
    assert len(new_reports) == 2, 'The upgraded API must create another reason and another entity report.'
    all_reports = [anchor, *new_reports]
    assert int(query('SELECT COUNT(*) FROM UserReports')) == 3, 'Unexpected reports after the legacy upgrade.'
    timestamps = read_reports(all_reports)
    assert timestamps[anchor['id']] == legacy['timestamp'], 'The schema upgrade or repeat rewrote the original report time.'
    current = indexes()
    assert OLD_INDEX not in current, 'The account-wide unique index still blocks separate entity reports.'
    assert current.get(NEW_INDEX) == NEW_COLUMNS, 'The contextual report unique index was not installed.'
    assert query(f"SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='{VERSION}'") == '1', 'The report upgrade marker is missing.'
    if 'upgradedTimestamps' in legacy:
        assert timestamps == legacy['upgradedTimestamps'], 'An idempotent upgrade or restart changed report timestamps.'
    else:
        legacy['upgradedTimestamps'] = timestamps
        persist()
    print('Legacy report-index upgrade passed: original row/time preserved, per-entity reasons accepted, new unique index and idempotent history verified.')
