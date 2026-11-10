# Ingatlan · Otthonra

Magyar nyelvű ingatlanpárosító alkalmazás. Egy felhasználó több ingatlant és több keresési igényt kezelhet, majd egyet aktiválva fedezheti fel a hozzá illő ajánlásokat. Magánszemélyként a keresői kedvelés ingyenes, ingatlanközvetítőként 1 kredit; az eladói ajánlás mindkét fióktípusnál 2 kredit. Kölcsönös érdeklődéskor megnyílik az üzenetküldés és láthatóvá válnak az elérhetőségek. Ingatlanközvetítőnek mindkét szerepben csak magánszemély ajánlható; magánszemély mindkét fióktípust láthatja.

## Google Cloud tesztkörnyezet

A `scripts/gcp/` telepítői az `ingatlan-513620` projekthez készítenek külön `-dev` szolgáltatásokat: Firebase Hosting webet, Cloud Run API-t külön Google Cloud SQL Auth Proxy konténerrel, valamint Cloud SQL for MySQL-adatbázist. Az első indítás a saját Google Cloud Shellből történik; a telepítő kiírja a Google által biztosított HTTPS-címet. A tesztoldal valódi regisztrációt és szerveres adatmentést használ, ingyenes tesztkreditekkel.

**Az alap tesztadatcsomag 12 felhasználót, 354 ingatlant és 352 keresést tartalmaz**, köztük 3 ingatlanközvetítőt. Minden példafiók közös jelszava: `OtthonraDemo2026!`.

| Fióktípus | E-mail-címek |
|---|---|
| Alap magánszemélyek | `anna@otthonra.local`, `peter@otthonra.local`, `eszter@otthonra.local` |
| Ingatlanközvetítők | `daniel.kozvetito@otthonra.local`, `kata.kozvetito@otthonra.local`, `gabor.kozvetito@otthonra.local` |
| További magánszemélyek | `reka@otthonra.local`, `bence@otthonra.local`, `julia@otthonra.local`, `marton@otthonra.local`, `lilla@otthonra.local`, `balazs@otthonra.local` |

Minden fiókban van aktiválható keresés vagy ingatlan, és minden példafiók 100 ingyenes tesztkredittel indul. A közvetítők aktív kereséssel indulnak: például Dániellel rögtön kipróbálható az 1 kredites keresői kedvelés. Anna, Péter és Eszter eredeti alapmintái mellett sok új, egymáshoz illő magánszemély- és közvetítői ajánlat szerepel. A példafiókok megosztott, kitalált tesztadatokhoz tartoznak. Mind a 19 vármegyében és Budapesten vannak lakások és házak, kisebb garzontól nagy családi házig, eltérő árakkal, méretekkel és szobaszámokkal. A keresések között nyitott korlátú példák is szerepelnek.

A feltöltés a backend indulásának része. Merge után a szokásos **Actions → Deploy Google Cloud test → Run workflow → main** telepítést indítsd: a backendbe beágyazott tesztadatcsomag automatikusan létrejön, külön adatfeltöltő parancs vagy workflow nélkül.

**Minden új teszt Cloud Run-revízió friss tesztállapotot kap:** az alkalmazásadatok törlődnek, majd visszaállnak a fenti példafiókok, ingatlanok, keresések és kezdő kreditek. Ez a tesztelés közben létrehozott saját fiókokat, döntéseket, párosításokat és üzeneteket is törli. Azonos revízió új példányának indulásakor vagy újraindításakor az adatok megmaradnak; egy korábban már feltöltött régi revízió újraindítása sem törli az újabb tesztállapotot.

Az automatikus tesztfeltöltés kizárólag `Deployment__Environment=test` és `Database__SeedTestFixtures=true` mellett fut. A csomag verziója `20261109-test-fixtures-v3`; a teszttelepítő bekapcsolja a megfelelő jelzőt. A szokásos éles környezetben ez a törlés és feltöltés nem fut le.

**A visszatérítések ütemezésének első telepítésekor** a teljes `bash scripts/gcp/run-dev.sh` parancs szükséges a Cloud Shellben, a frissített tároló gyökeréből; ez létrehozza az új tesztütemezőt is. A későbbi kiadások a megszokott Actions workflow-val mennek.

