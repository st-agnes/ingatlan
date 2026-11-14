#!/usr/bin/env python3
"""Fetch the official Geofabrik Hungary PBF, verify its published MD5, and pin SHA256.

The latest URL is mutable: the adjacent manifest records the exact bytes and
source response metadata needed to identify a run. Existing output is refused.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import signal
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

URL = 'https://download.geofabrik.de/europe/hungary-latest.osm.pbf'
MAX_BYTES = 2 * 1024**3
CHUNK_BYTES = 1024**2
TIMEOUT_SECONDS = 600


def validate_url(url):
    value = urlsplit(url)
    if (value.scheme != 'https' or value.hostname != 'download.geofabrik.de'
            or value.username is not None or value.password is not None
            or value.port not in (None, 443) or value.fragment or value.query
            or not re.fullmatch(r'/europe/hungary-(?:latest|\d{6})\.osm\.pbf(?:\.md5)?', value.path)):
        raise ValueError('Only official HTTPS Geofabrik Hungary PBF/checksum URLs are allowed')
    return url


class ValidatedRedirects(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@contextmanager
def deadline(seconds):
    if not hasattr(signal, 'setitimer'):
        raise RuntimeError('A POSIX deadline timer is required')
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError('The country download exceeded its total deadline')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def response_length(response, limit):
    validate_url(response.geturl())
    if response.status != 200:
        raise ValueError('Source did not return HTTP 200')
    if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
        raise ValueError('Unexpected HTTP content encoding')
    declared = response.headers.get('Content-Length')
    if declared is not None and (not declared.isdigit() or not 0 < int(declared) <= limit):
        raise ValueError('Invalid or oversized Content-Length')
    return int(declared) if declared is not None else None


def parse_checksum(data):
    text = data.decode('ascii').strip()
    match = re.fullmatch(r'([a-fA-F0-9]{32})\s+\*?(hungary-(?:latest|\d{6})\.osm\.pbf)', text)
    if not match:
        raise ValueError('Invalid official MD5 checksum document')
    return match[1].lower(), match[2]


def copy_verified(response, destination, expected_md5):
    declared = response_length(response, MAX_BYTES)
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    received = 0
    while True:
        chunk = response.read(min(CHUNK_BYTES, MAX_BYTES - received + 1))
        if not chunk:
            break
        received += len(chunk)
        if received > MAX_BYTES:
            raise ValueError('PBF exceeds the 2 GiB download limit')
        destination.write(chunk)
        md5.update(chunk)
        sha256.update(chunk)
    if received == 0 or (declared is not None and received != declared):
        raise ValueError('PBF byte count differs from Content-Length')
    if md5.hexdigest() != expected_md5:
        raise ValueError('PBF MD5 differs from the official checksum (possibly a latest update race)')
    return {'bytes': received, 'md5': md5.hexdigest(), 'sha256': sha256.hexdigest(),
            'finalUrl': response.geturl(), 'lastModified': response.headers.get('Last-Modified'),
            'etag': response.headers.get('ETag')}


def fetch(output):
    output = Path(output)
    manifest_path = output.with_name(output.name + '.source.json')
    temporary = output.with_name(output.name + '.part')
    for path in (output, manifest_path, temporary):
        if path.exists():
            raise FileExistsError(f'Output already exists: {path}')
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = build_opener(ValidatedRedirects())

    def request(url):
        return opener.open(Request(validate_url(url), headers={
            'User-Agent': 'Otthonra-public-country-boundary-collector/1.0',
            'Accept-Encoding': 'identity'}), timeout=45)

    try:
        with deadline(TIMEOUT_SECONDS):
            with request(URL + '.md5') as response:
                response_length(response, 4096)
                checksum_document = response.read(4097)
                if len(checksum_document) > 4096:
                    raise ValueError('Checksum document exceeds 4096 bytes')
                expected_md5, checksum_filename = parse_checksum(checksum_document)
            with request(URL) as response, temporary.open('xb') as target:
                result = copy_verified(response, target, expected_md5)
        manifest = {
            'version': 1, 'provider': 'Geofabrik', 'source': 'OpenStreetMap',
            'scope': 'Hungary country extract', 'url': URL, 'checksumUrl': URL + '.md5',
            'checksumFilename': checksum_filename, 'file': output.name,
            'retrievedAt': datetime.now(timezone.utc).isoformat(), **result,
            'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
            'attributionUrl': 'https://www.openstreetmap.org/copyright',
            'licenseUrl': 'https://opendatacommons.org/licenses/odbl/1-0/',
            'notes': ['The latest URL is mutable; SHA256 identifies this exact snapshot.',
                      'MD5 verifies the publisher checksum; SHA256 pins the acquired bytes.',
                      'OSM community boundaries are not necessarily official legal boundaries.']}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.rename(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        if not output.exists():
            manifest_path.unlink(missing_ok=True)
        raise
    print(json.dumps({'file': str(output), 'bytes': result['bytes'], 'sha256': result['sha256']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New .osm.pbf file path')
    args = parser.parse_args()
    try:
        fetch(args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Country source download failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
