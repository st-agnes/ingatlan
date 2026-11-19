"""Verify actual CI MySQL counts, durable receipts and reserved fake geocoding."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

if os.environ.get('CI') != 'true' or len(sys.argv) not in (2, 3) or not re.fullmatch(r'[a-f0-9]{12,64}', sys.argv[1]) or len(sys.argv) == 3 and sys.argv[2] != '--schema-only':
    raise SystemExit('Use only a disposable GitHub CI MySQL container.')


def query(sql):
    result = subprocess.run(['docker', 'exec', '--env', 'MYSQL_PWD=ci-only-password', sys.argv[1],
                             'mysql', '--user=otthonra', '--batch', '--skip-column-names',
                             'otthonra_ci', '--execute', sql], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('The disposable onboarding database assertion failed; SQL and credentials were not printed.')
    return result.stdout.strip().splitlines()


for table in ['Properties', 'SearchRequests']:
    columns = query(f"SELECT COLUMN_NAME,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='otthonra_ci' AND TABLE_NAME='{table}' AND COLUMN_NAME IN ('CreationRequestId','CreationRequestHash') ORDER BY COLUMN_NAME")
    assert columns == ['CreationRequestHash\tYES', 'CreationRequestId\tYES'], 'Legacy rows need additive nullable creation columns.'
    index = query(f"SELECT NON_UNIQUE,GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='otthonra_ci' AND TABLE_NAME='{table}' AND INDEX_NAME='IX_{table}_OwnerId_CreationRequestId' GROUP BY NON_UNIQUE")
    assert index == ['0\tOwnerId,CreationRequestId'], 'Owner-scoped retry uniqueness must be enforced by MySQL.'
assert query("SELECT COUNT(*) FROM __OtthonraSchemaVersions WHERE Version='20261118-idempotent-entity-creation'") == ['1']
if len(sys.argv) == 3:
    for table in ['Properties', 'SearchRequests']:
        assert query(f"SELECT COUNT(*) FROM {table}")[0] != '0', 'The legacy upgrade must retain existing entities.'
        assert query(f"SELECT COUNT(*) FROM {table} WHERE CreationRequestId IS NOT NULL OR CreationRequestHash IS NOT NULL") == ['0'], 'Existing entities must keep nullable creation receipts.'
    print('Legacy onboarding upgrade: existing entities retained, nullable receipt columns and unique owner indexes added exactly once.')
    raise SystemExit(0)

fixture = json.loads(Path('.local/onboarding-fixture.json').read_text())
owners = [str(uuid.UUID(owner['id'])) for owner in fixture['owners']]
assert len(owners) == 2
for kind, table in [('property', 'Properties'), ('search', 'SearchRequests')]:
    expected = [row for row in fixture['rows'] if row['kind'] == kind]
    assert len(expected) == 6
    actual = query(f"SELECT Id,OwnerId,Archived,COALESCE(CreationRequestId,'NULL'),COALESCE(CHAR_LENGTH(CreationRequestHash),0) FROM {table} WHERE OwnerId IN ('{owners[0]}','{owners[1]}') ORDER BY Id")
    assert len(actual) == len(expected), 'The real database contains duplicate onboarding creations.'
    by_id = {str(uuid.UUID(row['id'])): row for row in expected}
    for line in actual:
        entity_id, owner_id, archived, key, hash_length = line.split('\t')
        row = by_id[entity_id]
        assert owner_id == str(uuid.UUID(row['ownerId']))
        assert int(archived) == int(row['archived'])
        assert key == (str(uuid.UUID(row['creationRequestId'])) if row['creationRequestId'] else 'NULL')
        assert int(hash_length) == (64 if row['creationRequestId'] else 0)
providers = query(f"SELECT DISTINCT GeocodingProvider FROM Properties WHERE OwnerId IN ('{owners[0]}','{owners[1]}')")
assert providers == ['test-fixture'], 'Fictional onboarding properties must use the reserved TEST provider.'
print('Onboarding MySQL store: exact row counts, archive state, owner-scoped unique indexes, SHA256 receipts and TEST geocoding passed.')
