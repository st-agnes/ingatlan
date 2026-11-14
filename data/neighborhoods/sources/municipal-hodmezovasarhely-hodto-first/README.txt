Hódmezővásárhely / Hódtó — first estimated circuit candidate

One historical neighborhood candidate, not a downloaded municipal polygon or
current authoritative boundary. Source: municipal ITS adopted 17 September 2014,
resolution 217/2014. (09.17), section 2.3.4, printed page 61. The document equates
the named Hódtó quarter with a circuit of Kaszap, Andrássy, Bajcsy-Zsilinszky,
and railway135. A separate 8-word literal quote and precise locator are retained.
The 2023 naming decree confirms Hódtó as an urban quarter name, without proving
its geometry. Original municipal PDF bytes and the selected-section screenshot
were unavailable after subsequent HTTP 403; that source-access limit remains.

The candidate uses literal OSM linework from the pinned Hungary PBF snapshot
(replication timestamp 2026-11-12T21:23:05Z). Its 125 edges all lie on consecutive
original OSM node segments. Twelve actual roundabout ways supply 115.941842 m
of explicitly inferred physical junction arcs. No synthetic connector, endpoint
snap, buffer, bounding rectangle, or point-generated perimeter closes the ring.
The Hódtó name point is a semantic cross-check only. An independent review found
one face using all four cited groups before consulting that point. The valid,
hole-free polygon has 126 vertices and area 634216.374674 m², wholly inside the
archived municipality. Geometry attribution: © OpenStreetMap contributors,
ODbL-1.0, https://www.openstreetmap.org/copyright . Source PDF map geometry was
not copied and no source PDF map reuse license is assumed.

Technical validation does not verify the original municipal source geometry or
the 2014-to-2026 alignment. Retain estimated=true, confidence=low,
usableForAddressAssignment=false, accuracyMeters=null. Keep this candidate in
the separate inferred research layer. No primary source-supported count changes.

package-registry-entry.json is the integration proposal with paths into this
standalone folder. hod-hodto-inferred-registry-entry.json is the byte-identical
original staging proposal, preserved for frozen-handoff/audit replay. The
original staging hashes are retained in hod-hodto-frozen-handoff.json and in
manifest.json. No global registry, review file, or export is modified here.

From the repository root, validate the archived local package without the PBF:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-hodmezovasarhely-hodto-first/validate-package.py

This checks every package hash, all 13 original frozen input hashes, the archived
municipality, source/candidate status, project geometry rules, and byte-identical
converter replay in a temporary folder. It does not write to this package.

The original independent audit script and result remain byte-identical. To
repeat its fresh original-PBF readback, provide the pinned 315 MB PBF and original
country municipality reference at their recorded .local paths, then run:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-hodmezovasarhely-hodto-first/hod-independent-review.py --check

PBF SHA256:
224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a
