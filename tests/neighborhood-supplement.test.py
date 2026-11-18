#!/usr/bin/env python3
"""Offline HTTP fixtures and extraction/packaging checks; never contacts a host."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import signal
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supplement', ROOT/'scripts/neighborhoods/collect-public-supplement.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
URL = 'https://veszprem.hu/research.pdf'


class Response:
    def __init__(self, data, headers=None, status=200, url=URL, delay=0):
        self.data = io.BytesIO(data)
        self.headers = headers or {}
        self.status = status
        self.url = url
        self.delay = delay
        self.reads = 0

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.url
    def read(self, size):
        self.reads += 1
        if self.delay: time.sleep(self.delay)
        return self.data.read(size)


class CollectorTests(unittest.TestCase):
    def test_public_https_allowlist_and_redirects(self):
        for url in ['http://veszprem.hu/x', 'https://evil.test/x', 'https://u:p@veszprem.hu/x',
                    'https://veszprem.hu:444/x', 'https://veszprem.hu/x#f',
                    'https://veszprem.hu/x?token=secret', 'file:///etc/passwd']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                collector.validate_url(url)
        self.assertEqual(collector.validate_url(URL), URL)
        request = collector.Request(URL)
        redirects = collector.PublicRedirects()
        redirected = redirects.redirect_request(request, None, 302, '', {}, '/new.pdf')
        self.assertEqual(redirected.full_url, 'https://veszprem.hu/new.pdf')
        for target in ['http://veszprem.hu/new.pdf', 'https://evil.test/new.pdf']:
            with self.assertRaises(ValueError):
                redirects.redirect_request(request, None, 302, '', {}, target)

    def test_exact_bytes_hash_no_auth_and_content_length(self):
        body = b'%PDF-1.7\nactual fixture bytes\n'
        captured = []
        def opener(request, **kwargs):
            captured.append(request)
            return Response(body, {'Content-Length': str(len(body))})
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'source.pdf'
            record = collector.fetch(URL, target, 'pdf', open_url=opener)
            self.assertEqual(target.read_bytes(), body)
            self.assertEqual(record['sha256'], collector.digest(body))
            self.assertEqual(record['bytes'], len(body))
        self.assertEqual(captured[0].get_method(), 'GET')
        self.assertIsNone(captured[0].data)
        self.assertFalse(any(k.lower() in {'authorization', 'cookie'} for k in captured[0].headers))

    def test_invalid_responses_never_leave_partial_downloads(self):
        cases = [Response(b'%PDF-1.7', status=403), Response(b'%PDF-1.7', {'Content-Length': '999'}),
                 Response(b'%PDF-1.7', {'Content-Length': '2'}), Response(b'not a pdf'),
                 Response(b'%PDF-1.7', {'Content-Encoding': 'gzip'}),
                 Response(b'%PDF-1.7', url='https://evil.test/file.pdf')]
        with tempfile.TemporaryDirectory() as directory:
            for index, response in enumerate(cases):
                target = Path(directory)/f'bad-{index}.pdf'
                with self.subTest(index=index), self.assertRaises(ValueError):
                    collector.fetch(URL, target, 'pdf', max_bytes=64, open_url=lambda *a, **kw: response)
                self.assertFalse(target.exists())
            target = Path(directory)/'stream-overflow.pdf'
            with self.assertRaises(ValueError):
                collector.fetch(URL, target, 'pdf', max_bytes=6,
                                open_url=lambda *a, **kw: Response(b'%PDF-1.7more'))
            self.assertFalse(target.exists())

    def test_whole_request_deadline_covers_body_read_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGALRM)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'slow.pdf'
            with self.assertRaises(TimeoutError):
                collector.fetch(URL, target, 'pdf', timeout=0.01,
                                open_url=lambda *a, **kw: Response(b'%PDF-1.7', delay=0.05))
            self.assertFalse(target.exists())
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0)

    def test_error_json_and_incomplete_bodies_are_not_successes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'source.json'
            for response in [Response(b'{"error":{"code":403}}'), Response(b'{}', {'Content-Length':'5'})]:
                with self.assertRaises(ValueError):
                    collector.fetch(URL, target, 'json', open_url=lambda *a, **kw: response)
                self.assertFalse(target.exists())

    def test_pdf_exports_only_bounded_map_extracts_with_original_fingerprint(self):
        import fitz
        doc = fitz.open();page = doc.new_page()
        page.draw_rect(fitz.Rect(40,40,200,180), color=(0,0,1))
        page.insert_text((45,80), 'Varosreszek')
        raw = doc.tobytes();doc.close()
        original_fetch = collector.fetch
        def mocked(url, destination, kind, **kwargs):
            return original_fetch(url, destination, kind, open_url=lambda *a, **kw: Response(raw))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'output'
            with patch.object(collector, 'fetch', side_effect=mocked), contextlib.redirect_stdout(io.StringIO()):
                success = collector.collect({'id':'fixture','kind':'pdf','url':URL,'pdfPageHints':[1]}, output)
            self.assertTrue(success)
            self.assertEqual((output/'_private/source.pdf').read_bytes(),raw)
            with zipfile.ZipFile(output/'artifact.zip') as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith('fixture/') for name in names))
                self.assertFalse(any(name.endswith('.pdf') or '_private' in name for name in names))
                report = json.loads(archive.read('fixture/source-manifest.json'))
                self.assertEqual(report['source']['sha256'],collector.digest(raw))
                self.assertFalse(report['fullPdfPublished'])
                vector = json.loads(archive.read('fixture/page-0001.json'))
                self.assertTrue(vector['vectorExtractionComplete'])
                self.assertEqual(vector['coordinateSpace'],'Original PDF points; not geographic coordinates')
                self.assertIn('fixture/page-0001.png',names)
                page_record = report['extraction']['selectedPages'][0]
                self.assertEqual(page_record['graphicClipPdfPoints'],[40,40,200,180])
                self.assertEqual(page_record['previewStatus'],'graphic_excerpt')
                self.assertEqual(struct.unpack('>II',archive.read('fixture/page-0001.png')[16:24]),(320,280))
                self.assertIsNone(archive.testzip())
            self.assertLessEqual((output/'artifact.zip').stat().st_size,collector.MAX_BUNDLE)

    def test_graphic_crop_ignores_narrative_and_page_frames(self):
        import fitz
        document=fitz.open();page=document.new_page()
        page.insert_text((40,300),'Narrative text is not a map figure.')
        self.assertIsNone(collector.graphic_clip(page,page.get_drawings()))
        page.draw_rect(page.rect)  # A source-page frame must not restore the whole page.
        page.draw_rect(fitz.Rect(20,20,80,80))
        page.draw_rect(fitz.Rect(85,25,130,80))
        self.assertEqual(list(collector.graphic_clip(page,page.get_drawings())),[20,20,130,80])
        document.close()

    def test_failure_still_has_small_diagnostic_artifact_without_response_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'output'
            with (patch.object(collector,'fetch',side_effect=OSError('do not print this transport detail')),
                  contextlib.redirect_stdout(io.StringIO())):
                success = collector.collect({'id':'fixture','kind':'pdf','url':URL},output)
            self.assertFalse(success)
            with zipfile.ZipFile(output/'artifact.zip') as archive:
                report = json.loads(archive.read('fixture/source-manifest.json'))
                self.assertEqual(report['reason'],'OSError')
                self.assertNotIn('do not print',json.dumps(report))

    def test_bundle_limit_fails_without_publishing_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory);public=output/'public';public.mkdir()
            (public/'evidence.txt').write_text('source evidence')
            (output/'_private').mkdir();(output/'_private/source.pdf').write_bytes(b'%PDF-secret')
            with self.assertRaises(ValueError):collector.package(public,output,'fixture',max_bytes=1)
            self.assertFalse((output/'artifact.zip').exists())
            self.assertFalse((output/'artifact.zip.part').exists())

    def test_manifest_sources_are_unique_and_explicitly_public(self):
        document=json.loads((ROOT/'data/neighborhoods/research/supplement-sources.json').read_text())
        ids=[row['id'] for row in document['sources']]
        self.assertEqual(len(ids),8);self.assertEqual(len(set(ids)),8)
        for row in document['sources']:collector.validate_url(row['url'])


if __name__=='__main__':unittest.main()
