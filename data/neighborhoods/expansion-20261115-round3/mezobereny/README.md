# Mezőberény – Városközpont, 2026-11-15

**Egy új poligon készült**, a korábban csak névponttal ismert Városközpont teljes, önkormányzati utcajegyzékkel meghatározott területére. A csomag nem egy épületet, közteret, egyetlen háztömböt vagy a teljes város beépített területét veszi át. A városrész becsült területe **60,61 hektár**, határvonala körülbelül **3,85 km**.

Beemelendő: **`features.geojson`**, EPSG:4326 / WGS84, hosszúság–szélesség sorrend. A saját cél teljesült (`unresolved.json` üres); az országos gyűjtés ettől még nem teljes.

## Elsődleges határleírás

A [2010. májusi önkormányzati antiszegregációs terv](https://mezobereny.hu/adattar/PMH/antiszegr._2010_._majus_.pdf) nyomtatott 8. oldala, PDF-index 7, 17 egymást követő utcával adja meg a Városközpont zárt határát. A tényként átírt, rendezett útszakaszjegyzék a `boundary-definition.json` fájlban szerepel. Hunyadi János utcánál indul és Gyomai útról ugyanoda tér vissza.

A [2021. februári ITS-megalapozó tanulmány](https://mezobereny.hu/adattar/Kozerdeku/megalapozo-tanulmany-mezobereny-integralt-telepuelesfejlesztesi-strategiajahoz_vegleges_210303-653048pdf.pdf) 144–146. oldala újraértékeli és megtartja a korábbi felosztást; az 54. ábra mutatja a városrészeket. A leírás alapján a központ lakóutcákra és a Luther tér, Kismester–Nagymester utcák, valamint a Kölcsey-lakótelep környezetére is kiterjed. Ezért a funkcionális Városközpont nem azonos egyetlen szűkebb építési övezettel vagy a városháza telkével.

A dokumentumokat a webes PDF-szövegnézeten ellenőriztük; a teljes PDF-binárisok nincsenek a csomagban. Az offline újraépítéshez a visszakereshető URL, lapszám és strukturált, tényszerű határjegyzék, valamint a mellékelt tényleges útnyomvonalak elegendők. Nem állítjuk, hogy a PDF térképi kontúrjának natív vektorexportja készült.

## Geometriai módszer és bizonytalanság

A már archivált, 2026-11-12T21:23:05Z OSM-kivonat tényleges útpontjaiból áll össze az önkormányzati utcajegyzék sorrendjét követő zárt útvonal. A `boundary-route-audit.json` minden határlépéshez felsorolja a tényleges OSM-vonalazonosítókat és a hosszt. Az útvonal mind a 17 megadott utcalépést használja; az egymást követő végpontok mindenütt tényleges forrásszakaszokhoz tartoznak. Nincs kitalált egyenes záróél, kör, ponthalmazburkolás, Voronoi-felosztás vagy névpontból képzett doboz.

A történeti és a mai utcanevek között rövid illesztések szükségesek: Jeszenszky utca kb. 10 m, Kölcsey utca kb. 123 m, Petőfi Sándor út kb. 17 m. Ezek is tényleges, archivált útszakaszok, de a történeti utcaleírás mai térképre értelmezése miatt **becslésként** szerepelnek. A 2010-es szöveg a Puskin-szakasz két oldalát is beleérti; az elkészült körvonal utcai középvonalat követ, ezért a telekoldali kiterjedés nem földmérési pontosságú.

A rekord `method=map_or_text_estimate`, `estimated=true`, `lowConfidence=true`. A 2021-es megerősítés történeti kontextus; nincs állítás a 2026-os hivatalos nyilvántartási állapotról. A különböző névhasználatú szomszédos városrészekkel való átfedés megengedett.

## Megőrzött forrás és újraépítés

- `source-roads.geojson`: 254 teljes, tényleges helyi OSM-vonal az objektumazonosítókkal, tagekkel és URL-ekkel.
- `source-municipality.geojson`: tényleges OSM-közigazgatási határ, erre történik az eredmény levágása.
- `source-manifest.json`: a korábbi archivált állomány és az eredeti PBF SHA256 értéke, időbélyeg, vizsgálati kiterjedés, ODbL-1.0 és © OpenStreetMap contributors forrásmegjelölés.
- `baseline-target.json`: az eredeti névpont és az egyetlen hiányzó cél.
- `boundary-definition.json`: elsődleges forráshivatkozás, lapszám, történeti határsorrend, mai névmegfeleltetések és a bizonytalanságok.
- `boundary-route.geojson`: a teljes tényleges forráspont-sorozatból álló zárt vonal.
- `center-review.png`: a rekonstrukció áttekintő térképe, nem hivatalos határtérkép.

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/mezobereny/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/mezobereny/verify.py
```

Az újraépítés helyi forrásokból, hálózat nélkül, bájtra azonos eredményt ad. Shapely és pyproj szükséges; a térkép újrarajzolásához Pillow is (`render.py`). A `prepare.py` már meglévő helyi archívumból másolja ki a forrást, nem új hálózati gyűjtést végez. Az alkalmazás, a globális katalógus, a MySQL-adatbázis és a Cloud-környezet ebben a részfeladatban nem módosult.
