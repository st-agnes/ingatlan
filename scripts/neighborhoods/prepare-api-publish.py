#!/usr/bin/env python3
"""Prepare a committed checkpoint for lease-checked GitHub connector publishing.

This is offline preparation only. It never contacts GitHub or changes Git refs.
The caller verifies the remote base, uploads missing blobs, checks the resulting
tree against headTree, then creates a commit and advances the feature branch.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 16 * 1024**2

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def tree(ref):
    result = {}
    for entry in git('ls-tree', '-rlz', ref).split(b'\0'):
        if not entry:
            continue
        meta, path = entry.split(b'\t', 1)
        mode, kind, sha, size = meta.split()
        result[path.decode()] = dict(path=path.decode(), mode=mode.decode(),
            type=kind.decode(), sha=sha.decode(), size=int(size))
    return result

def paths(base, kind):
    return [p.decode() for p in git('diff', '--no-renames', '--name-only', '-z',
        '--diff-filter='+kind, base, 'HEAD').split(b'\0') if p]

def prepare(base, output):
    subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=ROOT, check=True)
    previous, current = tree(base), tree('HEAD')
    reachable = {row['sha'] for row in previous.values()}
    rows, groups, group, group_size = [], [], [], 0
    for path in paths(base, 'ACMT'):
        row = current[path]
        if row['type'] != 'blob' or row['mode'] not in {'100644', '100755'}:
            raise ValueError('Unsupported checkpoint entry: '+path)
        raw = (ROOT/path).read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual != row['sha']:
            raise ValueError('Working file differs from committed blob: '+path)
        row.update(inline=False, alreadyInBase=row['sha'] in reachable)
        if not row['alreadyInBase'] and len(raw) <= 65536:
            try:
                entry = {k: row[k] for k in ('path', 'mode', 'type')}
                entry['content'] = raw.decode('utf-8')
                size = len(json.dumps(entry, ensure_ascii=False).encode())
                if group and group_size+size > 250000:
                    groups.append(group); group=[]; group_size=0
                group.append(entry); group_size+=size; row['inline']=True
            except UnicodeDecodeError:
                pass
        if not row['inline'] and not row['alreadyInBase'] and 4*((len(raw)+2)//3)+1024 >= LIMIT:
            raise ValueError('Compress the artifact before connector upload: '+path)
        rows.append(row)
    if group:
        groups.append(group)
    result = dict(base=base, head=git('rev-parse', 'HEAD').decode().strip(),
        baseTree=git('rev-parse', base+'^{tree}').decode().strip(),
        headTree=git('rev-parse', 'HEAD^{tree}').decode().strip(),
        message=git('log', '-1', '--format=%B').decode().rstrip()+'\n',
        files=rows, deleted=paths(base, 'D'), inlineGroups=len(groups),
        base64ChunkBytes=393216, requestBodyLimitBytes=LIMIT)
    output.mkdir(parents=True, exist_ok=True)
    (output/'manifest.json').write_text(json.dumps(result, ensure_ascii=False))
    for index, entries in enumerate(groups):
        (output/f'inline-{index}.json').write_text(json.dumps(entries, ensure_ascii=False))
    print(json.dumps(dict(manifest=str(output/'manifest.json'), files=len(rows),
        reused=sum(row['alreadyInBase'] for row in rows),
        uploadBlobs=sum(not row['inline'] and not row['alreadyInBase'] for row in rows),
        inlineGroups=len(groups), headTree=result['headTree'])))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='Verified remote feature-branch SHA')
    parser.add_argument('--output', default='.local/github-api-publish')
    args=parser.parse_args()
    prepare(args.base, ROOT/args.output)
