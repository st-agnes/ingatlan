# Körmend – round 3, 2026-11-15

Six distinct quarter names receive **estimated, low-confidence search polygons**. These estimate whole quarters and estate open space, not individual buildings. All six are valid WGS84 polygons inside Körmend and contain their archived known label. No place-point circle, Voronoi partition or broad-parent alias was created. Overlapping historic/local usages are retained with their own names.

| Name | Estimated area | Evidence and construction |
| --- | ---: | --- |
| Belváros | 1.402 km² | The [municipal 2021 notice](https://www.kormend.hu/Hirek/2021_evi_hulladekszallitassal_kapcsolatos_tajekoztato.html) identifies the streets south of Rákóczi and bounded by the Rába as Belváros. Original Rákóczi/Sport road-node paths and the Rába river arc form the main perimeter. Western Munkácsy-side and eastern Sport/Kauz-side closures to the river are inferred. This includes the central residential/historic core and castle/park side. |
| Bartók Béla lakótelep | 0.045 km² | Three original streets actually named for the estate plus the entire mapped common grass/open-land polygon form the estate envelope, with a 20 m inferred outer frontage allowance. The grass is a contextual estate input, not independently asserted as a boundary. |
| Kis Amerika | 0.288 km² | The local Ötház/Képúti/Meggyfa/Gyümölcsöskert grid and its local Mátyás/Ady/Vasútmellék approaches form the envelope, supported by the archived named-quarter street inventory. |
| Rokkant telep | 0.172 km² | Local Ady/Hunyadi/Erkel/Vasútmellék/Thököly associations support a residential/station-side estimate. The actual main Hunyadi trace constrains the east side, using the municipality's Tisztviselő-to-the-east description as context. This inferred division is especially uncertain. |
| Tisztviselő telep | 0.344 km² | Primary municipal Hunyadi/east-side description and the official transit-map name support the actual Árpád/Bacsó/Keleti/Rózsa/Vörösmarty/Móricz residential street grid and adjoining Táncsics/Mártírok streets. |
| Vasúton túl | 0.507 km² | The official transit-map name and archived named-quarter street inventory support the northern/eastern residential grid from Erkel/Petőfi through Gárdonyi/Diófa to Avar/Arasz. It does not copy the entire plural municipal waste-collection zone. |

The [municipal 2025 calendar](https://www.kormend.hu/editor_up/Hirek/2025/hulladek/Kormend-naptar-2025.V2mod.pdf) separately recognizes the northern quarters and the Bartók estate. Its indexed text was actually retrieved and is archived in the evidence JSON files. The [official MÁV transit PDF](https://helyimenetrend.mavcsoport.hu/files/public/helyi_menetrendek/kormend/Kormend_tkp_A3_251119.pdf) was opened through the web connector; its returned text labels Belváros, Tisztviselő telep and Vasúton túl. This packet uses that text as name/location context. **No PDF-image boundary tracing or unseen PDF digitization is claimed.** PDF bytes were not downloaded. A screenshot attempt returned a textual image placeholder without archivable pixels and contributes no geometric evidence.

The archived Openalfa street lists are OSM-derived secondary evidence, not official boundary definitions. They are combined with primary name/quarter descriptions and actual archived street geometries. `quarter-recipes.json` explicitly selects local segments of long town-wide streets. `build-quarter-estimates.py` constructs their whole-block convex envelopes and adds an inferred 35 m outer frontage allowance (20 m for Bartók). These outer joins and allowances are estimates; they do not assert that all source-listed streets or a particular centreline are legal boundaries. The Hunyadi constraint for Rokkant uses the main secondary road, excluding a same-named residential spur.

## Reproduce offline

From the repository root:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115-round3/kormend/build.py
```

This rebuilds all six features and both geometry-proof files using only archived inputs. Python, shapely and pyproj are required; no network, full-country PBF scan or original PDF is needed. `validate.py` checks geometry, municipal containment, label containment, distinct geometries, metadata, and deterministic rebuilding. `preview.py` produces an offline context preview.

The unchanged source road/area/label/municipality archives were reused from round 2 `west-planning/kormend/`. The source OSM snapshot is 2026-11-12; the previously recorded full PBF SHA256 is `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`. Complete original source way/node IDs, references, tags, versions, timestamps and source URLs are retained. The metric envelope operation uses EPSG:23700 and outputs EPSG:4326. Native road/river vertices are preserved for the Belváros traced parts; the five envelopes explicitly infer new outer edges. Geometry is © OpenStreetMap contributors, ODbL 1.0; no open licence is asserted for municipal documentary text.

Exact quarter extremities remain unresolved for all six. They are unsuitable for automatic address assignment or cadastral interpretation. `unresolved.json` records these limitations; it contains no missing assigned name. `alias-proposals.json` is empty. No global registry, old packet or Git file was modified.
