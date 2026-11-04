#!/usr/bin/env bash
# Run as the project owner in Google Cloud Shell. This provisions TEST only.
set -euo pipefail
set +x
umask 077

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
helper="$root/scripts/gcp/bootstrap-dev.py"
project_id=""
region="europe-west1"
plan_only=false
while (($#)); do
  case "$1" in
    --project) project_id="${2:?Missing project ID}"; shift 2 ;;
    --region) region="${2:?Missing region}"; shift 2 ;;
    --plan) plan_only=true; shift ;;
    -h|--help)
      printf '%s\n' 'Usage: bash scripts/gcp/bootstrap-dev.sh --project PROJECT_ID [--region europe-west1] [--plan]' \
        'Run in Cloud Shell with project Owner access and billing enabled. Creates only -dev resources.'
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done
[[ "$project_id" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || { printf '%s\n' 'Pass a valid --project Google Cloud Project ID.' >&2; exit 1; }
[[ "$region" == europe-west1 ]] || { printf '%s\n' 'This reviewed test deployment supports only europe-west1.' >&2; exit 1; }
for command_name in gcloud python3 curl; do command -v "$command_name" >/dev/null || { printf 'Required command missing: %s\n' "$command_name" >&2; exit 1; }; done

temporary="$(mktemp -d)"
bootstrap_step='Projekt és számlázás ellenőrzése'
finish() {
  local status=$?
  trap - EXIT
  rm -rf "$temporary"
  if ((status != 0)); then
    # Only a fixed phase name is printed: never BASH_COMMAND or secret arguments.
    printf '\nTELEPÍTÉS MEGÁLLT: %s (hibakód: %s).\n' "$bootstrap_step" "$status" >&2
  fi
  exit "$status"
}
trap finish EXIT
step() { bootstrap_step="$1"; printf '\nLÉPÉS: %s\n' "$bootstrap_step"; }
gc() { gcloud --project="$project_id" --quiet "$@"; }
field() { python3 "$helper" field "$1" "$2"; }
marker='Managed by st-agnes/ingatlan bootstrap-dev.'
labels='app=otthonra,environment=dev,managed-by=otthonra-bootstrap'

# Read metadata only; a permission/network error is never treated as Not Found.
describe() {
  local output="$1"; shift
  if gc "$@" --format=json >"$output" 2>"$temporary/describe-error"; then return 0; fi
  if python3 - "$temporary/describe-error" "$@" <<'PY'
import pathlib,re,sys
text=pathlib.Path(sys.argv[1]).read_text()
# SDK failures are not all emitted as HTTP/structured error codes. Never turn
# an access, credentials or transport failure into permission to create.
denied=re.search(r'permission|forbidden|unauth|credentials|UNAVAILABLE|DEADLINE_EXCEEDED|RESOURCE_EXHAUSTED|SERVICE_DISABLED|\b(?:401|403|429|5[0-9]{2})\b|connection|network|timed?\s*out|timeout|unrecognized arguments|invalid (?:argument|choice)|usage:',text,re.I)
missing=re.search(r'NOT_FOUND|not found|does not exist|\b404\b',text,re.I)
command=sys.argv[2:]
if command[:3]==['run','services','describe'] and len(command)>3:
    # Cloud Run uses "Cannot find service [NAME]" (or parentheses) for 404s.
    # Match only the exact requested service, never a missing credential/helper.
    name=re.escape(command[3])
    run_missing=re.search(r'\(gcloud\.run\.services\.describe\)\s*:?\s*cannot find service\s+[\[(]'+name+r'[\])]\.?\s*$',text,re.I|re.M)
    missing=run_missing
sys.exit(0 if missing and not denied else 1)
PY
  then return 1; fi
  cat "$temporary/describe-error" >&2
  exit 1
}

gc projects describe "$project_id" --format=json >"$temporary/project.json"
[[ "$(field "$temporary/project.json" lifecycleState)" == ACTIVE ]] || { printf '%s\n' 'Project is not active.' >&2; exit 1; }
project_number="$(field "$temporary/project.json" projectNumber)"
[[ "$project_number" =~ ^[1-9][0-9]{5,16}$ ]] || { printf '%s\n' 'Google project number cannot form the reviewed Hosting site ID.' >&2; exit 1; }
gc billing projects describe "$project_id" --format=json >"$temporary/billing.json"
[[ "$(field "$temporary/billing.json" billingEnabled)" == true ]] || { printf '%s\n' 'Link a billing account to this project first.' >&2; exit 1; }

printf 'Project: %s\nRegion: %s\n' "$project_id" "$region"
printf '%s\n' \
  'Test-only plan: one MySQL 8.4 Enterprise db-f1-micro instance, 10 GiB SSD (growth capped at 20 GiB), standard backups.' \
  'One Cloud Run -dev service (0 minimum / 2 maximum instances), one Hosting site, dev identities and secrets.' \
  'Cloud SQL is continuously billable: budget roughly USD 10-15/month before tax; actual storage/backups and regional prices vary.' \
  'No production service, database, domain, Stripe key or service-account JSON key is created.'
if "$plan_only"; then exit 0; fi

step 'Google API-k engedélyezése'
gc services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com run.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
  firebase.googleapis.com firebasehosting.googleapis.com

step 'Teszt szolgáltatásfiókok'
runtime_account="otthonra-runtime-dev@$project_id.iam.gserviceaccount.com"
deploy_account="otthonra-deploy-dev@$project_id.iam.gserviceaccount.com"
for account in otthonra-runtime-dev otthonra-deploy-dev; do
  if describe "$temporary/account.json" iam service-accounts describe "$account@$project_id.iam.gserviceaccount.com"; then
    python3 "$helper" service-account "$temporary/account.json"
  else
    gc iam service-accounts create "$account" --display-name="$account" --description="$marker" >/dev/null
  fi
done

step 'Teszt konténertároló'
if describe "$temporary/registry.json" artifacts repositories describe otthonra-dev --location="$region"; then
  python3 "$helper" owned "$temporary/registry.json"
  [[ "$(field "$temporary/registry.json" format)" == DOCKER ]] || { printf '%s\n' 'Existing dev registry is not Docker.' >&2; exit 1; }
else
  gc artifacts repositories create otthonra-dev --location="$region" --repository-format=docker --description="$marker" --labels="$labels" >/dev/null
fi

step 'Cloud SQL tesztadatbázis'
if describe "$temporary/sql.json" sql instances describe otthonra-mysql-dev; then
  python3 "$helper" sql "$temporary/sql.json" "$region"
else
  python3 "$helper" root-flags "$temporary/root-flags.json"
  gc beta sql instances create otthonra-mysql-dev --region="$region" --database-version=MYSQL_8_4 --edition=ENTERPRISE \
    --tier=db-f1-micro --availability-type=ZONAL --storage-type=SSD --storage-size=10 \
    --storage-auto-increase --storage-auto-increase-limit=20 --backup-start-time=03:00 --retained-backups-count=7 \
    --assign-ip --ssl-mode=ENCRYPTED_ONLY --deletion-protection --labels="$labels" --flags-file="$temporary/root-flags.json" >/dev/null
fi
if ! describe "$temporary/database.json" sql databases describe otthonra_dev --instance=otthonra-mysql-dev; then
  gc sql databases create otthonra_dev --instance=otthonra-mysql-dev --charset=utf8mb4 --collation=utf8mb4_unicode_ci >/dev/null
fi

step 'Tesztadatbázis-jelszó és JWT-titok'
connection_name="$project_id:$region:otthonra-mysql-dev"
gc sql users list --instance=otthonra-mysql-dev --format=json >"$temporary/users.json"
user_exists="$(python3 "$helper" find-user "$temporary/users.json")"
for kind in mysql jwt; do
  secret_name="otthonra-$kind-dev"
  if describe "$temporary/secret.json" secrets describe "$secret_name"; then
    python3 "$helper" owned "$temporary/secret.json"
    gc secrets versions access latest --secret="$secret_name" >"$temporary/$kind-secret"
    python3 "$helper" secret-value "$temporary/$kind-secret" "$kind" "$connection_name"
  else
    if [[ "$kind" == mysql && "$user_exists" == yes ]]; then
      printf '%s\n' 'The application DB user already exists but its managed connection secret is missing. Restore that secret before retrying; no password was changed.' >&2
      exit 1
    fi
    python3 "$helper" make-secret "$temporary/$kind-secret" "$kind" "$connection_name"
    gc secrets create "$secret_name" --replication-policy=user-managed --locations="$region" --labels="$labels" --data-file="$temporary/$kind-secret" >/dev/null
  fi
  gc secrets add-iam-policy-binding "$secret_name" --member="serviceAccount:$runtime_account" --role=roles/secretmanager.secretAccessor >/dev/null
done
if [[ "$user_exists" != yes ]]; then
  python3 "$helper" user-flags "$temporary/mysql-secret" "$temporary/user-flags.json"
  gc sql users create otthonra_dev --instance=otthonra-mysql-dev --host=% --flags-file="$temporary/user-flags.json" >/dev/null
fi
gc projects add-iam-policy-binding "$project_id" --member="serviceAccount:$runtime_account" --role=roles/cloudsql.client --condition=None >/dev/null

step 'Cloud Run tesztszolgáltatás és jogosultságok'
if describe "$temporary/service.json" run services describe otthonra-api-dev --region="$region"; then
  python3 "$helper" service "$temporary/service.json" "$region" "$runtime_account"
else
  # This placeholder only reserves the owned service and permits narrowly scoped CI.
  # It is replaced by deploy-dev.sh; this script never claims the app is deployed.
  gc run deploy otthonra-api-dev --region="$region" --image=us-docker.pkg.dev/cloudrun/container/hello:latest \
    --service-account="$runtime_account" --min-instances=0 --max-instances=2 --memory=512Mi --cpu=1 \
    --labels="$labels" --no-allow-unauthenticated >/dev/null
fi
gc run services add-iam-policy-binding otthonra-api-dev --region="$region" --member=allUsers --role=roles/run.invoker >/dev/null
gc run services add-iam-policy-binding otthonra-api-dev --region="$region" --member="serviceAccount:$deploy_account" --role=roles/run.developer >/dev/null
gc iam service-accounts add-iam-policy-binding "$runtime_account" --member="serviceAccount:$deploy_account" --role=roles/iam.serviceAccountUser >/dev/null
gc artifacts repositories add-iam-policy-binding otthonra-dev --location="$region" --member="serviceAccount:$deploy_account" --role=roles/artifactregistry.writer >/dev/null
gc projects add-iam-policy-binding "$project_id" --member="serviceAccount:$deploy_account" --role=roles/run.viewer --condition=None >/dev/null
gc projects add-iam-policy-binding "$project_id" --member="serviceAccount:$deploy_account" --role=roles/firebasehosting.admin --condition=None >/dev/null
gc projects add-iam-policy-binding "$project_id" --member="serviceAccount:$deploy_account" --role=roles/serviceusage.serviceUsageConsumer --condition=None >/dev/null

step 'GitHub rövid életű Google-identitás'
if describe "$temporary/pool.json" iam workload-identity-pools describe otthonra-dev --location=global; then
  python3 "$helper" description "$temporary/pool.json"
  [[ "$(field "$temporary/pool.json" state)" == ACTIVE ]] || { printf '%s\n' 'GitHub test identity pool is not active.' >&2; exit 1; }
else
  gc iam workload-identity-pools create otthonra-dev --location=global --display-name=otthonra-dev --description="$marker" >/dev/null
fi
condition="assertion.repository_id == '1441962351' && assertion.repository_owner_id == '9905462' && assertion.repository == 'st-agnes/ingatlan' && assertion.event_name == 'workflow_dispatch' && ((assertion.ref == 'refs/heads/main' && assertion.workflow_ref == 'st-agnes/ingatlan/.github/workflows/deploy-dev.yml@refs/heads/main') || (assertion.ref == 'refs/heads/codex/google-cloud-test' && assertion.workflow_ref == 'st-agnes/ingatlan/.github/workflows/deploy-dev.yml@refs/heads/codex/google-cloud-test'))"
if describe "$temporary/provider.json" iam workload-identity-pools providers describe github --location=global --workload-identity-pool=otthonra-dev; then
  python3 "$helper" provider "$temporary/provider.json" "$condition"
else
  gc iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=otthonra-dev \
    --display-name=github --description="$marker" --issuer-uri=https://token.actions.githubusercontent.com \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref" \
    --attribute-condition="$condition" >/dev/null
fi
gc iam service-accounts add-iam-policy-binding "$deploy_account" \
  --member="principalSet://iam.googleapis.com/projects/$project_number/locations/global/workloadIdentityPools/otthonra-dev/attribute.repository_id/1441962351" \
  --role=roles/iam.workloadIdentityUser >/dev/null

step 'Firebase tesztprojekt és webcím'
# Firebase APIs use the current Cloud Shell login. The bearer header stays in a
# private temporary file, never in terminal output, process arguments or Git.
rest() {
  local method="$1" url="$2" output="$3" body="${4:-}" code attempt
  for attempt in 1 2 3 4; do
    printf 'header = "Authorization: Bearer %s"\n' "$(gcloud auth print-access-token)" >"$temporary/curl-auth"
    if [[ -n "$body" ]]; then
      code="$(curl --silent --show-error --connect-timeout 15 --max-time 60 --config "$temporary/curl-auth" --request "$method" \
        --header 'Content-Type: application/json' --data "$body" --output "$output" --write-out '%{http_code}' "$url")" || return 1
    else
      code="$(curl --silent --show-error --connect-timeout 15 --max-time 60 --config "$temporary/curl-auth" --request "$method" \
        --output "$output" --write-out '%{http_code}' "$url")" || return 1
    fi
    # Retry reads only: retrying a create after an ambiguous response could create
    # a second Firebase app. Permission errors and non-idempotent requests fail.
    if [[ "$method" == GET && "$code" =~ ^(429|500|502|503|504)$ && "$attempt" -lt 4 ]]; then sleep 2; continue; fi
    printf '%s' "$code"
    return
  done
}
expect_ok() { [[ "$1" =~ ^2[0-9][0-9]$ ]] || { printf 'Google Firebase API request failed (HTTP %s); no response body containing configuration was printed.\n' "$1" >&2; exit 1; }; }
wait_operation() {
  local operation="$1" deadline=$((SECONDS+600)) code state
  [[ "$operation" =~ ^operations/[A-Za-z0-9_./-]+$ ]] || { printf '%s\n' 'Unexpected Firebase operation name.' >&2; exit 1; }
  while :; do
    code="$(rest GET "https://firebase.googleapis.com/v1beta1/$operation" "$temporary/operation.json")"; expect_ok "$code"
    state="$(python3 "$helper" operation-state "$temporary/operation.json")" || return 1
    if [[ "$state" == done ]]; then return; fi
    ((SECONDS<deadline)) || { printf '%s\n' 'Firebase provisioning timed out; retrying this bootstrap will reuse its resources.' >&2; exit 1; }
    sleep 3
  done
}
code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/$project_id" "$temporary/firebase.json")"
if [[ "$code" == 404 ]]; then
  code="$(rest POST "https://firebase.googleapis.com/v1beta1/projects/$project_id:addFirebase" "$temporary/firebase-operation.json" '{}')"; expect_ok "$code"
  wait_operation "$(field "$temporary/firebase-operation.json" name)"
else expect_ok "$code"; fi
code="$(rest GET "https://firebase.googleapis.com/v1beta1/projects/$project_id/webApps?pageSize=100" "$temporary/apps.json")"; expect_ok "$code"
app_id="$(python3 "$helper" find-app "$temporary/apps.json")"
if [[ -z "$app_id" ]]; then
  code="$(rest POST "https://firebase.googleapis.com/v1beta1/projects/$project_id/webApps" "$temporary/app-operation.json" "{\"displayName\":\"$marker\"}")"; expect_ok "$code"
  wait_operation "$(field "$temporary/app-operation.json" name)"
  app_id="$(field "$temporary/operation.json" response.appId)"
fi
site_id="otthonra-dev-$project_number"
code="$(rest GET "https://firebasehosting.googleapis.com/v1beta1/projects/$project_number/sites/$site_id" "$temporary/site.json")"
if [[ "$code" == 404 ]]; then
  code="$(rest POST "https://firebasehosting.googleapis.com/v1beta1/projects/$project_number/sites?siteId=$site_id" "$temporary/site.json" "{\"appId\":\"$app_id\"}")"; expect_ok "$code"
else expect_ok "$code"; fi
python3 "$helper" site "$temporary/site.json" "$app_id"

step 'Telepítési konfiguráció mentése'
python3 "$helper" manifest "$root/.local/gcp/dev-config.json" "$project_id" "$project_number" "$region"
printf '\n%s\n' 'Test infrastructure and GitHub deployment identity are configured.' \
  'The Cloud Run service is still a placeholder. The application is NOT deployed yet.' \
  'Next: run scripts/gcp/deploy-dev.sh with .local/gcp/dev-config.json as described in docs/GOOGLE-CLOUD-TEST.md.' \
  'For GitHub Actions, set the repository variable GCP_DEV_CONFIG to the non-secret JSON in .local/gcp/dev-config.json.' \
  'Firebase Hosting deployment permissions apply to Hosting sites throughout this project; review that role before adding production sites later.'
