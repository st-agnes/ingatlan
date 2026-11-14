#!/usr/bin/env python3
"""Download and verify one immutable OSM Hungarian boundary archive.

The output directory must be new. Only public HTTPS raw.githubusercontent.com
requests are allowed, including every redirect; no credentials are required.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPOSITORY = 'ferenci-tamas/BudapestiElerhetoseg'
COMMIT = '2f7a91ee1f320e6a08488ef8413715be13abf226'
COMMIT_DATE = '2025-08-28T17:51:58Z'
ARCHIVE_NAME = 'kozighatarok.zip'
URL = f'https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/{ARCHIVE_NAME}'
EXPECTED_BYTES = 6285474
EXPECTED_GIT_BLOB_SHA1 = 'e7f24b8ef283cffee740cd3cd3a3c3ec16b71d0d'
MAX_BYTES = 12 * 1024 * 1024
TIMEOUT_SECONDS = 45
CHUNK_BYTES = 64 * 1024


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'raw.githubusercontent.com'
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError('Only HTTPS raw.githubusercontent.com URLs are allowed')
    return url


class ValidatedRedirects(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@contextmanager
def deadline(seconds):
    # GitHub's Ubuntu collector runs on POSIX. A socket timeout alone permits
    # an arbitrarily slow trickle; this alarm bounds DNS, connect and all reads
    # together. Fail before networking on a platform without a strict timer.
    if not hasattr(signal, 'setitimer'):
        raise RuntimeError('A POSIX timer is required for the bounded download')
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError('The archive download exceeded 45 seconds')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def copy_verified(response, destination):
    validate_url(response.geturl())
    if response.status != 200:
        raise ValueError('The archive request did not return HTTP 200')
    encoding = response.headers.get('Content-Encoding', 'identity').lower()
    if encoding != 'identity':
        raise ValueError('Unexpected compressed HTTP response')
    declared = response.headers.get('Content-Length')
    if declared is not None:
        if not declared.isdigit() or int(declared) > MAX_BYTES:
            raise ValueError('Invalid or oversized archive Content-Length')
        if int(declared) != EXPECTED_BYTES:
            raise ValueError('Archive Content-Length differs from the pinned size')
    git_hash = hashlib.sha1(b'blob '+str(EXPECTED_BYTES).encode()+b'\0')
    sha256 = hashlib.sha256()
    received = 0
    while True:
        chunk = response.read(min(CHUNK_BYTES, MAX_BYTES-received+1))
        if not chunk:
            break
        received += len(chunk)
        if received > MAX_BYTES:
            raise ValueError('The archive exceeds the 12 MiB download limit')
        destination.write(chunk)
        git_hash.update(chunk)
        sha256.update(chunk)
    if received != EXPECTED_BYTES:
        raise ValueError('Archive byte count differs from the pinned size')
    if git_hash.hexdigest() != EXPECTED_GIT_BLOB_SHA1:
        raise ValueError('Archive Git blob SHA1 differs from the pinned source')
    return {'path': ARCHIVE_NAME, 'bytes': received,
            'gitBlobSha1': git_hash.hexdigest(), 'sha256': sha256.hexdigest()}


def fetch(output):
    validate_url(URL)
    output.mkdir(parents=True, exist_ok=False)
    temporary = output/(ARCHIVE_NAME+'.part')
    started = time.monotonic()
    try:
        request = Request(URL, headers={
            'Accept': 'application/octet-stream', 'Accept-Encoding': 'identity',
            'User-Agent': 'Otthonra-public-boundary-collector/1.0'})
        with deadline(TIMEOUT_SECONDS):
            with build_opener(ValidatedRedirects()).open(request, timeout=TIMEOUT_SECONDS) as response:
                with temporary.open('xb') as target:
                    archive = copy_verified(response, target)
        temporary.rename(output/ARCHIVE_NAME)
        manifest = {
            'source': 'OpenStreetMap Hungarian administrative boundary export',
            'repository': REPOSITORY, 'sourceCommit': COMMIT,
            'sourceCommitDate': COMMIT_DATE,
            'sourceUrl': URL,
            'originalDownloadUrl': 'http://data2.openstreetmap.hu/hatarok/kozighatarok.zip',
            'retrievedAt': datetime.now(timezone.utc).isoformat(),
            'license': 'ODbL-1.0',
            'licenseUrl': 'https://opendatacommons.org/licenses/odbl/1-0/',
            'copyrightUrl': 'https://www.openstreetmap.org/copyright',
            'attribution': '© OpenStreetMap contributors',
            'archive': archive,
            'notes': [
                'The date is the mirror commit date, not a documented OSM extraction date.',
                'Archive layers and geographic coverage require inspection before import.',
                'No archive entries are extracted by this downloader.'
            ]
        }
        (output/'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f'Verified public boundary archive: {archive["bytes"]} bytes; '
          f'SHA256 {archive["sha256"]}; {time.monotonic()-started:.1f}s')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path,
                        help='Fresh output directory for the archive and provenance manifest')
    args = parser.parse_args()
    try:
        fetch(args.output)
    except (OSError, ValueError, RuntimeError, HTTPError, URLError) as exc:
        # Public fixed URL only; avoid printing verbose transport/proxy objects.
        print(f'Boundary archive download failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
