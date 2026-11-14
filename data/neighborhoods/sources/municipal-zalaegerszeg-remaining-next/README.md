# Zalaegerszeg remaining numbered source quarters

This package freezes six **estimated** candidates from figure 1 (original PDF page 12) and its numbered quarter-name table (page 13) of the municipal 2014–2020 ITS approval draft. It does not change the frozen five primary Zalaegerszeg features, global registries, or global counts. The six-feature export is `remaining-inferred-import.geojson`; its proposed inferred-layer entry is `remaining-registry-entry.json`.

| Unit | Name | Explicit inferred source-boundary treatment | Length in map registration | Current exact OSM named place |
| --- | --- | --- | ---: | --- |
| 6 | Iparterület | Fill one original 1-pixel corner-touching mask hole; preserve both original exterior rings and another 1-pixel interior hole | 27.70 m of removed hole boundary; 47.89 m² added | Unknown; no exact match observed |
| 10 | Zalabesenyő | Label-ring tangent to east band; local inferred cap | 58.36 m (1.47% perimeter) | Confirmed independently |
| 11 | Botfa | Two source lobes connected through label annotation | 221.68 m (2.67%) | Confirmed independently |
| 12 | Bazita | North/south source lobes connected through label annotation | 474.34 m (5.98%) | Confirmed independently |
| 13 | Ebergény | Three source lobes connected through label annotation; southwest lobe assignment has extra uncertainty | 583.87 m (21.95%) | Confirmed independently |
| 14 | Szenterzsébethegy | Two source lobes connected through label annotation | 514.13 m (6.34%) | Confirmed independently |

These lengths measure the reconstructed source segments under the inherited map registration. They are **not accuracy estimates**. Local cap confidence is low. A 64-segment radius-31-pixel disc is only the explicitly declared annotation-removal window; no final quarter is a circle. Outside each annotation window, the source-cell footprint is unchanged to floating-point precision. Inside it, the shortest convex connection of the observed interior entry intervals is one possible interpretation. All new cap lines and alternatives with midpoint displacement of up to ±3 pixels, bounded by the window, remain separate artifacts. These alternatives illustrate ambiguity, not statistical limits. Ebergény is particularly uncertain because a substantial fraction of its small perimeter is reconstructed.

`remaining-literal-source-pixels.geojson` and `remaining-literal-world.geojson` retain the unaltered two-part unit 6 source contour. Both labelled cells are source-closed. The raw contour is Shapely-valid but the project validator rejects a single-pixel hole touching its exterior at one corner (`hole_outside_shell`). The exported estimated interpretation changes exactly that one pixel, with the literal original, changed pixel, strict failure and alternative of retaining quarantine all preserved. The historical source table expressly calls Iparterület a quarter; industrial use is not an exclusion. Current identity remains unknown and no alias was invented.

The unnumbered detached cell 92 near Bazita is retained **unassigned** in `remaining-unassigned-source-pixels.geojson`. Ebergény has an alternative omitting unlabelled southwest lobe 70 in `remaining-ebergeny-omit-lobe70-source-pixels.geojson`. Compound source units 9/15/16 and outer areas 17–20 were not cloned onto constituent quarters. The copied `zalaegerszeg-source-raster.geojson`, `zalaegerszeg-import.geojson` and `zalaegerszeg-quarantine.geojson` are historical seven-feature reference inputs, not this package's candidate export.

The frozen affine transforms original image coordinates to EPSG:23700 and then WGS84. Pixel indices denote original pixel centers; observed inside-stroke cell edges are half-integer coordinates. The same inherited affine was used for the frozen five primary features. It was fitted to municipal perimeter dashes and has **zero independent interior controls and unknown absolute accuracy**. Perimeter residuals are registration diagnostics. Independent current-name points are evidence only, never controls or replacement boundaries. The contemporary Zalabesenyő named-place point lies45.69m outside the reconstructed historical candidate; this disagreement is retained and did not cause a fit or shift. A small approximately 31.71 m² extension of unit 6 beyond the archived contemporary municipality is retained rather than clipped. No candidate is a current legal/cadastral boundary or usable for automatic address assignment. Municipal map open-reuse rights are not independently established; ODbL applies to OSM evidence.

To reproduce offline from the repository root (the name scan reads the pinned local PBF):

```sh
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/extract-current-name-evidence.py
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/derive-remaining.py
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/finalize-evidence.py
node data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/validate-remaining.mjs
python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/export-inferred.py
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/independent-review.py --check
node data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/independent-strict-validator.mjs remaining-inferred-import.geojson remaining-literal-world.geojson
python data/neighborhoods/sources/municipal-zalaegerszeg-remaining-next/manifest.py --check
```

The independent review reconstructs source pixel membership and exposed edges without the producer's horizontal-run union, recomputes the inherited affine, validates source/world transformations, tests inferred windows/alternatives and checks the one-pixel change. `remaining-conversion-proof.json`, `remaining-manual-reconstruction-proof.json`, `remaining-iparterulet-one-pixel-inference-proof.json`, `current-name-evidence.json`, `remaining-strict-validator-review.json` and `independent-source-registration-review.json` provide the detailed evidence. All six inferred exports must pass the project `validateGeometry`; the raw literal unit 6 failure is expected and retained.
