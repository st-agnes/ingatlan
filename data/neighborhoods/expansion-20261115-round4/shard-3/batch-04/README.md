# Frozen batch 04 — fourteen remaining town/rural areas

14 valid, estimated, low-confidence polygons in 7 municipalities. The four Kiskunhalas quarters and Inárcs Bucka use actual complete street groups, with municipal planning or infrastructure evidence. Rural estimates use complete farm/hamlet and named-lane/field/forest units; their broad agricultural edges are deliberately approximate. They are source-informed outlines along actual roads and landscape boundaries, not coordinate circles, boxes, Voronoi cells or isolated building footprints.

Alsószőlők's source view was widened to 8500 metres before tracing to avoid cutting off the long southern farm row. Felsőszőlők and Aranyegyháza remain separately named, potentially overlapping agricultural interpretations. Vitéz sor includes the succession of farms, not only the native orchard. Alsóráda's tiny scrub feature was rejected as partial.

Kunbaracs Sarlósár needs particular caution: its saved point is inside Kunbaracs and the outline follows that small forest-clearing hamlet. Nearby Tatárszentgyörgy also has a documented Sarlósár locality. No source established equivalence, so the two were not merged and Tatárszentgyörgy records are not misrepresented as proof of the Kunbaracs boundary.

`build.py batch-04` and `verify.py batch-04` reproduce exact bytes offline. `summary.json` retains all context-source hashes; each feature retains the full interpretive vertices, registration, contextual source URLs and limits. All labels are covered after municipality clipping. Geographic precision is not certified. No application integration or database write is included.
