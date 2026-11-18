# Kisvárda – hat funkcionális városrész, 2026. november 15.

**6 új, becsült terület**, köztük az elsőként elkészített teljes **Városközpont**. Mindegyik `estimated: true`, `lowConfidence: true` és `candidateBoundaryKind: planning_unit`. A városrészek nevét és határoló utcáit a 2015-ös önkormányzati ITS adja, a koordináták a tényleges helyi úthálózat és területhasználat alapján kézzel készített durva becslések.

A fő réteg nevei: Városközpont; Nyugati Kertvárosi rész; Északi Kertvárosi rész; Kiemelt Szolgáltatói városrész; Keleti városrész; Déli Ipari Szolgáltatói Városrész. A `center-features.geojson` a Városközpont önálló kivonata, nem még egy hozzáadandó réteg.

## Mit támaszt alá a forrás?

A [hivatalos ITS](https://www.kisvarda.hu/wp-content/uploads/2025/03/ITS__Kisvarda.pdf) 20. oldala kifejezetten funkcionális és földrajzi felosztásként írja le a hat egységet, közigazgatási és jogalanyi státusz nélkül. A 21. oldal a hat egységet számozza; a 22. oldal táblázata az egyes egységekhez utca-, tér- és vasútneveket rendel. A 44. oldal a lehatárolásokat az akcióterületeknél megismétli. A dokumentum 2015-ös, az URL-ben szereplő 2025 a feltöltés ideje.

A korábban archivált `kisvarda-boundary-definitions.json` helyi másolata itt `source-boundary-definitions.json` néven megmarad. A táblázatot a gyűjtéskor a webes csatlakozóval újra ellenőriztük. A forrás-PDF nem található helyben, letöltésére nem vártunk. A geometriák **nem natív PDF-poligonok és nem a nyomtatott térképek pontos digitalizálásai**: az ellenőrzött szöveges határleírás és a mentett fizikai térkép alapján készültek.

## A becslés értelmezése

A Városközpont a történeti központ egész utcaterületét fogja át az Ostrom–Arany–Kossuth–Petőfi–Széchenyi–Liptay és vasút/Gyár/Aradi, illetve a nyugati Várday környezetében. A forrás Rákóczi, Szent László és Várday „külső oldalát” is említi; ezekhez nem találtunk telekhatáronként megállapítható távolságot. A tágabb történeti központi utcaterület megmarad, de a külső utcai ingatlanhatárokat nem állítjuk pontosnak.

A többi egységnél is a teljes helyi utcaterület volt a cél, nem egy névpont körüli kör vagy egyetlen kis utcacella. A mai térképen egyes forrásbeli utcanevek szakaszai nem kapcsolódnak egyértelmű zárt gyűrűvé; például a Nyugati Kertvárosi rész listájában Várday kétszer szerepel. A rövid összekötéseket és a kertvárosok külső kert-/mezőgazdasági átmeneteit ezért becsültük. A déli egységnél a gyárterületek egészének megtartásához a déli területhasználati átmenet is támpont.

A Kiemelt Szolgáltatói városrész északi kapcsolatát a mai Andy Vajna utca szemlélteti; ebből nem állítottunk fel hivatalosan igazolt utcaátnevezési megfeleltetést. A Liptai/Liptay, Jéki/Jékei, Halasy/Halassy, Móser/Mózer, illetve a rövid Széchenyi/Rákóczi/Csokonai alakok térképi értelmezése a `source-evidence.json` fájlban szerepel. Ezek helyi geometriai támpontok, nem globális helynév-szinonimák.

A becslések egymással és más történeti/helyi felosztásokkal átfedhetnek. Nem állítunk hézag- és átfedésmentes városi felosztást, jelenkori teljességet vagy cím-hozzárendeléshez alkalmas jogi határokat. **Kör, puffer, pontból képzett téglalap, Voronoi és konvex burok nem készült.** Az egységekhez nem gyártottunk kitalált névpontokat.

## Fájlok és újraépítés

- `features.geojson`: a hat fő alakzat WGS84-ben.
- `selection.json`: a befagyasztott kézi csúcsok és az egyedi indokolások.
- `source-lines.geojson`: 1781 tényleges helyi út-, vasút- és vízvonal, OSM URL-lel, verzióval és időbélyeggel.
- `source-areas.geojson`: 229 tényleges zárt területhasználati/rekreációs OSM-útvonal a térképi környezethez. Ez nem a város összes multipoligonjának teljes rétege.
- `source-municipality.geojson`, `source-boundary-definitions.json`: településhatár és a korábban archivált utcanév-leírások.
- `context-1.png`–`context-6.png`: az áttekintett tényleges úthálózat, a forráslista alapnév szerinti kiemelésével. A mai rövidített nevek egy része szürke maradhat.
- `source-evidence.json`, `summary.json`, `validation.json`, `unresolved.json`: eredet, eredmény és korlátok.
- `alias-proposals.json`: két, ugyanazon számozott ITS-egységre igazolt névváltozat-javaslat; globális névjegyzék nem módosult.

A fő réteg minden szükséges bemenete megmarad. Újraépítés hálózat, PDF-letöltés és országos PBF nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/kisvarda/build.py
```

Függőségek: `shapely`, `pyproj`. Az opcionális `extract-osm.py` egy célzott, egyszeri helyi PBF-útvonalolvasást végez (`osmium`), a `render.py` a mentett vonalakból készít kontextusképeket (`Pillow`). A forrás-PBF SHA-256-a a rekordokban és a bizonyítékfájlban megmarad.

Ellenőrzés: mind a hat alakzat érvényes, nem üres WGS84 Polygon/MultiPolygon és a megfelelő forrás szerinti településhatáron belül van. A település–név párok egyediek. A név szerinti mind a hat ITS-egység feldolgozása nem igazol teljes városi térbeli lefedettséget.

OSM: ODbL-1.0, © OpenStreetMap contributors. Az ITS bizonyítékforrás; külön újrafelhasználási licencet nem állapítottunk meg.
