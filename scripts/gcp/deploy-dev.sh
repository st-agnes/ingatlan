#!/usr/bin/env bash
# Deploy only the prepared test environment. Works with Cloud Shell ADC or GitHub OIDC.
set -euo pipefail
set +x
umask 077

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
config_path='.local/gcp/dev-config.json'
image_digest=''
while (($#)); do
  case "$1" in
    --config) config_path="${2:?Missing config path}"; shift 2 ;;
    --image) image_digest="${2:?Missing image digest}"; shift 2 ;;
    *) echo 'Usage: bash scripts/gcp/deploy-dev.sh [--config FILE] [--image REGISTRY_IMAGE@sha256:DIGEST]' >&2; exit 2 ;;
  esac
done
for tool in node gcloud; do command -v "$tool" >/dev/null || { echo "$tool is required." >&2; exit 1; }; done
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { console.error("Node.js 22+ is required for the pinned deployment tools."); process.exit(1); }'

mkdir -p .local/gcp
deployment_tmp="$(mktemp -d "$repo_root/.local/gcp/deployment.XXXXXX")"
trap 'rm -rf "$deployment_tmp"' EXIT
node --input-type=module - "$config_path" "$deployment_tmp/config.json" <<'NODE'
import {writeFile} from 'node:fs/promises';
import {readDevConfig} from './scripts/gcp/prepare-site.mjs';
const config = await readDevConfig(process.argv[2]);
await writeFile(process.argv[3], JSON.stringify(config), {mode: 0o600});
NODE
mapfile -t config_values < <(node --input-type=module - "$deployment_tmp/config.json" <<'NODE'
import {readDevConfig} from './scripts/gcp/prepare-site.mjs';
const config = await readDevConfig(process.argv[2]);
for (const name of ['projectId','region','serviceName','registry','connectionName','siteId','runtimeServiceAccount','mysqlSecret','jwtSecret']) console.log(config[name]);
NODE
)
[[ ${#config_values[@]} -eq 9 ]] || { echo 'Invalid development config.' >&2; exit 1; }
project_id="${config_values[0]}"; region="${config_values[1]}"; service="${config_values[2]}"
registry="${config_values[3]}"; connection="${config_values[4]}"; site_id="${config_values[5]}"
runtime_account="${config_values[6]}"; mysql_secret="${config_values[7]}"; jwt_secret="${config_values[8]}"
registry_host="${region}-docker.pkg.dev"
image_base="$registry_host/$project_id/$registry/otthonra-api"

# The bootstrap-created marker prevents this script adopting a different service.
gcloud run services describe "$service" --project "$project_id" --region "$region" --format=json > "$deployment_tmp/service.json"
node --input-type=module - "$deployment_tmp/service.json" <<'NODE'
import {readFile} from 'node:fs/promises';
const service = JSON.parse(await readFile(process.argv[2], 'utf8'));
const labels = service.metadata?.labels ?? {};
if (labels.app !== 'otthonra' || labels.environment !== 'dev' || labels['managed-by'] !== 'otthonra-bootstrap') throw new Error('This is not the bootstrap-managed Otthonra test service; refusing to deploy.');
NODE

# Firebase must use Google ADC rather than a cached Firebase login or token.
# Its configstore uses XDG_CONFIG_HOME; Google ADC keeps its original HOME or
# GOOGLE_APPLICATION_CREDENTIALS selector. The scoped directory expires on exit.
[[ -z "${FIREBASE_TOKEN:-}" ]] || { echo 'Use Google Application Default Credentials for this test deployment; a legacy FIREBASE_TOKEN is not supported.' >&2; exit 1; }
if ! gcloud auth application-default print-access-token > /dev/null 2> "$deployment_tmp/adc-error"; then
  echo 'Google ADC is not ready. In Cloud Shell run: gcloud auth application-default login, then retry. No service or Hosting release was changed.' >&2
  exit 1
fi

if [[ -z "$image_digest" ]]; then
  command -v docker >/dev/null || { echo 'Docker is required to build the API image.' >&2; exit 1; }
  revision="$(git rev-parse HEAD)"
  [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Deploy from a checked-out repository commit.' >&2; exit 1; }
  image_tag="$image_base:$revision"
  gcloud auth configure-docker "$registry_host" --quiet
  docker build --platform linux/amd64 --file backend/Dockerfile --tag "$image_tag" .
  bash scripts/gcp/push-image.sh "$image_tag"
  digest="$(gcloud artifacts docker images describe "$image_tag" --project "$project_id" --format='value(image_summary.digest)')"
  image_digest="$image_base@$digest"
fi
[[ "$image_digest" == "$image_base@sha256:"* ]] && [[ "${image_digest##*@sha256:}" =~ ^[0-9a-f]{64}$ ]] || {
  echo 'Only a digest-pinned image in this project’s test repository may be deployed.' >&2; exit 1;
}

web_origin="https://$site_id.web.app"
gcloud run deploy "$service" \
  --project "$project_id" --region "$region" --platform managed --quiet \
  --image "$image_digest" --service-account "$runtime_account" \
  --execution-environment gen2 --port 8080 --cpu 1 --memory 512Mi --concurrency 20 \
  --min 0 --max 2 --timeout 60 \
  --set-cloudsql-instances "$connection" \
  --set-env-vars "ASPNETCORE_ENVIRONMENT=Production,Deployment__Environment=test,Database__Initialize=true,Database__SeedDemo=false,Credits__EnableDemoTopup=true,Cors__Origins__0=$web_origin" \
  --set-secrets "ConnectionStrings__MySql=$mysql_secret:latest,Jwt__Key=$jwt_secret:latest" \
  --startup-probe 'httpGet.path=/api/health,initialDelaySeconds=0,timeoutSeconds=3,periodSeconds=5,failureThreshold=48' \
  --update-labels 'app=otthonra,environment=dev,managed-by=otthonra-bootstrap'

api_origin="$(gcloud run services describe "$service" --project "$project_id" --region "$region" --format='value(status.url)')"
node --input-type=module - "$api_origin" <<'NODE'
const origin = new URL(process.argv[2]);
if (origin.protocol !== 'https:' || !origin.hostname.endsWith('.run.app')) throw new Error('Cloud Run did not return its expected HTTPS address.');
const response = await fetch(new URL('/api/health', origin), {signal: AbortSignal.timeout(30000)});
const health = response.status === 200 ? await response.json() : null;
if (health?.status !== 'ready' || health.deployment !== 'test' || health.testCreditsEnabled !== true) throw new Error('The deployed test API/database is not a healthy test installation; Hosting was not changed.');
console.log('The deployed test API and database are ready.');
NODE

node scripts/gcp/prepare-site.mjs "$deployment_tmp/config.json" .local/gcp/site
firebase_version="$(node -p 'try { require("./.local/gcp/tools/node_modules/firebase-tools/package.json").version } catch { "missing" }')"
if [[ "$firebase_version" != '14.17.0' ]]; then
  command -v npm >/dev/null || { echo 'npm is required for the Firebase CLI.' >&2; exit 1; }
  npm install --prefix .local/gcp/tools --no-save --no-package-lock firebase-tools@14.17.0
fi
XDG_CONFIG_HOME="$deployment_tmp/firebase-config" .local/gcp/tools/node_modules/.bin/firebase deploy \
  --project "$project_id" --config "$repo_root/.local/gcp/site/firebase.json" --only hosting --non-interactive
node --input-type=module - "$web_origin" <<'NODE'
const origin = process.argv[2];
const [home, runtime, health] = await Promise.all(['/', '/runtime-config.js', '/api/health'].map(async path => {
  const response = await fetch(new URL(path, origin), {signal: AbortSignal.timeout(30000)});
  if (response.status !== 200) throw new Error(`Hosted test check failed for ${path}: HTTP ${response.status}`);
  return response.text();
}));
const backend = JSON.parse(health);
if (!/runtime-config\.js/.test(home) || !/mode:\s*"api"/.test(runtime) || !/environment:\s*"test"/.test(runtime) || backend.status !== 'ready' || backend.deployment !== 'test' || backend.testCreditsEnabled !== true) throw new Error('The hosted frontend is not connected to its live test API.');
console.log(`Test application ready: ${origin}/`);
NODE
