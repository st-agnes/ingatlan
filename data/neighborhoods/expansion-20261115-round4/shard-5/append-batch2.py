from pathlib import Path
import json,gzip
P=Path(__file__).resolve().parent;T=json.load(open(P/'targets.json'));S=json.load(open(P/'selection.json'))
raw=[
('Szirmabesenyő','Királyhegy','rural','External rural roads and watercourses outline the whole Királyhegy hillside locality, including its scattered residential parcels; historical limits are approximate.'),
('Mezőhegyes','Ómezőhegyes','rural','Broad actual road enclosure covering the older estate/village area, including the Kozma Ferenc and Csekonics surroundings; it estimates the historical locality, not the buildings alone.'),
('Újszentmargita','Tuka','rural','Compact actual local-road enclosure around the mapped Tuka name. This is a rough settlement search area; the larger historical Tuka-puszta landscape is not fully represented.'),
('Komádi','Hercegföld','areas:1332435095,1332435094,1332435093','Combined mapped agricultural/industrial estate parcels at Hercegföld. The main source object explicitly has addr:place=Hercegföld; surrounding outlying fields are excluded.'),
('Derecske','Móriczföld','street','External rural-road enclosure of the named fringe locality, rather than an arbitrary radius. Historical agricultural land belonging to the name may extend beyond these roads.'),
('Nyírtelek','Tiszti-lakótelep','street','Whole local road enclosure containing the Honvéd/Laktanya estate and name point; old military-estate boundaries are uncertain.'),
('Újfehértó','Pázmány','rural','Whole rural-road enclosure beside Sorhegy at the mapped Pázmány locality. This preserves agricultural/old-garden search context without claiming a cadastral boundary.'),
('Újfehértó','Szügyönyi-tag','rural','Broad actual rural-road enclosure around the historical tag, including the outer garden/residential fringe; the tag has no verified modern formal boundary.'),
('Kemecse','Körmenditanya','rural','Broad rural-road enclosure around Körmenditanya sor and its scattered farms. Includes agricultural surroundings rather than just the nearest farmyard.'),
('Nagykálló','Korányi-lakótelep','street','External road enclosure containing the whole mapped estate and internal park near Korányi Frigyes utca; the estate boundary is an estimate.'),
('Létavértes','Kardosliget','rural','Whole rural-road enclosure across the mapped forest/meadow locality, including the historic dispersed settlement context. Exact estate limits are uncertain.'),
('Létavértes','Kossuth Szőlőskert','areas:228381215','The broad mapped vineyard tract containing the Kossuth garden point and Kossuth kert road is used as an estimated whole historic vineyard-garden footprint; unnamed adjoining vineyards may overlap.'),
('Apagy','Meleghegy','street','Whole external-road enclosure of the named agricultural/old-garden locality. Boundaries follow actual mapped roads, with no fixed-distance buffer.'),
('Nyírgelse','Szalmadpuszta','street','Whole external street enclosure around the compact settlement beside Benczúr/Báthori roads, incorporating several mapped residential parcels; broader historical fields are uncertain.'),
('Nyírbátor','Győrliget','rural','Whole external rural-road enclosure at the Győrliget name point, including the Pócsi/Váraditag scattered estate area. This is distinct from the mapped Györgyliget park; municipal medical-district legislation lists both Győrliget and Györgyliget.'),
('Vásárosnamény','Vásárosnaményi Ipari park','street','Broad external road enclosure covering the mapped industrial campus and associated land. The park is associated with the mapped locality point; legal industrial-park parcel membership is not verified.'),
('Csenger','Ipari Park','street','Broad external road enclosure at the mapped industrial-park locality, incorporating developed and reserve land rather than a single factory footprint. Exact parcel membership is uncertain.'),
('Csengersima','Nagygéc','rural','Broad former-village area enclosed by the surviving rural road network around Gécitelep and the memorial church. The 1970 flood destroyed most of the village; this estimates the historical settlement search area, not just the memorial park.'),
('Mályi','Öreghegyi lakópark','hull','Whole housing-estate envelope traced from its actual flower-named street network, including Kamilla, Zsálya, Kankalin, Boróka and surrounding streets. Connections between external street endpoints are estimated.'),
('Kemecse','Kemecsei Ipari park','rural','Broad actual road enclosure on the southwestern city fringe at the mapped Iparipark access road. Municipal and government sources describe about 100 ha of development land; this coarse roughly 142 ha enclosure includes reserve/agricultural land and is not the legal park boundary.')]
urls={('Mezőhegyes','Ómezőhegyes'):['https://mezohegyes.hu/html/muemlekek/index.html'],('Újszentmargita','Tuka'):['https://www.turistautak.hu/poi.php?id=46833'],('Nyírgelse','Szalmadpuszta'):['https://dnyem.hu/plebaniak/nyiradony/'],('Nyírbátor','Győrliget'):['https://njt.jog.gov.hu/jogszabaly/2021-12-SP-5Y1408'],('Csenger','Ipari Park'):['https://www.szon.hu/pr-cikkek-komarom-esztergom/2023/12/lezarult-a-csengeri-ipari-park-fejlesztesenek-ii-uteme'],('Csengersima','Nagygéc'):['https://csengersima.asp.lgov.hu/foldrajzi-fekves','https://oroksegtar.reformatus.hu/index.php/csengersimai-megmaradas-temploma'],('Mályi','Öreghegyi lakópark'):['https://ingatlan.com/malyi-oreghegyi-lakopark/elado'],('Kemecse','Kemecsei Ipari park'):['https://site.kemecse.hu/2024/05/27/az-osszetartas-es-egyutt-gondolkodas-varosa/','https://kormany.hu/hirek/ujabb-merfoldko-a-zahonyi-terseg-fejlodeseben']}
for city,name,k,note in raw:
 m=next(m for m in T['municipalities'] if m['municipality']==city);t=next(t for t in m['targets'] if t['name']==name);s={'municipality':city,'name':name,'contextKey':m['contextKey'],'kind':'area' if k.startswith('areas:') else ('roadHull' if k=='hull' else 'cell'),'approximationNote':note,'batch':2,'pointSource':t['pointCandidates'][0],'supportingUrls':urls.get((city,name),[])}
 if k.startswith('areas:'):s['sourceAreaIds']=['osm:way:'+i for i in k.split(':')[1].split(',')]
 elif k=='hull':
  names=['Kamilla utca','Zsálya utca','Kankalin utca','Pipacs utca','Hóvirág utca','Boróka utca','Margaréta utca','Alföldi Géza utca','Ibolya utca','Fenyő utca','Liliom utca'];roads=json.loads(gzip.decompress((P.parent/'contexts'/m['contextKey']/'roads.geojson.gz').read_bytes()))['features'];s['sourceLineIds']=[f['id'] for f in roads if f['properties']['tags'].get('name') in names]
 else:s['cellId']=m['contextKey']+':'+name+':'+k
 S.append(s)
assert len(S)==40
(P/'selection.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n')
