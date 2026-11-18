Kaposvár supplemental municipal sources — bounded evidence packet
===============================================================

No new fine quarter polygon is emitted. The 2009 action-area plan and the
July 2023 version 2.0 FVS retain maps of the same ten functional planning
units already preserved in municipal-kaposvar-raster-next: four single-name
units and six compound groups. Exact coordinate equality is not asserted.
The compound map units have no finer internal contour. None is copied onto
constituent names, and the four existing units are not duplicated here.

The FVS title covers 2021–2027; its cover date is July 2023, while its PDF
creation metadata is February 2024. Page 181 explicitly retains the prior
ten-quarter division. That supports the planning scheme in the newer
publication. It does not independently validate every canonical fine name,
exact historical boundary position, or current 2026 address assignment.

The two unmodified selected native JPEG map images are retained. The 2009
map is PDF page 26, xref 157, 944×1301. The FVS map is PDF page 182, xref 991,
1342×1007. Neither map page has native PDF vector paths. Their coordinates
are source-image pixels, not geographic coordinates. No geographic fit,
claimed control accuracy, extrapolation bound or polygon is produced.

The 2009 plan explicitly distinguishes the whole Belváros quarter from the
13.85 ha Városközpont rehabilitation action area within it (pages 27 and
44). Later closed intervention maps therefore cannot become a whole-quarter
polygon. The four prose subparts of Belváros have no individual mapped
contours. FVS page 186 separately names Donner and Rómahegy and describes
physical edges, a useful future lead; it does not draw their internal split.
Rómahegy also relies on an unestablished historical belterületi boundary.

assessment.json records these semantic decisions and their limits.
independent-review.json supplies an independent source/map audit.
source-inventory.json pins the complete local PDFs, selected image bytes,
page numbers, xrefs, dimensions, URLs and document dates. Original PDFs
remain ignored under .local; only selected maps and short evidence belong
to this packet. Public publication does not itself establish an open map
reuse licence.

Reproduce from the pinned local originals, with PyMuPDF installed:
  python data/neighborhoods/sources/municipal-kaposvar-supplement-next/reproduce.py
  python data/neighborhoods/sources/municipal-kaposvar-supplement-next/reproduce.py --check

The check is read-only and makes no network requests. It verifies original
SHA256 and size, key source text on cited pages, map-image xref and bytes,
and the absence of native paths on the assessed map pages. It checks the
source inventory and images; it does not algorithmically prove the human
semantic review. The manifest pins every file in this bounded packet.

Existing frozen source packets, shared registries and exports are unchanged.
