# Ingatlan · Otthonra

Magyar nyelvű ingatlanpárosító alkalmazás. Egy felhasználó több ingatlant és több keresési igényt kezelhet, majd egyet aktiválva fedezheti fel a hozzá illő ajánlásokat. A kereső kedvelése ingyenes, az eladó ajánlása 2 kredit. Kölcsönös érdeklődéskor megnyílik az üzenetküldés és láthatóvá válnak az elérhetőségek.

## Fejlesztőkörnyezet a felhőben

A tároló tartalmazza a fejlesztéshez szükséges .NET 8 SDK, Node.js 22 és MySQL 8 környezet konfigurációját a `.devcontainer/` alatt. Devcontainer-kompatibilis felhős környezetben (például GitHub Codespaces) a környezet automatikusan telepít, fordít és indít. A webes felület a továbbított **3000-es porton** érhető el, az API ugyanazon a címen, az `/api` útvonal alatt működik. Telefonon sem kell a távoli API localhost-címét kézzel megadni.

Más felhős fejlesztőkörnyezet előkészítésekor az installlépés: `bash scripts/cloud-setup.sh`; az indítás: `node scripts/dev.mjs --background`. A telepítő a hiányzó .NET 8 SDK-t a projekt saját, Gitből kizárt `.local/` könyvtárába telepíti. A MySQL-t a mellékelt konfiguráció indítja, vagy a `ConnectionStrings__MySql` változóval megadott szervert használja. A szükséges eszköz- és hálózati jogosultságokat a futtatókörnyezetnek biztosítania kell.

Minden push és pull request elindítja a GitHub Actions ellenőrzést: .NET-fordítás, xUnit-tesztek, 63 JavaScript-teszt és valódi MySQL-en végzett API-integrációs, illetve sémafrissítési teszt. A tesztadatbázis ideiglenes; az alkalmazás fejlesztői adatbázisa Docker-kötetben marad meg.

Fejlesztői újraindítás: `node scripts/dev.mjs --restart`; állapotellenőrzés: `node scripts/dev.mjs --status`. A parancs kiírja a tényleges helyi és Codespaces-címet. A webes felület API-hibánál is elérhető marad, a leálló szolgáltatásokat a felügyelő újraindítja. A Codespace-hez történő visszacsatlakozáskor az indítás automatikusan lefut.

Részletes előkészítés és indítás: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Gyors indítás saját gépen

Szükséges: Docker Compose és Node.js 20+. A projekt gyökerében:

```sh
node scripts/setup-local.mjs
docker compose up --build -d
```

- Felület: **http://localhost:8080**
- API: **http://localhost:5080/api/health**
- A felület **Beállítások → Kapcsolódás a saját szerverhez** részében add meg a `http://localhost:8080` címet (a felülettel azonos címet).
- Példafiókok: `anna@otthonra.local` és `peter@otthonra.local`. Mindkettő jelszava `OtthonraDemo2026!`. Saját fiókot is regisztrálhatsz a kapcsolódási űrlapon.

A webes felület önmagában böngészős demóként is használható. Demómódban a módosítások csak az adott böngészőben tárolódnak, az üzenetek nem jutnak el valódi emberekhez, a kreditfeltöltés nem jár fizetéssel. API-kapcsolat esetén a .NET backend és a MySQL tárolja az adatokat. A demó és a valós API adatai külön maradnak.

## Mi készült el?

- Magyar, mobilméretre is alkalmazkodó felület, ingatlanfotókkal, kattintással, billentyűzettel és húzással kezelhető ajánlókártyákkal.
- Ingatlanok és keresési igények létrehozása, szerkesztése, archiválása, aktív profil kiválasztása.
- Település-kiegészítés eladói és keresői oldalon, 3155 magyar település és Budapest 23 kerülete közös katalógusából. Mentéshez találatot kell választani.
- Egy keresésben több település és budapesti kerület is választható, például Budapest V. kerület, Budapest IX. kerület, Solymár és Pilisvörösvár. Bármely kiválasztott hely megfelelhet; a teljes Budapest választása minden kerületet elfogad.
- A helyszínlista a beviteli mező alatt jelenik meg, és máshová kattintva választás nélkül bezárható. Új keresés mentése után külön visszajelzés és „Ingatlanok felfedezése” gomb segít az aktiválásban.
- Keresésnél a minimumár, a maximum alapterület és a maximum szobaszám elhagyható; az üres mező valóban nyitott korlát. Házhoz telekméret is megadható.
- Hely, típus, ár, alapterület, szobaszám, erkély és lift szerinti megfelelés; a már elbírált párok kizárása.
- JWT-hitelesítés, sózott PBKDF2-jelszótárolás, tulajdonosi jogosultságok, rejtett elérhetőségek.
- Végleges, újraküldés esetén egyszer feldolgozott döntések; tranzakciós kreditlevonás, kreditnapló és kölcsönös párosítás.
- Párosításokhoz kötött kapcsolatfelvétel és üzenetküldés.
- Stripe Checkout integráció szerveroldali csomagárakkal és aláírt, idempotens webhookos kreditjóváírással. A használatához saját Stripe-kulcsok és HTTPS-webhook szükségesek.
- Frontendtől független REST API későbbi mobilkliensekhez.

