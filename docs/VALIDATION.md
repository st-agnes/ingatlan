# Ellenőrzési állapot

A .NET és MySQL futtatása a GitHub Actions felhős tesztkörnyezetében sikerült. A korábbi helyi sandboxhibák már nem akadályozzák a tárolóban lévő kód fordításának és adatbázisos működésének ellenőrzését.

Bizonyított futás: [GitHub Actions, 2026. november 1.](https://github.com/st-agnes/ingatlan/actions/runs/41324183251), kódverzió: `1b2d08b92162abc2bef3c81273de537ea7dc069f`. A mindenkori frissebb ellenőrzések a tároló Actions lapján és a pull requestnél láthatók.

| Ellenőrzés | Eredmény |
|---|---|
| .NET 8 fordítás | Sikeres |
| xUnit szerveroldali tesztek | 22/22 sikeres |
| Böngészős üzleti modell | 9/9 sikeres |
| Offline felületi integráció | 7/7 sikeres, szimulált DOM |
| API-adapter | 8/8 sikeres, backend-formátumú mock HTTP-válaszok |
| Fejlesztői infrastruktúra | 3/3 sikeres |
| API és MySQL 8 elindítása | Sikeres, elérhető health végpont |
| Valódi MySQL-es API-integráció | Sikeres |

Az adatbázisos teszt ellenőrizte a regisztrációt, tulajdonosi jogosultságokat, kompatibilis ajánlást, kontaktadatok zárolását, elégtelen egyenleget, párhuzamos ismételt kéréseknél az egyszeri kreditlevonást, kölcsönös párosítást és üzenetküldést.

A valós fordítás során talált EF Core-csomagverzióütközést javítottuk: a futásidejű Core és Relational csomagok explicit azonos verzióval kerülnek át a tesztprojektbe. A MySQL hosszú szöveg- és JSON-mezőit longtext típusra állítottuk a sorhosszkorlát miatt; ehhez regressziós modellteszt is tartozik.

## További, külön ellenőrzést igénylő területek

- Valódi böngészős vizuális/akadálymentességi ellenőrzés és képernyőkép: az offline DOM-tesztek ezt nem helyettesítik.
- A devcontainer saját képének teljes felépítése: a konfiguráció és az indítószkriptek ellenőrizve, a .NET/MySQL futás a GitHub Actions környezetben igazolt.
- Stripe tesztfizetés, webhookkézbesítés és pénzügyi egyeztetés: saját Stripe-tesztkulcsok és elérhető webhook szükségesek; fizetés nem történt.
- Állandó éles tárhely, mentések és monitoring beállítása külön üzembe helyezési feladat.

A CI-adatbázis a futás végén törlődik. A fejlesztőkörnyezet MySQL-adatai Docker-kötetben maradnak meg. A CI sikere a tesztelt folyamatok működését igazolja; nem állítja, hogy minden éles üzemeltetési feltétel készen áll.
