"""Offline estimated rings for street groups verified against public sources.

Actual saved OSM roads provide all perimeter coordinates. The existing name
point only selects the cell; it never supplies dimensions or boundary vertices.
The chosen enclosing roads are our explicitly estimated map interpretation,
not an assertion that each source publishes an exact legal boundary.
"""
from pathlib import Path
import json,gzip
from shapely.geometry import shape,Point
from shapely.ops import polygonize,unary_union,transform
from pyproj import Transformer
HERE=Path(__file__).parent
P=HERE.parent
roads=json.load(gzip.open(P/'southeast-source-roads.geojson.gz','rt'))['features']
to_m=Transformer.from_crs(4326,23700,always_xy=True).transform
specs=[
dict(name='Szent László-telep',names=['Öntöző utca','Tápióbicske utca','Pesti út','Lemberg utca'],point=(19.2811744,47.4760104),sourceUrl='https://utcak-magyarorszag.openalfa.com/utcak/agyagos-utca-szent-laszlo-telep-xvii-keruelet-budapest',supportingUrls=['https://utcak-magyarorszag.openalfa.com/utcak/pestvideki-utca-szent-laszlo-telep-xvii-keruelet-budapest','https://utcak-magyarorszag.openalfa.com/utcak/kisvarda-utca-szent-laszlo-telep-xvii-keruelet-budapest','https://utcak-magyarorszag.openalfa.com/utcak/fuezesabony-utca-szent-laszlo-telep-xvii-keruelet-budapest','https://utcak-magyarorszag.openalfa.com/utcak/szabadsag-sugarut-szent-laszlo-telep-xvii-keruelet-budapest','https://telepekbudapest.blogspot.com/p/xvii.html'],note='Estimated public-map street-group extent containing documented Agyagos, Pestvidéki, Kisvárda, Füzesabony, Nápoly, Szabadság sugárút and Derkovits tér streets. The enclosing Tápióbicske, Öntöző, Lemberg and Pesti roads are a coarse interpretation of the saved street fabric, not published official limits. Historical and everyday estate extents may be smaller or overlap adjacent Rákoscsaba subdivisions.'),
dict(name='Virágtelep',names=['Csabagyöngye utca','Lemberg utca','Pesti út','Zrínyi utca'],point=(19.2878228,47.4780932),sourceUrl='https://utcak-magyarorszag.openalfa.com/utcak/koeroemvirag-utca-viragtelep-xvii-keruelet-budapest',supportingUrls=['https://utcak-magyarorszag.openalfa.com/utcak/mehecske-utca-viragtelep-xvii-keruelet-budapest','https://utcak-magyarorszag.openalfa.com/utcak/kalmarvoelgy-utca-viragtelep-xvii-keruelet-budapest','https://hungary-streets.openalfa.com/streets/tanar-utca-viragtelep-17th-district-budapest','https://www.hirbalaton.hu/szerednyey-bela-az-en-kertem-a-balaton-magyarmezogazdasag-hu/','https://hetfa.hu/wp-content/uploads/2023/02/BP17_ITS_Megalapozo-vizsgalat-1.-kotet_ELFOGADOTT_20220825.pdf'],note='Broad estimated public-map street-group extent east of Lemberg and west of Zrínyi, south of Csabagyöngye and north of Pesti. Public street maps associate Körömvirág, Méhecske, Százdi, Kalmárvölgy and Tanár with Virágtelep; independent reporting identifies the Fátyolvirág/Tubarózsa/Körömvirág cluster. The 2022 planning assessment places the distinctive paired-house estate within this larger four-road sector. Its exact 1980s development footprint is smaller and was not recovered; this approximate search area includes neighboring street blocks.'),
dict(name='Királyhágó lakópark',names=['Kappel Emília utca','Kétújfalu utca','Királyhágó út','Halomi út'],point=(19.2099577,47.4215982),sourceUrl='https://www.tomorylajos-muzeum.hu/a-xviii-keruleti-laktanyak-sorsa-1990-utan1/',supportingUrls=['https://reticolo.hu/hu/referenciak/ingatlanfejlesztes/76-kiralyhago-4-lakopark','https://www.18kerterkepen.hu/telepek-es-utcak/telepek/','https://forum.index.hu/Article/showArticle?t=9109482'],note='Estimated road-bounded envelope of the 2000s Királyhágó street-front estate, using Kétújfalu, Kappel Emília, Halomi and Királyhágó. The district museum distinguishes this former sports-field frontage from the later development toward Tarkő/Kétújfalu centered on Herrich Károly tér, which is outside this ring. Developer reference confirms Királyhágó4 at81. Internal named phases and adjacent branded estates retain distinct identities; no alias or precise parcel boundary is asserted.')
]
out=[]
for s in specs:
 fs=[f for f in roads if f['properties'].get('name') in s['names']]
 polys=polygonize(unary_union([shape(f['geometry']) for f in fs]))
 selected=[g for g in polys if g.covers(Point(s['point']))]
 assert len(selected)==1,(s['name'],len(selected))
 g=selected[0].simplify(.000025,preserve_topology=True)
 assert g.is_valid and not g.is_empty
 out.append(dict(name=s['name'],municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=[[round(x,8),round(y,8)] for x,y in g.exterior.coords],anchors=s['names'],sourceUrl=s['sourceUrl'],supportingUrls=s['supportingUrls']+[f['properties']['source']['url'] for f in fs],approximationNote=s['note'],derivation='Interpret enclosing source roads around independently documented street group; polygonize actual saved OSM lines, select the source-bounded cell using name point, simplify0.000025degree. No point buffer or synthetic rectangle.',areaSquareMetres=round(transform(to_m,g).area)))
result=dict(schemaVersion=1,date='2026-11-15',features=out,unresolved=[dict(name='Szárazhegy',reason='Available authoritative planning sources describe the proposed Szárazhegy expansion or the Panoráma first phase; neither establishes the whole historical Szárazhegy neighborhood. First-phase street bounds Szigetcsép/Barnabás/Szárazhegy/Pesti describe a narrow northeastern strip; the saved label point lies southwest of Szigetcsép. No point was forced into that child footprint.',sourceUrls=['https://www.hatvanizoltan.hu/index.php?id=Szarazhegy_LakoteruletBeepitesiTerv','https://einfoszab.budapest.hu/Session/SSDC_Item/91858?key=fovarosi-kozgyules-bizottsagainak-nyilvanos-ulesei&organizationtype=2&parentId=6795&parenttype=2&sessionType=4&type=3'])])
(HERE/'proposed-traces-2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for f in out:print(f['name'],f['areaSquareMetres'],len(f['ring']))
