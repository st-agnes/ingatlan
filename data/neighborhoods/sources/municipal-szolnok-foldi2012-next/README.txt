Szolnok — native map evidence only
=================================

Zero geographic polygons are admitted. One closed native image-pixel
footprint is preserved for the historical source label Szanda-szőlős.
It is not a longitude/latitude polygon or an address-assignment boundary.

Source: Földi Katalin's doctoral thesis, cover Pécs 2012, Figure 9 on PDF and
printed page 72. The caption credits the KSH Szolnok 2003 functional-division
volume. The thesis PDF metadata is January 2013; that does not change the
2003 underlying-map date or establish current validity. The original KSH
volume remains unacquired. The acquired thesis SHA256, original URL and
native image metadata are pinned in source-inventory.json.

The map is one 441×539 RGB raster, xref153, with zero native PDF paths.
figure9-native-pixels.png is a lossless decoding of its actual native pixels;
it is not claimed to be an original PNG file embedded in the PDF. The image
is stretched nonuniformly to a landscape rectangle on the thesis page.
The map colors encode seven functional classes, not seven unique quarters.
The selected southern green footprint has its own internal printed name;
other green areas are not copied onto that name.

The selected four-connected component uses R<70, G>180, B<70 and an interior
seed at pixel (325,347). Its 5724 actual classified pixels and row runs are
archived. Filling 158 fully enclosed text/ink-hole pixels gives 5882 pixel².
The 207-coordinate exterior follows pixel-cell edges; only collinear vertices
are omitted. No exterior gap, separate component, manual cap, image frame,
buffer or hull is used. This is an estimated color-fill footprint, not a
claim of tracing the centre of the original black outline. Threshold
sensitivity changes the exterior by at most one pixel in the two tested
settings; that is not an accuracy bound.

Pletykafalu is a useful additional visible named footprint, but leader lines
cut its fill into mask components. It is not merged or reconstructed in this
first subset. Estate labels and other functional units remain source labels
until their exact hierarchy and whole-quarter identities are reviewed.

There is no geographic registration. A recognizable Tisza/Zagyva confluence
alone does not determine scale, rotation or nonuniform stretching. No second
reviewed physical control, grid, scale bar, street base or spatial holdout
is established. Place-name points do not validate extents or replace controls.
Source-age, control and extrapolation uncertainty remain unknown. No current
canonical-name, whole-quarter, legal-boundary or open-reuse claim is made.

Offline reproduction/check, using the pinned local PDF:
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-szolnok-foldi2012-next/reproduce.py --check

Dependencies: PyMuPDF, Pillow, NumPy, SciPy and Shapely. Original PDFs remain
in ignored local storage; only the selected map, native footprint, short
source facts and proof belong to this packet. Existing frozen sources and
global registries/exports/docs are unchanged.
