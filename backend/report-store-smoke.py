"""Check report timestamps directly in the disposable CI MySQL container, never a hosted DB."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

if os.environ.get('CI') != 'true' or len(sys.argv) != 3 or sys.argv[2] not in ('record', 'verify'):
    raise SystemExit('Use only as a disposable GitHub CI report-store check.')
container_id, phase = sys.argv[1:]
if not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
    raise SystemExit('Invalid disposable container ID.')
path = Path('.local/broker-upgrade-fixture.json')
fixture = json.loads(path.read_text())
expected = {str(uuid.UUID(row['id'])): row for row in fixture['reports']}
ids = ','.join("'" + key + "'" for key in expected)
query = f"""SELECT Id,ReporterId,ReportedUserId,EntityKind,EntityId,Reason,
DATE_FORMAT(CreatedAt,'%Y-%m-%dT%H:%i:%s.%fZ') FROM UserReports WHERE Id IN ({ids}) ORDER BY Id"""
result = subprocess.run(['docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', container_id,
                         'mysql', '--user=otthonra', '--batch', '--skip-column-names',
                         'otthonra_ci', '--execute', query], capture_output=True, text=True, check=True)
rows = [line.split('\t') for line in result.stdout.strip().splitlines()]
assert len(rows) == len(expected) == 3, 'Stored reports missing or duplicated.'
start = dt.datetime.fromisoformat(fixture['reportStart'].replace('Z', '+00:00')) - dt.timedelta(seconds=5)
end = dt.datetime.fromisoformat(fixture['reportEnd'].replace('Z', '+00:00')) + dt.timedelta(seconds=5)
timestamps = {}
for report_id, reporter, reported, kind, entity, reason, timestamp in rows:
    report_id = str(uuid.UUID(report_id))
    row = expected[report_id]
    assert str(uuid.UUID(reporter)) == row['reporterId']
    assert str(uuid.UUID(reported)) == row['reportedUserId']
    assert kind == row['entityKind'] and str(uuid.UUID(entity)) == row['entityId']
    assert reason == 'suspected_agent'
    instant = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    assert start <= instant <= end, 'Report timestamp is missing or is not stored as UTC.'
    timestamps[report_id] = timestamp
if phase == 'record':
    fixture['reportTimestamps'] = timestamps
    path.write_text(json.dumps(fixture))
    path.chmod(0o600)
else:
    assert timestamps == fixture['reportTimestamps'], 'A duplicate report or restart changed its original timestamp.'
print('Report database check passed: three unique reports, correct source ownership, UTC timestamps, and ' +
      ('snapshot recorded.' if phase == 'record' else 'unchanged timestamps after duplicate requests and restart.'))
