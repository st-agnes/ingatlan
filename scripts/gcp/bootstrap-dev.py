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


def api_error_summary(value, heading, auth_path=None):
    """Report only Google error diagnostics; never dump bodies or credentials."""
    token = ""
    if auth_path:
        try:
            match = re.search(r'Authorization: Bearer ([^"\r\n]+)', pathlib.Path(auth_path).read_text())
            token = match.group(1) if match else ""
        except OSError:
            pass

    def clean(text, limit=400):
        if not isinstance(text, (str, int)) or isinstance(text, bool):
            return ""
        text = str(text)
        if token:
            text = text.replace(token, "[REDACTED]")
        text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED]", text, flags=re.S)
        text = re.sub(r"\bBearer\s+[^\s,;\"']+", "Bearer [REDACTED]", text, flags=re.I)
        text = re.sub(r"\b(?:ya29\.[A-Za-z0-9._~-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]{20,})", "[REDACTED]", text)
        text = re.sub(r'''(?i)(["']?(?:access_token|refresh_token|id_token|client_secret|password|jwt_key|api_key)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;]+)''', r"\1[REDACTED]", text)
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = re.sub(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]", " ", text)
        return " ".join(text.split())[:limit]

    print(heading, file=sys.stderr)
    error = value.get("error") if isinstance(value, dict) else None
    if not isinstance(error, dict):
        print("Google error details were not available as JSON.", file=sys.stderr)
        return
    status = clean(error.get("status"), 64)
    if not status:
        rpc_code = error.get("code")
        status = {7: "PERMISSION_DENIED", 9: "FAILED_PRECONDITION", 16: "UNAUTHENTICATED"}.get(rpc_code, "") if isinstance(rpc_code, int) else ""
    details = error.get("details")
    details = details if isinstance(details, list) else []
    reasons = []
    for detail in details:
        if not isinstance(detail, dict) or detail.get("@type") != "type.googleapis.com/google.rpc.ErrorInfo":
            continue
        reason = clean(detail.get("reason"), 80)
        if reason:
            reasons.append(reason)
        domain = clean(detail.get("domain"), 100)
        metadata = detail.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        fields = [("reason", reason), ("domain", domain)]
        fields.extend((key, clean(metadata.get(key), 160)) for key in ("service", "consumer", "permission"))
        line = "; ".join(f"{key}={val}" for key, val in fields if val)
        if line:
            print("Google ErrorInfo: " + line[:600], file=sys.stderr)
        break  # One bounded ErrorInfo entry is enough for a terminal summary.
    message = clean(error.get("message"))
    if status:
        print("Google status: " + status, file=sys.stderr)
    if message:
        print("Google message: " + message, file=sys.stderr)
    terms = str(error.get("message", "")) + " " + " ".join(str(d.get("detail", "")) for d in details if isinstance(d, dict))
    if "firebase tos not accepted" in terms.lower():
        print("Firebase Terms: https://console.firebase.google.com/?forceCheckTos=true", file=sys.stderr)
    elif "USER_PROJECT_DENIED" in reasons:
        print("Quota project: serviceusage.services.use permission is required on the selected project.", file=sys.stderr)


MYSQL_LEGACY_OPTIONS = ";SslMode=None;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;"
MYSQL_OPTIONS = ";SslMode=None;AllowPublicKeyRetrieval=True;MaximumPoolSize=10;ConnectionTimeout=15;DefaultCommandTimeout=30;"


def validate_mysql_connection(connection):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]:europe-west1:otthonra-mysql-dev", connection):
        raise ValueError("MySQL authentication settings require the reviewed managed test connection.")


def mysql_prefix(connection):
    # The owned secret and deployment bind this loopback listener to the exact
    # Cloud SQL instance. The Auth Proxy handles remote IAM and TLS transport.
    validate_mysql_connection(connection)
    return "ConnectionProtocol=Tcp;Server=127.0.0.1;Port=3306;Database=otthonra_dev;User ID=otthonra_dev;Password="


