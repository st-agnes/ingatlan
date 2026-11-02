#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v node >/dev/null 2>&1; then
  echo 'Node.js 20+ is required. The supplied devcontainer installs Node.js 22 automatically.' >&2
  exit 1
fi
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { console.error("Node.js 20+ is required."); process.exit(1); }'
if ! command -v dotnet >/dev/null 2>&1; then
  if [ ! -x .local/dotnet/dotnet ]; then
    command -v curl >/dev/null 2>&1 || { echo 'curl is required for the .NET SDK installation.' >&2; exit 1; }
    mkdir -p .local/dotnet
    installer_path="$(mktemp)"
    trap 'rm -f "$installer_path"' EXIT
    curl --fail --location --retry 2 --connect-timeout 10 --max-time 120 https://dot.net/v1/dotnet-install.sh --output "$installer_path"
    bash "$installer_path" --channel 8.0 --install-dir "$PWD/.local/dotnet" --no-path
  fi
  export DOTNET_ROOT="$PWD/.local/dotnet"
  export PATH="$DOTNET_ROOT:$PATH"
fi
node scripts/setup-local.mjs
dotnet restore backend/Otthonra.Tests/Otthonra.Tests.csproj
dotnet build backend/Otthonra.Tests/Otthonra.Tests.csproj --no-restore
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj --no-build
node tests/model.test.mjs
node tests/frontend.test.mjs
node tests/api.test.mjs
node tests/development.test.mjs
node tests/locations.test.mjs
printf '%s\n' 'Setup complete. Start .NET, MySQL, and the web UI with: node scripts/dev.mjs'
