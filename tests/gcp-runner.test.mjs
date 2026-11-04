import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, readFile, writeFile, copyFile, rm, stat} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

async function fixture(bootstrap, deploy, action) {
  const root = await mkdtemp(join(tmpdir(), 'otthonra-runner-'));
  try {
    await mkdir(join(root, 'scripts/gcp'), {recursive: true});
    await copyFile(new URL('../scripts/gcp/run-dev.sh', import.meta.url), join(root, 'scripts/gcp/run-dev.sh'));
    await writeFile(join(root, 'scripts/gcp/bootstrap-dev.sh'), bootstrap);
    await writeFile(join(root, 'scripts/gcp/deploy-dev.sh'), deploy);
    const run = (...args) => spawnSync('bash', ['scripts/gcp/run-dev.sh', ...args], {cwd: root, encoding: 'utf8', timeout: 5000});
    await action({root, run});
  } finally { await rm(root, {recursive: true, force: true}); }
}

test('bootstrap failure keeps full private log, summarizes the error after help and never deploys', async () => {
  await fixture('printf "ERROR: unknown argument --labels\\n"; for i in {1..60}; do echo "Google help line $i"; done; exit 2', 'touch DEPLOYED', async ({root, run}) => {
    const result = run();
    assert.equal(result.status, 2);
    assert.match(result.stderr, /MEGÁLLT: 1\/2/);
    assert.match(result.stderr, /ERROR: unknown argument --labels/);
    assert.match(result.stderr, /cloudshell edit/);
    assert.doesNotMatch(result.stdout + result.stderr, /Google help line/);
    assert.ok((await readFile(join(root, '.local/gcp/deployment.log'), 'utf8')).includes('Google help line 60'));
    assert.equal((await stat(join(root, '.local/gcp/deployment.log'))).mode & 0o777, 0o600);
    await assert.rejects(stat(join(root, 'DEPLOYED')), {code: 'ENOENT'});
  });
});

test('deployment failure is reported as phase two without claiming readiness', async () => {
  await fixture('echo bootstrap-done', 'echo "Google ADC is not ready. In Cloud Shell run: gcloud auth application-default login"; exit 1', async ({run}) => {
    const result = run();
    assert.equal(result.status, 1);
    assert.match(result.stderr, /MEGÁLLT: 2\/2/);
    assert.match(result.stderr, /gcloud auth application-default login/);
    assert.doesNotMatch(result.stdout, /KÉSZ:/);
  });
});

test('verified deployment prints a short final URL and preserves the prior run on retry', async () => {
  await fixture('echo bootstrap-done', 'echo "Test application ready: https://otthonra-dev-123456789012.web.app/"', async ({root, run}) => {
    let result = run(); assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /KÉSZ:/);
    assert.match(result.stdout, /https:\/\/otthonra-dev-123456789012.web.app\//);
    const first = await readFile(join(root, '.local/gcp/deployment.log'), 'utf8');
    result = run(); assert.equal(result.status, 0, result.stderr);
    assert.equal(await readFile(join(root, '.local/gcp/deployment.log.previous'), 'utf8'), first);
  });
});

test('a zero exit without the verified deployment marker cannot report a working application', async () => {
  await fixture('echo bootstrap-done', 'echo placeholder-only', async ({run}) => {
    const result = run();
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stdout, /KÉSZ:/);
    assert.match(result.stderr, /működés nincs igazolva/);
  });
});


test('a Firebase failure keeps the useful Google reason and action in the short terminal summary', async () => {
  await fixture("echo 'Google Firebase API request failed: Firebase project lookup (HTTP 403).'\necho 'Google ErrorInfo: reason=USER_PROJECT_DENIED; service=firebase.googleapis.com; consumer=projects/120611818277'\necho 'Google status: PERMISSION_DENIED'\necho 'Google message: The quota project requires serviceusage.services.use permission.'\necho 'Quota project: serviceusage.services.use permission is required on the selected project.'\necho 'Unrelated log details must remain in the private file.'\nexit 1", 'touch DEPLOYED', async ({root, run}) => {
    const result = run();
    assert.equal(result.status, 1);
    assert.match(result.stderr, /reason=USER_PROJECT_DENIED/);
    assert.match(result.stderr, /Google status: PERMISSION_DENIED/);
    assert.match(result.stderr, /serviceusage.services.use/);
    assert.doesNotMatch(result.stdout + result.stderr, /Unrelated log details/);
    await assert.rejects(stat(join(root, 'DEPLOYED')), {code: 'ENOENT'});
  });
});


test('deploy-only resumes the application deployment without rerunning completed infrastructure setup', async () => {
  await fixture('touch BOOTSTRAP_RAN; exit 92', 'echo "Test application ready: https://otthonra-dev-123456789012.web.app/"', async ({root, run}) => {
    const result = run('--deploy-only');
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /1\/1 Alkalmazás telepítése/);
    assert.match(result.stdout, /KÉSZ:/);
    assert.doesNotMatch(result.stdout, /Előkészítés/);
    await assert.rejects(stat(join(root, 'BOOTSTRAP_RAN')), {code: 'ENOENT'});
  });
});


test('a recovered earlier error cannot mask the final deployment failure', async () => {
  await fixture('echo "ERROR: earlier network attempt recovered"', 'echo "ERROR: final Cloud Run deployment failed"; exit 1', async ({run}) => {
    const result = run();
    assert.equal(result.status, 1);
    assert.match(result.stderr, /ERROR: final Cloud Run deployment failed/);
    assert.doesNotMatch(result.stderr, /earlier network attempt/);
  });
});


test('deploy-only cannot silently ignore an explicitly selected project', async () => {
  await fixture('touch BOOTSTRAP_RAN', 'touch DEPLOY_RAN', async ({root, run}) => {
    const result = run('--deploy-only', '--project', 'different-project-123');
    assert.equal(result.status, 2);
    assert.match(result.stderr, /do not combine it with --project/);
    await assert.rejects(stat(join(root, 'BOOTSTRAP_RAN')), {code: 'ENOENT'});
    await assert.rejects(stat(join(root, 'DEPLOY_RAN')), {code: 'ENOENT'});
  });
});


test('deploy-only forwards an explicit existing image intact and keeps readiness verification', async () => {
  const image = 'europe-west1-docker.pkg.dev/ingatlan-513620/otthonra-dev/otthonra-api@sha256:' + 'a'.repeat(64);
  await fixture('touch BOOTSTRAP_RAN; exit 92', 'printf "%s\\n" "$@" > DEPLOY_ARGS\necho "Test application ready: https://otthonra-dev-123456789012.web.app/"', async ({root, run}) => {
    const result = run('--deploy-only', '--image', image);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(await readFile(join(root, 'DEPLOY_ARGS'), 'utf8'), `--image\n${image}\n`);
    assert.match(result.stdout, /KÉSZ:/);
    await assert.rejects(stat(join(root, 'BOOTSTRAP_RAN')), {code: 'ENOENT'});
  });
});

test('an explicit existing image requires deploy-only before any setup or deployment runs', async () => {
  await fixture('touch BOOTSTRAP_RAN', 'touch DEPLOY_RAN', async ({root, run}) => {
    const result = run('--image', 'existing-image');
    assert.equal(result.status, 2);
    assert.match(result.stderr, /--image requires --deploy-only/);
    await assert.rejects(stat(join(root, 'BOOTSTRAP_RAN')), {code: 'ENOENT'});
    await assert.rejects(stat(join(root, 'DEPLOY_RAN')), {code: 'ENOENT'});
  });
});
