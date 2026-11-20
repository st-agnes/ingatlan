import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

// Execute the real actions/github-script preflight, rather than a second copy
// of its release-authorization predicate. No GitHub or cloud calls are made.
const root = fileURLToPath(new URL('../', import.meta.url));
const workflow = await readFile(new URL('../.github/workflows/deploy-dev.yml', import.meta.url), 'utf8');
const validateJob = workflow.slice(workflow.indexOf('  validate:'), workflow.indexOf('\n  deploy:'));
const script = validateJob.match(/^          script: \|\n((?:^            .*\n|^\n)*)/m)?.[1]
  .split('\n').map(line => line.startsWith('            ') ? line.slice(12) : line).join('\n');
assert.ok(script, 'The deployment must retain an executable CI preflight before cloud authentication.');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const preflight = new AsyncFunction('require', 'process', 'github', 'context', 'core', script);
const require = createRequire(import.meta.url);
const sha = 'a'.repeat(40);
const config = Object.freeze({
  projectId: 'ingatlan-513620', projectNumber: '123456789012', region: 'europe-west1',
  serviceName: 'otthonra-api-dev', registry: 'otthonra-dev', sqlInstance: 'otthonra-mysql-dev',
  connectionName: 'ingatlan-513620:europe-west1:otthonra-mysql-dev', databaseName: 'otthonra_dev',
  databaseUser: 'otthonra_dev', mysqlSecret: 'otthonra-mysql-dev', jwtSecret: 'otthonra-jwt-dev',
  siteId: 'otthonra-dev-123456789012',
  runtimeServiceAccount: 'otthonra-runtime-dev@ingatlan-513620.iam.gserviceaccount.com',
  deployServiceAccount: 'otthonra-deploy-dev@ingatlan-513620.iam.gserviceaccount.com',
  workloadIdentityProvider: 'projects/123456789012/locations/global/workloadIdentityPools/otthonra-dev/providers/github'
});
const run = (change = {}) => ({
  id: 44637247992, head_sha: sha, event: 'push', status: 'completed', conclusion: 'success',
  path: '.github/workflows/ci.yml', head_repository: {id: 1441962351, full_name: 'st-agnes/ingatlan'}, ...change
});

function harness(rows = [], {manifest = JSON.stringify(config), requestError = null} = {}) {
  const outputs = new Map(), queries = [], messages = [];
  const github = {rest: {actions: {async listWorkflowRuns(query) {
    queries.push(query);
    if (requestError) throw requestError;
    // Reproduce the observed GitHub response: a server-side status filter can
    // hide a trusted, completed successful push even for the exact head SHA.
    return {data: {workflow_runs: Object.hasOwn(query, 'status') ? [] : rows}};
  }}}};
  const context = {repo: {owner: 'st-agnes', repo: 'ingatlan'}, sha};
  const core = {
    setOutput: (name, value) => outputs.set(name, value),
    info: message => messages.push(String(message)),
    warning: message => messages.push(String(message))
  };
  const environment = {env: {GITHUB_WORKSPACE: root, ...(manifest === null ? {} : {GCP_DEV_CONFIG: manifest})}};
  return {outputs, queries, messages, execute: () => preflight(require, environment, github, context, core)};
}

function approved(h) {
  assert.deepEqual(JSON.parse(h.outputs.get('config')), config);
  assert.equal(h.outputs.get('workload_identity_provider'), config.workloadIdentityProvider);
  assert.equal(h.outputs.get('service_account'), config.deployServiceAccount);
  assert.equal(h.outputs.get('project_id'), config.projectId);
  assert.equal(h.outputs.size, 4);
  assert.equal(h.queries.length, 1);
  assert.deepEqual(h.queries[0], {
    owner: 'st-agnes', repo: 'ingatlan', workflow_id: 'ci.yml', head_sha: sha, per_page: 100
  });
}

test('a successful automatic CI run is found without the GitHub status filter that hid it', async () => {
  const h = harness([run()]);
  await h.execute();
  approved(h);
});

test('a manually dispatched full CI run can authorize the same exact trusted commit', async () => {
  const h = harness([run({event: 'workflow_dispatch'})]);
  await h.execute();
  approved(h);
});

test('a successful run remains eligible among failed, pending and unrelated history', async () => {
  const h = harness([
    run({id: 3, status: 'completed', conclusion: 'failure'}),
    run({id: 2, head_sha: 'b'.repeat(40)}),
    run({id: 1, status: 'in_progress', conclusion: null}),
    run({id: 4, event: 'workflow_dispatch'})
  ]);
  await h.execute();
  approved(h);
});

for (const [label, change] of [
  ['a different commit', {head_sha: 'b'.repeat(40)}],
  ['a queued run', {status: 'queued'}],
  ['an unfinished run', {status: 'in_progress'}],
  ['a missing completion status', {status: undefined}],
  ['a failed run', {conclusion: 'failure'}],
  ['a cancelled run', {conclusion: 'cancelled'}],
  ['a skipped run', {conclusion: 'skipped'}],
  ['a pull request run', {event: 'pull_request'}],
  ['a pull request target run', {event: 'pull_request_target'}],
  ['a repository dispatch', {event: 'repository_dispatch'}],
  ['a fork run', {head_repository: {id: 987654321, full_name: 'fork/ingatlan'}}],
  ['missing source repository identity', {head_repository: null}],
  ['a different workflow', {path: '.github/workflows/deploy-dev.yml'}],
  ['missing workflow identity', {path: undefined}]
]) test(`release authorization rejects ${label}`, async () => {
  const h = harness([run(change)]);
  await assert.rejects(h.execute(), /No successful completed.*integration tests run was found for this exact commit/i);
  assert.equal(h.outputs.size, 0, 'Rejected CI cannot publish deployment configuration or identities.');
});

test('no matching workflow run fails before publishing cloud configuration', async () => {
  const h = harness([]);
  await assert.rejects(h.execute(), /No successful completed.*integration tests run was found for this exact commit/i);
  assert.equal(h.outputs.size, 0);
});

test('invalid or missing deployment configuration is rejected before querying GitHub', async () => {
  for (const manifest of [null, '', '{invalid-json', JSON.stringify({...config, serviceName: 'otthonra-api-prod'})]) {
    const h = harness([run()], {manifest});
    await assert.rejects(h.execute());
    assert.equal(h.queries.length, 0);
    assert.equal(h.outputs.size, 0);
  }
});

test('GitHub lookup failure cannot authorize cloud access or emit configuration', async () => {
  const h = harness([run()], {requestError: new Error('The CI lookup is unavailable.')});
  await assert.rejects(h.execute());
  assert.equal(h.outputs.size, 0);
});

test('validation stays read only and cloud authentication depends on its successful result', () => {
  assert.match(validateJob, /contents: read/);
  assert.match(validateJob, /actions: read/);
  assert.doesNotMatch(validateJob, /id-token: write|google-github-actions\/auth|setup-gcloud|gcloud\s/);
  const deployJob = workflow.slice(workflow.indexOf('\n  deploy:'));
  assert.match(deployJob, /needs: validate/);
  assert.match(deployJob, /google-github-actions\/auth@/);
});
