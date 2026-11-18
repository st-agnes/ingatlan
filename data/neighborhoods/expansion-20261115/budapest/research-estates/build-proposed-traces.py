"""Rebuild proposed estimated rings from frozen road geometry, offline.

Kisszentmihály and Szent György-telep use intersections of the exact cited
road/waterway lines and district boundary. Óhegyi and EcoLiget use explicitly
recorded manual circulation/boundary-road anchors.
"""
from pathlib import Path
import json,gzip
from shapely.geometry import shape,Point,Polygon
from shapely.ops import polygonize,unary_union,transform
from pyproj import Transformer
HERE=Path(__file__).parent
P=HERE.parent
roads=[]
for fn in P.glob('*-source-roads.geojson.gz'):
 roads.extend(json.load(gzip.open(fn,'rt'))['features'])
parents=json.load(open(P/'parent-features.geojson'))['features']
district=next(shape(f['geometry']) for f in parents if f['properties']['name']=='XVI. kerület')
to_m=Transformer.from_crs(4326,23700,always_xy=True).transform
out=[]
paper='https://www.bp16.hu/sites/default/files/hir/2013/dokumentum/2013_09_11_17_pdf_10615.pdf'
for name,names,pt,note in [
 ('Kisszentmihály',['Szlovák út','Timur utca'],(19.1799243,47.5396445),'Historical boundary convention from the 2013 district history article: Rákospalotai határút / district boundary / Timur utca / Szlovák út. The article also discusses a later proposed Timur-to-Csömöri boundary change. Adopted extent is the historical alternative, not an alias for all Árpádföld. The saved district boundary supplies the northern cadastral edge; its short NW portion follows Rákospalotai határút.'),
 ('Szent György-telep',['János utca','Csömöri út','Szilas-patak'],(19.1692289,47.5346909),'Historical four-side extent from district history: Rákospalotai határút / Szilas-patak / Csömöri út / János utca. Exact frozen road and stream intersections form the ring; the district boundary follows Rákospalotai határút on its NW side. Street-centerline and watercourse convention is an estimated search area, not a parcel boundary.')]:
 fs=[f for f in roads if f['properties'].get('name') in names]
 polys=polygonize(unary_union([shape(f['geometry']) for f in fs]+[district.boundary]))
 chosen=[g for g in polys if g.covers(Point(pt))]
 assert len(chosen)==1
 ring=list(chosen[0].simplify(.000025,preserve_topology=True).exterior.coords)
 out.append(dict(name=name,municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=ring,anchors=names+['XVI. kerület / Rákospalotai határút'],sourceUrl=paper,supportingUrls=['https://www.openstreetmap.org/relation/1552464']+[f['properties']['source']['url'] for f in fs],approximationNote=note,derivation='Polygonize union of saved named road/stream lines and frozen native XVI district boundary, select existing name point only to identify the source-bounded cell, simplify 0.000025 degree. The point does not create the boundary.'))

ring=[
 [19.146576,47.4748639],
 [19.1478573,47.4756969],
 [19.149395,47.476695],
 [19.150195,47.4772117],
 [19.1517901,47.4782381],
 [19.152604,47.4777294],
 [19.1534716,47.4771708],
 [19.1518753,47.4749395],
 [19.1516221,47.4750809],
 [19.1516435,47.4746893],
 [19.1515604,47.4743984],
 [19.1515055,47.4742915],
 [19.1513383,47.4741091],
 [19.1508102,47.4736879],
 [19.1504952,47.4735521],
 [19.1496702,47.4733648],
 [19.1494541,47.4732248],
 [19.1492936,47.4730845],
 [19.1485151,47.4735888],
 [19.1479234,47.4739749],
 [19.146576,47.4748639]]
ohegy_names=['Petrőczy utca','Kada utca','Száraz utca','Harmat utca','Csombor utca','Sorház utca','Noszlopy utca']
out.append(dict(name='Óhegyi lakótelep',municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=ring,anchors=ohegy_names,sourceUrl='https://net.jogtar.hu/rendelet?council=x-kerulet&dbnum=553&docid=A1300012.10R',supportingUrls=['https://www.openstreetmap.org/way/'+str(i) for i in [26354113,47658772,47658830,58721887,101166308,101166315,101166317,127060035,127170545,254871858,275221903,464717800,863990485]],approximationNote='Estimated estate envelope anchored to official street membership in X district regulation 12/2013 Annex2 G. Follows Petrőczy and Kada to Harmat, then the ends of Csombor and Sorház; the eastern link from Sorház to the eastern Noszlopy loop is a manual approximate estate edge. Noszlopy and Petrőczy form the south edge. This includes all named official estate streets; it is broader than the smaller four-road core and intentionally estimated. No parcel precision is claimed.',derivation='Manual WGS84 road-intersection/end-point ring, including approximate eastern connector; all anchors checked against frozen southeast road geometry.'))

ring=[
 [18.981872,47.4627148],
 [18.9826266,47.4627092],
 [18.9826239,47.4626135],
 [18.9825919,47.462379],
 [18.9825426,47.4621778],
 [18.982478,47.461901],
 [18.9824396,47.4617146],
 [18.9824865,47.4617094],
 [18.982474,47.4616765],
 [18.9823193,47.4616493],
 [18.9822618,47.4617886],
 [18.9822137,47.4619058],
 [18.9820988,47.4621852],
 [18.982005,47.4624086],
 [18.9819649,47.4625011],
 [18.981872,47.4627148]]
out.append(dict(name='EcoLiget lakópark',municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=ring,anchors=['Alsóhatár utca 5 estate private driveways, OSM ways743704119/743704120','Eastern private estate footway, OSM way648297931','Alsóhatár frontage sidewalk, OSM way743704125'],sourceUrl='https://budaors.hu/dokumentumok/onkormanyzat/jegyzokonyvek/kepviselo-testulet/kt_jegyzokonyv_2017-04-26.pdf',supportingUrls=['https://kozigazgatas.ujbuda.hu/sites/default/files/attachments/files/kozigazgatasujbudahu/2022_10/01megalapozo_1.pdf']+['https://www.openstreetmap.org/way/'+str(i) for i in [648297931,743704119,743704120,743704125]],approximationNote='Estimated actual estate circulation envelope at officially identified Alsóhatár utca5 / project parcel1151/5. Northern edge follows private entrance driveway; eastern and southern edges follow private estate paths; western edge follows the Alsóhatár frontage sidewalk. A short eastern gap between driveway end and private path is joined manually. This is a small circulation-derived approximation within the estate, not a claim to reproduce parcel1151/5. No outline was inferred from the name point.',derivation='Manual ring from frozen actual private driveway/path vertices, including short connector.'))

for f in out:
 g=Polygon(f['ring']);assert g.is_valid and not g.is_empty
 f['areaSquareMetres']=round(transform(to_m,g).area)
 f['ring']=[[round(x,8),round(y,8)] for x,y in f['ring']]
(HERE/'proposed-traces.json').write_text(json.dumps(dict(schemaVersion=1,date='2026-11-15',features=out),ensure_ascii=False,indent=2)+'\n')
for f in out:print(f['name'],f['areaSquareMetres'],len(f['ring']))
