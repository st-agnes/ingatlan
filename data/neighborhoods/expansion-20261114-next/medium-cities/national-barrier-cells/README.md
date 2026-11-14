# Dense-source barrier-cell estimates

This is a separate, low-confidence follow-up to the archived national source
surface collection. The 556 dense shared-footprint candidates are input
context, not admitted quarter borders. Their source shapes are split by actual
mapped major roads, railway tracks and river/stream/canal courses.

`extract.py` makes at most one national PBF pass. It retains original barrier
way coordinates and all dense source areas in `source-barriers.geojson` and
`source-contexts.geojson`. Polygonization uses only the original source-area
boundary plus real clipped source linework. There is no snapping, synthetic
straight divider, Voronoi, hull, circle or buffer operation.

Candidate cells must contain exactly one still-missing source place name.
Names already covered by the frozen core, registered source layers and the
435 bounded national-surface candidates may coexist. Cells must be smaller
than 90% of their original dense surface and share a boundary with a mapped
major barrier. Coarse area limits are 0.005–0.25 km² for names containing
lakópark, 0.01–0.75 km² for lakótelep and 0.02–4 km² for other quarter names.

`features.geojson` selects at most 200 names, using the largest qualifying cell
per name and spreading the bounded output over municipalities. Every candidate
is classified `physical_barrier_cell_estimate`, with quality score 15. These
are approximate local search footprints; they do not demonstrate that the
actual neighborhood follows these barriers. Grade-separated crossings and
the source place-point location may affect the inferred cell.

`all-candidate-cells.geojson` retains all qualified alternatives.
`skipped-contexts-and-cells.json` records dense source contexts, candidate
rejections and their reasons. The complete source contexts, lines and labels
allow subdivision to be reproduced without losing skipped geometry.
`baseline-known-keys.json` freezes duplicate suppression so later integration
into the main catalogue cannot make a rerun silently drop its own output.

Run `extract.py --saved-sources` to reconstruct cells using the preserved
linework without another PBF pass. Use the same workspace geodata Python
environment as the other neighborhood collection scripts. OpenStreetMap
sources are ODbL-1.0, © OpenStreetMap contributors.
