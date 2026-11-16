# Round 4 — shard 2

Frozen final output: **68 polygons for all 68 assigned names in 23 municipalities**. Every output is `estimated: true`, `lowConfidence: true`; no native quarter boundary is claimed. The five immutable batches contain 14, 12, 17, 14 and 11 new names. `features.geojson` is their aggregate. `task-selection.json` freezes the assignment at baseline `19caaea641ae90080ab725fd03a68362530199a9`. The assignment is not an authoritative inventory: zero remaining assigned names establishes neither complete town nor national coverage.

These are broad search-area estimates based on preserved actual roads, tracks, drainage, native municipal boundaries, land-use/compound surfaces and cited public locality evidence. They are not legal or surveyed boundaries. No circle, point-generated box, Voronoi region or automatic road hull is used. Identification points select the locality and check the ring; they do not generate the geometry. Map viewports only define rendering/extraction windows.

`specs/*.json` preserves every manually drawn ring, named geometry anchors, source paths and uncertainty note. `evidence-ledger.json` connects those inputs and factual/inferred observations to all 68 outputs. `source-manifest.json` lists the actual local inputs with SHA256 hashes. Web research is preserved in `research/`; municipal PDFs were observed through connector text/indexed map descriptions, and no unobserved native PDF digitization is claimed. The municipal Felsőtag street sequence, Klenity streets, Diósd historic streets and Pannónia estate streets provide explicit boundary anchors. Other edges, particularly historical fields, hillside gardens and estate phase transitions, are inferred.

Pomáz uses the frozen round-2 street/surface context copied here as `cached-pomaz-*`. The other towns use `../contexts/<contextKey>/`, produced by the parent's one shared country pass and referenced/hash-checked per feature. No further PBF scan or shell network was used. OSM source date: `2026-11-12T21:23:05Z`. OSM data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL-1.0. Native source metadata is preserved in the context files. Derived source views for all 68 targets are retained in `map-*.png`, with `map-registration.json` and `render-maps.py`.

Historical, functional and parent/child overlap is intentional. `aliases-proposed.json` proposes no identity merges. Examples kept separate include Felsőtag/Tihanyi, Felsőhegy/Farkasverem, Györgyhegy/Györgyliget, Róka-hegy/Rókahegyi and Bösztör/Bösztörpuszta. Hókony represents the named waterfront settlement strip, while Bösztör/Bösztörpuszta estimate the major/hamlet localities; their wider historical rural landscapes are not claimed to have exact established perimeters. The Diósd Ófalu estimate follows the cited protected historic street portion; everyday usage may be broader. `unresolved.json` records these continuing uncertainties even though all assigned names have an estimate.

Offline rebuild/verification from repository root, with Python and Shapely:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-2/build.py
python3 data/neighborhoods/expansion-20261115-round4/shard-2/finalize.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-2/verify.py
```

`create-*.py` records coordinate assembly stages; the final `specs/*.json` files are the authoritative offline build inputs. Verification checks geometry validity, source hashes, all 69 identification points, assignment coverage, batch identity and byte-identical reconstruction. These are integrity checks and do not establish positional accuracy or complete conventional extent. `WORK-STATE.json` is final; collection in this shard is finished. Integration and publishing belong to the parent task.
