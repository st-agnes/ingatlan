# A webes felület és a .NET API összekötése

A webes felület alapértelmezésben böngészőben tárolt demóadatokkal indul. Ez lehetővé teszi a profilváltás, a lapozás, a kölcsönös találat és a kreditfogyás kipróbálását önálló szerver nélkül. A demóban indított kreditfeltöltés nem jár fizetéssel.

A valódi API használatához indítsd el a MySQL-t és a .NET szervert a projekt üzemeltetési útmutatója szerint. A felület Beállítások oldalán add meg az API alapcímét, majd jelentkezz be vagy regisztrálj. A cím a szerver gyökere legyen; a végén szereplő `/api` részt az adapter eltávolítja, mielőtt összeállítja az útvonalakat.

A `dist/api.js` exportjai:

- `getModel()`: a mentett API-kapcsolat alapján API-adaptert vagy a böngészős demómodellt adja vissza.
- `connectApi(baseUrl, email, password, registerData?)`: belépés, illetve megadott `registerData` esetén regisztráció; sikeres hitelesítés után menti a kapcsolatot és visszaadja az API-adaptert.
- `disconnectApi()`: törli a mentett hitelesítést és visszaadja a demómodellt. A demóadatok megmaradnak.

Az API-adapter a demómodelllel azonos felületet nyújt, de minden adatkezelő metódusa aszinkron. A hívónak `await` használatával kell megvárnia a `getState()`, `feed()`, `matches()` és a módosító műveletek eredményét. Az adapter nem vált át észrevétlenül demóadatokra szerverhiba, lejárt munkamenet vagy hálózati hiba esetén.

A helyi `otthonra.api` kulcs kizárólag az API-címet és a Bearer tokent tartalmazza; jelszó nem kerül mentésre. A kijelentkezés ezt a kulcsot törli. Éles használatkor HTTPS-t és szigorú tartalombiztonsági szabályokat használj; a token tárolási módja a végleges üzemeltetési környezethez igazítható. A forrásadatokhoz való jogosultságot minden esetben a .NET szerver ellenőrzi.

A külön telepített webes felület pontos eredetét a backend engedélyezett CORS-eredetei közé kell felvenni. A HTTPS-en megnyitott webes felülethez HTTPS API-t használj. Fejlesztéskor a frontend és a backend egyaránt futhat helyi HTTP-címen.

A webes árak millió forintban szerepelnek; az adapter a backend teljes forintban tárolt árait két irányban átváltja. Az API-adapternek átadott képcímeknek más kliensekből is elérhetőnek kell lenniük. A demó `/assets/` képei kizárólag a webes demó saját mintaképei.
