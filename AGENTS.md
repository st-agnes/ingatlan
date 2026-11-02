# Working in this repository

This is Otthonra, a Hungarian real-estate matching application. The backend is .NET 8 with EF Core/Pomelo and MySQL 8. The browser frontend is buildless native JavaScript/CSS in `dist/`; no npm install or frontend compilation is needed.

## Prepare and run

- The `.devcontainer/` configuration supplies the .NET SDK, Node.js 22, and MySQL, then runs the setup/start commands automatically.
- In another supported development environment, run `bash scripts/cloud-setup.sh`. It installs a missing SDK into ignored `.local/dotnet`, restores, builds, and checks the project.
- Start services with `node scripts/dev.mjs --background`; logs are in `.local/dev.log`. Stop the supervisor with `node scripts/dev.mjs --stop`.
- `ConnectionStrings__MySql` selects a supplied database. Without it, the development supervisor starts the root Compose MySQL service.
- The web UI is on port 8080 and proxies `/api` to .NET. Use the forwarded web origin when connecting from a phone or remote browser.
- The backend Docker build context is the repository root (`docker build -f backend/Dockerfile .`), because it embeds `dist/data/settlements.json` shared with the browser.
- With `Database__Initialize=true`, startup runs `EnsureCreated` and then the additive, repeatable `SchemaUpgrade` version `20261102-locations-and-lot-area`. Existing rows use canonical legacy-location fallback; do not delete the database or Docker volume to apply this upgrade. This is a targeted upgrade, not a general EF migration system.
- In a managed cloud, use its provided network/proxy/CA and Docker instructions. Diagnose denied operations or service errors rather than disabling sandboxing, TLS verification, or credential protections.

## Validation

Run the checks appropriate to the change:

```sh
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj
node tests/model.test.mjs
node tests/frontend.test.mjs
node tests/api.test.mjs
node tests/development.test.mjs
node tests/locations.test.mjs
```

With Development API and MySQL running, `node backend/smoke.mjs http://localhost:8080` checks real authorization, contact privacy, matching, messaging, and concurrent single credit billing through the web proxy. It creates disposable test accounts. GitHub Actions runs the complete suite with an ephemeral MySQL service.

The JavaScript suites currently contain 48 tests: locations 5, model 14, API adapter 12, frontend 10, and development 7. Passing mock/offline tests does not establish .NET or real MySQL success; report those only after checking CI. CI also verifies upgrading an initial-release schema and starting it again without losing data.

## Business and data rules

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
