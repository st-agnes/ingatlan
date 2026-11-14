# Tartós kereshetőterület-azonosítók

A `search-area-identities.json` a kereshető helyek tartós személyazonossági
nyilvántartása. Kezdőállapota a 2240 rekordos export azonosítóit és kanonikus
névkulcsait őrizte meg. Nem szabad egy újabb export alapján nulláról újragenerálni.

Minden aktív bejegyzés tárolja az `id`, `municipality`, `canonicalNameKey` és
`nameKeys` mezőt. A `nameKeys` az eddig látott név- és aliasváltozatok normalizált
halmaza. Új alias vagy jobb forráspoligon kiválasztása megőrzi az azonosítót és
a kanonikus kulcsot. Egy korábban ismert alias eltűnése a forrásból nem választja
újra külön a már összevont neveket. A különböző nevű, átfedő területeket továbbra
is külön kell kezelni, kivéve, ha kifejezett alias-kapcsolat köti össze őket.

Ha egy új, kifejezett alias két már létező azonosságot köt össze, az ábécérendben
kisebb azonosító marad aktív. A másik azonosító a `redirects` listába kerül
`retiredId` és `targetId` mezőkkel. A további összevonások átirányításláncai
közvetlenül a végső aktív azonosítóra lapulnak. Ez az azonosság technikai
kiválasztása; a legjobb poligon kiválasztása ettől független marad.

Új forráscsomag vagy alias feldolgozásakor:

```sh
python3 scripts/neighborhoods/build-search-areas.py --update-identities
python3 scripts/neighborhoods/build-search-areas.py --check
python3 tests/neighborhoods-search-areas.test.py
```

Az első parancs a nyilvántartással együtt újraírja az exportokat. A `--check`
csak olvas és összehasonlít: sem a nyilvántartást, sem az exportokat nem módosítja.
A kapcsoló nélküli futtatás megáll, ha a nyilvántartás frissítésére lenne szükség;
ilyenkor a `--update-identities` kapcsolót kéri.

Az SQL továbbra is csak a `NeighborhoodSearchAreas` adatállományát kezeli.
A saját tranzakcióján belül, a beszúrások/frissítések előtt kizárólag a
nyilvántartásban kifejezetten visszavont `retiredId` értékeket törli. Más sort nem
töröl, és az alkalmazás egyéb tábláit nem módosítja. A későbbi alkalmazás az
átirányításokat használhatja régebbi, elmentett helyazonosítók feloldásához.
Ez az export elkészítésekor nem futtat SQL-t, és nem kapcsolódik adatbázishoz.

A regressziós tesztek lefedik az új, korábban rendeződő alias és a jobb geometria
melletti azonosító-megőrzést, két régi azonosító összevonását, az alias későbbi
eltűnését, az átirányításlánc lapítását és a törlés pontos azonosítólistáját.
