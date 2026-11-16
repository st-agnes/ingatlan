# Frozen batch 03 — twelve whole-area interpretations

12 features in 6 municipalities, all estimated/low confidence. Municipal street, planning, townscape and project documents supply geographic context where available; archived native roads and compounds supply the actual edges. This batch contains all five Gyömrő backlog names, Acsaújlak's whole castle/farm hamlet, Mende-Pusztaszentistván, two Bag and two Aszód areas, and Göd OVIT.

Kastélydomb has an explicit municipal four-street description; Aszód industrial streets and Falujárók estate are supported by municipal planning documents. Closed/industrial sites include their associated access yards, not only building footprints.

Important limitation: Göd OVIT is the northern named industrial employment block, with saved label candidate 0 covered. Candidate 1 lies across M2 on open land and has no matching physical site; it is deliberately not bridged to the first site. The emitted shape does not certify a residential OVIT estate or the identity of that second point. Municipal OVIT establishment address supports the northern site. Treat the extent as low confidence.

Run the same `build.py batch-03` and `verify.py batch-03` commands as the prior packet. All geometries are valid and reproduce byte identically offline; source-input hashes and map vertices are embedded in summary/provenance. Circle count is zero within this packet. Exact geographic precision is not asserted.
