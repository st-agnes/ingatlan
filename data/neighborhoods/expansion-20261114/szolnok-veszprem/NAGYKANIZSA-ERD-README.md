# Nagykanizsa és Érd – további gyors területbecslések

## Nagykanizsa: 18 névvel ellátott terület

A helyben már megőrzött, nyilvánosan letölthető 2024-es önkormányzati FVS
151–152. oldalának két natív térképképét használtuk. Az oldalak a
`merretekerjek.hu` szolgáltatást nevezik meg forrásként. A regionális térképen
látható beépítési foltok, domborzat és főutak alapján a külvárosi részekhez,
a részletes belvárosi úthálózat alapján hat központi városrészhez készült
hozzávetőleges poligon. A poligonok becsült választóvonalakat tartalmaznak;
a forrás nem rajzol városrészhatárokat.

A névvel megjelölt térképi helyek és a megőrzött OSM helypontok egyeztetésével
számolt affin elhelyezés illesztési maradéka 75 m (regionális) és 15,5 m
(belvárosi) RMS. Ez a névpontpárokra vonatkozó illesztési érték, **nem a becsült
határok igazolt pontossága**. Az abszolút pontosság ismeretlen.

Mind a 18 alakzat érvényes, és tartalmazza a hozzá tartozó névpontot. A
megőrzött 19 nagykanizsai OSM helynévből Bajcsa kimarad: a regionális térkép
kiterjedésén kívül van. Körpótlás nincs. Az akcióterületi térképből nem neveztünk
át fejlesztési területet városrésszé.

Újraépítés: `python3 reproduce-nagykanizsa.py`, NumPy/PyProj/Shapely mellett.
A kimenet `nagykanizsa-features.geojson`; a forráspixel-csúcsok, az illesztő
párok és a műszaki összesítés külön JSON-állományok. A két forráskép
`nagykanizsa-fvs-xref1086.jpeg`, `nagykanizsa-fvs-xref1091.jpeg`.

## Érd: 26 névvel ellátott terület

A helyben meglevő országos OSM-pillanatkép alapján térképet készítettünk Érd
főútjairól, vasútjairól, vízfolyásairól, településhatáráról és névvel jelölt
helypontjairól. Ennek alapján kézzel, hozzávetőlegesen becsültük meg a helyek
kiterjedését, a látható fő közlekedési akadályokat követő, illetve azokat helyi
összekötésekkel kiegészítő egyszerűsített sokszögekkel.

A forrás **nem tartalmaz a felsorolt helynevekhez megadott városrészhatárokat**.
A most létrehozott vonalak kifejezetten becslések, `qualityScore:25`
jelöléssel. Nem szabad őket gépi forráspoligonként vagy bizonyítottan hivatalos
városrészhatárként kezelni. A becsléseket az eredeti településhatárra vágtuk.
Körpótlás, Voronoi-felosztás és automatikusan generált sugár nincs a csomagban.

A 27 helypontból 26 különböző név adódik. A két Parkváros nevű pontot egy tágabb
szülőterület foglalja magában; Fenyves-Parkváros és más külön nevű kisebb
területek átfedése szándékosan megmarad. Minden névpont a megfelelő becsült
poligonban van; ez a műszaki koherenciát ellenőrzi, nem a határ pontosságát.

Újraépítés: `python3 reproduce-erd.py`, PyProj/Shapely mellett. Kimenet:
`erd-features.geojson`. Az újraépítéshez szükséges településhatár, helypontok,
a térképkép regisztrációja és a kézi csúcspontok külön megőrzöttek. Az összes
2230 közlekedési/vízrajzi forrásvonal az `erd-source-barriers.geojson` fájlban
van, eredeti OSM-azonosítókkal és származási adatokkal. A forrás térképkép:
`erd-road-map.png`; EOV-ból visszavetített WGS84-koordinátákat használunk.

E csomag az OSM-adatokra az ODbL-1.0 licencet és az
„© OpenStreetMap contributors” forrásmegjelölést viszi tovább. A nagykanizsai
önkormányzati dokumentum térképének külön újrafelhasználási licence nincs
azonosítva; az eredeti szolgáltatói hivatkozást minden rekord megőrzi.

Az eredeti Szolnok–Veszprém 48 rekord és a Békéscsaba 26 rekord változatlan.
Az új Nagykanizsa–Érd állományok összesen további 44 alakzatot adnak.
