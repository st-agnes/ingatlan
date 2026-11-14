Salgótarján: eight real source-color outlines, inferred geographic placement

Status: separate inferred research batch; 0 primary features; 8 estimated features.
The June2022 ITS 2021–2027 retains the 2008/2014 subdivision. Original native
map date and CRS are unknown. Original source names and this history are retained.

Source: https://www.salgotarjan.hu/wp-content/uploads/fejlesztesidokumentumok_20220629_its.pdf
Original SHA256: d0c46f2a4797517874b770da6d64dba88cf81de5170cf09e2857284644a31a25
Archived PDF excerpt: source-pages125-137.pdf. Original embedded JPEGs and hashes
are listed in source-image-inventory.json. The original full PDF is a local input,
not needed by the converter when the archived source and proof are available.

The eight complete, separately labelled detail contours are Somoskő, Rónafalu,
Rónabánya, Zagyvaróna, Beszterce lakótelep, Forgáchtelep, Somlyóbánya, Baglyasalja.
Somlyóbányatelep and Forgách-telep are retained as source-heading variants.
The ten broad overview groups are not duplicated onto their constituent names.
The Salgóbánya/Eresztvény five-name/four-body discrepancy and the
Szabadságtelep/Ferenctelep disagreement remain unresolved; no boundary is invented.
Cropped yellow neighbor fragments and cropped Városközpont remain excluded.

Native contour proof:
- profile-source-pixel-contours.geojson contains original image-pixel coordinates,
  not longitude/latitude. Raw color cells and filled outlines are both preserved
  in profile-main-correspondence-review.json. Tiny enclosed cadastral/ink voids
  of31/13/7/3/9/5/14/1 pixels are interpreted as cartographic ink. No external edge
  is replaced, no originally separate component is bridged, no image frame is used
  as a closing segment. Pixel-cell outlines estimate the source colored footprint;
  they do not claim to follow the literal center of every printed black stroke.
  Exact native RGB rules (signed integer differences): yellow r-b>25 AND g-b>25;
  orange r-b>45 AND g-b>15; red r-g>30 AND r-b>30. Components use8-neighbour
  connectivity. This source predicate is distinct from overview calibration rules.
- profile-main-registration-refined.json supersedes the old registration only.
  More complete target ROIs and separation of green/salmon adjacent units improve
  Forgách/Baglyasalja registration. The old diagnostic is retained unchanged.
  Rónafalu/Rónabánya share one transform of their continuous source-map panel.
- exploratory-frame-registration.json and review-frame-scope-and-pixels.json
  describe the overview→EOV fit using4716 actual source foreground-edge pixels.
  The map context supports historical municipal scope, but legal boundary identity,
  original raster CRS and physical controls are not established. This is an inferred
  approximate placement. Fit residuals are not independent absolute accuracy.
- derive-inferred.py applies the two stored transforms then EPSG23700→4326,
  rounds8 decimals, and preserves every original contour vertex/component.
  conversion-proof.json records input hashes, matrices and output topology.

No arbitrary buffer, hull, chord, snapping, repair, missing edge, street substitution,
clipping to a current municipality, constituent split or name-point boundary exists.
The current OSM name points only corroborate name occurrence; they are neither
geographic controls nor validation of any boundary. The modern municipality is
a fit reference and diagnostic, not a source boundary for the exported quarters.
current-name-review.json rechecks all8 exact point coordinates, complete OSM tags,
object versions and timestamps against the SHA256-pinned local country PBF.

All geographic features have sourceIsOfficial=false, sourceIsHardBoundary=false,
absoluteAccuracyMetres=null, claimedAbsoluteAccuracyMetres=null and
usableForAddressAssignment=false. Municipal publication of the source is preserved
as sourcePublisherIsMunicipal=true. Open-map reuse rights for municipal imagery are
unestablished; OSM reference data requires ODbL attribution. No source geometry is
promoted to the primary layer. inferred-registry-entry.json is a candidate only;
the global registry is not modified by this batch.

Offline rebuild/check from repository root:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-salgotarjan-next/derive-inferred.py
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-salgotarjan-next/derive-inferred.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-salgotarjan-next/audit-independent.py

Refine-registration reproduction (not needed by normal exporter):
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-salgotarjan-next/refine-profile-registration.py

These commands use already installed local dependencies. No network installation,
extra permissions, deployment, external mutation or credential access is involved.
