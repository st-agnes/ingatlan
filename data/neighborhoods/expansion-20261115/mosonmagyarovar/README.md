# Mosonmagyaróvár – 2026-11-15 expansion

`features.geojson` adds 14 of the 16 point-only names in the 2026-11-14 inventory. Belváros and Dunapart remain unresolved. Ipartelep already has a collected polygon and is not duplicated. Every new feature is explicitly `estimated: true`, `lowConfidence: true` and unsuitable for automatic address assignment. No point-radius circles, Voronoi cells or aliases are created.

The seven principal residential-quarter estimates come from the coloured map on PDF page 5 of the Mosonmagyaróvári Városvédő Egyesület's [2021 city history](https://www.mve1985.hu/images/CLLD/I_resz.pdf). `source-clld2021.pdf`, its embedded map, contextual text pages and the manual pixel interpretations are archived. The [2008 municipal IVS](https://www.movinnov.hu/docs/IVS-1.pdf), archived as `source-ivs2008.pdf`, provides corroborating historic quarter identities and named-road circuits on printed pages 37–38. Its units are broader statistical groups in several places; those polygons have not been indiscriminately assigned to each smaller estate.

The CLLD map groups Lucsony and Károlyliget in one pink parent. The two outputs are deliberately different, adjoining estimates: the older Lucsony settlement north of the approximate Palánk/Kígyó corridor, and the later Károlyliget garden-city extension south of it. The accompanying source history, distinct contemporary names and the source street plan support this division, but its internal line is low confidence. Broad Majorok and Mofém quarters may overlap their separately named newer estates. Magyaróvár follows the broad yellow source quarter; the old OSM Magyaróvár name node is west of this footprint and was not used to force its extent.

The 534×737 map is manually traced and affinely georeferenced using the recognizable castle locality, Királyhidai/Huszár Gál junction and Szent István király/Mosonyi Mihály junction. Pixel selections are approximate. `georef-preview.png` overlays contemporary OSM roads for review; the old schematic map has visible local mismatches. A three-control fit does not establish surveyed accuracy. Likely local uncertainty is tens to hundreds of metres, and edges should be treated as broad search hints.

Vár reuses the unchanged source polygon of the named Mosonmagyaróvári vár grounds. This recognizable site contains the Vár name node; the locality may extend beyond those grounds.

Gyöngyös-telep and Halászi úti lakótelep use explicit enclosing real street blocks selected by the named locality nodes, supported by the city-history descriptions and visible quarter/street map. Their full development perimeter may cover further blocks. The other four estate estimates use envelopes of explicit source street networks. Manninger János and Móra Ferenc each use only road ways carrying that estate's name, so the two distinct names do not receive an identical enclosing parent block. These are rough interior footprints and may omit buildings outside the internal roads. Duna uses the named royal/historical-person street set, consistent with the local municipal-news account of its street naming. Lajta uses its residential street network across the Lajta from Mofém, including the municipally documented Lomb street park. The Lajta selection is geographically scoped to the estate on the archived map to exclude a different Kalász utca farther south. Convex-hull connections between outer road vertices are explicit estimates, not surveyed parcel boundaries. Individual limits and source URLs are attached to each feature.

## Offline reproduction

From the repository root:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/mosonmagyarovar/build-street-traces.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/mosonmagyarovar/build-road-estates.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/mosonmagyarovar/build.py
```

Python, numpy, shapely and pyproj are needed. Generation is offline from the archived JSON/GeoJSON/raster inputs. Optional `extract-osm.py` recreates the local road and contextual named/land-use polygon archive from the already-local Hungary PBF and needs pyosmium; it is unnecessary for normal regeneration. `preview-roads.py` and `georef-preview.py` need Pillow.

The OSM snapshot is 2026-11-12, country PBF SHA256 `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`, © OpenStreetMap contributors, ODbL 1.0. Original way IDs, node references, tags, versions and timestamps are archived. No open municipal or association map licence is asserted; these PDFs are documentary evidence for explicitly estimated search polygons. Source acquisition is also recorded centrally in `../downloaded-sources/acquisition-status.json`.

`build-proof.json` pins all geometry inputs. `summary.json` and `unresolved.json` record coverage, validation and the two remaining names. Only this packet was edited; global registry integration is left to the coordinating agent.
