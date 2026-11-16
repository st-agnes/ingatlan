# Round 4, shard 1: remaining western/central localities

This is a collection packet, not application integration. The task's 61 names are preserved in `target-selection.json`. Work proceeds in immutable batches. Each batch's `features-batch-NN.geojson` has its own source traces and validation SHA. A later batch does not rewrite an earlier one.

## Interpretation and accuracy

These are deliberately coarse source-backed extent estimates. All inferred features have `estimated=true`, `lowConfidence=true`, `wholeQuarterAccuracyVerified=false` and `pointRadiusFallback=false`. OpenStreetMap place points establish the name/locality; they do **not** establish its boundary. The manually selected extents are interpreted from actual mapped streets, tracks, waterways, woodland/plot edges and, when available, independent municipal text. Closing links and rear plot edges remain approximations. The output is neither a cadastral survey nor a set of official administrative boundaries. Rural dűlő names may describe agricultural tracts rather than urban residential quarters.

`maps/*.png` visualize the frozen shared OpenStreetMap contexts. Their JSON records register pixels to WGS84. **The viewport rectangle is only a rendering window and is never used as an output geometry.** All pixel traces are explicit human-reviewed irregular perimeters. No circles, point-distance contours, boxes or Voronoi cells are generated. A technical point-in-polygon check confirms the named point was not accidentally lost during tracing; that does not establish full neighbourhood accuracy.

In batch 01, Rigópuszta and Csemetekert reuse native complete farmyard/nursery footprints after name/context association. Csemetekert is expressly a compact site-scale locality estimate; a wider quarter boundary has not been established. Other batch-01 outlines interpret whole local tracts/street fabrics instead of tiny covering parks/ponds. Details and uncertainty are per feature in `approximationNote`. In particular Balatonszéplak's shore-side and Ezüstpart approaches are approximate and must not be mistaken for a surveyed shoreline/tourism boundary.

## Rebuild offline

From the repository root:

```
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-1/build.py 01
```

Requires Python, Shapely and pyproj. The shared `../contexts/<contextKey>/` files and their geometry are frozen inputs; every feature records their paths and SHA-256 hashes. No PBF scan or network access is needed. `batch-NN-traces.json` records the manually chosen map vertices, actual source feature IDs where native footprints were selected, source notes and municipal URLs. `evidence/` saves web connector responses for independently searched source documents. `validation-batch-NN.json` checks nonempty valid WGS84 polygons, municipality clipping, area and source-name-point inclusion.

OpenStreetMap source attribution: © OpenStreetMap contributors, ODbL 1.0. Shared extraction snapshot: 2026-11-12. Municipal/university text is cited as corroborating locality/location evidence; it is not represented as containing surveyed polygons.

## Final collection result

All **61 targets in 33 municipalities were attempted**. Five frozen batches contain **60 candidate polygons**: 55 manual map/street/field estimates and 5 native site footprints with inferred locality association. The combined convenience file is `features.geojson`; integrate either the combined file or its batches, never both. `summary.json`, `attempts.json`, `manifest.json` and `unresolved.json` provide counts, hashes and every target's disposition.

The remaining unit is **Dombóvár – Külterületek**. Municipal ITS/HEP sources explicitly discuss the five detached puszta settlements, but the complete statistical unit boundary is not established. No residual of the whole municipality, arbitrary outer polygon or unrelated small parcel is substituted merely to report zero unresolved targets. Existing rural settlement data is preserved elsewhere; this unresolved group does not mean all individual puszták lack geometry.

**Dombóvár canonicalization caveat:** the ITS spelling `Szuhay-domb` has an explicit circuit south of Dózsa. The current `Szuhajdomb` core geometry is a small street-cell estimate north of Dózsa, containing a northern OSM label. Batch 05 supplies the documented planning extent as a source candidate. Review canonicalization and retain source alternatives rather than blindly declaring either two unrelated whole quarters or an exact alias. No name point was invented for this planning unit. The park-side closure is coarse; the historical Gyenis street split is independently documented by the municipality.

Rebuild the remaining batches with the same command and numbers `02`, `03`, `04`, `05`; then run `finalize.py` to regenerate combined summaries. The packet has no runtime/network/PBF dependency beyond the frozen shared contexts and checked-in traces. All output geometries are valid and nonempty. A name-point check is reported only when a source point exists; it is not an accuracy test.
