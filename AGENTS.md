# Working in this repository

This is Otthonra, a Hungarian real-estate matching application. The backend is .NET 8 with EF Core/Pomelo and MySQL 8. The browser frontend is buildless native JavaScript/CSS in `dist/`; no npm install or frontend compilation is needed.

## Prepare and run

- The `.devcontainer/` configuration supplies the .NET SDK, Node.js 22, and MySQL, then runs the setup/start commands automatically.
- In another supported development environment, run `bash scripts/cloud-setup.sh`. It installs a missing SDK into ignored `.local/dotnet`, restores, builds, and checks the project.
- The development web port is configured once by `scripts/development-config.mjs` (default 3000); listener, readiness and forwarded URLs must agree. Full Docker Compose keeps its separate web port 8080.
- Use `node scripts/dev.mjs --restart` to wait for a complete stop and start. Start/stop commands serialize through a local lock; postStart and postAttach may call them together. Keep owned API/web process groups independent and restart failed children without taking the web down on API failure. Status is read-only: `node scripts/dev.mjs --status`.
- Start services with `node scripts/dev.mjs --background`; logs are in `.local/dev.log`. Stop the supervisor with `node scripts/dev.mjs --stop`.
- `ConnectionStrings__MySql` selects a supplied database. Without it, the development supervisor starts the root Compose MySQL service.
- The web UI is on port 3000 and proxies `/api` to .NET. Use the forwarded web origin when connecting from a phone or remote browser.
- The backend Docker build context is the repository root (`docker build -f backend/Dockerfile .`), because it embeds `dist/data/settlements.json` shared with the browser.
- With `Database__Initialize=true`, startup runs `EnsureCreated` and then the additive, repeatable `SchemaUpgrade` version `20261102-locations-and-lot-area`. Existing rows use canonical legacy-location fallback; do not delete the database or Docker volume to apply this upgrade. This is a targeted upgrade, not a general EF migration system.
- In a managed cloud, use its provided network/proxy/CA and Docker instructions. Diagnose denied operations or service errors rather than disabling sandboxing, TLS verification, or credential protections.

## Google Cloud test deployment

- The current authorized cloud scope is TEST only in project `ingatlan-513620`, region `europe-west1`. Create only the named `-dev` resources. Custom DNS and production provisioning are separate work.
- `bash scripts/gcp/run-dev.sh` performs the first bootstrap/deploy with a private `.local/gcp/deployment.log`, a short error summary and final verified URL. `node scripts/gcp/status-dev.mjs` is read-only and must never treat a Cloud Run placeholder or browser demo as a successful installation. SQL ownership labels require the documented **beta** `gcloud beta sql instances create`; the GA create command rejects `--labels`.
- `scripts/gcp/bootstrap-dev.sh --project ingatlan-513620 --plan` reads project/billing metadata; the normal bootstrap provisions the dev infrastructure and writes ignored `.local/gcp/dev-config.json`. `scripts/gcp/deploy-dev.sh` builds/deploys the API and Firebase Hosting site. The user runs the first bootstrap/deployment in their own Cloud Shell; repository access alone does not provide Google Cloud credentials here.
- Initial Cloud Run absence is reported by the SDK as `Cannot find service [NAME]`. Handle this only for `run services describe` and the exact requested name, then create the owned dev service. Permission, credential, network and CLI errors must remain fatal; a generic missing endpoint does not establish resource absence.
- Firebase REST requests must bind `X-Goog-User-Project` to the validated target project. Stop before curl on missing/failed access-token generation. For non-2xx replies, report the operation, HTTP code and bounded/redacted Google error status/message/ErrorInfo fields; never dump response bodies or successful app configuration. A 403 is not evidence of Firebase absence: only 404 permits addFirebase. A `Firebase Tos Not Accepted` error requires the user to accept terms in Firebase Console.
- Keep generated SQL/JWT secrets in Secret Manager and private temporary files. The config manifest contains resource identifiers, not secret payloads. Do not print tokens, connection strings, passwords, credential files or service-account JSON keys.
- Hosted frontend configuration is generated into staging: `globalThis.OTTHONRA_CONFIG = Object.freeze({mode: 'api', environment: 'test'})`. The tracked config defaults to the local demo. Hosted login uses the current origin, logout/401 returns to authentication, and server failures must not silently fall back to demo data.
- The hosted test backend uses ASP.NET `Production`, `Deployment__Environment=test`, no demo seed, and explicitly enabled nonpayment test credits. The server controls the capability; ordinary Production must not expose the free top-up endpoint even when the enable flag is true. Test deployments reject live Stripe keys.
- Later GitHub releases use `.github/workflows/deploy-dev.yml`, the nonsecret `GCP_DEV_CONFIG` repository variable and short-lived OIDC/Workload Identity Federation. Only the approved repository/workflow and `main` or `codex/google-cloud-test` refs may deploy, after CI succeeds on the selected commit.
- Firebase Hosting deployment IAM is currently project-scoped. Do not claim that the `-dev` site name provides IAM isolation from a future production site; revisit access before adding production. The dev SQL user belongs to its own dev SQL instance.
- See `docs/GOOGLE-CLOUD-TEST.md` for Cloud Shell commands, ADC setup, costs and manual release steps. Mock/CI success is not proof that the user's Google Cloud environment is live.

