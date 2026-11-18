# Round 4, shard 4 — 63 low-confidence neighborhood polygons

All 63 assigned names in 31 municipalities were attempted and have source-informed WGS84 geometry. The 56 known place points are covered. Every feature is valid, lies within its municipality and is explicitly estimated with low confidence. No circle, point buffer, point rectangle or Voronoi construction is used.

Import only `features.geojson` (63 features). Alternatively the immutable `batch-01` through `batch-04` feature files contain disjoint batches of12,20,20,11names. Do not import both approaches: checkpoint files duplicate the full packet identities. Diagnostic/source GeoJSON files are inputs, not extra neighborhoods.

Most shapes follow explicitly selected groups of actual road, stream, railway, mapped land-use and municipal compartments. Rural surrounding land is retained. Dense estates/quarters use broader groups of neighboring blocks. Native farmyard enclosures represent two small rural settlements. Kecskemét has six actual municipal overview-map traces, registered coarsely from nine other settlement/label correspondences (162m fit residual; no accuracy guarantee), plus three road-block groups. Zsóry-fürdő includes the whole holiday/bath road district. Óbög uses the mapped Bög settlement corridor with adjoining physical land and may overlap Újbög. Salgótarján’s explicitly rural planning unit is approximated by the municipality remainder after mapped continuous built-up surfaces and the prior Eresztvény estimate are excluded.

These are approximate address-search areas, not authoritative or fully verified modern neighborhood boundaries. Some source compartments or literal settlement footprints are partial. `unresolved.json` and per-feature approximation notes preserve those limitations. In particular only42%of the coarse Bödögsor map trace remains inside the modern municipality. The map spellings Bordás/Borbás and northern industrial/logistical name alignment need identity handling; `alias-review.json` proposes review without changing global aliases. Parent/child quarters and their overlaps are retained.

Offline rebuild from this directory:

`PYTHONPATH=/workspace/ingatlan/.local/geodata python build.py`

Requires Python with Shapely, pyproj and NumPy. All geometry inputs, source object versions/URLs, original PBF hash and place/address source records are in `source-inputs/`; no PBF scan, network or PDF download is needed. `selections.json` stores the explicit geometry recipe. `source-evidence.json` records boundary/source anchors and selection limitations. Municipal source-page subsets and map registration are archived in `kecskemet/` and `salgotarjan/`; primary web facts are paraphrased in `primary-web-source-facts.json`. `features-preview.pdf` provides31town map pages. `inspection/`, source map crops and candidate cell files are diagnostic material.

The executable full-packet build is `build.py`. A copied initial recipe in `batch-01/build.py` is historical checkpoint evidence; to replay that subset separately, put its `selections.json` beside a copy of the full-packet build and the archived source-inputs, or filter the full rebuilt output by the checkpoint names.

OSM snapshot2026-11-12T21:23:05Z; PBF SHA256224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a. © OpenStreetMap contributors, ODbL-1.0. The parent performed one shared country extraction; this shard did not scan the PBF or mutate any older/global packets.
