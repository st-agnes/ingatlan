This is one LOW-CONFIDENCE ESTIMATED Belváros candidate for Szentes. It is a
reviewable reconstruction from an explicit older municipal IVS street/river
circuit and current literal OpenStreetMap road/path/waterway centerlines.

inferred-candidate.geojson is the only compiled candidate. The orange Apponyi
perimeter variant is retained under raw/ as an alternative for the same quarter;
it must not be exported or counted as another neighborhood. Preferred area is
1.156813 km², 99 vertices. The alternative differs by 41,611 m² (3.6%). This is a
finite interpretation comparison, not an absolute positional accuracy bound.
Only the Apponyi square interpretation has two reconstructed footprints. The
other five assumptions each retain one chosen physical path and an unresolved
source choice; they do not have independently reconstructed alternative areas.
The two footprints therefore do not form a full uncertainty envelope.

The source contour has NOT been observed. Original PDF/map bytes were not
acquired; web indexed municipal PDF text supplied the factual boundary list.
The municipal URL is a January2015 reupload of an older edition containing
2009/2010 material. Exact adoption/date and historical street alignment were not
verified. Current FVS indexed map descriptions and OSM labels establish names
only; they do not prove boundary equivalence or determine this geometry.

The 19 distinct source facts consist of fifteen named roads, Kurca, the Apponyi
square reference and two cadastral-road references. semantic-proof.json explains
all roles, aliases and unverified parcel matches. The six explicit junction
assumptions, actual OSM edge/node references, lengths and alternative are in
raw/szentes-bounded-inference-proof.json. Two river junctions use chosen nearby
physical pedestrian bridges; the source does not select those detours.

Every output segment lies on a literal archived current OSM source segment.
There are 96 original source vertices and two exact native bridge/river line
intersections, plus the repeated closing vertex. No synthetic connector, snap,
geometry repair, buffer, circle or bounding rectangle is used. Current name
points under raw/ were read only after geometry creation and serve as labels.

Default offline reproduction (from repository root):
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-szentes-belvaros-first/reproduce.py
Add --checks for the separate native-segment/municipality containment check.
The full country PBF and network are not needed for replay. The source-way
archive preserves full original ways, node references, tags, versions and dates.
Raw scripts/inputs and expected outputs are pinned by manifest.json.

review.json distinguishes same-author geometric checks from independent review.
The first exploratory whole-road polygonization selected an unrelated small
closed face; it was rejected. The retained reproducer enumerates finite adjacent
face unions and requires all fifteen source roads plus Kurca on the perimeter.
The rejected trial created no registry/export entry.

Neither primary/official-boundary status, exact historical alignment, current
legal accuracy, absolute positional accuracy nor address assignment is approved.
Geometry attribution: © OpenStreetMap contributors, ODbL-1.0. Municipal street
and river facts guide the circuit; no municipal map paths were copied.
