# Szombathely – 2026-11-15 expansion

`features.geojson` contains 14 WGS84 Polygon/MultiPolygon search areas for the 14 names missing from the 2026-11-14 priority inventory. All are explicitly `estimated: true`, `lowConfidence: true` and unsuitable for automatic address assignment. There are no alias proposals and no point buffers.

Eleven names come from the municipality's [2013 IVS](https://kbr.szombathely.hu/kbrfile/46469.pdf), which reproduces the 2001-census/2003-KSH internal division of the city. These historical units are preserved as source-defined units even when they overlap present-day neighbourhoods. They are not substitutions for modern Olad, Herény, Kámon, Újperint, Gyöngyösszőlős, Gyöngyöshermán or Szentkirály polygons. In particular source unit 14 includes several eastern communities and source unit 10 combines Alsóhegy and Középhegy; neither is aliased to one contained modern name.

Ten of those eleven use a coarse manual trace of the numbered 480×476 overview map. Red unit separators and the historical grey/green built-up perimeter define the traces in `map-traces.json`. The three controls in `control-points.json` are, in order: Dolgozók útja/Faludi Ferenc utca (pixel 75,151); Zrínyi Ilona utca/Mátyás király út (219,272); Hámor utca/Bártfa utca (296,176). Coordinates are the corresponding intersections in archived OSM road geometry. A local affine fit maps pixels to WGS84. This old, low-resolution map supports rough areas only; local error may be tens to hundreds of metres and the fit itself does not establish accuracy. `georef-preview.png` overlays archived contemporary streets/waterways on the raster for review. The industrial unit 16 excludes the already traced unit 15 Éhen Gyula kertváros.

The remaining historical unit, **Belváros (városmag)**, reuses the archived municipal street-circuit trace in `existing-belvaros-documentary-trace.geojson`; its ordered-road evidence is in `source-unit1-trace-proof.json`. It must remain separate from the currently selected modern OSM Belváros: approximately 0.662 versus 1.222 km², intersection-over-union 0.483. An initial alias hypothesis was rejected on this footprint evidence.

The three contemporary estate/local names use real closed street blocks selected by their archived OSM named nodes, not circles. `build-estate-traces.py` polygonizes only the explicitly listed enclosing roads. Géfin's block is supported by the municipal former-barracks/Remix description between Gagarin, Géfin Gyula, Kálvária and Szent László király streets. Öntöde uses the block east of Géfin Gyula utca around the named point and the primary local Öntöde landmark. Lovasiskola uses the Jégpince–Brenner János–Lovagló–Mélykúti envelope around Rákosi Jenő and Matók Leó streets; the estimate includes some gardens and the adjacent riding ground. These are deliberately rough search envelopes; full development-phase and parcel boundaries are not claimed. Source URLs and individual limitations are attached to each feature. `web-source-evidence.json` and `web-search-evidence.json` archive the web connector's source text and metadata. The municipal PDF direct-open timed out; its indexed municipal text, the academic name/site description and the primary source URLs are preserved in the search archive. `estate-source-areas.geojson` archives nearby original OSM building/land-use polygons solely for visual context, not as a claimed estate perimeter.

## Offline reproduction

From the repository root:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/szombathely/build-estate-traces.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261115/szombathely/build.py
```

Dependencies: Python, numpy, shapely and pyproj. Generation needs no network and does not read the country PBF. The optional `extract-estate-areas.py` reproduces the contextual OSM building/land-use archive from the already-local, pinned Hungary PBF; it additionally needs pyosmium. `preview-estates.py` and `georef-preview.py` generate review images and additionally use Pillow.

Archived municipal proof pages, the embedded overview JPEG, source boundary definitions, OSM linework, named points, documentary unit 1/unit 15 traces and the fixed manual interpretations are all in this directory. The OSM snapshot is 2026-11-12, SHA256 `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`, © OpenStreetMap contributors, ODbL 1.0. The municipal document is documentary evidence; no open municipal-map licence is asserted.

`build-proof.json` pins generation inputs. `summary.json` records coverage and validation. Historical textual ambiguities, modern growth and street-side/parcel choices remain approximation limits, not reasons to replace the recorded source units with parent-place polygons. Only files in this packet were changed; integration into the global registry is left to the coordinating agent.
