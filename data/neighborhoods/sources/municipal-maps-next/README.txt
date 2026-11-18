Kecskemét – source-defined street circuit

One fine quarter is derived: Erzsébetváros. It is a subquarter inside the broader
Belváros in the municipal 2021 source, not a relabeling of the whole parent area.
The exact municipal boundary statement is preserved in kecskemet-circuit-source.json
and the original-page subset kecskemet-source-pages.pdf. Original publisher PDF
SHA256, subset SHA256, exact OSM way features and source archive hashes are retained.

Every exported vertex is an actual preserved OSM source vertex, and every segment
is covered by one of the 18 used source ways on the five specified streets. There
are no inferred connectors, buffers, synthetic closing chords or geometry repairs.
Two tiny road-junction cells are excluded. The entire polygon is contained in the
canonical Kecskemét municipality polygon. Independent source/geometry review is
in scout/kecskemet-independent-review.json.

This is still an unreviewed boundary candidate, not a cadastral/current legal or
automatic address-assignment layer. The interpretation uses municipal 2021 facts
with actual 2026 OSM street centerlines; street-side parcel precision is not claimed.
The other six fine source subquarters remain explicitly unresolved in the source
facts. Broad Belváros is a parent area and does not replace the seven finer quarters.

Geometry: ODbL-1.0, © OpenStreetMap contributors. The publicly published municipal
source has no independently verified explicit open geodata licence. Its factual
road boundary statement is used; cadastral source geometry is not copied.

Reproduce/check from the repository root:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-municipal-maps-next.py --check
Dependencies: Python3, Shapely2.1.2, pyproj3.7.2. No network request is made.

Other inspected city maps are documented in scout/inspection.json: Pécs DOES show
fine quarter lines but the 585x514 raster and unresolved control matching prevent
a reliable geographic export. Miskolc and Salgótarján maps show merged planning
clusters. No unvalidated polygon was manufactured from those maps.
