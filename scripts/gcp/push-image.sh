#!/usr/bin/env bash
# Upload one validated dev image; retry only explicit transient network failures.
set -uo pipefail
set +x
umask 077

if [[ $# -ne 1 || ! "$1" =~ ^europe-west1-docker\.pkg\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/otthonra-dev/otthonra-api:[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'ERROR: Docker image upload failed: expected a commit-tagged image in this project’s europe-west1 otthonra-dev repository.' >&2
  exit 2
fi
image="$1"
for upload_tool in docker timeout; do
  if ! command -v "$upload_tool" >/dev/null; then
    printf 'ERROR: Docker image upload failed: required tool %s is unavailable.\n' "$upload_tool" >&2
    exit 1
  fi
done
upload_tmp="$(mktemp -d)" || exit 1
trap 'rm -rf "$upload_tmp"' EXIT

# An access/configuration failure must not become retryable merely because an
# endpoint or explanatory message also mentions a connection or timeout.
fatal_pattern='unauthorized:|forbidden:|permission[[:space:]_]+denied|denied:|authentication (required|failed)|no basic auth credentials|invalid (username|password|token)|error getting credentials|[[:space:]](401|403)([[:space:]:;,.]|$)|status( code)?[[:space:]:]+(401|403)|x509:|unknown authority|SSL certificate|certificate (signed|verify|verification|has expired|is not|validation)|bad certificate|manifest (invalid|unknown)|invalid manifest|unsupported media type|name unknown|repository .*not (found|exist)|invalid reference|tag.*(invalid|immutable)|invalid (repository|tag)|cannot connect to the docker daemon'
network_pattern='connection refused|connection reset|i/o timeout|dial tcp.*timeout|TLS handshake timeout|context deadline exceeded|network is unreachable|no such host|temporary failure in name resolution|unexpected EOF'

for attempt in 1 2 3; do
  attempt_log="$upload_tmp/attempt-$attempt.log"
  printf 'Docker image upload: attempt %s/3.\n' "$attempt"
  if timeout --signal=TERM --kill-after=5s 180s docker push "$image" >"$attempt_log" 2>&1; then
    cat "$attempt_log"
    printf '%s\n' 'Docker image upload completed.'
    exit 0
  else
    upload_status=$?
  fi
  cat "$attempt_log"
  if LC_ALL=C grep -Eiq "$fatal_pattern" "$attempt_log"; then
    printf 'ERROR: Docker image upload failed: access, certificate, image or repository error; no retry (exit %s).\n' "$upload_status" >&2
    exit "$upload_status"
  fi
  if [[ "$upload_status" -eq 124 ]] || LC_ALL=C grep -Eiq "$network_pattern" "$attempt_log"; then
    if [[ "$upload_status" -eq 124 ]]; then
      network_detail='the upload attempt timed out after 180 seconds'
    elif LC_ALL=C grep -Eiq 'connection refused' "$attempt_log"; then
      network_detail='the registry connection was refused'
    elif LC_ALL=C grep -Eiq 'no such host|temporary failure in name resolution' "$attempt_log"; then
      network_detail='registry DNS resolution failed'
    else
      network_detail='the registry connection was interrupted or timed out'
    fi
    if [[ "$attempt" -lt 3 ]]; then
      printf 'Registry network error: %s; retrying the same image.\n' "$network_detail" >&2
      sleep "$((attempt * 2))"
      continue
    fi
    printf 'ERROR: Docker image upload failed after 3 attempts: %s (exit %s).\n' "$network_detail" "$upload_status" >&2
    exit "$upload_status"
  fi
  printf 'ERROR: Docker image upload failed: unclassified error; no retry (exit %s).\n' "$upload_status" >&2
  exit "$upload_status"
done
