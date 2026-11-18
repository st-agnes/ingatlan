Kecskemét Figure74 — Hunyadiváros proper, explicit inferred first subset

This package contains one separately pictured Hunyadiváros source cell from
the May 2021 municipal consultation draft, original PDF 154–156 / printed 152–154.
The larger Hunyadiváros–Ceglédi út district is not copied under the fine name.
PDF 155 expressly distinguishes four constituent areas and describes strong
local identity in Hunyadiváros proper. The other mapped cells remain available
for later derivation; functional use alone is not a reason to reject them.
The literal map label “Békéscsaba úti gazdasági övezet” and the prose’s
“Békéscsabai úti” forms remain separate. Vasútpark denotes the larger pictured
station-side cell, not automatically the recreational park footprint.

The selected contour has 2391 vertices including closure. Of these, 2378 are
literal original maxRGB<=45 black JPEG pixels. Thirteen vertices cross three
short intervals overprinted by the blue economic-area label. Their actual
source-black endpoints, manual pixel continuations, original colors and
unselected alternatives are explicit in source-pixel-trace.json and
source-inference-alternatives.json. The endpoint distances are 11.314, 3.606
and 6.403 source pixels. These are low-confidence source-boundary hypotheses,
not observed black strokes or calibrated geographic accuracy bounds.

One of the six unselected alternative paths self-intersects when substituted
into the whole source ring. Its failed diagnostic is retained. The selected
ring is valid, hole-free and away from the image frame; its 2390 edges are
8-neighbor source-pixel steps. No source-frame closure, geographic snap,
buffer, repair or simplification is used. The initial failed strict-black
attempt remains under exploratory-diagnostics. SourceRasterContourVerified
is false; the black portions and explicit exceptions are checked separately.

The pictured divider places the northwestern poultry-factory footprint on the
Ceglédi-labelled side, while the prose assigns the factory to Hunyadiváros.
This unresolved map/prose nuance is retained. The contour is not altered to
resolve it, and that factory is not substituted for the separate southern
economic triangle.

Photographic matching uses only the original Figure73/74 images: 13 fitted,
10 held-out and 25 rejected grid searches. Maximum holdout residual is
0.47120478654527725 target pixels. Four physical roof/loop observations were
recorded before fitting by the image-registration producer; they are not a
separate blind physical review. A different numeric implementation recomputes
all 48 searches. Preliminary scale attempts, weak searches and crops remain
in image-registration-work with their original reports and portable code.

The inverse image relation is composed with the copied Figure73 EOV affine.
Its six original manual image observations and literal OSM road coordinates
are independently refitted, while the frozen Figure73 files remain unchanged.
The inherited calibration remains inferred. Its residuals and sensitivity
diagnostics do not establish geographic accuracy. The earlier failed,
unconfirmed same-image junction comparison is preserved as a diagnostic.

Of the 2391 contour vertices, 2008 lie outside the observed photographic hull
and 1914 outside the original Figure73 image rectangle. Maximum distance
beyond the photographic hull is 517.4211135309429 target pixels. Full geographic
placement is unvalidated. The current original-PBF Hunyadiváros name node lies
inside the candidate, but was never a control and does not validate its extent.
The 23 calibration roads and one current name node received a fresh direct
read of the pinned original PBF; 117 unique node coordinates were compared.

All output is INFERRED: absoluteAccuracyMeters:null and
usableForAddressAssignment:false. Source-era versus current/legal/cadastral
extents, orthophoto capture date and open municipal source-map reuse rights
remain unverified. OSM controls/name evidence is subject to ODbL-1.0.

Offline replay from the repository root, using the final directory:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/trace-source-pixels.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/source-independent-review.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/image-registration-work/explore-scale.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/image-registration-work/fit-image-registration.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/image-registration-work/verify-image-registration-direct.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/derive.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/verify-original-pbf.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure74-first/finalaudit-independent.py --check

Default replay needs adjacent archived inputs and the repository project
validator, with no network or external frozen cohort. The original-PBF checker
rereads the pinned full PBF when available; without it, --check verifies the
archived proof/input hashes and explicitly reports that limited replay mode.
The registry entry is an integration candidate. This separate final copy does
not change the active staging folder, global registries/exports or earlier
frozen cohorts. manifest.json pins every package file except itself.
