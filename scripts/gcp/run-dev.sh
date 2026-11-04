#!/usr/bin/env bash
# First Cloud Shell deployment with persistent, private logs and a short summary.
set -uo pipefail
set +x
umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root" || exit 1
project_id='ingatlan-513620'
deploy_only=false
project_supplied=false
image_digest=''
while (($#)); do
  case "$1" in
    --project) project_id="${2:?Missing project ID}"; project_supplied=true; shift 2 ;;
    --deploy-only) deploy_only=true; shift ;;
    --image) image_digest="${2:?Missing image digest}"; shift 2 ;;
    *) printf '%s\n' 'Usage: bash scripts/gcp/run-dev.sh [--project PROJECT_ID] [--deploy-only [--image REGISTRY_IMAGE@sha256:DIGEST]]' >&2; exit 2 ;;
  esac
done
if "$deploy_only" && "$project_supplied"; then
  printf '%s\n' 'ERROR: --deploy-only uses the validated dev-config.json project; do not combine it with --project.' >&2
  exit 2
fi
if [[ -n "$image_digest" ]] && ! "$deploy_only"; then
  printf '%s\n' 'ERROR: --image requires --deploy-only and an already prepared dev-config.json.' >&2
  exit 2
fi
deploy_args=()
if [[ -n "$image_digest" ]]; then deploy_args+=(--image "$image_digest"); fi
mkdir -p .local/gcp || exit 1
log_path="$repo_root/.local/gcp/deployment.log"
if [[ -f "$log_path" ]]; then mv "$log_path" "$log_path.previous" || exit 1; fi
: > "$log_path" || exit 1
chmod 600 "$log_path" || exit 1
run_step() {
  local label="$1"; shift
  printf '%s\n' "$label (részletek a naplóban)"
  if "$@" >> "$log_path" 2>&1; then return 0
  else
    local code=$?
    printf 'MEGÁLLT: %s; hibakód: %s\n' "$label" "$code" >&2
    python3 - "$log_path" <<'PY'
import pathlib,re,sys
lines=pathlib.Path(sys.argv[1]).read_text(errors='replace').splitlines()
api_prefixes=('Google Firebase API request failed:', 'Firebase provisioning operation failed.', 'Google ErrorInfo:', 'Google status:', 'Google message:', 'Firebase Terms:', 'Quota project:')
api_start=next((i for i,line in enumerate(lines) if line.startswith(api_prefixes[:2])),None)
if api_start is not None:
    for line in lines[api_start:api_start+7]:
        if line.startswith(api_prefixes):
            print(line[:400],file=sys.stderr)
else:
    for line in reversed(lines):
        if re.search(r'ERROR:|unrecognized arguments|Bootstrap validation failed:|Error:|ADC is not ready|is required\.|Google access token',line,re.I):
            line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line)
            print(line[:240],file=sys.stderr)
            break
PY
    printf 'Napló megnyitása: cloudshell edit %s\n' "$log_path" >&2
    exit "$code"
  fi
}
if "$deploy_only"; then
  run_step '1/1 Alkalmazás telepítése' bash scripts/gcp/deploy-dev.sh "${deploy_args[@]}"
else
  run_step '1/2 Előkészítés' bash scripts/gcp/bootstrap-dev.sh --project "$project_id"
  run_step '2/2 Alkalmazás telepítése' bash scripts/gcp/deploy-dev.sh "${deploy_args[@]}"
fi
python3 - "$log_path" <<'PY'
import pathlib,re,sys
log=pathlib.Path(sys.argv[1]).read_text(errors='replace')
urls=re.findall(r'Test application ready: (https://otthonra-dev-[1-9][0-9]{5,16}\.web\.app/)',log)
if not urls:
    print('A parancsok lefutottak, de a működés nincs igazolva. Futtasd: node scripts/gcp/status-dev.mjs',file=sys.stderr)
    sys.exit(1)
print('KÉSZ: a tesztalkalmazás és az adatbázis ellenőrzése sikeres.')
print(urls[-1])
PY
