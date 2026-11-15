import json
from pathlib import Path
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize
P=Path(__file__).parent
ways=json.load(open(P/'source-ways.geojson'))['features'];points={f['properties']['name']:f for f in json.load(open(P/'source-named-points.geojson'))['features']}
specs=[('Belváros',['Pozsonyi út','Ady Endre utca','Városkapu tér','Királyhidai utca','Szent István király út','Fő utca','Malom-ági Lajta']),('Duna lakópark',['Erzsébet királyné út','Konrád utca','Zsófia királyné utca','Gizella királyné út','Károly Róbert út','Géza fejedelem utca','Wathay Ferenc út','Akadémia tér']),('Gyöngyös-telep',['Halászi út','Várallyai György utca','Sólyom utca','Gyöngyös utca','Platán sor','Gazdász utca']),('Halászi úti lakótelep',['Halászi út','Gyöngyvirág utca','Csokonai Vitéz Mihály utca','Lehel utca','Kálnoki út','Tündérfátyol utca','Szellőrózsa utca']),('Lajta lakókert',['Dohy János utca','Lajtaszer','Gát utca','Háncs utca','Zsilip utca','Tölténygyári út','Lomb utca']),('Manninger János lakótelep',['Szent István király út','Gulyás Lajos utca','Móra Ferenc utca','Sattler János utca','Manninger János lakótelep','Vörösmarty Mihály utca']),('Móra Ferenc-lakótelep',['Gulyás Lajos utca','Szent István király út','Károly út','Móra Ferenc utca','Móra Ferenc lakótelep','Sattler János utca','Vörösmarty Mihály utca']),('Dunapart',['Fazekas Mihály utca','Petőfi Sándor utca','Duna utca','Felsőötház utca','Mosonyi Mihály utca','Kökény utca','Rév utca','Fatelep köz'])]
units=[]
for name,roads in specs:
 fs=[f for f in ways if f['properties']['name'] in roads];polys=list(polygonize(unary_union([shape(f['geometry']) for f in fs])));point=shape(points[name]['geometry']);containing=[g for g in polys if g.covers(point)];print(name,len(fs),len(polys),'containing',len(containing))
 if not containing:continue
 poly=min(containing,key=lambda g:g.area)
 if poly.area<0.0000001:continue
 sourceids=[f['properties']['source']['osmId'] for f in fs if shape(f['geometry']).intersection(poly.boundary).length>1e-9]
 units.append(dict(name=name,id='estimated:mosonmagyarovar:street:'+str(points[name]['properties']['source']['osmId']),method='Estimated enclosing street block from archived OSM geometry of the named locality streets and adjacent through streets; polygonize this explicit street list and select the closed block containing the source name point.',sourceUrl=points[name]['properties']['source']['url'],supportingUrls=['https://www.mve1985.hu/images/CLLD/I_resz.pdf','https://www.movinnov.hu/docs/IVS-1.pdf'],sourceLineIds=['way/'+str(i) for i in sourceids],sourcePeriod='OSM snapshot 2026-11-12',approximationNote='Rough local search envelope bounded by '+', '.join(roads)+'. These streets identify a recognizable block around the named locality; the full named estate/neighbourhood may span additional blocks. This is an explicit street-network interpretation, not an official boundary or a point-radius approximation.',geometry=mapping(poly),roadsConsidered=roads))
(P/'street-traces.json').write_text(json.dumps(dict(units=units),ensure_ascii=False,indent=2)+'\n')
