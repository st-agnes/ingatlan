#!/usr/bin/env python3
"""Fetch public research sources and export bounded map extracts, never full PDFs.

Run only in a permitted network environment. The ordinary offline catalogue build
never invokes this collector. Raw source bytes remain in _private/ on the runner;
only public/ and its provenance are packaged in artifact.zip (at most24MiB).
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import signal
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

HOSTS = frozenset({'veszprem.hu', 'zalaegerszeg.hu', 'kph.kaposvar.hu',
                  'maps.szentendre.hu', 'infoterkep.szegedvaros.hu', 'www.arcgis.com'})
MAX_BYTES = 80 * 1024 * 1024
MAX_ASSET = 2 * 1024 * 1024
MAX_BUNDLE = 24 * 1024 * 1024
MAX_PAGES = 6
SECRET_QUERY_KEYS = {'token', 'access_token', 'api_key', 'apikey', 'key', 'authorization', 'sig', 'signature'}


class CollectionError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def validate_url(url):
    p = urlsplit(url)
    if (any(ord(c) < 32 for c in url) or p.scheme != 'https' or p.hostname not in HOSTS
            or p.username is not None or p.password is not None or p.port not in (None, 443)
            or p.fragment or any(k.lower() in SECRET_QUERY_KEYS for k, _ in parse_qsl(p.query))):
        raise CollectionError('URL is outside the public HTTPS source allowlist')
    return url


class PublicRedirects(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = validate_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, target)


@contextmanager
def deadline(seconds=90):
    if not hasattr(signal, 'setitimer'):
        raise CollectionError('A POSIX whole-request deadline is required')
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def expired(_signum, _frame):
        raise TimeoutError('Whole-request deadline exceeded')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] or previous_timer[1]:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def fetch(url, destination, kind, *, max_bytes=MAX_BYTES, open_url=None, timeout=90):
    """Bound DNS/open/redirect/read together; preserve exact received source bytes."""
    validate_url(url)
    opener = open_url or build_opener(PublicRedirects()).open
    request = Request(url, headers={'User-Agent': 'Otthonra-public-boundary-research/1.0',
                                    'Accept-Encoding': 'identity'})
    try:
        with deadline(timeout), opener(request, timeout=min(timeout, 30)) as response:
            final_url = validate_url(response.geturl())
            if response.status != 200:
                raise CollectionError('Source did not return HTTP200')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                raise CollectionError('Unexpected source content encoding')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not declared.isdigit() or int(declared) > max_bytes):
                raise CollectionError('Invalid or oversized source Content-Length')
            size = 0
            hasher = hashlib.sha256()
            with destination.open('wb') as out:
                while True:
                    block = response.read(min(65536, max_bytes - size + 1))
                    if not block:
                        break
                    size += len(block)
                    if size > max_bytes:
                        raise CollectionError('Source exceeded byte limit')
                    hasher.update(block)
                    out.write(block)
            if declared is not None and size != int(declared):
                raise CollectionError('Incomplete source body')
            if size == 0:
                raise CollectionError('Empty source body')
            data = destination.read_bytes()
            if kind == 'pdf' and not data.startswith(b'%PDF-'):
                raise CollectionError('Source does not have PDF magic')
            if kind in ('html', 'js', 'json'):
                text = data.decode('utf-8-sig')
                if kind == 'json':
                    value = json.loads(text)
                    if isinstance(value, dict) and 'error' in value:
                        raise CollectionError('Remote JSON error response')
                if kind == 'html' and not re.search(r'<!doctype\s+html|<html\b', text[:4096], re.I):
                    raise CollectionError('Source does not have HTML markup')
            return {'requestedUrl': url, 'finalUrl': final_url, 'bytes': size,
                    'sha256': hasher.hexdigest(), 'httpStatus': 200}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def graphic_clip(page, drawings):
    """Largest connected substantial graphic; omit page frames and text-only pages."""
    import fitz
    area = page.rect.get_area()
    rectangles = []
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            clipped = rect & page.rect
            if 0.03 * area <= clipped.get_area() < 0.9 * area:
                rectangles.append(clipped)
    for drawing in drawings:
        rect = drawing['rect'] & page.rect
        if rect.width >= 8 and rect.height >= 8 and max(64, 0.001 * area) <= rect.get_area() < 0.9 * area:
            rectangles.append(rect)
    groups = []
    for rect in rectangles:
        group = fitz.Rect(rect)
        changed = True
        while changed:
            changed = False
            for index, previous in enumerate(groups):
                if (group + (-8, -8, 8, 8)).intersects(previous):
                    group |= previous
                    groups.pop(index)
                    changed = True
                    break
        groups.append(group)
    return max(groups, key=lambda rect: rect.get_area()) if groups else None


def pdf_extract(source, public, entry):
    import fitz  # Pinned only by the collection workflow; not an offline-build dependency.
    document = fitz.open(source)
    scores = []
    hints = set(entry.get('pdfPageHints', []))
    keywords = [normalized(k) for k in entry.get('keywords', ['varosresz'])]
    for index, page in enumerate(document):
        text = normalized(page.get_text('text'))
        score = sum(5 for k in keywords if k in text)
        score += 2 if ('terkep' in text or 'abra' in text) and 'varosresz' in text else 0
        if index + 1 in hints:
            score += 20
        # A contents-page mention alone is a poor map candidate.
        if score and (index >= 6 or index + 1 in hints):
            scores.append((score, index))
    selected = sorted(index for _, index in sorted(scores, key=lambda x: (-x[0], x[1]))[:MAX_PAGES])
    report = {'pageCount': len(document), 'selectedPages': [], 'selector':
              'At most6 keyword-ranked pages plus explicit physical-page hints; selection is research-only, not proof of a quarter map.',
              'pymupdfVersion': fitz.VersionBind, 'originalPdfIncluded': False,
              'narrativeTextExported': False, 'absoluteBoundaryAccuracyMetres': None}
    label_budget = 180
    for index in selected:
        page = document[index]
        target = public / f'page-{index+1:04d}'
        drawings = page.get_drawings()
        # Preserve complete drawing records; omitted records stay explicitly marked.
        retained, item_count = [], 0
        for drawing in drawings:
            if item_count + len(drawing['items']) > 200000:
                break
            retained.append(drawing)
            item_count += len(drawing['items'])

        def serial(value):
            if isinstance(value, dict):
                return {key: serial(v) for key, v in value.items()}
            if isinstance(value, (list, tuple, fitz.Point, fitz.Rect, fitz.Quad)):
                return [serial(v) for v in value]
            return value

        labels = []
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    text = span['text'].strip()
                    words = text.split()
                    if text and len(text) <= 65 and len(words) <= 6 and len(words) <= label_budget:
                        labels.append({'text': text, 'bbox': list(span['bbox']), 'size': span['size']})
                        label_budget -= len(words)
        vector = {'pdfPageOneBased': index+1, 'pageRect': list(page.rect), 'coordinateSpace': 'Original PDF points; not geographic coordinates',
                  'drawingRecordCount': len(drawings), 'retainedDrawingRecords': len(retained),
                  'vectorExtractionComplete': len(retained) == len(drawings),
                  'shortLabelSpans': labels, 'labelsMayBeIncomplete': True, 'drawings': serial(retained)}
        encoded = json.dumps(vector, ensure_ascii=False, allow_nan=False).encode('utf-8')
        vector_status = 'written'
        if len(encoded) <= 12 * 1024 * 1024:
            target.with_suffix('.json').write_bytes(encoded)
        else:
            vector_status = 'omitted_over_12MiB'
        clip = graphic_clip(page, drawings)
        scale = None
        if clip is not None:
            scale = min(2.0, 2400 / max(clip.width, clip.height))
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, clip=clip).save(target.with_suffix('.png'))
        # Original map-image pixels are useful when the PDF display downsamples them.
        images = []
        text = normalized(page.get_text('text'))
        map_context = 'varosresz' in text and any(word in text for word in ('terkep', 'abra', 'jelenkori', 'lehatar'))
        for image_index, image in enumerate(page.get_images(full=True)[:4]):
            rects = page.get_image_rects(image[0])
            if not map_context or clip is None or not any(clip.contains(rect) for rect in rects):
                continue
            extracted = document.extract_image(image[0])
            if extracted['width'] >= 256 and extracted['height'] >= 256 and len(extracted['image']) <= 8 * 1024 * 1024:
                name = f'page-{index+1:04d}-image-{image_index:02d}.{extracted["ext"]}'
                (public/name).write_bytes(extracted['image'])
                images.append({'path': name, 'width': extracted['width'], 'height': extracted['height'],
                               'sha256': digest(extracted['image'])})
        report['selectedPages'].append({'pdfPageOneBased': index+1, 'vectorStatus': vector_status,
             'vectorExtractionComplete': vector['vectorExtractionComplete'], 'originalImages': images,
             'renderScale': scale, 'graphicClipPdfPoints': list(clip) if clip is not None else None,
             'previewStatus': 'graphic_excerpt' if clip is not None else 'no_map_preview',
             'previewIsSourcePageExcerpt': clip is not None})
    document.close()
    return report


class ScriptLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'script':
            value = dict(attrs).get('src')
            if value:
                self.sources.append(value)


def html_extract(source, public, entry):
    data = source.read_bytes()
    (public/'source.html').write_bytes(data)
    parser = ScriptLinks()
    parser.feed(data.decode('utf-8-sig'))
    results = []
    seen = set()
    for candidate in parser.sources:
        url = urljoin(entry['url'], candidate)
        if url in seen:
            continue
        seen.add(url)
        if urlsplit(url).hostname != urlsplit(entry['url']).hostname:
            continue
        try:
            validate_url(url)
        except CollectionError:
            continue
        if len(results) >= 6:
            break
        record = {'url': url}
        try:
            path = public/f'script-{len(results):02d}.js'
            record.update(fetch(url, path, 'js', max_bytes=MAX_ASSET, timeout=45), status='downloaded', path=path.name)
        except (CollectionError, HTTPError, URLError, OSError, TimeoutError, UnicodeError, json.JSONDecodeError) as error:
            record.update(status='failed', reason=failure_code(error))
        results.append(record)
    return {'sameHostScriptAssets': results, 'authenticatedSessionUsed': False}


def failure_code(error):
    if isinstance(error, HTTPError):
        return f'http_{error.code}'
    if isinstance(error, TimeoutError):
        return 'whole_request_deadline'
    if isinstance(error, CollectionError):
        return str(error)  # Only collector-authored strings, never response bodies/headers.
    return type(error).__name__


def package(public, output, source_id, max_bytes=MAX_BUNDLE):
    archive = output/'artifact.zip'
    temporary = output/'artifact.zip.part'
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(public.rglob('*')):
            if path.is_file():
                bundle.write(path, f'{source_id}/{path.relative_to(public).as_posix()}')
    if temporary.stat().st_size > max_bytes:
        temporary.unlink()
        raise CollectionError('Extract bundle exceeds24MiB; reduce selected pages before rerunning')
    temporary.replace(archive)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise CollectionError('Extract bundle CRC verification failed')
    return {'path': archive.name, 'bytes': archive.stat().st_size, 'sha256': digest(archive.read_bytes())}


def collect(entry, output):
    source_id = entry.get('id', '')
    if not re.fullmatch(r'[a-z0-9-]{1,64}', source_id) or entry.get('kind') not in {'pdf', 'html', 'json'}:
        raise CollectionError('Invalid source specification')
    validate_url(entry['url'])
    output.mkdir(parents=True, exist_ok=False)
    private = output/'_private'; private.mkdir()
    public = output/'public'; public.mkdir()
    record = {'id': source_id, 'kind': entry['kind'], 'url': entry['url'],
              'retrievedAt': datetime.now(timezone.utc).isoformat(), 'status': 'started',
              'fullPdfPublished': False, 'quarterGeometryVerified': False,
              'rightsStatus': 'Source redistribution rights not independently established; excerpts are research evidence.'}
    manifest = public/'source-manifest.json'
    write_json(manifest, record)
    try:
        original = private/f'source.{entry["kind"]}'
        limit = MAX_BYTES if entry['kind'] == 'pdf' else MAX_ASSET
        record['source'] = fetch(entry['url'], original, entry['kind'], max_bytes=limit)
        record['stage'] = 'source_downloaded'
        write_json(manifest, record)
        if entry['kind'] == 'pdf':
            with deadline(240):
                record['extraction'] = pdf_extract(original, public, entry)
        elif entry['kind'] == 'html':
            record['extraction'] = html_extract(original, public, entry)
        else:
            (public/'source.json').write_bytes(original.read_bytes())
        record['status'] = 'collected'
    except Exception as error:
        record.update(status='failed', reason=failure_code(error))
    record['files'] = [{'path': p.relative_to(public).as_posix(), 'bytes': p.stat().st_size,
                        'sha256': digest(p.read_bytes())} for p in sorted(public.rglob('*')) if p.is_file() and p != manifest]
    write_json(manifest, record)
    try:
        bundle = package(public, output, source_id)
    except CollectionError:
        # Keep an actionable, small failure artifact; raw PDF is still never published.
        record.update(status='failed', reason='extract_bundle_over_limit')
        for path in public.iterdir():
            if path.is_file() and path != manifest:
                path.unlink()
        record['files'] = [];write_json(manifest, record)
        bundle = package(public, output, source_id)
    print(json.dumps({'id': source_id, 'status': record['status'], 'artifactBytes': bundle['bytes'],
                      'artifactSha256': bundle['sha256']}, ensure_ascii=False))
    return record['status'] == 'collected'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.sources.read_text(encoding='utf-8'))
    if document.get('schemaVersion') != 1 or not isinstance(document.get('sources'), list):
        raise CollectionError('Invalid source manifest')
    matches = [entry for entry in document['sources'] if entry.get('id') == args.source]
    if len(matches) != 1:
        raise CollectionError('Source identifier must match exactly one manifest entry')
    return 0 if collect(matches[0], args.output) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (CollectionError, OSError, ValueError) as error:
        print('Supplement collection could not start: ' + failure_code(error), file=sys.stderr)
        sys.exit(1)
