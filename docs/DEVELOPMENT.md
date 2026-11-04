# .NET–MySQL fejlesztőkörnyezet

A tároló tartalmazza a szükséges környezet leírását. Az előkészítésért a `scripts/cloud-setup.sh`, a szolgáltatások indításáért a `scripts/dev.mjs` felel. A környezet újraépítése és az alkalmazás adatainak törlése külön művelet; az indítóparancsok megőrzik az adatbázist és a meglévő `.env` fájlt.

## Előkészített felhős workspace / Codespaces / Dev Containers

A `.devcontainer/devcontainer.json` .NET 8 SDK-t, Node.js 22-t és MySQL 8 szolgáltatást definiál. A MySQL külön konténerben, saját kötetben fut. A workspace-en belül nincs szükség saját Docker daemonra; az API a `mysql` szolgáltatásnévvel kapcsolódik az adatbázishoz. A fejlesztői adatbázis kizárólag a compose belső hálózatán érhető el, nem publikál 3306-os portot.

GitHub Codespaces esetén a repo Code → Codespaces → Create codespace lehetősége ezt a leírást használja, ha a fiókban elérhető és a szolgáltatás használata engedélyezett. A Codespaces külön szolgáltatás: saját keretei és esetleges díjai vannak. A konfiguráció egy Docker-alapú VS Code Dev Containers környezetben is használható.

Az előkészítés automatikusan futtatja:

```sh
bash scripts/cloud-setup.sh
```

Ez helyi fejlesztői titkokat készít elő, letölti a .NET-függőségeket, fordít, majd futtatja az xUnit- és JavaScript-teszteket. A devcontainer minden induláskor és csatlakozáskor háttérben indítja az API-t és a webes kiszolgálót:

```sh
node scripts/dev.mjs --background
```

Napló: `.local/dev.log`. Azonos, már futó szolgáltatást az indító nem hoz létre másodszor. Az alkalmazás a továbbított **3000-es porton** használható. A webes kiszolgáló `/api` útvonalon továbbítja a kéréseket a .NET API-nak, így a telefonon megnyitott felületnek sem kell a telefon saját `localhost` címét használnia. Az API-adapterhez a továbbított webes oldal gyökércímét add meg.

A 5080-as port közvetlen API-vizsgálatra is továbbítható. A fejlesztői portokat tartsd privátként, hacsak nem kifejezetten megosztott tesztkörnyezetet készítesz.

A felhős munkakörnyezet újraindítása nem jelent éles tárhelyet. A fejlesztői MySQL-kötet a környezet életciklusához kötött; fontos adatokhoz külön mentés és éles adatbázis szükséges.

## Natív felhős Linux-környezet

Ha a workspace nem devcontainerben fut, a következő előkészítő parancs a hiányzó .NET 8 SDK-t a repo figyelmen kívül hagyott `.local/dotnet` könyvtárába telepíti, rendszergazdai jog nélkül:

```sh
bash scripts/cloud-setup.sh
node scripts/dev.mjs
```

Node.js 20+ és Linux `flock` (util-linux) szükséges; a mellékelt devcontainer és a CI ezt biztosítja. A szolgáltatásindító a már beállított `ConnectionStrings__MySql` változót használja; ha ilyen nincs, a helyi Docker Compose MySQL-szolgáltatását indítja el. Utóbbihoz Docker-hozzáférés szükséges. A telepítéshez engedélyezett HTTPS-csomagletöltés kell; a script megőrzi a környezet proxy- és TLS-beállításait.

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

A `.github/workflows/ci.yml` minden push és pull request esetén külön GitHub Actions futtatóban állítja össze a .NET 8 és MySQL 8 környezetet, fordít, lefuttatja az xUnit-teszteket és a 63 JavaScript-tesztet, majd elindított API-val az integrációs smoke-tesztet. A CI-adatbázis és jelszavai egyszer használatos tesztkörnyezethez tartoznak. Személyes vagy éles titok nem szükséges hozzá. A workflow állapotát a repo Actions lapján lehet ellenőrizni; a konfiguráció jelenléte önmagában nem jelenti, hogy a futás már sikeres volt.

