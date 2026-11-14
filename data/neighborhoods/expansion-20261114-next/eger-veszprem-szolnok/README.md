# Eger, Veszprém, Szolnok – a körös helyettesítések csökkentése

2026-11-14-i kutatási csomag: **28 új poligon**, 0 körös becslés, továbbá egy
már meglévő egri terület dokumentált névváltozatai. A gyűjtés nem módosítja az
alkalmazást vagy az adatbázist; a közös katalógusba történő beolvasás külön lépés.

| Település | Új terület | Jelleg |
|---|---:|---|
| Eger | 8 | 1 tényleges OSM-felület, 1 térképi részunió, 1 kivonással becsült terület, 5 utcahálózat alapján becsült rész |
| Veszprém | 13 | kisebb lakótelepek, városrészek és völgyek utcahálózat alapján becsült határa |
| Szolnok | 7 | vasúti, úthálózati és településszerkezeti támpontokból becsült rész |

## Eredmények

- `eger-source-features.geojson`: Lajosváros, Almagyar, Érsekkert.
- `eger-features.geojson`: Bervai lakótelep, Fenstherm Lakópark, Pásztorvölgy,
  Tetemvár, Cifrahóstya.
- `veszprem-features.geojson`: Aranyosvölgy, Temetőhegy, Pajtakert, Veszprémi Vár,
  Veszprémvölgy, Endrődi Sándor-lakótelep, Petőfiváros, Takácskert,
  Nándortelep, Hóvirág lakótelep, Egry József utcai lakótelep,
  Cserhát-lakótelep, Cholnoky-lakótelep.
- `szolnok-features.geojson`: Déli városrész, Cukorgyári lakótelep, Piroska,
  Meggyesitelep, Malomszeg, Alcsisziget, Tabán.
- `alias-suggestions.json`: az OSM mentett neve szó szerint
  **Felsőváros (Északi városrész)**; ez a meglévő egri Felsőváros poligon
  névváltozataként kezelhető. Nem készül újabb, azonos területű poligon.

Az Érsekkert a 120931688-as OSM parkfelület változatlan koordinátáival szerepel.
Lajosváros a korábban megőrzött keleti és nyugati térképi rész tényleges uniója.
Almagyar a térképi Almagyar–Merengő terület és a megőrzött Merengő felület
különbsége; utóbbi nem feltétlenül fedi a hétköznapi Merengő fogalom teljes
területét, ezért az eredmény kifejezetten becslés.

## A kisebb területek levezetése

A városi önkormányzati/történeti térképek nagyobb területei csak háttérként
szerepelnek. A finomabb poligonokat a megtartott tényleges OSM utak, vasutak,
vízfolyások, látható utcatömbök és beépítési szélek alapján becsültük.
A poligonokhoz külön `boundaryRationale` mező írja le a támpontokat.
Az egyenes összekötések és a kisebb területeket elválasztó élek becslések,
nem hivatalos vagy szó szerint egy forrástérképre nyomtatott határok.

Az elkészült kisebb részek nem a teljes korábbi szülőterület átnevezett
másolatai. A Veszprémi Vár nem az Érseki palota épületének poligonja,
a szolnoki Tabán nem az azonos nevű kosárlabdapálya, a Cholnoky-lakótelep
pedig nem a teljes Cholnokyváros változatlan másolata. Tágabb és szűkebb
felosztások között átfedés lehetséges és szándékosan megengedett.

## Megőrzött források és újraelőállítás

A `*-roads.geojson` állományok tényleges forrásvonalak, a `*-areas.geojson`
állományok tényleges zárt forrásfelületek. Az OSM-kivágás a PBF egy menetben
történő helyi feldolgozásával készült; a PBF azonosítója, dátuma és a kiválasztás
szabálya a `road-extraction.json` fájlban található. Nem állítjuk, hogy a
megtartott way-verziók és node-hivatkozások minden node teljes verziótörténetét
is tartalmazzák.

A `*-road-map.png` térképek a mentett vonalakból közvetlen koordináta-
átszámítással készültek. A `*-registration.json` rögzíti az EOV-alapú
képi transzformációt és a mentett névpontokat, a `*-traces.json` pedig a
képernyőn becsült töréspontokat. Ezekből hálózati hozzáférés nélkül újra
előállíthatók a végső GeoJSON-ok:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/eger-veszprem-szolnok/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/eger-veszprem-szolnok/build-eger-source.py
```

Az általános függőségek: Python 3, Shapely, pyproj. A nyers helyi PBF ismételt
kivágásához pyosmium, a térképképekhez Pillow is szükséges. A végső poligonok
újraelőállításához nem szükséges újra lefuttatni a PBF-kivágást vagy a térképek
rajzolását, mert az összes levezetési bemenet megmaradt.

A `sources.json` tartalmazza a tényleges forráscímeket és a bemeneti fájlok
SHA-256 lenyomatait. Az önkormányzati/disszertációs képek szabad újrafelhasználási
licence nem volt megállapítható; a mentett OSM-vonalak ODbL-1.0 forrásúak.

A `summary.json` rögzíti a kimeneti lenyomatokat és az ellenőrzést: mind a 28
poligon szerkezetileg érvényes, a nevek településenként egyediek, és az összes
mentett saját névpont a megfelelő felületbe esik. Ez utóbbi elhelyezési
ellenőrzés, nem a valódi határ független pontossági mérése. Az újraépítés
mind a négy kimeneti fájlt bájtra azonosan állította elő.
