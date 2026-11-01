# Ingatlan · Otthonra

Magyar nyelvű ingatlanpárosító alkalmazás. Egy felhasználó több ingatlant és több keresési igényt kezelhet, majd egyet aktiválva fedezheti fel a hozzá illő ajánlásokat. A kereső kedvelése ingyenes, az eladó ajánlása 2 kredit. Kölcsönös érdeklődéskor megnyílik az üzenetküldés és láthatóvá válnak az elérhetőségek.

## Fejlesztőkörnyezet a felhőben

A tároló tartalmazza a fejlesztéshez szükséges .NET 8 SDK, Node.js 22 és MySQL 8 környezet konfigurációját a `.devcontainer/` alatt. Devcontainer-kompatibilis felhős környezetben (például GitHub Codespaces) a környezet automatikusan telepít, fordít és indít. A webes felület a továbbított **8080-as porton** érhető el, az API ugyanazon a címen, az `/api` útvonal alatt működik. Telefonon sem kell a távoli API localhost-címét kézzel megadni.

Más felhős fejlesztőkörnyezet előkészítésekor az installlépés: `bash scripts/cloud-setup.sh`; az indítás: `node scripts/dev.mjs --background`. A telepítő a hiányzó .NET 8 SDK-t a projekt saját, Gitből kizárt `.local/` könyvtárába telepíti. A MySQL-t a mellékelt konfiguráció indítja, vagy a `ConnectionStrings__MySql` változóval megadott szervert használja. A szükséges eszköz- és hálózati jogosultságokat a futtatókörnyezetnek biztosítania kell.

Minden push és pull request elindítja a GitHub Actions ellenőrzést: .NET-fordítás, xUnit-tesztek, 31 JavaScript-teszt és valódi MySQL-en végzett API-integrációs teszt. A tesztadatbázis ideiglenes; az alkalmazás fejlesztői adatbázisa Docker-kötetben marad meg.

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
- Település, kerület, típus, ár, alapterület, szobaszám, erkély és lift szerinti megfelelés; a már elbírált párok kizárása.
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
backend/Otthonra.Api/     .NET 8, EF Core és Pomelo MySQL
backend/Otthonra.Tests/   Szerveroldali szabályok egységtesztjei
backend/smoke.mjs         API-integrációs ellenőrzés futó tesztszerverhez
tests/                   Böngészős üzleti tesztek
scripts/setup-local.mjs   Helyi titkok létrehozása értékek kiírása nélkül
docker-compose.yml       MySQL 8 + .NET API + Nginx frontend
```

A frontend nem igényel buildlépést. Helyi statikus kiszolgálás: `python3 -m http.server 8080 --directory dist`. A HTML-t HTTP-n nyisd meg, mert az ES-modulok fájlból való megnyitását a böngészők korlátozzák.

Részletes API-leírás és szerverindítás: [backend/README.md](backend/README.md). Frontend összekötése: [docs/API-INTEGRATION.md](docs/API-INTEGRATION.md). Fizetés: [docs/PAYMENTS.md](docs/PAYMENTS.md).

## Ellenőrzés

```sh
node tests/model.test.mjs
node tests/frontend.test.mjs
node tests/api.test.mjs
dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj
node backend/smoke.mjs http://localhost:5080
```

Az átadási környezetben a JavaScript szintaktikai ellenőrzése és a 9 modellteszt, a 7 offline felületi teszt, a 8 API-adapterteszt és a 7 infrastruktúrateszt sikeres. Az API-adaptert backend-formátumú mock válaszokkal ellenőriztük. A .NET- és MySQL-ellenőrzéseket a tároló CI-folyamata végzi el; a tényleges legutóbbi eredmény a GitHub Actions felületén látható. Stripe-próbafizetéshez saját tesztkulcsok szükségesek. Az aktuális ellenőrzési állapotot a `docs/VALIDATION.md` tartalmazza.

## Élesítés

A Docker-alapbeállítások helyi kipróbálásra valók. Éles környezethez Production mód, HTTPS, saját titkok, pontos CORS-origin és kikapcsolt demóadatok szükségesek. A fizetési kulcsokat kizárólag a backend kapja meg. Az első adatbázist az EF létrehozza; későbbi sémaváltozásokhoz verziózott migráció szükséges. A képek jelenleg HTTPS-hivatkozásokkal adhatók meg. Közvetlen képfeltöltés, e-mail-megerősítés, jelszó-visszaállítás és üzemeltetési megfigyelés nincs ebben az első verzióban.
