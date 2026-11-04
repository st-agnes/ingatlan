# Ellenőrzési állapot

## Google Cloud teszttelepítés

Az új CI ugyanazt a .NET 8 API-t MySQL 8.0 és 8.4 mellett is ellenőrzi, Docker-builddel, valódi adatbázisos integrációval és sémafrissítéssel. A hosted böngészőteszt asztali, tablet- és mobilméretben valódi regisztrációt, keresésmentést, aktiválást, tesztkreditet, újratöltést és újbóli belépést vizsgál. A Production hosting explicit tesztjelölés nélkül nem adhat ingyen kreditet.

A bootstrap tesztjei helyi Google-parancs- és HTTP-helyettesítőkkel futnak, a Hosting csomagolótesztjei ideiglenes fájlokkal. Nem hoznak létre számlázott cloud-erőforrást. A sikeres CI nem igazol élő Google Cloud-telepítést; annak hitelesítése, IAM-ja, Cloud SQL-kapcsolata és publikus HTTPS-címe az első Cloud Shell-futtatáskor ellenőrizhető. Az aktuális CI-eredményt a pull request ellenőrzései mutatják.

## Fejlesztői indítás és helyreállítás

A JavaScript-csomag külön ellenőrzi a fejlesztői konfigurációt és életciklust. A CI külön élő folyamattesztet futtat: API nélküli webes elérés, ismételt és párhuzamos indítás, megvárt leállás, azonnali újraindítás, egyéni webport és API-/webfolyamat-kiesés utáni helyreállítás. A Codespaces külső porttovábbítását ez nem helyettesíti. A teljes eredmény a PR aktuális CI-futásánál látható.

## Helyszínválasztó és keresésindítás javítása

A katalógus-, modell-, API-adapter-, offline felületi és infrastruktúrateszteken belül a regressziók a külső kattintást és fókuszváltást, a beírt szöveg megőrzését, az eseménykezelők eltávolítását, valamint a mentés utáni visszajelzést, aktiválást és hibakezelést ellenőrzi.

A `tests/browser.test.mjs` valódi Chromiumban, 1280×900, 800×1100 és 390×844 méretben vizsgálja, hogy a találati lista nem takarja el a beírt szöveget. Az érintéses/kattintásos bezárás, a billentyűzetes választás, a sikeres mentés, a felfedezés gomb és a „Később” folyamat is része. Ezt a CI futtatja; eredménye és hiba esetén képernyőképei a pull request ellenőrzéseinél találhatók. A korábbi verziók bizonyított eredményei alább maradnak meg.

## Településválasztó és többhelyszínes keresés

A 2026. november 2-i fejlesztés teljes ellenőrzése sikeres. Bizonyított futás: [GitHub Actions](https://github.com/st-agnes/ingatlan/actions/runs/41409659020), kódverzió: `3341917edfdfb7f228ec09e2e1d354530535bc0f`.

| Ellenőrzés | Eredmény |
|---|---|
| Közös településkatalógus és szűrés | 5/5 sikeres |
| Böngészős üzleti modell és régi demóadatok | 14/14 sikeres |
| Offline felületi integráció | 10/10 sikeres, szimulált DOM |
| API-adapter | 12/12 sikeres, mock HTTP-válaszok |
| Fejlesztői infrastruktúra | 7/7 sikeres |
| .NET 8 fordítás és xUnit | Sikeres, 30/30 teszt |
| Docker API, beágyazott katalógussal | Sikeres build |
| Valódi MySQL-es API-integráció | Sikeres |
| Korábbi séma frissítése, adatmegőrzés | Sikeres |
| Ismételt indítás, adatmegőrzés | Sikeres |

Az új CI a települések és budapesti kerületek vegyes kiválasztását, a nyitott keresési határokat és a házak telekméretét is vizsgálja. Külön, ideiglenes adatbázison ellenőrzi a korábbi séma frissítését, a felhasználók, entitások, matchek, üzenetek és kreditnapló megőrzését, valamint az ismételt indítást. A három új oszlop eltávolítása kizárólag ebben az eldobható CI-adatbázisban történik; az alkalmazás frissítése csak hiányzó oszlopokat ad hozzá.

## Az első verzió ellenőrzése

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

- Teljes vizuális és akadálymentességi audit: a CI célzott Chromium-folyamattesztjei és az offline DOM-tesztek ezt nem helyettesítik.
- A devcontainer saját képének teljes felépítése: a konfiguráció és az indítószkriptek ellenőrizve, a .NET/MySQL futás a GitHub Actions környezetben igazolt.
- Stripe tesztfizetés, webhookkézbesítés és pénzügyi egyeztetés: saját Stripe-tesztkulcsok és elérhető webhook szükségesek; fizetés nem történt.
- Állandó éles tárhely, mentések és monitoring beállítása külön üzembe helyezési feladat.

A CI-adatbázis a futás végén törlődik. A fejlesztőkörnyezet MySQL-adatai Docker-kötetben maradnak meg. A CI sikere a tesztelt folyamatok működését igazolja; nem állítja, hogy minden éles üzemeltetési feltétel készen áll.