Első telepítés, várható költség, Google-hitelesítés és későbbi GitHub-kiadások: **[docs/GOOGLE-CLOUD-TEST.md](docs/GOOGLE-CLOUD-TEST.md)**. A dokumentáció az előkészített telepítést írja le; az alkalmazás Google Cloudban történő tényleges indulását a helyszíni health-ellenőrzés igazolja. A saját dev aldomain később hozzáadható.

## Fejlesztőkörnyezet a felhőben

A tároló tartalmazza a fejlesztéshez szükséges .NET 8 SDK, Node.js 22 és MySQL 8 környezet konfigurációját a `.devcontainer/` alatt. Devcontainer-kompatibilis felhős környezetben (például GitHub Codespaces) a környezet automatikusan telepít, fordít és indít. A webes felület a továbbított **3000-es porton** érhető el, az API ugyanazon a címen, az `/api` útvonal alatt működik. Telefonon sem kell a távoli API localhost-címét kézzel megadni.

Más felhős fejlesztőkörnyezet előkészítésekor az installlépés: `bash scripts/cloud-setup.sh`; az indítás: `node scripts/dev.mjs --background`. A telepítő a hiányzó .NET 8 SDK-t a projekt saját, Gitből kizárt `.local/` könyvtárába telepíti. A MySQL-t a mellékelt konfiguráció indítja, vagy a `ConnectionStrings__MySql` változóval megadott szervert használja. A szükséges eszköz- és hálózati jogosultságokat a futtatókörnyezetnek biztosítania kell.

Minden push és pull request elindítja a GitHub Actions ellenőrzést: .NET-fordítás, xUnit- és JavaScript-tesztek, böngészős próbák, valamint valódi MySQL-en végzett API-integrációs és sémafrissítési tesztek. A tesztadatbázis ideiglenes; az alkalmazás fejlesztői adatbázisa Docker-kötetben marad meg.

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
- Helyi példafiókok: `anna@otthonra.local` és `peter@otthonra.local`, jelszó: `OtthonraDemo2026!`. Saját fiókot is regisztrálhatsz a kapcsolódási űrlapon. A felhős tesztoldal külön feltöltött példáit a fenti Google Cloud szakasz írja le.

A webes felület önmagában böngészős demóként is használható. Demómódban a módosítások csak az adott böngészőben tárolódnak, az üzenetek nem jutnak el valódi emberekhez, a kreditfeltöltés nem jár fizetéssel. API-kapcsolat esetén a .NET backend és a MySQL tárolja az adatokat. A demó és a valós API adatai külön maradnak.

## Mi készült el?

