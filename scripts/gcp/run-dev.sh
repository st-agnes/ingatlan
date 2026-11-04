#!/usr/bin/env bash
# First Cloud Shell deployment with persistent, private logs and a short summary.
set -uo pipefail
set +x
umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root" || exit 1
project_id='ingatlan-513620'
if (($#)); then
  if [[ $# -eq 2 && "$1" == --project ]]; then project_id="$2"
  else printf '%s\n' 'Usage: bash scripts/gcp/run-dev.sh [--project PROJECT_ID]' >&2; exit 2; fi
fi
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
for line in lines:
    if re.search(r'ERROR:|unrecognized arguments|Bootstrap validation failed:|Error:|ADC is not ready|is required\.',line,re.I):
        line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line)
        print(line[:240],file=sys.stderr)
        break
PY
    printf 'Napló megnyitása: cloudshell edit %s\n' "$log_path" >&2
    exit "$code"
  fi
}
run_step '1/2 Előkészítés' bash scripts/gcp/bootstrap-dev.sh --project "$project_id"
run_step '2/2 Alkalmazás telepítése' bash scripts/gcp/deploy-dev.sh
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
