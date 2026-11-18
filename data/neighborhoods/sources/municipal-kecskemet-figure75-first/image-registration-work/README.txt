Figure74 → Figure75 photographic image relation

This local image relation was made from adjacent original JPEGs only. No world
coordinates, geographic model, quarter names, boundary rings or name points
participate in matching. Original municipal source-map reuse rights and the
orthophoto capture date remain unverified. Publisher PDF SHA256:
83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939

The parent preserved a preliminary two-patch/32-size search in explore-scale.py
and exploratory-scale-search.json. All32 scale attempts remain, including weak
correlations and wrong-location matches. They are exploratory observations,
not additional fit or held-out controls. The parent then proposed a final
fixed27-patch grid with48-pixel source/target templates. The exact plan and
alternating training/held-out partition were recorded before final grid NCC.
The proposed grid succeeded unchanged; no retry or residual tuning occurred.

The final27 searches include6 usable training,7 usable held-out and14 rejected.
All records remain in image-registration.json. No final source patch overlaps
another final patch or either preliminary source patch. Accepted NCCs exceed
the predeclared0.85 threshold and have nonedge peaks.
Maximum held-out residual:0.23222357979104435 target pixel.
Maximum training residual:0.11938945446149579 target pixel.
Minimum accepted NCC:0.8935435688450077.
Only the six training matches fit the affine matrix.

verify-image-registration-direct.py imports no producer code. Direct strided
window dot products and sums independently check all27 FFT-produced searches,
then refit the six training matches and check every residual. This separately
implemented numeric path is by the same agent, not a blind physical review.

The post-preliminary qualitative review shows matching industrial roof rows,
a rounded yard, narrow orange roof and a separate pale/blue roof constellation.
Its original-pixel grid crops are preserved. Preliminary NCC and the final
model were already available when this visual review was made. There are no
invented pre-NCC manual observations or additional independent controls.

The matched hull describes only the observed lower-Figure74/upper-left-Figure75
photo overlap. Reptéri lakótelep lies far to the east of this observed overlap.
A good photographic relation does not validate that extrapolation, inherited
geographic calibration, full photo-frame identity, source-cell extent or
absolute boundary accuracy. Geographic registration:false; absolute accuracy:
null; usableForAddressAssignment:false.

Portable local replay with numpy/scipy/Pillow/shapely available:
python3 /path/to/image-registration-work/fit-image-registration.py --check
python3 /path/to/image-registration-work/verify-image-registration-direct.py --check

Both commands use adjacent pinned files and no network. The original exploratory
script is retained as authored; rerunning it rebuilds its exploratory report.
work-manifest.json pins every file except itself.
