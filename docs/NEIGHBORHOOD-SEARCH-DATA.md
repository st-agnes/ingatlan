# Kereshető városrészek, átfedő területek és MySQL-import

A 2026. november 14-én megadott gyűjtési stratégia alapján a korábbi kutatási rétegeket és az új forráscsomagokat egy név szerint egyesített keresési állomány fogja össze. A gépi poligonok átvételéhez nem szükséges külön mai név- vagy földrajzi pontosságellenőrzés. A térképi becslések, történeti felosztások és tágabb városrészcsoportok is szerepelhetnek benne.

## Aktuális fájlok

- `data/neighborhoods/search-areas.geojson.gz`: minden kiválasztott terület WGS84-poligonnal, stabil azonosítóval és forráshivatkozásokkal, tömörítve tárolva a repóban.
- `data/neighborhoods/search-areas.geojson`: a tömörített állomány teljes, bájtra azonos helyi nézete. Az építőprogram előállítja, és a ZIP is tartalmazza; mérete miatt külön tömörítetlen Git-példányt nem tárolunk.
- `data/neighborhoods/search-area-names.json`: kisebb névjegyzék a későbbi helyszínválasztóhoz, névváltozatokkal és `Vénkert (Debrecen)` jellegű címkével.
- `data/neighborhoods/search-areas.mysql.sql.gz`: MySQL 8.0/8.4 táblaséma és idempotens adatfeltöltés. A tömörítés a GitHub-mentések méretét csökkenti.
- `data/neighborhoods/search-areas-report.csv` és `.json`: kiválasztott területek településenként és módszerenként.
- `data/neighborhoods/search-areas-deduplication.json`: melyik változatot választottuk és mely forrásváltozatok maradtak meg alternatívaként.
- `data/neighborhoods/search-area-identities.json`: tartós azonosítók és korábban összevont nevek; új névváltozat vagy jobb geometria nem hoz létre új azonosítót.
- `downloads/neighborhoods/otthonra-keresheto-varosreszek.zip`: az aktuális poligonok, névjegyzék és külön tartalékkörök letölthető csomagja, belső SHA-256-jegyzékkel. A MySQL-import külön letölthető fájl marad; annak ellenőrző összege a ZIP jegyzékében is szerepel.

A korábbi `neighborhoods.geojson`, `estimated-candidates.geojson` és a hozzájuk tartozó jelentések megmaradnak történeti kutatási állapotként. Az új, bővebb keresési állomány számait a `search-areas-report` mutatja.

A fő GeoJSON önmagában is kibontva használható, teljes újraépítés nélkül:

```sh
gzip -dc data/neighborhoods/search-areas.geojson.gz > data/neighborhoods/search-areas.geojson
```

Az ellenőrzések friss klónozás után a kötelező tömörített exportból is működnek.
A ZIP-ben a teljes tömörítetlen GeoJSON megmarad; geometriát vagy metaadatot nem
hagytunk el az átcsomagolás során.

## Névazonosság és kiválasztás

A település és a normalizált név együtt azonosít egy területet. A kis- és nagybetű, szóköz és kötőjel nem különböztet meg városrészt; a dokumentált névváltozatok is összevonódnak. Az ékezeteket nem töröljük. Azonos nevű területek különböző településeken külön rekordok maradnak. A különböző nevű kisebb és nagyobb területek átfedése szándékosan megengedett.

Az azonos helyet leíró alternatívák közül elsőbbséget kap az OSM közigazgatási határ, majd a natív, névvel ellátott forráspoligon, a forrástérkép poligonja, a térképi vagy szöveges becslés, az elnevezett felszín körvonala, végül a pontból képzett tartalékkör. Azonos forrásszintnél az egész városrészt leíró szülőterület előnyt kap az azonos nevű részterülettel szemben; utána a megadott adatminőség és stabil sorrend dönt. A kiválasztott geometria nem lesz a többi forrásalakzat mesterséges uniója.

A névvel ellátott lakóterület, kerttelep vagy ipari felszín körvonala hasznos kereshető terület lehet, de nem feltétlenül fedi egy tágabb, azonos nevű köznyelvi városrész teljes kiterjedését. Ezért ezek a rekordok külön `named_source_footprint` módszerjelölést kapnak, és egy teljesebb térképi városrészhatár megelőzi őket.

