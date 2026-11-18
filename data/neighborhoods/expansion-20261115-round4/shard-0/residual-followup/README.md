# Western shard residual follow-up

The frozen parent packet is unchanged. This separate packet contributes **Gyugy / Sandipuszta**, one low-confidence WGS84 polygon, derived from 30 actual OSM building footprints around the independently named locality. The 116,474 m² envelope includes an estimated 20 m allowance for yards/frontage and generalizes gaps within the built compound. It is explicitly partial relative to an unknown historical estate, and unsuitable for authoritative address assignment. No circle, point buffer, Voronoi cell or track-only hull was used. Alsómajor remains a distinct locality.

The Hungarian Digital Place-name Register documents Sandipuszta in 1862–1974 and distinguishes it from Sandi vineyard and field names. The original OSM point lies among the 30 selected buildings. This anonymous-building extraction supplies the spatial evidence missing from the first frozen packet. A later photo register gives a numbered Sandipuszta address to a roadside cross; this supports continued name use but supplies no boundary and is not treated as a chapel location.

**Babosdöbréte / Árkosháza-puszta has a separate, reviewed quality-9 candidate** in `arkoshaza-reviewed-candidate.geojson`. Its historical identity is confirmed by MNL records (including six houses/31 residents in 1962), municipal historical text, and the HUN-REN regesta index placing it north of Babosdöbréte. The municipality reports that the hamlet disappeared. No current extracted building lies within 766 m of the exact OSM point.

The reviewed candidate is a coherent 1,000,796 m² rural representative tract north of the present village core. The actual road/forest/municipal linework closes around the name point with no invented edges. Seven tracks supply most exterior edges; the actual municipal border supplies 998 m of closure, and a forest ring is an interior exclusion. There is no closed physical-only circuit containing this point. No other known place label or native residential/farmyard/industrial surface lies inside; no extracted building intersects it. The anonymous-building window covers 95.93% of the tract, and no complete-building claim is made for the northern tip. This is **not a recovered historical compound or estate perimeter**: `historicEstateBoundaryKnown:false`, `disappearedSettlement:true`, `representativeLandscapeTract:true`, `partialFootprint:true`, `lowConfidence:true`. It is separately ready for root's final intake decision and does not alter the pinned Sandipuszta collection.

`arkoshaza-landscape-review.png` shows the reviewed native edges and context; `arkoshaza-geographic-review.json` records the interpretation and coverage limitations. The earlier `arkoshaza-road-municipality-proposal.geojson` is retained as pre-review evidence only. The extraction viewport is never an output boundary. Image-only PDF screenshot placeholders were not treated as viewed maps or digitized.

Offline rebuild:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python check-arkoshaza-circuit.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python build-arkoshaza-candidate.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python validate.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python render-context.py
```

`source-inputs/` archives the exact selected source polygons, the two full anonymous-building extracts, roads/areas/labels, municipal geometry and PBF provenance. `recipe.json` defines the sole accepted estimate; `build-proof.json` records hashes and geometric checks. Web search/open evidence is preserved verbatim as tool responses in `evidence/`, with limitations stated above. All OSM inputs are from the 2026-11-12 snapshot, ODbL-1.0, © OpenStreetMap contributors. No aliases are proposed.
