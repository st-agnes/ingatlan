# Frozen batch 02 — fourteen urban street/plot estimates

This packet adds 14 named areas in 8 municipalities. All are explicitly estimated and low confidence; none is an official cadastral boundary. The polygons interpret whole actual residential street/plot groups, not point buffers, rectangles, nearest-point cells or individual building footprints. Different named areas may overlap. Source context geometry, hashes, map registration and all chosen pixel vertices are retained in the batch specifications and feature provenance.

Kistarcsa is particularly well supported: the local historical description identifies four enclosing streets for each of Kakastelep and Telep. Municipal development, transport, road/asset or meeting records confirm the other local names and geographic context, while the archived native road/landuse data supplies the actual spatial edges. Where there is no explicit named-area perimeter, the choice of outer streets/plots is disclosed as inference. Szada Halesztanya is a coarse historic locality estimate, not an assertion that it equals all of modern Fenyvesliget.

Rebuild and verify from the repository root:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-3/build.py batch-02
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-3/verify.py batch-02
```

All 14 geometries are valid, cover their saved locality label and reproduce byte identically offline. Technical verification does not establish exact geographic accuracy. See `summary.json` for all input hashes and `features.geojson` for construction and source URLs. No application or production database changes are included.
