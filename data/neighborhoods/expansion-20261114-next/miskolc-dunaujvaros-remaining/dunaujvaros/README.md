# Six remaining Dunaújváros search-area estimates

This small follow-up covers Újtelep, Táborállás, Római városrész, Barátság
városrész, Dunapart and the informal fine-scale Duna sor search name.

Five coarse polygons are informed by the municipal development concept's
named boundary corridors (printed pages 11–14), existing legal-reference facts
and the preserved actual local OSM street, railway and waterway context.
Unlocated cadastral, cliff and fence edges are **manual rough connections**.
Their coordinates are deliberately approximate; these are neither native
source polygons nor exact reconstructions of the statutory boundaries.

Duna sor is a separate small inhabited street-context estimate around its
source name point and street frontage. No independently established official
quarter border is claimed for this informal search name. Overlap with larger
quarters is intentional. Dunapart is an approximate central riverfront belt;
the full southern cadastral parcel sequence was not reconstructed.

`source-context-lines.geojson` retains unchanged actual mapped source lines;
not every retained road is an outer quarter boundary. The context map was
rendered from those existing source lines and OSM quarter-label points.
`source-facts.json` records the municipal source, page numbers, relevant
corridors and precise inference limitations. The source PDF was read using a
public web connector; original PDF bytes are not archived in this packet.

`trace-specifications.json` preserves all chosen vertices, and `build.py`
recreates the polygons and technical summaries offline from the retained
source context, name points and municipality. The coarse rings are clipped
to the original municipality. There are no circles, Voronoi partitions or
whole-city patches. Each resulting polygon contains its named source point.

All six records are explicitly estimated, with quality score 25 for the five
corridor-context traces and 20 for informal Duna sor. These scores indicate
rough collection priority, not measured geographic accuracy. OpenStreetMap
source geometry is ODbL-1.0, © OpenStreetMap contributors; municipal planning
text is cited as factual context.
