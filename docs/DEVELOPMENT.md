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

A `.github/workflows/ci.yml` minden push és pull request esetén külön GitHub Actions futtatóban állítja össze a .NET 8 és MySQL 8 környezetet, fordít, lefuttatja az xUnit-teszteket és a 24 alkalmazási és 7 fejlesztőkörnyezeti JavaScript-tesztet, majd elindított API-val az integrációs smoke-tesztet. A CI-adatbázis és jelszavai egyszer használatos tesztkörnyezethez tartoznak. Személyes vagy éles titok nem szükséges hozzá. A workflow állapotát a repo Actions lapján lehet ellenőrizni; a konfiguráció jelenléte önmagában nem jelenti, hogy a futás már sikeres volt.

## Ha a továbbított 8080-as cím 502-t ad

A Ports listája a konfigurációban megadott továbbításokat is tartalmazza, ezért önmagában nem igazolja a webes kiszolgáló futását. A parancsokat a projekt gyökerében kell futtatni, ahol a `scripts/` és `backend/` könyvtár van; a mellékelt devcontainerben ez `/workspaces/ingatlan`.

```sh
cd /workspaces/ingatlan
node scripts/dev.mjs --background
```

Az indító csak akkor tér vissza sikeresen, amikor a webes főoldal és a proxyn át elért API is 200-as állapotot ad. Ha a supervisor leáll vagy az indulás túllépi az időkeretet, hibát és rövid naplórészletet ír ki. A teljes futási napló `.local/dev.log`; ha ez a fájl a megfelelő projektmappában sem létezik, az automatikus indító nem hozta létre a naplót.

A helyi elérés külön ellenőrizhető:

```sh
curl -I --max-time 5 http://127.0.0.1:8080/
curl --fail --max-time 5 http://127.0.0.1:5080/api/health
tail -n 60 .local/dev.log
```

Ha mindkét helyi végpont működik, de a továbbított cím 502-t ad, a Codespaces továbbítását kell ellenőrizni. A port belső protokollja HTTP, miközben a böngészőben megnyitott külső `app.github.dev` cím HTTPS marad. A devcontainer ezt mindkét portnál explicit beállítja. A meglévő Codespace egyedileg eltárolt protokollját a Ports panelen lehet ellenőrizni. A portot a vizsgálathoz nem kell nyilvánossá tenni.

Az indítás módosításának CI-tesztje ugyanazt a `scripts/dev.mjs --background` parancsot használja, bekapcsolt demóadat-feltöltéssel és valódi MySQL-adatbázissal; ezt követi a webes proxyn keresztüli API-teszt. Ez az indítási láncot ellenőrzi, a felhasználó adott Codespace-ének GitHub-porttovábbítását külön kell megvizsgálni.
