Donner — bounded inferred physical-boundary candidate
===================================================

One low-confidence candidate is preserved, with no primary-layer or address
assignment claim. Its four-edge circuit is Kapos river, Zselic-patak,
Szigetvári utca and road 67. Area is about 2.729 km². The candidate has 166
ring coordinates and uses 30 original OSM ways. No combined Donner–Rómahegy
map geometry is copied, split or assigned to either constituent name.

The July 2023 version 2.0 municipal FVS names Donner separately from the
Rómahegy place adjoining it to the east (PDF page 186). The printed Donner
sentence visibly contains the malformed phrase “a 67-es út és Kapos a
Zselic-csatorna között”. The four-edge interpretation is therefore explicitly
an inference; the source is not silently corrected. On page 185 the same
document equates road 67 with Zselici út. The candidate follows the current
OSM road 67/Zselici route and current Szigetvári utca. No independent survey
of route changes between the source date and the PBF date has been made.
The source's Szigetvári út spelling and OSM's Szigetvári utca are treated as
a disclosed name correspondence. The current Pécsi utca is retained as
context but is not silently substituted for any source boundary.

Actual OSM geometry closes all four sides. Kapos/Zselic share node 290209038;
Szigetvári/67 share node 27421028. The two other corners are analytical
intersections of actual road/water source segments at their crossings. No
snapping, projected extension or manual closing segment is used. The Zselic
arc stops at its Szigetvári crossing; the additional downstream Zselic/67
crossing is not a corner of this ordered circuit. Source-node topology,
rather than arbitrary geometric crossings, connects each physical arc.

The original PBF is SHA256
224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a,
with replication timestamp 2026-11-12T21:23:05Z. The literal source archive
retains complete selected roads/waterways, original IDs, tags, node references,
coordinates, way versions and timestamps. Its acquisition window never
becomes a boundary. construction-proof.json records each used source segment
and its endpoint fractions. Original OSM node coordinates remain verbatim;
only the two analytical corner coordinates are new mathematical points.

No raster georeference or control fit is asserted. Literal modern routes
have real geographic coordinates, while their equivalence to intended 2023
quarter edges is uncertain. Source-age, route-choice, line-position and
absolute boundary accuracy remain unquantified. claimedAbsoluteAccuracyMetres
is null, and no search radius is assigned. The two short PDF page crops prove
the source wording and road-name correspondence. Complete PDFs remain local.

Independent review confirms the distinct Donner identity, the explicitly
interpreted four-edge reading, and a valid simple circuit. The independent
node graph uses exactly the same paths and source-way sets. Intersecting
straight segments in EOV rather than WGS84 produces a 0.00045 m numerical
boundary difference. This only measures two calculation models; it is not a
measured geographic accuracy or confidence interval.

Reproduce/check the candidate, proof and SVG preview:
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-kaposvar-donner-next/reproduce.py --check

Check the original municipal PDF and selected proof crops:
  python data/neighborhoods/sources/municipal-kaposvar-donner-next/extract_source_evidence.py --check

Independent read-only geometry audit:
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-kaposvar-donner-next/independent_audit.py --candidate data/neighborhoods/sources/municipal-kaposvar-donner-next/donner-candidate.geojson

Optional full local PBF re-extraction, read-only when --check is given:
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-kaposvar-donner-next/extract_osm.py --check

All commands are offline. Dependencies are PyMuPDF, Shapely, pyproj and
pyosmium, with the latter needed only for PBF re-extraction. The manifest
pins the candidate and all evidence. Municipal-map open reuse rights are
not independently established; ODbL-1.0 applies to OSM geometry. Current
canonical fine-name validation, legal/cadastral status and source-to-address
validation remain unresolved. Rómahegy is not forced closed using an assumed
historical built-up limit. Other frozen batches and global registries are
unchanged.
