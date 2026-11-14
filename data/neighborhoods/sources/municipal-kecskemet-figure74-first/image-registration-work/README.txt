Figure73 → Figure74 photographic image registration work

This directory is a local source-image registration result, not a geographic
calibration or a neighborhood-boundary approval. It was created using only the
two original JPEGs. No geographic model, world coordinate, neighborhood name,
name point or source-quarter ring was used in photographic matching.

The original JPEGs are byte-preserved. Figure73 PDF143/xref172 is the source;
Figure74 PDF154/xref176 is the target. Publisher PDF SHA256:
83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939
Source URL:
https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf
The municipal consultation draft is dated May2021. Orthophoto date and open
reuse rights for the municipal source map are unverified.

Producer manual observations of the same tall-roof corners and bus-yard loop/
bay structures were archived before any NCC computation. Their four original
interpretation boxes all contain the subsequent model comparison. These were
made by the producer and are NOT a separate blind physical review. The raw
pixel-axis crops are preserved without geographic overlays.

Two preliminary patches established an approximate image scale. Every tested
scale, including weak results, remains in exploratory-scale-search.json and
can be replayed by explore-scale.py. Neither preliminary patch is an additional
fit or held-out control. Before the final grid computation, the fixed grid,
44-pixel target-template size, 0.85 NCC threshold and alternating training/
held-out partition were recorded in registration-plan-before-fit.json.

The final report retains all48 nonoverlapping grid source patches:13 usable
training,10 usable held-out and25 rejected. No accepted held-out patch overlaps
a preliminary scale-search patch. Only training matches fit the affine.
Maximum held-out residual:0.47120478654527725 target pixel.
Maximum training residual:0.19673796028086363 target pixel.
Minimum accepted NCC:0.8501126040360163.
The two source-quarter maps highlight different photo regions; linework,
labels and tonal differences prevent some grid patches from being usable.

verify-image-registration-direct.py imports no producer code and recomputes
all48 searches with direct strided-window dot products and sums, rather than
the producer's FFT convolution. It refits the training affine and checks every
residual. This is an independently implemented numeric path by the same agent,
not a separate independent human/agent visual review.

The matched texture hulls in direct-verification.json delimit the actually
observed local overlap. Full Figure74 coverage, common global photo-frame
identity, geographic placement and boundary accuracy are not validated.
Absolute accuracy:null. usableForAddressAssignment:false.

Portable local replay, from any working directory with numpy/scipy/Pillow/
shapely available (the repository uses PYTHONPATH=.local/geodata):
python3 /path/to/image-registration-work/explore-scale.py --check
python3 /path/to/image-registration-work/fit-image-registration.py --check
python3 /path/to/image-registration-work/verify-image-registration-direct.py --check

All three scripts read adjacent pinned files and require no network or other
source directory. work-manifest.json pins every file except itself.
