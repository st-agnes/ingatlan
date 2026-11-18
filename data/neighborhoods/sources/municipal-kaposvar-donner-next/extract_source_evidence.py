#!/usr/bin/env python3
"""Reproduce two bounded municipal PDF text-image proof crops; no network."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import fitz

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PDF = ROOT / '.local/neighborhoods/supplement-originals/kaposvar-fvs.pdf'
SHA256 = '291aba20ffcc41e604ad737bb6d132ae51b51d70303285e36702e4fc04e6901e'


def build():
    raw = PDF.read_bytes()
    assert len(raw) == 6965334 and hashlib.sha256(raw).hexdigest() == SHA256
    document = fitz.open(stream=raw, filetype='pdf')
    assert '2023. július' in document[0].get_text()
    assert '2.0 verzió' in document[0].get_text()
    records = []
    outputs = {}
    for page_number, term, filename in [
        (185, 'Zselici út', 'source-p185-route-name.png'),
        (186, 'A Kapos déli', 'source-p186-donner-description.png'),
    ]:
        page = document[page_number - 1]
        block = next(block for block in page.get_text('blocks') if term in block[4])
        rectangle = fitz.Rect(block[:4])
        rectangle.x0, rectangle.x1 = 80, 535
        if page_number == 186:
            rectangle.y0 = 174
            assert 'a 67-es út és Kapos a Zselic-csatorna között' in block[4]
        image = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=rectangle).tobytes('png')
        outputs[filename] = image
        records.append({'pdfPageOneBased': page_number, 'rectanglePdfPoints': list(rectangle),
                        'renderScale': 2.5, 'output': filename,
                        'sha256': hashlib.sha256(image).hexdigest()})
    proof = {
        'schemaVersion': 1, 'sourceUrl': 'https://kph.kaposvar.hu/data/adattar/fvs21-27/fvs21-27.pdf',
        'localRawPath': str(PDF.relative_to(ROOT)), 'pdfSha256': SHA256,
        'pdfBytes': len(raw), 'pdfPageCount': len(document),
        'coverDate': '2023-07', 'coverVersion': '2.0', 'planningPeriod': '2021–2027',
        'pdfCreationMetadata': document.metadata['creationDate'],
        'p185ShortRouteQuote': '67-es úttól (Zselici út)',
        'p186PrintedMalformedPhrase': 'a 67-es út és Kapos a Zselic-csatorna között',
        'sourceInterpretation': 'Donner lies south of the Kapos between road 67 and Zselic-csatorna, toward Szigetvári út. The sentence visibly contains an extraneous or misplaced Kapos token; this packet discloses the four-edge reading as an inference rather than silently correcting the source.',
        'distinctQuarterIdentityEvidence': 'The next sentence describes Rómahegy as adjoining Donner to the east, with its own named-edge sequence. This supports Donner as a distinct named place; the combined map-unit geometry is not used to create a child.',
        'modernRouteChoice': 'Same-document p185 identifies road 67 as Zselici út. The November2026 OSM road67/Zselici route and Szigetvári utca are used. No independent historical route-change survey has been performed.',
        'sourceAgeUncertaintyMetres': None, 'currentFineNameIndependentlyConfirmedFor2026': False,
        'crops': records, 'rawPdfCommitted': False,
        'municipalSourceOpenReuseLicenceEstablished': False,
        'usableForAddressAssignment': False,
    }
    outputs['source-evidence.json'] = (json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode()
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for filename, raw in build().items():
        if args.check:
            assert (HERE / filename).read_bytes() == raw, filename
        else:
            (HERE / filename).write_bytes(raw)
    print('Pinned municipal source and both bounded page crops verified.')