- Kétlépcsős ajánló: minden feltételt teljesítő találat 100%, a részlegesek eltérésarányos súlyozott pontot kapnak és csak külön hozzájárulás után jelennek meg. A helyszín és típus kizáró feltétel. Keresőként azonos egyezésnél a beérkezett kedvelés és ár-érték arány, eladóként a beérkezett kedvelés, egyezés és keresési specializáltság rendezi az ajánlatokat. [Képletek és súlyok](docs/ARCHITECTURE.md#egyezési-százalék-és-rangsorolási-mutatók).

- Bejelentkezés nélküli, keresési igényekre épülő kezdőoldal néhány eladó ingatlannal. Hozzávetőleges, vármegye szintű IP-alapú ajánlás, helyhozzáférési engedélykérés nélkül; a régió kézzel is kiválasztható. Sikertelen becslésnél országos példák jelennek meg. A keresések és az ingatlanok már az első képernyőn megjelennek, külön eladói és otthonkereső csatlakozási gombbal. Az ajánló változatos típus-, ár-, méret- és helyszínmintát választ, oldalfrissítéskor új összeállítással. Generált címeket és strukturált adatokat közöl, elérhetőséget és pontos címet nem.
- A fizetett, 14 napig megválaszolatlan kedvelés eredeti kreditdíja egyszer visszajár, alkalmazáson belüli értesítéssel és kreditnapló-bejegyzéssel. A határidőn belüli kedvelés vagy elutasítás válasznak számít; későbbi válasz esetén a visszatérítés továbbra is jár. A felhőben óránkénti feldolgozás és belépéskori ellenőrzés kezeli az esedékes jóváírásokat.

- Regisztrációkor magánszemély vagy ingatlanközvetítő fiók választható. Mások ajánlatain a „Magánszemély” vagy „Ingatlanközvetítő” jelölés látszik; a saját ingatlanokon és kereséseken nincs ismételt fióktípusjelzés.
- Közvetítők mind keresőként, mind eladóként csak magánszemélyekkel kapnak ajánlást. A szerver a közvetítő–közvetítő döntést is elutasítja; a korábbi párosítások és beszélgetések megmaradnak.
- „Hirdetés jelentése” mások ajánlatainál: jelentés mások ingatlanainál és kereséseinél. Egy ok választható: „Ingatlanközvetítő” (csak magánhirdetésnél), „Hamis, megtévesztő tartalom”, „Egyéb szabálytalanság” vagy „Már nem aktuális”. A jelentés az adott entitáshoz és okhoz tartozik; az UTC-időbélyeg az adatbázisban marad, a felületen nem jelenik meg.
- Külön „Kedveltek” menüpont az éppen aktív ingatlant vagy keresést kedvelő profiloknak. A lista megtekintése ingyenes, a viszonzásra a szokásos kreditdíj vonatkozik. Látszik a korábbi saját döntés, a párosítás és az is, ha a pár jelenleg nem illeszkedik; elérhetőség továbbra is csak kölcsönös találatnál nyílik meg.
- Magyar, mobilméretre is alkalmazkodó felület, ingatlanfotókkal, kattintással, billentyűzettel és húzással kezelhető ajánlókártyákkal.
- Ingatlanok és keresési igények létrehozása, szerkesztése, archiválása, aktív profil kiválasztása.
- Település-kiegészítés eladói és keresői oldalon, 3155 magyar település és Budapest 23 kerülete közös katalógusából. Mentéshez találatot kell választani.
- Egy keresésben több település és budapesti kerület is választható, például Budapest V. kerület, Budapest IX. kerület, Solymár és Pilisvörösvár. Bármely kiválasztott hely megfelelhet; a teljes Budapest választása minden kerületet elfogad.
- 24 KSH szerinti városkörnyék is kiválasztható a keresésben, például „Budapest és környéke (81 település)” és „Debrecen és környéke (13 település)”. A szám a központot is tartalmazza; a csoportok konkrét településekkel és kerületekkel együtt használhatók. [Források és teljes lista](docs/LOCATION-DATA.md#város-és-környéke-csoportok).
- A helyszínlista a beviteli mező alatt jelenik meg, és máshová kattintva választás nélkül bezárható. Új keresés mentése után külön visszajelzés és „Ingatlanok felfedezése” gomb segít az aktiválásban.
- Keresésnél a minimumár, a maximum alapterület és a maximum szobaszám elhagyható; az üres mező valóban nyitott korlát. Házhoz kötelező telekméretet megadni; emeletet, erkélyt és liftet nem kérünk.
- Opcionális, több értéket elfogadó keresési feltételek: állapot, falazat, épületkor, kilátás, fűtéstípus és emelet; külön választható belmagasság. Az ingatlanon egy érték adható meg, szintén opcionálisan.
- Eladói fő- és kiegészítő fűtés közös legördülő listából, több parkolóhely kijelölése; szigetelés, energetikai besorolás, légkondi, napelem és parkolóhely. Az igen/nem mezők az ismeretlen értéket is megőrzik. Részletes értékek és API-mezők: [Ingatlanparaméterek](docs/PROPERTY-PARAMETERS.md).
- Külön egész- és félszobaszám, az összetétel megőrzésével; a keresési szobaszám az egész + fél / 2 összegre vonatkozik. A számmezőkben a negatív érték bevitele blokkolt.
- Hely, típus, ár, alapterület, szobaszám és a megadott opcionális paraméterek szerinti megfelelés; a már elbírált párok kizárása.
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
node tests/areas.test.mjs
node tests/attributes.test.mjs
node tests/development.test.mjs
node tests/gcp-deployment.test.mjs
node tests/gcp-run-config.test.mjs
node tests/gcp-bootstrap.test.mjs
node tests/gcp-mysql.test.mjs
node tests/gcp-firebase.test.mjs
node tests/gcp-runner.test.mjs
node tests/gcp-push.test.mjs
node tests/gcp-status.test.mjs
node tests/gcp-seed.test.mjs
node tests/demo-data.test.mjs
node scripts/gcp/export-demo-data.mjs --check
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj
node backend/smoke.mjs http://localhost:5080
```

A JavaScript-tesztek a katalógust, a modellt, az API-adaptert, az offline felületet, az indítási életciklust és a Google Cloud-telepítés előkészítését ellenőrzik. A CI .NET-fordítást, xUnit-teszteket, Docker-buildet, valódi MySQL-es API-próbákat és Chromium-teszteket futtat. Az offline felületi tesztek szimulált DOM-ot, az API-adapter tesztjei mock HTTP-válaszokat használnak. A telepítőtesztek nem helyettesítik a felhasználó Google Cloud-projektjének tényleges telepítését és külső elérésének ellenőrzését. Stripe-próbafizetéshez saját tesztkulcsok szükségesek. A korábbi bizonyított eredmények és futáslinkek: [docs/VALIDATION.md](docs/VALIDATION.md); az aktuális commit eredménye a pull request ellenőrzéseinél látható.

## Meglévő adatok frissítése

A normál additív sémafrissítés megőrzi a MySQL-adatokat és a böngészős demó mentett döntéseit, találatait. A felhős teszttelepítés külön, engedélyezett indulási szabálya új Cloud Run-revíziónál az alkalmazásadatokat alaphelyzetbe állítja a fenti tesztadatcsomagra. `Database__Initialize=true` esetén az indulás az EF `EnsureCreated` után lefuttatja a `SchemaUpgrade` additív, ismételhető frissítését (`20261102-locations-and-lot-area`): hozzáadja a helyazonosító- és telekméretmezőket. A meglévő helyadatokat a rendszer az ismert település- és kerületnevekből értelmezi. Frissítéshez indítsd újra az új verziót a meglévő kötettel; az adatbázist és a Docker-kötetet nem kell törölni.

Az opcionális ingatlanparaméterekhez a `20261105-property-attributes` verzió új oszlopokat ad hozzá a meglévő sorok és kapcsolatok megőrzésével. A `20261106-seller-form-details` a szobabontást, kiegészítő fűtést, több parkolóhelyet és keresési fűtésszűrőt adja hozzá. A `20261107-account-types-and-reports` a felhasználói fióktípust és az időbélyegzett `UserReports` táblát vezeti be; a meglévő fiókok magánszemélyként maradnak használhatók. A `20261107-interactions-and-report-reasons` megőrzi a korábbi jelentéseket és időbélyegeiket, és a jelentések egyediségét bejelentő–entitás–ok szerint állítja be. A `20261108-public-landing-and-like-refunds` a visszatérítés egyszeri könyvelését és az olvasható értesítéseket adja hozzá. Ehhez az új backendképet kell telepíteni; a korábbi kép ismételt használata ezt a fejlesztést nem tartalmazza.

A backend Docker-buildjének kontextusa a tároló gyökere, mert a közös településkatalógust is beágyazza. A Compose ezt már beállítja; közvetlen buildhez a gyökérből használd a `docker build -f backend/Dockerfile .` parancsot.

## Élesítés

A Docker-alapbeállítások helyi kipróbálásra valók. Éles környezethez Production mód, HTTPS, saját titkok, pontos CORS-origin és kikapcsolt demóadatok szükségesek. A fizetési kulcsokat kizárólag a backend kapja meg. Sémafrissítés előtt készüljön adatbázismentés; az aktuális additív frissítéshez az inicializálásnak engedélyezettnek kell lennie, a további változásokhoz is verziózott frissítés szükséges. A képek jelenleg HTTPS-hivatkozásokkal adhatók meg. Közvetlen képfeltöltés, e-mail-megerősítés, jelszó-visszaállítás és üzemeltetési megfigyelés nincs ebben az első verzióban.