## Validation

Run the checks appropriate to the change:

```sh
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj
node tests/model.test.mjs
node tests/frontend.test.mjs
node tests/api.test.mjs
node tests/development.test.mjs
node tests/locations.test.mjs
node tests/gcp-deployment.test.mjs
node tests/gcp-bootstrap.test.mjs
node tests/gcp-firebase.test.mjs
node tests/gcp-runner.test.mjs
node tests/gcp-status.test.mjs
```

With Development API and MySQL running, `node backend/smoke.mjs http://localhost:3000` checks real authorization, contact privacy, matching, messaging, and concurrent single credit billing through the web proxy. It creates disposable test accounts. GitHub Actions runs the complete suite with an ephemeral MySQL service.

Passing mock/offline tests does not establish .NET or real MySQL success; report those only after checking CI for the actual commit. The Google Cloud bootstrap and packaging tests use local fixtures/mocks and must not create billable resources. CI runs `node tests/development-smoke.mjs` against its disposable database to verify custom ports, concurrent startup, completed shutdown, immediate restart and child crash recovery. CI also verifies upgrading an initial-release schema and starting it again without losing data.

The real-browser regressions in `tests/browser.test.mjs` check input geometry, pointer/touch and keyboard dismissal, and search creation/activation at desktop, tablet, and mobile sizes. CI installs pinned Playwright into ignored `.local/browser-tests` and runs `node tests/browser.test.mjs http://localhost:3000` while the web server is running. Browser failure screenshots are CI artifacts.

## Business and data rules

- Creating a search must confirm the saved entity and offer discovery. Activate its saved ID only when the user chooses discovery; await activation before navigation. Dismissal preserves the previous active entity. Editing does not reopen the creation prompt.
- Location suggestions must not obscure their input. Outside pointer/focus closes suggestions without selecting or erasing text; clean up per-editor document listeners when the modal closes or is replaced.
- An account can own multiple properties and searches. Every action checks ownership and the active entity.
- Only compatible property/search pairs enter the feed; already judged pairs stay excluded for that side.
- A property selects one canonical `locationId`; a search selects a nonempty `locationIds` array. Public `GET /api/locations?q=&limit=` returns `{items:[{id,label,city,district}]}`. Explicit unknown IDs must fail validation. Keep legacy city/district reads compatible only with known catalogue values.
- Search locations use OR semantics across towns and Budapest districts. `city:Budapest` covers all districts; `district:Budapest:5` covers only district V. All other search filters still apply.
- Preserve nullable search bounds through form, storage and API serialization. In particular, blank `minPrice`, `maxArea` and `maxRooms` remain `null` and mean unbounded; do not coerce them to zero or a synthetic upper bound.
- `lotArea` is a nullable positive property measurement in square metres for `Ház`; clear it for other property types. There are no search plot-area bounds.
- `dist/data/settlements.json` is the canonical shared municipality source, embedded by .NET; `dist/locations-data.js` is its generated browser module. Source, license and update instructions are in `docs/LOCATION-DATA.md`. Preserve existing demo storage key `otthonra.demo.v3`, IDs, decisions, matches and balances when upgrading records.
- Search-side likes are free. A property-side like costs two credits exactly once. Credit balance, ledger, decision, and match updates must remain transactional.
- Public cards contain no contact details or exact address. Only a reciprocal match permits contact access and messaging.
- Keep runtime EF Core packages on the same patch version; Design is private but runtime references must flow to test/client projects.
- Large public text and JSON map to MySQL longtext with explicit input size limits.
- `.env`, `.local`, build output, logs, and credentials are excluded from version control. Use `scripts/setup-local.mjs` to generate local secrets without printing them.
- Stripe values are server-side configuration. Credit only verified paid webhook events, idempotently; the checkout return URL must never grant credits.
