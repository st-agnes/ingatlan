"""Independent source-line coverage and provenance check of the Erzsébetváros candidate."""
import hashlib,json
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import unary_union,transform
from pyproj import Transformer
b=Path(__file__).resolve().parents[1]
root=Path(__file__).resolve().parents[5]
g=json.load(open(b/'kecskemet-manual.geojson'));f=g['features'][0];s=shape(f['geometry']);proof=json.load(open(b/'kecskemet-trace-proof.json'));lines=json.load(open(b/'kecskemet-boundary-lines.geojson'))['features'];used=[x for x in lines if x['properties']['source']['osmId'] in proof['usedWayIds']];tr=Transformer.from_crs(4326,23700,always_xy=True).transform
by={}
for x in used:
 name=x['properties']['name'];by.setdefault(name,[]).append(shape(x['geometry']))
lengths={n:transform(tr,s.boundary.intersection(unary_union(v))).length for n,v in by.items()}
actual=hashlib.sha256((root/'.local/neighborhoods/nationwide-docs/originals/kecskemet-map.pdf').read_bytes()).hexdigest();assert actual==proof['sourcePdfSha256']
for field,file in [('sourceFactsSha256','kecskemet-circuit-source.json'),('sourceLineworkSha256','kecskemet-boundary-lines.geojson'),('archivedSourcePagesSha256','kecskemet-source-pages.pdf')]:assert hashlib.sha256((b/file).read_bytes()).hexdigest()==proof[field]
assert s.is_valid and s.exterior.is_ring
assert len(used)==18 and len(by)==5
assert all(l>0 for l in lengths.values())
assert s.boundary.difference(unary_union([shape(x['geometry']) for x in used])).length==0
assert all(not any(x['properties']['source']['tags'].get(k) not in [None,'no','0'] for k in ['bridge','tunnel','layer']) for x in used)
coords=f['geometry']['coordinates'][0];vertices=set(tuple(v) for x in used for v in x['geometry']['coordinates']);assert all(tuple(v) in vertices for v in coords)
out={'schemaVersion':1,'reviewedAt':'2026-11-13','artifact':'../kecskemet-manual.geojson','name':'Erzsébetváros','municipality':'Kecskemét','sourceWordingIndependentlyRead':True,'textPdfPageZeroBased':151,'mapPdfPageZeroBased':142,'mapVisuallyInspected':True,'sourcePeriod':'May2021 consultation version; publication file126/2021(XII16)','sourceTypeVariantsExplicit':{'Csongrádi utca':'Csongrádi út','Bajcsy Zsilinszky Endre utca':'Bajcsy-Zsilinszky Endre körút'},'valid':True,'ringVertices':len(coords),'exactSourceVertices':True,'allBoundarySegmentsCoveredByUsedSourceWays':True,'usedWays':len(used),'sourceStreetCount':len(by),'usedWayGradeSeparationCount':0,'boundaryLengthByStreetM_EPSG23700':lengths,'allThreeProofInputHashesVerified':True,'originalPdfHashVerified':True,'decision':'Accept as source-circuit-derived fine-quarter candidate, retaining independent_boundary_review and address-assignment-false flags. Not cadastral precision or current legal verification.','limitations':['Five-road centerline circuit is consistent with municipal text and depicted southeastern Belváros subquarter. This review does not independently survey street-side parcel assignment.','Projected area using EPSG23700 is282346.60m²; original proof area282378.71m² uses its own projection. Difference is below0.02percent.','No alternate street-name attribution survey or boundary-change register was available offline.']}
(b/'scout/kecskemet-independent-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Independent review passed')
