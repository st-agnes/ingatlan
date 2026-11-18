Nyíregyháza — first two historical source candidates
===================================================

These are LOW-CONFIDENCE, HISTORICAL inferred footprints. Örökösföld
lakótelep is an estimated neighborhood candidate. Érkert is a LOCAL_AREA
research candidate for a historical housing-estate footprint, with its name
inferred across statistical schemas; whole Érkert identity is unverified.
No primary-layer or address-assignment claim is made. Their
current exact names appear in the pinned November 2026 PBF-derived point
archive; the points do not establish their extents or enter the registration.

Source hierarchy and names
-------------------------
The acquired municipal IVS has a March 2008 cover, April 2008 creation
metadata and February 2014 modification metadata. The filename is not the
publication date. Pages 41–42 describe 27 KSH quarters based on the 2001
census, and 11 IVS units formed by merging them. Figure 7 on PDF/printed
page 43 shows the two distinct schemes. The underlying KSH volume is 2003.

ksh27-native.jpeg is the actual 1132×838 JPEG xref139, showing the finer
units. Its colors encode nine functional classes, not unique quarter names.
ivs11-native.jpeg is the actual 1129×842 JPEG xref635, with explicitly named
numbered units. Both original JPEG byte streams are preserved. The complete
PDF remains local, pinned by SHA256 in source-inventory.json.

Only two upper components are considered in this first subset. The actual
lower legend identifies 2 as Érkert and 3 as Örökösföld lakótelep. That lower
11-unit key does not directly label the upper 27-unit components; these are
different statistical schemes and the name assignments are inferences.
Each has a corresponding small upper footprint in the same city sector.
See the actual
source crops and legend in source-name-key-review.png. A separate affine
comparison between source maps uses seven paired outer-city corners; its
overlap diagnostics are about 0.715 and 0.918. These are identity-comparison
diagnostics, not exact source-shape equality or geographic accuracy. The
weaker Érkert correspondence is preserved as local-area evidence only,
and is not included in the fine-neighborhood count. The
lower numbered shapes do not construct or replace the upper fine contours.
Other unkeyed upper components and the remaining merged IVS units are not
admitted. Existing 2022 planning groups remain separate.

Actual native contours
----------------------
Each selected upper component uses four-neighbour connectivity and the
documented Pillow HSV thresholds H>135/H<190, S>65, V>45 (0–255 channels).
Érkert has 583 actual selected cells. Örökösföld has 1508 selected cells;
five fully enclosed source ink/noise-hole cells give 1513 cells. The source
row runs, seeds and threshold sensitivity are retained. Every native contour
edge is a pixel-cell edge at x±0.5/y±0.5. Only collinear vertices are removed,
with exactly zero area difference. There is no morphological closing, hull,
buffer, manual cap, exterior-gap bridge or other-component merger. These are
estimated fill footprints, not claims of tracing black stroke centres.

Registration and its limits
---------------------------
An affine image-to-EOV fit uses 11 manually identified corners on the actual
municipal silhouette and current OSM relation 1447608. Ten further corners
on that same municipal outline are withheld. The source-to-target corner
assignments and original municipality-ring vertex indices are archived.
No old 2022 map transform is reused. No place point determines the fit.

Withheld corner residuals: median 87.77 m, p95 215.83 m, maximum 226.90 m.
These same-outline diagnostics do not validate internal quarter positions,
historical boundary continuity or absolute accuracy. There are no independent
interior physical holdouts. Source generalization, manual corner selection,
historical municipal changes and internal distortions remain uncertain.
claimedAbsoluteAccuracyMetres is null; no accuracy/search radius is assigned.
Both candidates lie inside the fit-control convex hull, which establishes
only absence of geometric extrapolation beyond those control coordinates.
It does not establish accuracy. No municipality clipping is applied.

The northern source municipality tip touches the image edge. The fit uses
only explicit visible corner coordinates; no artificial frame-closing edge
is fitted or emitted. The two internal candidate outlines do not touch the
image frame. registration-review.png overlays the current municipal boundary
in red; blue markers are fit corners, purple markers are withheld corners,
white lines are the two native footprints, and magenta dots are name points.

Current point disagreement is preserved prominently. The Érkert point is
600.83 m outside the inferred historical candidate. The exact Örökösföld
lakótelep point is 86.80 m outside; the broader Örökösföld point is inside.
The fit is not shifted to these points. A point is not extent ground truth,
and these historical footprints are not presented as current whole extents.

Reproduction
------------
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-nyiregyhaza-fine2008-next/reproduce.py --check

The offline check pins the original PDF, both source JPEGs, literal current
municipality and three named-point records, and the manually reviewed control
specification. It reproduces native cells, source-name comparison, affine,
held-out residuals, WGS84 candidates, point diagnostics and both review images.
Dependencies: PyMuPDF, Pillow, NumPy, SciPy, Shapely and pyproj. Reference OSM
data originates in the pinned whole-country PBF; IDs, tags, coordinates,
object versions, timestamps and relation members are retained.

Source-map open reuse rights, current whole-quarter limits, legal/cadastral
status and address validation are not established. ODbL-1.0 applies to OSM
references. Original PDFs remain local; selected map extracts and proof only
are retained here. Existing frozen batches, shared registries and exports
are unchanged.
