# Who's On First source snapshot

This directory contains an unchanged source snapshot for review, not an approved boundary catalogue.

- Upstream repository: https://github.com/whosonfirst-data/whosonfirst-data-admin-hu
- Upstream commit: `4b64e4ebf99e9fbadc4e828bea25d41a9085b7f1`
- Retrieval date: 2026-11-12
- Scope: primary GeoJSON records under upstream `data/859` and `data/110`; original locality records referenced by their hierarchies are in `parents/`.
- 324 neighbourhood records: 64 Polygon, 3 MultiPolygon, 257 Point.
- 57 retrieved parent localities. One unavailable parent is explicitly recorded in `manifest.json`.
- Each raw GeoJSON file's original Git blob SHA-1 was checked against `manifest.json`. Originals have no terminal newline; preserve their exact bytes.
- No point, label bounding box, viewport or centroid was converted into a boundary.
- All source records remain `unreviewed`. They must not be used for automatic address classification without a separate reviewed acceptance.

## Coverage and quality

These 67 polygon candidates are concentrated around Budapest: 62 reference Budapest, one Csömör, one Budaörs, and three lack a locality in the hierarchy. This snapshot does not establish coverage for Debrecen or other Hungarian cities.

The records contain historical names, aliases, overlapping geometries and potentially surprising hierarchy/concordance values. For example, the Albertfalva record carries translations and a Wikidata reference associated with the whole XI district. Preserve this source evidence and review the actual geometry before accepting a canonical label or municipality.

`mz:is_current=-1` means unknown, not proof of retirement. Source `mz:is_official`, `mz:is_hard_boundary`, cessation, supersession and hierarchy values are preserved unchanged. A valid Polygon is not evidence that its boundary is official or suitable for house-level assignment.

The unavailable parent `101834157` is referenced by the Point record Szarvashegy (`85901291`), whose hierarchy names a different country than its top-level HU country field. No parent municipality was guessed or synthesized.

## Licensing and attribution

See the verbatim upstream [LICENSE.md](LICENSE.md). Who's On First requires a link to its licence. Its original work is CC0, while imported data can require additional attribution. Preserve the original properties, especially `src:geom`, and comply with the applicable source terms.

The polygon candidates here identify Quattroshapes as a geometry source. The upstream licence describes this source as CC BY and requests acknowledgement of foursquare Quattroshapes. Parent geometries and metadata may also identify GeoNames, GeoPlanet, EuroGlobalMap/FÖMI, Wikidata and other sources. The full upstream licence is retained instead of assuming a single blanket CC0 licence for every field.

## Snapshot manifest

`manifest.json` records each source file, upstream path, commit-pinned URL, original Git blob SHA, geometry type/source, locality references, active/supersession flags and draft review status. Its `records` and `parents` arrays distinguish neighbourhood candidates from municipality context records.

This collection was retrieved with read-only GitHub requests. No paid GIS service, hosted API, geocoder, app data migration or deployed application behavior is enabled by these files.
