#!/usr/bin/env python3
"""Collect cited public documents and useful PDF pages for boundary research."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading


def collect(entry, output):
    identifier = entry['id']
    if not re.fullmatch(r'[a-z0-9-]+', identifier):
        raise ValueError('Invalid document identifier')
    extension = entry['format']
    if extension not in ('pdf', 'html', 'xlsx', 'webp', 'png') or not entry['url'].startswith('https://'):
        raise ValueError('Unsupported source')
    original = output / 'originals' / f'{identifier}.{extension}'
    report = {**entry, 'retrievedAt': datetime.now(timezone.utc).isoformat()}
    try:
        result = subprocess.run([
            'curl', '--silent', '--show-error', '--location', '--fail',
            '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '15',
            '--max-time', '55', '--max-filesize', str(64 * 1024 * 1024),
            '--retry', '1', '--retry-max-time', '65', '--output', str(original),
            '--write-out', '%{http_code}', entry['url']
        ], capture_output=True, text=True, timeout=80)
        report['httpStatus'] = result.stdout.strip()
        if result.returncode:
            raise RuntimeError(f'download-exit-{result.returncode}')
        data = original.read_bytes()
        expected = entry.get('gitBlobSha1')
        git_blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if expected and expected != git_blob:
            raise ValueError('Pinned source fingerprint mismatch')
        if extension == 'pdf' and not data.startswith(b'%PDF'):
            raise ValueError('Not a PDF')
        if extension == 'xlsx' and not data.startswith(b'PK'):
            raise ValueError('Not an XLSX archive')
        report.update(status='downloaded', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), gitBlobSha1=git_blob)
        if extension == 'pdf':
            text_file = output / 'text' / f'{identifier}.txt'
            subprocess.run(['pdftotext', '-layout', str(original), str(text_file)], check=True, timeout=60, capture_output=True)
            pages = text_file.read_text(errors='replace').split('\f')
            requested = set(entry.get('pages', []))
            if not requested:
                requested = {i + 1 for i, page in enumerate(pages)
                    if re.search(r'városrész|városrészi|településrész', page, re.I)
                    and re.search(r'határ|térkép|lehatárol', page, re.I)}
            if len(pages) <= 4:
                requested.update(range(1, len(pages) + 1))
            selected = sorted(n for n in requested if 0 < n <= len(pages))[:20]
            page_directory = output / 'pages' / identifier
            page_directory.mkdir(exist_ok=True)
            preserved = []
            for page in selected:
                target = page_directory / f'page-{page:04d}.pdf'
                attempt = subprocess.run(['pdfseparate', '-f', str(page), '-l', str(page), str(original), str(target)], capture_output=True, timeout=30)
                if attempt.returncode == 0:
                    preserved.append(page)
            report.update(textPath=f'text/{identifier}.txt', selectedPages=preserved,
                pageCopies='Selected pages are derived copies; original full-document hash is retained above.')
        else:
            (output / 'documents' / original.name).write_bytes(data)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(status='failed', reason=str(error)[:180])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())['sources']
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('originals', 'documents', 'text', 'pages'):
        (args.output / name).mkdir()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda entry: collect(entry, args.output), sources))
    manifest = {'schemaVersion': 1, 'purpose': 'public boundary-source research; not all sources are polygon datasets', 'results': results}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    for record in results:
        print(f"{record['id']}: {record['status']}" + (f" ({record['reason']})" if record['status'] == 'failed' else ''))


if __name__ == '__main__':
    main()
