# Budapest — további 37, térképből és szövegből becsült keresési terület

2026-11-14-i kiegészítés a korábbi budapesti 46-os csomag változtatása nélkül. **Importálható eredmény: `features.geojson`.** Mind a 37 geometria alacsony bizonyosságú kézi becslés, nem hitelesített vagy hivatalos határvonal. Kör és Voronoi-felosztás nem készült.

## Eredmények

- Újpest: Kertváros, Északi Kertváros, Városközpont, Izzó lakótelep, Szilaspatak-lakópark és Károlyi Városnegyed.
- Óbuda és Budafok: Óbuda-lakókert, Gyógyszergyár és Lajos utcai lakótelep, Rózsavölgy, Rózsakert és Mézesfehér utcai lakótelep, valamint a József Attila utcai kísérleti lakótelep.
- Mátyásföld: Ómátyásföld, Újmátyásföld, Centenárium és Jókai-lakótelep, Petőfikert, Lándzsa utcai lakótelep.
- Délnyugat-Buda: Gazdagréti lakótelep és Madárhegyi lakópark.
- További pesti és csepeli területek: Csepel-Alsó Királyerdő, Gloriett-lakótelep, Szentlőrinc úti lakótelep, Kispest-Kertváros, Országbíró utcai lakótelep, Szilas lakótelep és Újpalotai lakótelep.
- Zugló és keleti kisebb lakóterületek: Egressy téri, Mogyoródi–Jerney úti, Nagy Lajos király úti, Pálya utcai, Szent Korona-, Egyenes utcai és Örs vezér téri lakótelep, Paskál lakópark, Zenit Corso.

A munkakezdéskori budapesti ismertnév-lista 397/463 poligonos találatáról ez 434/463-ra, **93,7%-ra** emeli a név szerinti lefedést. Ez nem bizonyítja minden lehetséges budapesti városrész hiánytalan lefedését. A 29 fennmaradó név a `packet-summary.json` fájlban szerepel.

## Hogyan készültek a határok?

A `manual-traces.json` tartalmazza a kézzel becsült WGS84-töréspontokat és minden terület térképi támpontjait. A becslések a tényleges, archivált utca-, vasút- és vízfolyásrajzhoz, a lakótelepi tömbök hálózatához és a meglevő névpontokhoz igazodó keresési körvonalak. Kisebb végszakaszok és bizonytalan lakótelep-átmenetek elemzői következtetések; a poligonok nincsenek forrás által megrajzolt, teljes városrész-határnak beállítva.

Az újpesti három nagyobb terület önkormányzati rendeletekben szereplő utcahurokja alapján lett megközelítően végigvezetve. A jogszabályi utcák támpontok: az itteni kézi vonalak nem helyettesítik a jogszabály térképi mellékletét. A hivatkozások minden érintett elem `supportingUrls` mezőjében megvannak.

Ómátyásföld és Újmátyásföld a korábban meglevő natív Mátyásföld-poligon külső határát őrzi meg. Az Ó/Új elkülönítésről szóló leírások alapján a Veres Péter út/HÉV vonalán becsült belső vágás készült. Hasonlóan Csepel-Alsó Királyerdőnél a meglevő Királyerdő-poligon külső határa marad meg, a déli területet a látható keresztutcák mentén becsült vágás választja le. A csepeli Alsó elnevezéshez külön hivatalos határ nem lett állítva.

Rózsavölgy a Hosszúréti-patak és az Ady Endre út körüli lakott völgy, valamint a környező hegyoldali utcák alapján kapott tágabb becslést. A gyűjteményben nincs Kis-/Nagy-Rózsavölgy-forráspoligon, ezért nem állítunk ilyen forrásegyesítést.

A lakóparkok/lakókertek szokásos méretkorlátja 0,25 km², a kisebb lakótelepeké 0,75 km². **Újpalotai lakótelepnél dokumentált 1 km²-es kivétel van:** a nagy, összefüggő lakótelep utcák mentén becsült területkörvonala a natív Újpalota határával lett metszve, így 0,88 km² maradt; a 3,62 km²-es egész szülőterület nincs a lakótelep neve alatt újrahasznosítva. A többi házas/történeti terület és a három újpesti szabályozási terület tágabb egység, ezért rájuk a kis lakótelepi korlát nem alkalmazható.

## Megőrzött bemenetek

- `name-points.geojson`: a 66 munkakezdéskor még pontként ismert helynév, eredeti OSM-objektumcímekkel.
- `parent-features.geojson`: a 397 meglévő budapesti terület befagyasztott kontextusa; a visszaépítés nem függ a később változó országos exporttól.
- Négy `*-source-roads.geojson.gz`: egy helyi országos PBF-feldolgozásból 184 736 teljes, tényleges OSM utca-/vasút-/vízvonal. Mindegyik elemben megvan az objektum URL-je, attribútuma, teljes koordinátasora és a PBF SHA-ja. A legnagyobb szektor tömörítve kb. 4,2 MB, tömörítés nélkül 38 MB; nincs 95 MB fölötti fájl.
- A `*-context.png` képek és regisztrációik a kézi becsléshez használt utcatérképi nézetek.
- `manual-traces.json`: minden kézi vonal és forrástámpont; `build.py`: a 37 eredmény visszaépítése.

OSM forrásadatok: © OpenStreetMap contributors, ODbL-1.0. Az eredeti helyi PBF SHA-ja: `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`. Az önkormányzati/helytörténeti webforrások URL-jei az egyes geometriákban és a nyers becslési jegyzékben találhatók.

## Újraépítés és ellenőrzés

A tároló gyökeréből, telepített `shapely` Python-csomaggal:

```sh
python3 data/neighborhoods/expansion-20261114-next/budapest-remaining/build.py
python3 data/neighborhoods/expansion-20261114-next/budapest-remaining/verify.py
```

A kész poligonokhoz nem kell hálózat vagy országos PBF. Az `extract-roads.py` csak a nyers kontextus újbóli kinyerésére szolgál, ha a helyi PBF rendelkezésre áll. A 37 geometria érvényes, tartalmazza a saját névpontját, nincs köztük normalizált névduplikáció, és bájtra azonosan újraépíthető. A térbeli és reprodukciós ellenőrzés nem határpontossági tanúsítás.