## Fejlesztői elérés, újraindítás és 502

A fejlesztői kiszolgáló alapértelmezett portja **3000**. A teljes helyi Docker Compose továbbra is a 8080-as portot használja; ezek külön futtatási módok. A fejlesztői `WEB_PORT` felülírását a webszerver, a készenléti ellenőrzés és a kiírt URL egyaránt figyelembe veszi.

Frissítés vagy ágváltás után, a Codespace termináljában:

```sh
cd /workspaces/ingatlan
node scripts/dev.mjs --restart
```

Ez megvárja a régi felügyelő és gyermekfolyamatai leállását, valamint a portok felszabadulását, majd elindítja és ellenőrzi az új verziót. Az operációs rendszer fájlleíróhoz kötött zárolása megakadályozza, hogy két egyidejű automatikus indítás második példányt hozzon létre. A MySQL-kötet és a `.env` megmarad. A `--background` és a kapcsoló nélküli indítás ismételt futtatása a már futó példányt használja. A zárolást a rendszer a parancs kilépésekor vagy megszakadásakor automatikusan elengedi.

A parancs kiírja a kiválasztott portot és a Codespaces környezetváltozóiból képzett böngészőcímet. A korábbi `-8080.app.github.dev` könyvjelző helyett a **-3000.app.github.dev** címet nyisd meg; a saját Codespace nevét tartsd meg. A Ports panelen a 3000-es port protokollja **HTTP**, a kívülről megnyitott cím továbbra is HTTPS. A port maradhat privát. Az új port új böngészős eredetet jelent: az API-hoz ismét be kell jelentkezni. A MySQL-adatok megmaradnak; a kizárólag böngészős demó adatai az eredeti cím helyi tárában maradnak. Meglévő Codespace-ben a port szükség esetén kézzel is hozzáadható a Ports panelen; ehhez nem kell az adatbázist vagy a környezetet törölni.

A `.devcontainer` friss beállításai csak a webes 3000-es portot továbbítják automatikusan. Újraépítés után a postStart és postAttach hook is gondoskodik az indításról. A fejlesztői API közvetlen 5080-as és a régi 8080-as portja automatikusan nem nyílik meg. A Codespace újraépítése nélkül is használható a fenti újraindítás és a 3000-es port kézi továbbítása.

Diagnosztika egy paranccsal:

```sh
node scripts/dev.mjs --status
```

Ez kiírja a felügyelő, a webes health végpont és a weben át elért API állapotát, titkok nélkül. A `/__dev/health` a web saját elérhetőségét jelzi. A statikus felület az API indulásakor vagy kiesésekor is működik; az API-kérés ilyenkor 503 JSON-választ kap. A felügyelő a váratlanul kilépő API-t és webszervert késleltetve újraindítja. A Codespace teljes leállását követően csak annak újraindulásakor és a hookok lefutásával lesz ismét elérhető az alkalmazás.

Ha a helyi web és API 200-as választ ad, de a kiírt külső cím 502-t, a hiba a GitHub porttovábbítási rétegében van. A GitHub a kiválasztott protokollt a Codespace életére megjegyzi, ezért egy régi port egyéni beállítása a repo módosításától nem feltétlenül változik meg. [Hivatalos porttovábbítási útmutató](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace). Az új port nem jelent garanciát a GitHub szolgáltatásának hibamentességére.

Részletes napló: `.local/dev.log`. A készenléti ellenőrzés legfeljebb 120 másodpercet vár a hideg .NET-fordításra. Hiba esetén rövid, érzékeny adatokat szűrő naplórészletet ír ki. A parancs nem állít le idegen folyamatot egy portütközés megszüntetéséhez.

A CI valódi MySQL mellett vizsgálja a párhuzamos indítást, a megvárt leállást, az azonnali újraindítást, az eltérő `WEB_PORT`-ot és a gyermekfolyamatok helyreállítását. A leállítás után nincs mesterséges várakozás a workflow-ban. Ez az alkalmazás indítási láncát bizonyítja; a felhasználó saját GitHub-porttovábbítása külön szolgáltatás.
