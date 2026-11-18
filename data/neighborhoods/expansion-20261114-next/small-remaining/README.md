# Small remaining Gyula / Salgótarján / Hódmezővásárhely / Debrecen packet

Final packet: **10 locally unique municipality/name features**, all valid polygons or multipolygons; no circles, buffers, hulls or Voronoi cells. Gyula 4, Hódmezővásárhely 3, Salgótarján 2 and Debrecen 1. Root integration applies global identity/alias deduplication.

- Literal named polygon: Gyula Mályvádi Őstölgyes nature reserve.
- Native surface footprints with explicitly inferred place association: Dénesmajor, Városerdő, Mályvádi erdészkolónia, Csókáspuszta, Ponyipuszta, Batida and Szikáncs.
- Coarse street/built-up context partitions: Debrecen Fészek lakópark and Hódmezővásárhely Kincsestelep.

`summary.json` records counts, source hashes and output SHA. `validation.json` checks valid/nonempty geometry, unique municipality/name pairs, absence of circles and parent-municipality placement. `unresolved.json` leaves Ella-major, Sitka and Tegehalom without new invented geometry: their available broad field/forest surfaces do not identify the named local extent. This is a limitation of this local packet, not a claim that no other source exists.

`target-name-points.geojson` freezes the initial 11 point-only targets. `extract-context.py` extracts actual OSM street, landuse/natural/leisure, place-name and nearby building geometry from the already cached Hungary PBF. This is a local operation; no new online service or geocoder is used. Full OSM object IDs, versions, tags, source URLs, PBF hash and attribution are retained. Raw source files are separate from inferred outlines. WGS84 coordinates are longitude,latitude.

The preserved context contains 18,413 road/rail/water ways, 4,859 landuse/natural/leisure polygons, 578 nearby building footprints and 260 place-name points. The gzip files retain original source geometry and can rebuild selected footprints without the original 329 MB PBF.

`build-rural.py` uses the explicitly enumerated surfaces in `rural-selection.json`. These are literal native surfaces or their union, with no gap filling. Several placepoints sit on streets a few metres outside the residential parcels; no buffer is added merely to contain those points. A residential/farmyard surface is a useful built-up search footprint, not evidence of a complete historical quarter border. The colony footprint is a small park/clearing containing its mapped forest house. Broader forests, fields and separate nearby named places are excluded.

`build-feszek.py` saves a compact 61,754 m² Debrecen Fészek lakópark footprint based on its namepoint and four real surrounding residential streets: Nádsíp utca, Derekassy István utca, Sütő András utca and Balogh Tamás utca. Two short dead-end gaps are joined approximately. The result is explicitly an inferred estate extent, not a source-defined estate boundary, and is below the 0.25 km² housing-park scale cap. `feszek-source-roads.geojson` preserves all four literal ways.

`build-kincsestelep.py` reduces the actual 10.1 km² Hódmezővásárhely core residential surface to a plausible compact northern urban part using the actual outer built-up edge and the Puskin-side/old Kenyere-channel street context. Some internal separators are rough hand estimates. The 0.735 km² result is not claimed to be an official or historically exact Kincsestelep border. Its mask vertices and source image extent are preserved in `kincsestelep-trace.json`.

`kecskemet-alias-review.json` and the source crops resolve two reference names using the already archived Figure 71:

- Earlier “Űrhegy” is a transcription error: the map clearly prints “Úrihegy”, agreeing with the current exact OSM namepoint.
- The yellow northeastern area labeled “Repülőtér” is the military airport, with Matkó separately far south. Applying the existing rough registration places that printed label inside native military-airfield relation 2763405. It is a source-context alias of Kecskeméti Katonai Repülőtér / MH 59, without asserting that old and current polygon edges coincide.

Normal rebuild, using the already retained source files:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/small-remaining/build-feszek.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/small-remaining/build-rural.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/small-remaining/build-kincsestelep.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/small-remaining/combine.py
```

The original PBF is needed only to repeat `extract-context.py`. `render-context.py` and `render-rural.py` reproduce the diagnostic street/landuse images. These images support coarse tracing; they are not independent map-accuracy validation.
