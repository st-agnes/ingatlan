#!/usr/bin/env python3
"""JSON-only helpers for the Cloud Shell bootstrap. Never print secret values."""
import json
import pathlib
import re
import secrets
import sys

MARKER = "Managed by st-agnes/ingatlan bootstrap-dev."
LABELS = {"app": "otthonra", "environment": "dev", "managed-by": "otthonra-bootstrap"}


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def require_owned(value):
    labels = value.get("labels", value.get("metadata", {}).get("labels", value.get("settings", {}).get("userLabels", {})))
    if not all(labels.get(key) == expected for key, expected in LABELS.items()):
        raise ValueError("Existing resource is not marked as this Otthonra test deployment; refusing to modify it.")


def main():
    action, *args = sys.argv[1:]
    if action == "field":
        value = read(args[0])
        for key in args[1].split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value is None:
            raise ValueError("Expected field missing from the Google API response: " + args[1])
        print(str(value).lower() if isinstance(value, bool) else value)
    elif action == "owned":
        require_owned(read(args[0]))
    elif action == "service-account":
        value = read(args[0])
        if value.get("description") != MARKER or value.get("disabled"):
            raise ValueError("Existing service account has a different owner or is disabled; refusing to change it.")
    elif action == "sql":
        value, region = read(args[0]), args[1]
        require_owned(value)
        settings = value.get("settings", {})
        if value.get("databaseVersion") != "MYSQL_8_4" or value.get("region") != region:
            raise ValueError("Existing test database uses a different region or MySQL version.")
        if settings.get("edition") != "ENTERPRISE" or settings.get("tier") != "db-f1-micro" or settings.get("availabilityType") != "ZONAL":
            raise ValueError("Existing database differs from the reviewed, small test configuration.")
        if settings.get("dataDiskType") != "PD_SSD" or not 10 <= int(settings.get("dataDiskSizeGb", 0)) <= 20:
            raise ValueError("Existing test database does not use the reviewed 10–20 GiB SSD storage.")
        if not settings.get("storageAutoResize") or int(settings.get("storageAutoResizeLimit", 0)) != 20:
            raise ValueError("Existing test database storage growth is not capped at 20 GiB.")
        backup = settings.get("backupConfiguration", {})
        if not backup.get("enabled") or backup.get("backupRetentionSettings", {}).get("retainedBackups") != 7:
            raise ValueError("Existing test database does not have the reviewed seven-backup retention.")
        if settings.get("ipConfiguration", {}).get("authorizedNetworks"):
            raise ValueError("The test database has an IP allowlist; this bootstrap expects proxy-only access.")
        if settings.get("ipConfiguration", {}).get("sslMode") != "ENCRYPTED_ONLY":
            raise ValueError("Existing test database does not require encrypted connections.")
        if value.get("state") != "RUNNABLE":
            raise ValueError("The test database is not runnable; inspect its Cloud SQL operation before retrying.")
    elif action == "service":
        value, region, account = read(args[0]), args[1], args[2]
        require_owned(value)
        if value.get("metadata", {}).get("labels", {}).get("cloud.googleapis.com/location") != region:
            raise ValueError("Existing test service is in another region.")
        if value.get("spec", {}).get("template", {}).get("spec", {}).get("serviceAccountName") != account:
            raise ValueError("Existing test service uses a different runtime identity.")
    elif action == "description":
        value = read(args[0])
        if value.get("description") != MARKER or value.get("disabled"):
            raise ValueError("Existing identity federation resource has a different owner or is disabled.")
    elif action == "provider":
        value, condition = read(args[0]), args[1]
        if value.get("description") != MARKER or value.get("attributeCondition") != condition or value.get("oidc", {}).get("issuerUri") != "https://token.actions.githubusercontent.com":
            raise ValueError("Existing GitHub federation differs from the reviewed test-only policy.")
        mapping = {"google.subject": "assertion.sub", "attribute.repository_id": "assertion.repository_id", "attribute.repository_owner_id": "assertion.repository_owner_id", "attribute.ref": "assertion.ref", "attribute.workflow_ref": "assertion.workflow_ref"}
        if value.get("attributeMapping") != mapping or value.get("state", "ACTIVE") != "ACTIVE" or value.get("disabled"):
            raise ValueError("Existing GitHub federation has unexpected claim mappings or is disabled.")
    elif action == "operation-state":
        value = read(args[0])
        if value.get("error"):
            raise ValueError("Firebase provisioning operation failed; inspect the operation in Google Cloud.")
        print("done" if value.get("done") else "pending")
    elif action == "secret-value":
        # Validate before using an existing secret; errors contain no secret data.
        path, kind, connection = args
        value = pathlib.Path(path).read_text().strip()
        if kind == "jwt":
            if not re.fullmatch(r"[0-9a-f]{96}", value):
                raise ValueError("Existing test JWT secret is not the expected generated key.")
        else:
            expected = "ConnectionProtocol=Unix;Server=/cloudsql/" + connection + ";Database=otthonra_dev;User ID=otthonra_dev;Password="
            if not value.startswith(expected) or not re.fullmatch(r"[0-9a-f]{64};SslMode=None;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;", value[len(expected):]):
                raise ValueError("Existing MySQL secret does not target this test database or has unexpected options.")
    elif action == "make-secret":
        path, kind, connection = args
        value = secrets.token_hex(48) if kind == "jwt" else (
            "ConnectionProtocol=Unix;Server=/cloudsql/" + connection
            + ";Database=otthonra_dev;User ID=otthonra_dev;Password=" + secrets.token_hex(32)
            + ";SslMode=None;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;"
        )
        pathlib.Path(path).write_text(value)
        pathlib.Path(path).chmod(0o600)
    elif action == "user-flags":
        value = pathlib.Path(args[0]).read_text()
        password = re.search(r"(?:^|;)Password=([0-9a-f]{64});", value)
        if not password:
            raise ValueError("Test connection secret has no generated password.")
        pathlib.Path(args[1]).write_text(json.dumps({"--password": password.group(1)}))
        pathlib.Path(args[1]).chmod(0o600)
    elif action == "root-flags":
        pathlib.Path(args[0]).write_text(json.dumps({"--root-password": secrets.token_hex(32)}))
        pathlib.Path(args[0]).chmod(0o600)
    elif action == "find-user":
        print("yes" if any(user.get("name") == "otthonra_dev" and user.get("host") == "%" for user in read(args[0])) else "no")
    elif action == "find-app":
        matches = [app for app in read(args[0]).get("apps", []) if app.get("displayName") == MARKER and app.get("state", "ACTIVE") == "ACTIVE"]
        if len(matches) > 1:
            raise ValueError("Multiple bootstrap web apps found; refusing to select one arbitrarily.")
        if matches:
            print(matches[0]["appId"])
    elif action == "site":
        value, app_id = read(args[0]), args[1]
        if value.get("appId") != app_id:
            raise ValueError("Existing Hosting site belongs to another Firebase web app; refusing to overwrite it.")
    elif action == "manifest":
        path, project, number, region = args
        value = {
            "projectId": project, "projectNumber": number, "region": region,
            "serviceName": "otthonra-api-dev", "registry": "otthonra-dev",
            "sqlInstance": "otthonra-mysql-dev", "connectionName": f"{project}:{region}:otthonra-mysql-dev",
            "databaseName": "otthonra_dev", "databaseUser": "otthonra_dev",
            "mysqlSecret": "otthonra-mysql-dev", "jwtSecret": "otthonra-jwt-dev",
            "siteId": "otthonra-dev-" + number,
            "runtimeServiceAccount": f"otthonra-runtime-dev@{project}.iam.gserviceaccount.com",
            "deployServiceAccount": f"otthonra-deploy-dev@{project}.iam.gserviceaccount.com",
            "workloadIdentityProvider": f"projects/{number}/locations/global/workloadIdentityPools/otthonra-dev/providers/github",
        }
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2) + "\n")
        target.chmod(0o600)
    else:
        raise ValueError("Unknown bootstrap helper action.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print("Bootstrap validation failed: " + str(error), file=sys.stderr)
        sys.exit(1)