## Felépítés

```text
dist/                    Önálló webes frontend, natív JavaScript + CSS
  model.js               Böngészős demó és helyi adatmentés
  api.js                 Aszinkron adapter a .NET REST API-hoz
  locations.js           Település- és kerületválasztás, helyegyezés
  data/settlements.json  A frontend és backend közös településkatalógusa
backend/Otthonra.Api/     .NET 8, EF Core és Pomelo MySQL
backend/Otthonra.Tests/   Szerveroldali szabályok egységtesztjei
backend/smoke.mjs         API-integrációs ellenőrzés futó tesztszerverhez
tests/                   Böngészős üzleti tesztek
scripts/setup-local.mjs   Helyi titkok létrehozása értékek kiírása nélkül
docker-compose.yml       MySQL 8 + .NET API + Nginx frontend
```

A frontend nem igényel buildlépést. Helyi statikus kiszolgálás: `python3 -m http.server 8080 --directory dist`. A HTML-t HTTP-n nyisd meg, mert az ES-modulok fájlból való megnyitását a böngészők korlátozzák.

Részletes API-leírás és szerverindítás: [backend/README.md](backend/README.md). Frontend összekötése: [docs/API-INTEGRATION.md](docs/API-INTEGRATION.md). Fizetés: [docs/PAYMENTS.md](docs/PAYMENTS.md).

Az API egy ingatlan helyét `locationId`, egy keresés helyeit `locationIds` azonosítókkal kezeli; az olvasható adatokat a `location`, illetve `locations` mezőben adja vissza. A nyilvános `GET /api/locations?q=Budapest%20V&limit=8` végpont `{items:[...]}` választ ad. A katalógus forrása és frissítése: [docs/LOCATION-DATA.md](docs/LOCATION-DATA.md).

## Ellenőrzés

```sh
node tests/model.test.mjs
node tests/frontend.test.mjs
node tests/api.test.mjs
node tests/locations.test.mjs
node tests/development.test.mjs
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj
node backend/smoke.mjs http://localhost:5080
```

A 63 JavaScript-teszt sikeres: 5 katalógus-, 14 modell-, 12 API-adapter-, 19 offline felületi és 13 infrastruktúrateszt. A GitHub Actionsben a .NET-fordítás, 30 xUnit-teszt, Docker-build és a valódi MySQL-es API-integráció is sikeres. A korábbi séma frissítése és az ismételt újraindítás megőrizte a tesztelt adatokat. Az API-adaptert backend-formátumú mock válaszokkal ellenőriztük; az offline felületi tesztek szimulált DOM-ot használnak. A CI külön valódi Chromium-próbát is futtat asztali, tablet- és mobilméretben a helyszínválasztó és a keresésindítás ellenőrzésére. Stripe-próbafizetéshez saját tesztkulcsok szükségesek. Részletek és futáslink: [docs/VALIDATION.md](docs/VALIDATION.md).

## Meglévő adatok frissítése

A jelenlegi kiadás megőrzi a MySQL-adatokat és a böngészős demó mentett döntéseit, találatait. `Database__Initialize=true` esetén az indulás az EF `EnsureCreated` után lefuttatja a `SchemaUpgrade` additív, ismételhető frissítését (`20261102-locations-and-lot-area`): hozzáadja a helyazonosító- és telekméretmezőket. A meglévő helyadatokat a rendszer az ismert település- és kerületnevekből értelmezi. Frissítéshez indítsd újra az új verziót a meglévő kötettel; az adatbázist és a Docker-kötetet nem kell törölni.

A backend Docker-buildjének kontextusa a tároló gyökere, mert a közös településkatalógust is beágyazza. A Compose ezt már beállítja; közvetlen buildhez a gyökérből használd a `docker build -f backend/Dockerfile .` parancsot.

## Élesítés

A Docker-alapbeállítások helyi kipróbálásra valók. Éles környezethez Production mód, HTTPS, saját titkok, pontos CORS-origin és kikapcsolt demóadatok szükségesek. A fizetési kulcsokat kizárólag a backend kapja meg. Sémafrissítés előtt készüljön adatbázismentés; az aktuális additív frissítéshez az inicializálásnak engedélyezettnek kell lennie, a további változásokhoz is verziózott frissítés szükséges. A képek jelenleg HTTPS-hivatkozásokkal adhatók meg. Közvetlen képfeltöltés, e-mail-megerősítés, jelszó-visszaállítás és üzemeltetési megfigyelés nincs ebben az első verzióban.