def mysql_password(value, connection):
    canonical_prefix = mysql_prefix(connection)
    legacy_prefix = "ConnectionProtocol=Unix;Server=/cloudsql/" + connection + ";Database=otthonra_dev;User ID=otthonra_dev;Password="
    if value.startswith(canonical_prefix):
        prefix, options = canonical_prefix, [MYSQL_OPTIONS]
    elif value.startswith(legacy_prefix):
        prefix, options = legacy_prefix, [MYSQL_LEGACY_OPTIONS, MYSQL_OPTIONS]
    else:
        raise ValueError("Existing MySQL secret does not target this test database or has unexpected options.")
    match = re.fullmatch(r"([0-9a-f]{64})(?:" + "|".join(re.escape(option) for option in options) + ")", value[len(prefix):])
    if not match:
        raise ValueError("Existing MySQL secret does not target this test database or has unexpected options.")
    return match.group(1)


def write_private(path, value):
    path = pathlib.Path(path)
    # Bootstrap already has umask 077; setting the mode also protects direct
    # helper use and reruns with a pre-existing destination file.
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(value)


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
    elif action == "scheduler":
        value, project, number, region = read(args[0]), args[1], args[2], args[3]
        expected_names = {f"projects/{identifier}/locations/{region}/jobs/otthonra-refunds-dev" for identifier in (project, number)}
        origin = f"https://otthonra-api-dev-{number}.{region}.run.app"
        target = value.get("httpTarget", {})
        oidc = target.get("oidcToken", {})
        if value.get("name") not in expected_names or value.get("description") != MARKER:
            raise ValueError("Existing refund Scheduler job belongs to another deployment; refusing to modify it.")
        if target.get("uri") != origin + "/internal/refunds/run" or target.get("httpMethod") != "POST" or target.get("oauthToken"):
            raise ValueError("Existing refund Scheduler job targets an unexpected service or authentication method.")
        if oidc.get("serviceAccountEmail") != f"otthonra-refunds-dev@{project}.iam.gserviceaccount.com" or oidc.get("audience") != origin:
            raise ValueError("Existing refund Scheduler job has an unexpected request identity or audience.")
        if value.get("state") != "ENABLED":
            raise ValueError("The refund Scheduler job is not enabled. Review/resume it in Cloud Scheduler before retrying.")
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
    elif action == "api-error":
        path, code, operation, *auth = args
        try:
            value = read(path)
        except (OSError, ValueError):
            value = None
        api_error_summary(value, f"Google Firebase API request failed: {operation} (HTTP {code}).", auth[0] if auth else None)
    elif action == "operation-state":
        value = read(args[0])
        if value.get("error"):
            api_error_summary(value, "Firebase provisioning operation failed.", args[1] if len(args)>1 else None)
            sys.exit(1)
        print("done" if value.get("done") else "pending")
    elif action == "secret-value":
        # Validate before using an existing secret; errors contain no secret data.
        path, kind, connection = args
        value = pathlib.Path(path).read_text().strip()
        if kind == "jwt":
            if not re.fullmatch(r"[0-9a-f]{96}", value):
                raise ValueError("Existing test JWT secret is not the expected generated key.")
        else:
            mysql_password(value, connection)
    elif action == "upgrade-mysql-secret":
        source, destination, connection = args
        value = pathlib.Path(source).read_text().strip()
        password = mysql_password(value, connection)
        upgraded = mysql_prefix(connection) + password + MYSQL_OPTIONS
        write_private(destination, upgraded)
        print("unchanged" if value == upgraded else "changed")
    elif action == "make-secret":
        path, kind, connection = args
        value = secrets.token_hex(48) if kind == "jwt" else mysql_prefix(connection) + secrets.token_hex(32) + MYSQL_OPTIONS
        write_private(path, value)
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
