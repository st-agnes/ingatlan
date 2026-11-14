#!/usr/bin/env python3
"""Reproduce the bounded Kaposvár supplemental-source assessment; no network.

Original PDFs remain in ignored .local. Only selected native map images and
short, page-specific identity evidence are retained in this source packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORIGINALS = ROOT / ".local/neighborhoods/supplement-originals"
SOURCES = [
    {
        "id": "kaposvar-belvaros2009",
        "url": "https://kph.kaposvar.hu/eloterjesztesek/et20090226/doku/e28m01.pdf",
        "sha256": "88ceb3ea0db709ee27a8003f29db3c12937f05ce447161b45e52e8b1b8e1ba3b",
        "bytes": 14880108,
        "pageCount": 243,
        "mapPage": 26,
        "mapXref": 157,
        "sourceDate": "2009-02",
        "title": "Kaposvár Városközpont funkcióbővítő városrehabilitációjának akcióterületi terve",
        "evidencePages": [1, 25, 26, 27, 28, 29, 30, 44],
        "requiredText": {
            1: ["2009. FEBRUÁR"],
            25: ["Az IVS-ben kijelölt városrészek", "Északnyugati városrész"],
            27: ["ezen a városrészen belül", "Gyékényesi vasútvonal"],
            44: ["13,85 ha", "város-rehabilitációs akcióterületként"],
        },
    },
    {
        "id": "kaposvar-fvs",
        "url": "https://kph.kaposvar.hu/data/adattar/fvs21-27/fvs21-27.pdf",
        "sha256": "291aba20ffcc41e604ad737bb6d132ae51b51d70303285e36702e4fc04e6901e",
        "bytes": 6965334,
        "pageCount": 388,
        "mapPage": 182,
        "mapXref": 991,
        "sourceDate": "2023-07",
        "planningPeriod": "2021–2027",
        "documentVersion": "2.0",
        "title": "Kaposvár Fenntartható Városfejlesztési Stratégiája 2021–2027",
        "evidencePages": [1, 181, 182, 183, 184, 185, 186, 187, 188],
        "requiredText": {
            1: ["2023. július", "2.0 verzió"],
            181: ["jelen stratégia is megtartja", "város tíz városrészét"],
            182: ["30. ábra: Kaposvár városrészei", "1. BELVÁROS"],
            183: ["4 jól elkülöníthető területre", "2. ÉSZAKNYUGATI VÁROSRÉSZ"],
            186: ["6. DONNER - RÓMAHEGY", "Ivánfai árok", "Szigetvári út"],
        },
    },
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build(originals: Path) -> dict[str, bytes]:
    outputs = {}
    records = []
    for source in SOURCES:
        path = originals / (source["id"] + ".pdf")
        raw = path.read_bytes()
        assert len(raw) == source["bytes"], (path, "size")
        assert sha(raw) == source["sha256"], (path, "sha256")
        document = fitz.open(stream=raw, filetype="pdf")
        assert len(document) == source["pageCount"]
        for number, required in source["requiredText"].items():
            # Join PDF line wraps and ordinary word-wrap hyphenation only.
            text = document[number - 1].get_text().replace("-\n", "-")
            joined = " ".join(text.split())
            for phrase in required:
                assert phrase in joined, (source["id"], number, phrase)
        page = document[source["mapPage"] - 1]
        image = document.extract_image(source["mapXref"])
        assert image["ext"] == "jpeg"
        assert not page.get_drawings(), "The assessed map is raster, not native PDF paths"
        output_name = f'{source["id"]}-p{source["mapPage"]}-source.jpeg'
        outputs[output_name] = image["image"]
        records.append({
            k: v for k, v in source.items() if k != "requiredText"
        } | {
            "originalPath": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "pdfCreationDateMetadata": document.metadata.get("creationDate"),
            "map": {
                "output": output_name,
                "sha256": sha(image["image"]),
                "bytes": len(image["image"]),
                "width": image["width"],
                "height": image["height"],
                "format": image["ext"],
                "nativeVectorPathCountOnMapPage": len(page.get_drawings()),
                "imageRectanglePdfPoints": [list(rect) for rect in page.get_image_rects(source["mapXref"])],
                "nativeImageBytesRetained": True,
                "pixelCoordinateSystem": "image pixels; x right, y down; not geographic coordinates",
                "geographicProjectionEmbedded": False,
                "geographicControlOrAccuracyClaimed": False,
            },
        })
    outputs["source-inventory.json"] = encoded({
        "schemaVersion": 1,
        "municipality": "Kaposvár",
        "assessmentDate": "2026-11-14",
        "sources": records,
        "rawPdfPolicy": "Original PDFs remain ignored/local; selected native map images retained only.",
        "sourceRightsStatus": "Public municipal publications; open reuse licence not independently established.",
    })
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare outputs without writing")
    parser.add_argument("--originals", type=Path, default=ORIGINALS)
    args = parser.parse_args()
    for name, expected in build(args.originals.resolve()).items():
        destination = HERE / name
        if args.check:
            assert destination.read_bytes() == expected, (name, "reproduction mismatch")
        else:
            destination.write_bytes(expected)
    print("Kaposvár supplemental native maps and pinned source inventory reproduced; 0 polygons emitted.")


if __name__ == "__main__":
    main()
