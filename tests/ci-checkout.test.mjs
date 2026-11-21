import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, readFile, rm, stat, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {spawnSync} from 'node:child_process';
import {openSync, closeSync} from 'node:fs';

const root = new URL('../', import.meta.url);
const patterns = await readFile(new URL('scripts/ci/checkout-patterns.txt', root), 'utf8');
const planningPatterns = await readFile(new URL('scripts/ci/planning-checkout-patterns.txt', root), 'utf8');
const workflow = await readFile(new URL('.github/workflows/ci.yml', root), 'utf8');

function checkoutBlocks(source) {
  const lines = source.split(/\r?\n/), blocks = [];
  let job;
  for (let index = 0; index < lines.length; index++) {
    const jobMatch = lines[index].match(/^  ([a-z0-9_-]+):\s*$/);
    if (jobMatch) job = jobMatch[1];
    const match = lines[index].match(/^(\s*)-\s+uses:\s+actions\/checkout@\S+\s*$/);
    if (!match) continue;
    const indent = match[1].length, block = [lines[index]];
    for (let next = index + 1; next < lines.length; next++) {
      if (lines[next].trim() && lines[next].match(/^\s*/)[0].length <= indent) break;
      block.push(lines[next]);
    }
    blocks.push({job, text: block.join('\n')});
  }
  return blocks;
}

function literalPatterns(block) {
  const lines = block.split('\n');
  const index = lines.findIndex(line => /^\s*sparse-checkout:\s*\|[-+]?\s*$/.test(line));
  assert.ok(index >= 0, 'Every CI checkout must declare the reviewed sparse patterns.');
  const indent = lines[index].match(/^\s*/)[0].length, content = [];
  for (const line of lines.slice(index + 1)) {
    if (!line.trim()) continue;
    if (line.match(/^\s*/)[0].length <= indent) break;
    content.push(line.trim());
  }
  return content.join('\n') + '\n';
}

test('all CI checkouts use the reviewed sparse patterns and let checkout enable blob filtering', () => {
  const blocks = checkoutBlocks(workflow);
  assert.ok(blocks.length > 0, 'The real CI workflow must contain checkout steps.');
  for (const {job, text: block} of blocks) {
    assert.equal(literalPatterns(block), ['plan', 'ci-validation'].includes(job) ? planningPatterns : patterns, job);
    assert.match(block, /^\s*sparse-checkout-cone-mode:\s*false\s*$/m);
    // checkout v4 automatically fetches blob:none for a sparse checkout. Its
    // explicit filter input overrides sparse-checkout, so never combine them.
    assert.doesNotMatch(block, /^\s*filter:/m);
  }
  for (const job of ['plan', 'ci-validation']) assert.equal(blocks.filter(block => block.job === job).length, 1, `${job} must use one explicit minimal checkout.`);
});

for (const planning of [false, true]) test(planning
  ? 'real Git planning checkout keeps only the verifier and workflow with the full tree identity'
  : 'real Git sparse checkout retains code and pinned input data while omitting research archives', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'otthonra-ci-checkout-'));
  const source = join(directory, 'source'), checkout = join(directory, 'checkout');
  const required = [
    'README.md', 'AGENTS.md', '.dockerignore', '.env.example', 'docker-compose.yml',
    '.github/workflows/ci.yml', '.devcontainer/devcontainer.json', 'docs/MAP-SEARCH.md',
    'backend/Otthonra.Api/Otthonra.Api.csproj', 'backend/fixtures/previous-schema.sql',
    'dist/app.js', 'dist/vendor/leaflet/leaflet.js', 'dist/data/neighborhoods.json.gz',
    'dist/data/map/index.json', 'dist/data/map/city-0123456789abcdef0123.json',
    'scripts/dev.mjs', 'scripts/ci/checkout-patterns.txt', 'scripts/ci/reuse-validation.mjs', 'tests/ci-checkout.test.mjs',
    'future-code/worker.js', 'data/streets/source.json', 'data/streets/coverage.json',
    'data/streets/sources/StreetNames.xml.gz', 'data/neighborhoods/search-areas.geojson.gz',
    'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
  ];
  const excluded = [
    'data/neighborhoods/catalog.geojson', 'data/neighborhoods/coverage.json',
    'data/neighborhoods/sources/country-osm/construction-lines.geojson.gz',
    'data/neighborhoods/expansion-20261115/downloaded-sources/municipal-map.pdf',
    'data/future-research/archive.dat'
  ];
  const git = (cwd, args, inputPath) => {
    const descriptor = inputPath ? openSync(inputPath, 'r') : null;
    try {
      const result = spawnSync('git', args, {cwd, stdio: [descriptor ?? 'ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 10000});
      assert.equal(result.status, 0, `git ${args[0]} failed: ${result.stderr || result.error || ''}`);
      return result.stdout.trim();
    } finally {
      if (descriptor !== null) closeSync(descriptor);
    }
  };
  try {
    await mkdir(source);
    git(source, ['init', '--quiet', '--initial-branch=main']);
    for (const path of [...required, ...excluded]) {
      await mkdir(join(source, path, '..'), {recursive: true});
      await writeFile(join(source, path), `tracked fixture for ${path}\n`);
    }
    git(source, ['add', '--all']);
    git(source, ['-c', 'user.name=CI checkout regression', '-c', 'user.email=ci@example.test', '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'Synthetic sparse checkout fixture']);
    const tree = git(source, ['rev-parse', 'HEAD^{tree}']);
    git(directory, ['clone', '--quiet', '--shared', '--no-checkout', source, checkout]);
    const patternPath = join(directory, 'sparse-patterns.txt');
    await writeFile(patternPath, planning ? planningPatterns : patterns);
    git(checkout, ['sparse-checkout', 'set', '--no-cone', '--stdin'], patternPath);
    git(checkout, ['checkout', '--quiet']);
    const expected = planning ? ['.github/workflows/ci.yml', 'scripts/ci/reuse-validation.mjs'] : required;
    const omitted = [...excluded, ...required.filter(path => !expected.includes(path))];
    for (const path of expected) assert.equal((await stat(join(checkout, path))).isFile(), true, `${path} must remain available.`);
    for (const path of omitted) await assert.rejects(stat(join(checkout, path)), {code: 'ENOENT'}, `${path} must not be materialized.`);
    assert.equal(git(checkout, ['rev-parse', 'HEAD^{tree}']), tree, 'Sparse checkout must preserve the full tested Git tree identity.');
    assert.equal(git(checkout, ['status', '--porcelain']), '', 'Excluded archives are not deleted from the commit.');
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});
