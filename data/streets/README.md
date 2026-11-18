# Magyar Posta street source snapshot

`sources/StreetNames.xml.gz` preserves every byte of the official public
`StreetNames.xml` downloaded on 2026-11-18, using deterministic gzip packaging.
Its decompressed SHA-256 is pinned in `source.json` together with the official
HTTP download link, source documentation hashes and acquisition provenance.

The source contains 124,188 postal street rows across all 3,155 canonical
municipalities. `coverage.json` records the complete audited coverage, including
130 Budapest rows whose special postal codes do not establish a district.
The derived runtime catalogue contains 123,354 street identities and retains
every source street/postcode pair. There are no manual city mappings.

Use permission, attribution, normalization, Budapest exceptions, runtime schema
and update instructions are documented in [STREET-DATA.md](../../docs/STREET-DATA.md).

```sh
python3 scripts/import-streets.py --check
python3 tests/street-data.test.py
```

The source supplies names, types, municipalities and postcodes. It supplies no
house numbers, property coordinates or street geometries.
