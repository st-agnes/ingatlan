# Reviewed identity corrections, without frozen-source edits

Two canonical-display/name corrections authorized after independent source identity review. All source geometry, low-confidence and partial-extent flags remain intact. This packet adds no new spatial area.

- Dombóvár: canonical **Szuhajdomb**, aliases **Szuhay-domb** and **Szuhaj-domb**. The explicit municipal ITS whole planning-circuit estimate is copied unchanged, with quality score increased by one to select it under the canonical display. The earlier small northern street-cell and original new estimate remain registered geometry alternatives under one identity. The shapes are not unioned; historical/source-scope limitations remain.
- Kecskemét: canonical child **Borbás belterület**, aliases **Bordás** and **Bordás belterület**. Same-document enumeration plus companion municipal volume establish the printed map spelling discrepancy. The small inner-settlement footprint is copied unchanged with quality score increased by one. The broader rural **Borbás** parent remains a separate identity; it is not part of this alias row.

Evidence is pinned to `../shard-1/identity-followup/review.json` and `../shard-4/alias-review.json` with primary URLs retained in each correction. `input-pins.json` locks the frozen inputs. Build/check offline with `PYTHONPATH=/workspace/ingatlan/.local/geodata python3 .../identity-corrections/build.py [--check]`. `register.py` idempotently applies only these two reviewed alias declarations and appends the exact correction packet/hash. Stable identity redirects and all original geometries are handled by the existing catalogue exporter; old frozen files are unchanged.

This review does not certify exact surveyed geography. It does not apply the separately proposed Bódogsor, Északi logistics/industrial or other pending aliases.
