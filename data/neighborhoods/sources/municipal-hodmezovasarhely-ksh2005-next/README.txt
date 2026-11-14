Hódmezővásárhely KSH 2005 — observed contours, estimated world placement

The proposed file contains nine historical neighborhood candidates: Belváros, Tarján, Tabán, Csúcs, Béketelep, Kertváros, Susán, Újváros and Kishomok. All remain ESTIMATED/nonofficial/nonhard/noncanonical and unsuitable for address assignment. No global registry or export was changed. Kishomok has separate named statistical city-part evidence despite its garden character. Whole current quarter extents and absolute accuracy remain unverified.

The original KSH map has 15 named native fill objects and 17 explicitly closed subpaths. Exact decimal PDF operands are preserved in source-native-paths.json, including the touching tiny triangles of Belváros and Kiskertek. The literal Hódtó path self-intersects; it remains raw and quarantined. The existing Hódtó estimate is unchanged and is not counted again. Four detached village depictions — Batida, Szikáncs, Erzsébet and Kútvölgy — are schematic/compressed and retain native coordinates only. Applying the central placement misses current Erzsébet/Kútvölgy points by kilometers. Generic Kiskertek remains a native garden/local-area depiction, not an additional fine quarter.

World placement uses three interpreted road-junction correspondences, grounded in source boundary text and actual current PBF road topology. Source-quarter and current-name points are never fit controls. The main similarity is in EOV/EPSG:23700, followed by vertexwise WGS84 projection; native contours are not repaired, clipped, simplified, buffered, snapped or closed through map frames. A two-control placement alternative is separate and is not another nine quarters.

The 15.03 m control RMS is not an accuracy bound. The held-out ambiguous Jókai/Kutasi junction differs by 55.76–74.73 m, while the independent Susán/Újváros rail135 edge check reaches 84.21 m. Most candidate footprints lie outside the small control triangle. Some whole-border comparisons against literal present street names differ by up to 1,014 m; source descriptions are simplified and current corridor names differ. No street-name equivalence or coordinate correction is inferred. The two-control alternative differs by up to 62.6 m among selected vertices; that difference is not a confidence interval.

Publication is July 2005; statistics principally reference 2001-02-01. The map survey/reference date and CRS are not stated. Current PBF name points corroborate location/identity only. The original full PDF stays in ignored local storage. Only the map crop, native path data and factual/paraphrased source evidence are archived here; no surrounding narrative or full PDF is copied.

KSH's notice requires attribution for secondary publication and reserves separate data-transfer permission to the Szeged directorate. Unrestricted reuse/data-transfer permission has not been established. OSM road/rail and name-point evidence is ODbL-1.0, © OpenStreetMap contributors.

Review source-native-paths.json, independent-source-review.json, road-control-specification.json, road-pbf-verification.json, registration-and-uncertainty.json and independent-world-review.json. The single curated proposal is registry-entry.json. source-manifest.json and artifact-manifest.json pin the packet. All 98 complete control/check ways and 512 node coordinates were revalidated against the actual local PBF.

Offline reproduction from repository root:
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-hodmezovasarhely-ksh2005-next/reproduce.py

The original KSH PDF, country PBF and existing archived Hód control/name inputs are required at their pinned local paths. Reproduction makes no network calls, writes only this new packet, and retains independent review files. verify-packet.py checks the retained data and rebuilds only its verification/manifests. No browser, remote CI, deployment or address-assignment approval is implied.
