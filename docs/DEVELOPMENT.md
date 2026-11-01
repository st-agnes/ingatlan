# .NET–MySQL fejlesztőkörnyezet

A tároló tartalmazza a szükséges környezet leírását. Az előkészítésért a `scripts/cloud-setup.sh`, a szolgáltatások indításáért a `scripts/dev.mjs` felel. A környezet újraépítése és az alkalmazás adatainak törlése külön művelet; az indítóparancsok megőrzik az adatbázist és a meglévő `.env` fájlt.

## Előkészített felhős workspace / Codespaces / Dev Containers

A `.devcontainer/devcontainer.json` .NET 8 SDK-t, Node.js 22-t és MySQL 8 szolgáltatást definiál. A MySQL külön konténerben, saját kötetben fut. A workspace-en belül nincs szükség saját Docker daemonra; az API a `mysql` szolgáltatásnévvel kapcsolódik az adatbázishoz. A fejlesztői adatbázis kizárólag a compose belső hálózatán érhető el, nem publikál 3306-os portot.

GitHub Codespaces esetén a repo Code → Codespaces → Create codespace lehetősége ezt a leírást használja, ha a fiókban elérhető és a szolgáltatás használata engedélyezett. A Codespaces külön szolgáltatás: saját keretei és esetleges díjai vannak. A konfiguráció egy Docker-alapú VS Code Dev Containers környezetben is használható.

Az előkészítés automatikusan futtatja:

```sh
bash scripts/cloud-setup.sh
```

Ez helyi fejlesztői titkokat készít elő, letölti a .NET-függőségeket, fordít, majd futtatja az xUnit- és JavaScript-teszteket. A devcontainer minden induláskor háttérben indítja az API-t és a webes kiszolgálót:

```sh
node scripts/dev.mjs --background
```

Napló: `.local/dev.log`. Azonos, már futó szolgáltatást az indító nem hoz létre másodszor. Az alkalmazás a továbbított **8080-as porton** használható. A webes kiszolgáló `/api` útvonalon továbbítja a kéréseket a .NET API-nak, így a telefonon megnyitott felületnek sem kell a telefon saját `localhost` címét használnia. Az API-adapterhez a továbbított webes oldal gyökércímét add meg.

A 5080-as port közvetlen API-vizsgálatra is továbbítható. A fejlesztői portokat tartsd privátként, hacsak nem kifejezetten megosztott tesztkörnyezetet készítesz.

A felhős munkakörnyezet újraindítása nem jelent éles tárhelyet. A fejlesztői MySQL-kötet a környezet életciklusához kötött; fontos adatokhoz külön mentés és éles adatbázis szükséges.

## Natív felhős Linux-környezet

Ha a workspace nem devcontainerben fut, a következő előkészítő parancs a hiányzó .NET 8 SDK-t a repo figyelmen kívül hagyott `.local/dotnet` könyvtárába telepíti, rendszergazdai jog nélkül:

```sh
bash scripts/cloud-setup.sh
node scripts/dev.mjs
```

Node.js 20+ szükséges. A szolgáltatásindító a már beállított `ConnectionStrings__MySql` változót használja; ha ilyen nincs, a helyi Docker Compose MySQL-szolgáltatását indítja el. Utóbbihoz Docker-hozzáférés szükséges. A telepítéshez engedélyezett HTTPS-csomagletöltés kell; a script megőrzi a környezet proxy- és TLS-beállításait.

A környezetben az SDK és a MySQL indításához szükséges hozzáférés előkészítése után a scriptek ugyanúgy futnak, mint helyi gépen. A konfigurációs fájlok önmagukban nem változtatják meg egy szolgáltató sandboxengedélyeit.

## Helyi gép, teljes Docker Compose

Csak Node.js és Docker Compose szükséges, a .NET SDK-t a Dockerfile biztosítja a fordításhoz:

```sh
node scripts/setup-local.mjs
docker compose up --build -d
```

Felület: `http://localhost:8080`; a `/api` ugyanazon a címen működik. Közvetlen API: `http://localhost:5080/api/health`. MySQL: csak a helyi gépről elérhető `127.0.0.1:3306`. A titkokat az indító a `.env` fájlban tárolja, és nem írja ki az értékeiket. A `.env` nem része a Git-tárolónak.

## Ellenőrzések és leállítás

```sh
# Teljes előkészítés és egységtesztek
bash scripts/cloud-setup.sh

# API-integráció valódi futó MySQL és Development API mellett
node backend/smoke.mjs http://localhost:5080

# Hátterezett fejlesztői szolgáltatások leállítása Linuxon
node scripts/dev.mjs --stop

# Teljes Docker Compose leállítása, az adatok megőrzésével
docker compose down
```

A smoke-teszt új, véletlen nevű tesztfiókokkal fut. Ellenőrzi a jogosultságokat, a párosítás előtti kontaktzárat, az egyidejű ismételt döntés egyszeri kreditlevonását, a kölcsönös találatot és az üzenetküldést. Éles adatbázison ne futtasd.

A `.github/workflows/ci.yml` minden push és pull request esetén külön GitHub Actions futtatóban állítja össze a .NET 8 és MySQL 8 környezetet, fordít, lefuttatja az xUnit-teszteket és a 24 alkalmazási és 3 fejlesztőkörnyezeti JavaScript-tesztet, majd elindított API-val az integrációs smoke-tesztet. A CI-adatbázis és jelszavai egyszer használatos tesztkörnyezethez tartoznak. Személyes vagy éles titok nem szükséges hozzá. A workflow állapotát a repo Actions lapján lehet ellenőrizni; a konfiguráció jelenléte önmagában nem jelenti, hogy a futás már sikeres volt.
