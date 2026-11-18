"""Offline validation of the fixed national boundary archive collector."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'fetch_national', Path(__file__).resolve().parents[1]/'scripts/neighborhoods/fetch-national.py')
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, headers=None, url=collector.URL):
        super().__init__(data)
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


class ArchiveCollectorTests(unittest.TestCase):
    def test_initial_and_redirect_urls_cannot_escape_approved_https_host(self):
        self.assertEqual(collector.validate_url(collector.URL), collector.URL)
        for url in ['http://raw.githubusercontent.com/a',
                    'https://raw.githubusercontent.com.example.org/a',
                    'https://raw.githubusercontent.com@evil.example/a',
                    'https://token@raw.githubusercontent.com/a',
                    'https://raw.githubusercontent.com:8443/a',
                    'https://github.com/a', 'file:///tmp/source']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                collector.validate_url(url)
        with self.assertRaises(ValueError):
            collector.ValidatedRedirects().redirect_request(
                None, None, 302, '', {}, 'https://evil.example/archive')

    def test_archive_is_streamed_and_both_fingerprints_are_checked(self):
        data = b'PK\x03\x04test archive fixture'
        git_sha = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        with patch.multiple(collector, EXPECTED_BYTES=len(data),
                            EXPECTED_GIT_BLOB_SHA1=git_sha, CHUNK_BYTES=3):
            output = io.BytesIO()
            result = collector.copy_verified(Response(data), output)
            self.assertEqual(output.getvalue(), data)
            self.assertEqual(result['gitBlobSha1'], git_sha)
            self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(result['bytes'], len(data))
            with self.assertRaisesRegex(ValueError, 'SHA1'):
                collector.copy_verified(Response(b'x'*len(data)), io.BytesIO())
            with self.assertRaisesRegex(ValueError, 'byte count'):
                collector.copy_verified(Response(data[:-1]), io.BytesIO())

    def test_limit_headers_compression_and_final_response_are_validated(self):
        for response, message in [
            (Response(b'1234'), '12 MiB'),
            (Response(b'', {'Content-Length': '4'}), 'oversized'),
            (Response(b'', {'Content-Encoding': 'gzip'}), 'compressed'),
            (Response(b'', url='https://evil.example/archive'), 'HTTPS')]:
            with self.subTest(message=message), patch.multiple(
                    collector, MAX_BYTES=3, EXPECTED_BYTES=2):
                with self.assertRaisesRegex(ValueError, message):
                    collector.copy_verified(response, io.BytesIO())

    def test_existing_output_is_rejected_before_any_network_request(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, 'build_opener') as opener:
            with self.assertRaises(FileExistsError):
                collector.fetch(Path(directory))
            opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
