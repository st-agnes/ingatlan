Kiskunfélegyháza — five estimated historical-neighborhood candidates

This source-local packet contains Kossuthváros, Petőfi lakótelep, Bankfalu,
Arany-hegyi lakótelep and Zöldmező lakótelep. It creates no primary admissions,
current legal-boundary claims or address-assignment approval. The local registry
descriptor remains unapplied by this producer. All original coordinates, source
masks, explicit source-cap evidence and placement alternatives are retained.

Official source:
Kiskunfélegyháza Város Integrált Településfejlesztési Stratégiája,
Felülvizsgálat 2016; Table 4 (physical PDF page 24), Map 2 (page 25).
https://kiskunfelegyhaza.hu/wp-content/uploads/2017/03/its_kiskunfelegyhaza_2016_felulvizsgalt.pdf
Original PDF SHA256:
5a32552dc02e2bca986d27d97e41633549b5d1f23147f8e00b6abbe7c421b48b
The full 139-page PDF stays in ignored .local storage. This packet retains only
the original 945×1364 map JPEG, short factual names and paraphrased provenance.
Map attribution: Önkormányzati adatszolgáltatás. Unrestricted municipal map
redistribution rights have not been independently established.

Source periods differ. The 2016 review follows KSH units based on municipal
2014 submissions, because those differ from the older 2008 IVS schema. The
quarter statistics use census 2011 data. None establishes a boundary survey date
or complete current extent. Unit 6 is the combined Déli Kertváros–Móraváros–
Bikahegy source unit and supplies no child boundaries. Unit 12 is intentionally
unmapped scattered farm territory. Unit 15 is a label without spatial extent.
None is converted into a new polygon by this packet.

Four contours are observed closed source RGB outline components. Their pixel
interiors are exact unions of native pixel cells. Petőfi is different: the black
number 3 interrupts its green border. Its main contour contains an explicit
two-cell barrier cap at [401,618] and [402,618]. The raw open mask, observed
endpoints and a separate five-cell alternative one row higher are retained.
Petőfi alone has estimatedContour=true and completeSourceContourObserved=false.
The registry descriptor deliberately has no blanket contour-observation override.
Arany-hegyi's nine disconnected internal pink marks remain in the raw mask;
they are not part of the enclosing outline component or asserted quarter holes.
No buffer, hull, morphology, snapping, smoothing, repair or frame closure is used.

One full-map affine model uses five actual current OSM road/rail junctions.
Remote junctions beside units 13 and 14 supplement three central junctions.
A full-map similarity model with the same controls is retained separately.
No suburb-name point enters either fit, and no feature receives an individual
shift or correction. Current points corroborate names and location only.
Petőfi-lakótelep and Aranyhegyi lakótelep are recorded as explicit source/current
spacing or hyphen spelling variants; source names are preserved without an
automatic canonical alias. All five current points lie inside the main estimates.

Manual source picks, thick colored border bands, old/unknown backdrop geometry,
model assumptions, pixel quantization and possible current extent changes leave
absolute positional accuracy unknown. Fit RMS and held-out road residuals are
correspondence diagnostics, not accuracy guarantees. Main/alternative differences
are not confidence bounds. The outlying scout file repeats the same two main
geometries for inspection and is never counted as two additional quarters.

OSM reference:
Pinned Hungary extract SHA256
224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a
Snapshot 2026-11-12T21:23:05Z; © OpenStreetMap contributors; ODbL-1.0.
https://www.openstreetmap.org/copyright
Eighty complete, unchanged control/holdout/context ways and five literal name
points are retained. The broad inspection cache and full PBF stay in .local.

Reproduction from repository root (no network):
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-kiskunfelegyhaza-its2016-next/validate.py
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-kiskunfelegyhaza-its2016-next/reproduce.py
The second command regenerates core outputs in an isolated temporary tree and
compares hashes, leaving this packet and global exports intact.
extract-reference.py can independently rescan the pinned PBF when required;
extract-source.py and register.py are producer scripts and rewrite local outputs.