Az úthálózatból képzett zárt cellák csak néhány tömböt, a külterületi forrásfelszínek
pedig esetenként csak a térképezett tanyaudvarokat fedik. Az új csomagok ezeknél
`lowConfidence`/`confidence: low`, `partialSourceFootprint` vagy `partialSettlementFootprint`
jelzőt és egyedi indokolást tárolnak a `sourceProperties` mezőben. Az ilyen
poligonból kimaradó cím ezért még tartozhat a köznyelvi városrészhez. A névjegyzék
feldolgozottságát és a teljes területi lefedettséget külön kell kezelni.
Az elnevezési pont és a forrás szerinti határ eltérése szintén megmarad a
metaadatokban; a geometriát nem tágítjuk pusztán a névpont befogadásához.

## Címvizsgálat és adatbázis

A cím koordinátáját külön geokódolási lépés adja meg. Ez az állomány a koordináta területen belüliségét teszi vizsgálhatóvá; címadatbázist és geokódoló szolgáltatást nem tartalmaz. Egy cím több, egymást átfedő városrészhez is tartozhat.

A SQL-csomag kizárólag a `NeighborhoodSearchAreas` táblát hozza létre vagy tölti. Nem változtatja meg az alkalmazás meglévő tábláit. Ha egy későbbi névazonosítás két korábbi katalógusazonosítót összevon, a tartós nyilvántartás rögzíti az átirányítást; az import csak ezeket a kifejezetten visszavont katalógusazonosítókat törölheti a saját táblájából. Más sorokat nem töröl. A névazonosságot egyedi index, a geometriát SRID 4326 és térbeli index tárolja. A betöltés például:

```sh
gzip -dc data/neighborhoods/search-areas.mysql.sql.gz | mysql --database=ingatlan
```

A későbbi alkalmazáskódban a koordináták és a település kötött paraméterek legyenek:

```sql
SET @address = ST_GeomFromText('POINT(21.61 47.55)', 4326, 'axis-order=long-lat');
SELECT Id, Name
FROM NeighborhoodSearchAreas
WHERE Municipality = 'Debrecen'
  AND MBRIntersects(Boundary, @address)
  AND ST_Intersects(Boundary, @address);
```

A `ST_Intersects` a határvonalra eső címet is elfogadja. A forrástérképekből becsült körvonalak természetesen közelítő földrajzi eredményt adnak. A nyers forrás, az alkalmazott módszer és a bizonytalanság a rekordban megmarad.

Ez a munka az adatgyűjtést és az importcsomagot készíti elő. Az alkalmazás helyszínválasztójába és backendjébe történő bekötés külön fejlesztés; a Google Cloud-adatbázist ezek a programok nem módosítják.

## Újraépítés és folytatás

```sh
python3 scripts/neighborhoods/build-search-areas.py
python3 scripts/neighborhoods/build-search-areas.py --check
python3 tests/neighborhoods-search-areas.test.py
python3 scripts/neighborhoods/package-search-areas.py --check
```

Új forráscsomag vagy névváltozat felvétele után `python3 scripts/neighborhoods/build-search-areas.py --update-identities` menti az új névazonosságokat és újragenerálja az exportot. A tartós nyilvántartást az adatokkal együtt kell megőrizni. Az import előkészített állomány; tényleges MySQL-szerveren ebben a munkamenetben nem futtattuk.

A források elfogadott kész csomagjait az `expansion-20261114/input-registry.json` SHA-256-tal rögzíti. A még feldolgozás alatt álló fájlok ezért nem változtatják meg észrevétlenül a kiadást. A részeredmények és a következő munkák az ugyanott tárolt `WORK-STATE.json` fájlban szerepelnek. Az országos teljes városrészszám továbbra sem ismert; az ismert névjegyzékek lefedése külön mérőszám, nem országos teljességi állítás.

A november 15-i folytatás saját állapota és részletes módszertana:
`data/neighborhoods/expansion-20261115/WORK-STATE.json`, illetve az ugyanott lévő
`README.md`. A közös regisztert és stabil azonosítókat ez a gyűjtési kör is
megtartja. A ZIP a gyűjtési körök mentett állapotát is tartalmazza.
