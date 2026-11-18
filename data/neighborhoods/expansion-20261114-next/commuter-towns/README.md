# Budaörs, Tatabánya and Dunakeszi: 29 additional practical footprints

These are **low-confidence estimated search footprints**, not newly discovered
official whole-quarter polygons. They replace 29 point-radius fallbacks with
mapped street/landuse interpretations: Budaörs 12, Tatabánya 9, Dunakeszi 8.
They are data-only research artifacts; they do not change the application.

The 15 hand-traced footprints use the saved physical-map context, actual roads,
open/wooded land transitions and existing native quarter parents where available.
The other 14 select actual closed local road/rail/water cells. Those may cover one
useful physically separated portion of a broader housing estate. Broad native
quarter names and smaller estate names remain distinct. Overlap is intentional;
in particular the Malomárok quarter and Malomárok lakópark are different scales.
No whole-city parent was copied to a local name. No circles, radius buffers,
Voronoi regions, nearest-label tessellation or point hulls were constructed.

## Retained evidence and reproduction

`extract-context.py` reads the already downloaded 2026-11-12 Hungary OSM snapshot
offline. Its SHA256 is pinned in `source-summary.json`. Original street ways,
closed landuse ways, named point evidence, municipal outlines and existing parent
features are retained in this directory. OSM attribution: © OpenStreetMap
contributors, ODbL-1.0. Named points supply names/location evidence, not boundaries.
`target-circles-reference.geojson` is an input reference only and must **never** be
imported as new polygon evidence.

`render-context.py` produces the saved physical maps and EOV/pixel registration.
`build-candidates.py` saves 98 diagnostic cells. **Do not import those candidates.**
`selection.json` records explicit per-town choices and manually traced vertices.
`build.py` rebuilds the final per-town files and refuses to alter an already saved
file's bytes. `validate.py` checks geometry, name uniqueness, source-point inclusion
and per-town hashes. `render-selected.py` overlays the selected footprints for review.

Run with the preinstalled GIS environment:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/commuter-towns/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/commuter-towns/validate.py
```

Only the three `*-features.geojson` files listed by `summary.json` are intake
artifacts. The earlier Fehérvár/Nyíregyháza 80-feature packet was left unchanged.

## Additional documentary context

Budaörs municipal public-space ordinance identifies Lakótelep using the
Szabadság út, Bretzfeld utca, Baross utca and Árok utca perimeter:
https://budaors.hu/dokumentumok/onkormanyzat/rendeletek/a-kozteruletek-hasznalatarol-25-2018-ix21.pdf
The output is an approximate trace of that street loop, not an exact legal
boundary assembly. The former attempt to assemble source road centre lines left
roundabout gaps and is not used as an exact result.

The Tatabánya municipal native map and registration remain archived in
`data/neighborhoods/sources/municipal-west/`; its source URL is
https://njt.jog.gov.hu/document/c5/c56aLL_EJR_13372578-H_SZ_3.mell_klet.pdf .
`tatabanya-native-quarter-map.png` is a review rendering. Local library evidence
identifies the Gál István estate and Bárdos school:
https://www.jamk.hu/ek/public/08030601/ki_kicsoda.pdf .

The Dunakeszi Tiszti estate is supported by named Janek Géza and Keszthelyi István
street context. Its much larger 638000 m² diagnostic cell was deliberately not
selected, because it also extends into riding/open land. The smaller manual
footprint is still an estimate.

## Remaining local work

The saved source context also covers seven Szigetszentmiklós and seven Gödöllő
fallback names. This final 29-feature cohort prioritizes the three stronger town
contexts; no national-completeness percentage is claimed.
