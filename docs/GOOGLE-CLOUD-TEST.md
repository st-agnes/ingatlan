# Google Cloud tesztkörnyezet

A telepítés az `ingatlan-513620` projekten belül hoz létre egy tesztkörnyezetet, `-dev` nevű szolgáltatásokkal. A webet Firebase Hosting, a .NET API-t és a külön Google Cloud SQL Auth Proxy konténert Cloud Run, az adatokat külön Cloud SQL for MySQL-példány szolgálja ki. A web és az API ugyanazon HTTPS-címen érhető el; az `/api` kéréseket a Hosting továbbítja a backendnek.

Az előkészített kód és a CI-ellenőrzés önmagában nem jelenti, hogy az alkalmazás már fut a Google Cloudban. Az első telepítést a projekt tulajdonosa a saját Google Cloud Shelljében végzi el. Ehhez a beszélgetésben nem kell Google-jelszót, hozzáférési tokent vagy szolgáltatásfiók-kulcsot megadni.

## Első indítás Cloud Shellből

Nyisd meg a [Google Cloud Shellt](https://console.cloud.google.com/cloudshell), és használd azt a Google-fiókot, amely az `ingatlan-513620` projektet kezeli. A projekthez aktív számlázási fiók szükséges. Egy számlázási fiók több projekthez is kapcsolódhat; a telepítő ellenőrzi a kiválasztott projekt állapotát és számlázását.

A következő blokk új `ingatlan-cloud-test` könyvtárba tölti le a telepítési ágat:

```sh
git clone --branch codex/google-cloud-test https://github.com/st-agnes/ingatlan.git ingatlan-cloud-test
cd ingatlan-cloud-test
bash scripts/gcp/bootstrap-dev.sh --project ingatlan-513620 --plan
```

A `--plan` csak projektadatokat és számlázási állapotot olvas, majd kiírja a létrehozandó erőforrásokat. A kiválasztott régió `europe-west1` (Belgium).

Az infrastruktúra és az alkalmazás létrehozása:

```sh
bash scripts/gcp/run-dev.sh
```

A futtató két rövid lépést ír ki, és a teljes kimenetet a privát, ignorált `.local/gcp/deployment.log` fájlba menti. Hiba esetén az utolsó sorokban a megállás helye, az aktuális hiba és a napló megnyitásának parancsa látható. Az előző futás naplója `deployment.log.previous` néven megmarad. Siker esetén a végén a megnyitható HTTPS-cím szerepel.

A Cloud Shellnek `gcloud`, Python 3, curl, Git, Docker és Node.js 22/npm eszközökre van szüksége. A Cloud SQL tulajdonosi címkéihez a dokumentált `gcloud beta sql instances create` parancsot használjuk; a stabil változat a `--labels` kapcsolót nem fogadja el. [Google-dokumentáció](https://docs.cloud.google.com/sql/docs/mysql/label-instance). A telepítő a Firebase CLI rögzített verzióját az ignorált `.local/gcp/tools` könyvtárba telepíti. A .NET SDK-t az API Docker-buildje biztosítja.

A bootstrap a Cloud Shell aktuális Google-bejelentkezését használja. Az alkalmazás telepítője Application Default Credentials (ADC) hitelesítést igényel. Ha a telepítő ADC-hiányt jelez, a Cloud Shellben futtasd:

```sh
gcloud auth application-default login
bash scripts/gcp/deploy-dev.sh
```

A böngészős Google-bejelentkezést a saját fiókoddal végezd el. A hozzáférési tokent és a létrejövő hitelesítő fájlt ne másold a tárolóba vagy a chatbe.

A bootstrap több percig is futhat, amíg az adatbázis elkészül. A végén még csak egy Cloud Run-helyőrző szolgáltatás létezik. A `deploy-dev.sh` fordítja és feltölti a tényleges alkalmazást, ellenőrzi az API/adatbázis kapcsolatát, feltölti a webet, majd kiírja a tesztcímet. A cím alakja:

```text
https://otthonra-dev-PROJECTNUMBER.web.app/
```

A `PROJECTNUMBER` értékét a telepítő a Google-tól olvassa ki; a cím kiírt, tényleges változatát nyisd meg. Az első indításhoz nem szükséges saját domain vagy DNS-módosítás. A `dev.sajatdomain.hu` később a teszt Hosting-site-hoz kapcsolható a Firebase konzolban, az ott megadott DNS-rekordokkal.

## Frissítés az automatikus kreditvisszatérítéshez

Az óránkénti ellenőrzés új Cloud Scheduler-erőforrást és külön kérési szolgáltatásfiókot használ. **Meglévő telepítésnél a módosítás merge-elése után egyszer a teljes előkészítést és telepítést futtasd**, ne csak a GitHub Actions alkalmazástelepítését:

```sh
cd ~/ingatlan-cloud-test
git switch main
git pull --ff-only
bash scripts/gcp/run-dev.sh --project ingatlan-513620
```

A teljes futás létrehozza az `otthonra-refunds-dev` Scheduler-feladatot és az azonos nevű szolgáltatásfiókot. A nem titkos `GCP_DEV_CONFIG` formátuma nem változik; a következő kiadások ismét indíthatók a **Deploy Google Cloud test** workflow-val. Az új tesztrevízió a korábban engedélyezett módon újratölti a tesztadatokat.

A feladat UTC szerint minden óra 17. percében meghívja a Cloud Run stabil címének `/internal/refunds/run` végpontját. Ez nulla futó példány esetén is elindítja a backendet; nem egy folyamatosan futó példány időzítőjére támaszkodik. A 14 nap leteltével a jóváírás a következő sikeres ellenőrzéskor történik, így rendes működés mellett legfeljebb körülbelül egy óra késés lehet. A backend a felhasználó adatainak lekérésekor és futás közben is feldolgozza az esedékes visszatérítéseket. Egy kedvelés díját egyszer írja jóvá, a tranzakcióban rögzített értesítéssel együtt.

A Scheduler Google által kiadott, rövid életű OIDC-tokent küld. Az audience a stabil Cloud Run-alapcím, a kérési identitás `otthonra-refunds-dev@PROJECTID.iam.gserviceaccount.com`; a backend az aláírás, lejárat és audience mellett ezt az ellenőrzött email-címet is megköveteli. A normál alkalmazás-bejelentkezés nem jogosít a belső végpont használatára. A kérés közvetlenül a Run szolgáltatásra megy, nem a Hosting átirányításán keresztül. Nem készül statikus token vagy letölthető szolgáltatásfiók-kulcs.

Egy próbálkozás határideje 180 másodperc; hiba esetén legfeljebb három újrapróbálkozás engedélyezett, 15–120 másodperces visszalépéssel és legfeljebb 30 perces újrapróbálási ablakkal. A feladat állapota és futási naplója a [Cloud Scheduler konzolban](https://console.cloud.google.com/cloudscheduler?project=ingatlan-513620) látható. A kézzel szüneteltetett feladatot a bootstrap nem indítja újra észrevétlenül: ilyen állapotnál megáll, és ellenőrzést kér. Szándékos szüneteltetés után a konzolban folytatható.

## Állapot és napló tabletről

A tároló könyvtárában futtatva néhány sorban, módosítás nélkül ellenőrizhető a telepítés:

```sh
node scripts/gcp/status-dev.mjs
```

A sikerhez a Cloud Run API-nak és a Hostingen át elért API-nak is el kell érnie a MySQL-t, tesztkörnyezetet és engedélyezett tesztkrediteket kell jeleznie. A Hosting futásidejű konfigurációjának valódi API-módot kell kérnie. A Cloud Run-helyőrzőt vagy a böngészős demót az ellenőrző nem tekinti kész alkalmazásnak. Hiányzó manifest esetén az előkészítés még nem fejeződött be.

Ha a korábbi futás Google-help szöveggel állt meg, frissítés és újrapróbálás ugyanabban a Cloud Shell-másolatban:

```sh
git pull --ff-only
bash scripts/gcp/run-dev.sh
```

A már létrejött, saját jelölésű erőforrásokat és titkokat az előkészítő tovább használja. Nem szükséges új adatbázist vagy Cloud Shell-másolatot létrehozni. A részletes napló az editorban olvasható, terminálgörgetés nélkül:

```sh
cloudshell edit .local/gcp/deployment.log
```

## MySQL-hitelesítési hiba javítása

Ha a Cloud Run indulási próbája meghiúsul, és az alkalmazásnapló `caching_sha2_password` hibát, RSA-kulcsot vagy `GetRsaPublicKeyAsync` közben keletkező `Access denied ... cloudsqlproxy` hibát említ, frissítsd a telepítési ágat, és egyszer futtasd a teljes előkészítést is:

```sh
git pull --ff-only
bash scripts/gcp/run-dev.sh
```

Ebben az esetben a `--deploy-only` helyett a teljes futtató szükséges, mert a Secret Managerben tárolt kapcsolati beállítást is frissíteni kell. Az előkészítő ellenőrzi a titok tulajdonosi címkéit és a teljes ismert régi formátumot, majd a meglévő MySQL-jelszó megtartásával új titokverziót ad hozzá. A JWT-kulcs, az SQL-felhasználó és az adatok megmaradnak. A már frissített titok ismételt futtatáskor nem kap új verziót. A telepítő új Cloud Run-revíziót kér akkor is, ha a Docker-kép tartalma változatlan, így az új példány a friss beállítást olvassa.

Az új kapcsolat rögzítetten `127.0.0.1:3306` TCP-címre mutat, ahol a Cloud Run szolgáltatáson belül a Google Cloud SQL Auth Proxy **2.26.3** konténere figyel. Az API megvárja a proxy indulási próbáját, majd saját, adatbázist ellenőrző próbával indul. A proxy a validált `PROJECT:europe-west1:otthonra-mysql-dev` példányhoz kapcsolódik a meglévő futtatási szolgáltatásfiókkal, IAM-ellenőrzéssel és távoli TLS-titkosítással. Az adatbázis `ENCRYPTED_ONLY` beállítása megmarad. Más TCP-címre, portra, felhasználóra vagy adatbázisra mutató titkot a migráció elutasít.

Ez a [Cloud SQL Proxy #2317-ben](https://github.com/GoogleCloudPlatform/cloud-sql-proxy/issues/2317) dokumentált Unix/SHA-2 hitelesítési problémát a TCP-útvonal használatával kerüli el. A korábbi Unix-beállítás RSA-kapcsolójának módosítása önmagában nem volt elegendő. A meglévő két Unix-formátum mindegyike közvetlenül a fenti TCP-beállításra frissül. A telepítő megtartja a Firebase korábbi revíziócímkéit is.

A CI friss SHA-2 felhasználóval a MySqlConnector TCP-hitelesítését, valamint a rögzített proxykép elérhetőségét és kapcsolóit ellenőrzi. Ez nem helyettesíti a Google-projekt tényleges IAM- és proxykapcsolatának ellenőrzését, amelyet a telepítés egészségpróbái végeznek el.

## Megszakadt Docker-feltöltés folytatása

Ha az előkészítés sikeresen mentette a manifestet, de a `docker push` hálózati hibával leállt, elegendő csak az alkalmazás telepítését folytatni:

```sh
git pull --ff-only
bash scripts/gcp/run-dev.sh --deploy-only
```

A `--deploy-only` a validált `.local/gcp/dev-config.json` projektjét használja; a `--project` kapcsolóval nem kombinálható. A meglévő infrastruktúra és titkok ilyenkor nem kerülnek újra előkészítésre. A Docker build felhasználhatja a korábban elkészült rétegeket. A feltöltő az egyértelmű kapcsolódási hibákat legfeljebb háromszor próbálja, próbánként 180 másodperces időkorláttal. Jogosultsági és tanúsítványhibánál megáll. A teljes napló továbbra is a `.local/gcp/deployment.log`, a rövid hiba pedig a terminál végén szerepel.

A `connect: connection refused` a hálózati kapcsolat létrejötte előtt történik; a naplóban korábban megjelenő regisztrált credential helper figyelmeztetés önmagában nem ezt jelenti. Rövid, hitelesítést nem küldő elérhetőségi próba a Cloud Shellből:

```sh
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 10 --max-time 15 https://europe-west1-docker.pkg.dev/v2/
```

A `401` a registry szokásos válasza hitelesítés nélkül, tehát a végpont ekkor elérhető volt. A `000` kapcsolódási hibát jelez. A shell és a Docker daemon hálózati útvonala eltérhet, és a DNS is több címet adhat; ez a próba önmagában nem bizonyítja, hogy a következő Docker-feltöltés sikerülni fog.

### Már feltöltött kép használata

Tartós Docker-hálózati hiba esetén egy **korábban sikeresen feltöltött**, teljes digesttel azonosított API-kép is megadható:

```sh
bash scripts/gcp/run-dev.sh --deploy-only --image REGISTRY_IMAGE@sha256:DIGEST
```

Ekkor a Docker-fordítás, a helyi Docker-feltöltés és annak hitelesítési beállítása kimarad. A telepítő csak a manifest saját teszttárolójába tartozó digestet fogad el; a képet a Cloud Run tölti le. Az aktuális telepítési kód szerinti proxy, a legújabb titokverzió és a jelenlegi frontend továbbra is települ, majd az API/adatbázis/Hosting ellenőrzés lefut. A privát napló és a végső működésellenőrzés megmarad.

A régebbi kép használata előtt ellenőrizni kell, hogy az a kívánt backendverziót tartalmazza. Pusztán telepítési beállítás javításakor azonos backendkód újra felhasználható; módosított backendhez új kép szükséges. A telepítő nem választ automatikusan régi képet. A `--image` a futtatóban csak `--deploy-only` mellett használható: a szükséges titokmigrációnak már előtte le kell futnia. Ez a lehetőség a Cloud Shell Docker-feltöltését kerüli meg; a hálózati elutasítás okát nem változtatja meg.

## Firebase API-hibák

A közvetlen Firebase REST-kérések az `X-Goog-User-Project` fejlécben a kiválasztott projektet használják kvótaprojektként, a Google [felhasználói tokenekre vonatkozó útmutatója](https://docs.cloud.google.com/sdk/gcloud/reference/auth/print-access-token) szerint. Ehhez a bejelentkezett fióknak `serviceusage.services.use` jogosultság szükséges ezen a projekten. A Firebase CLI külön folyamatában a `GOOGLE_CLOUD_QUOTA_PROJECT` szintén a validált célprojektet jelöli; ez nem írja át a Cloud Shell globális beállításait.

403 esetén a telepítő kiírja a pontos műveletet, a Google státuszát, rövid hibaüzenetét és az elérhető strukturált indokot (`reason`, `service`, `consumer`, `permission`). A teljes API-választ, tokent és alkalmazáskonfigurációt nem írja ki. A futtató ezeket a rövid diagnosztikai sorokat a terminál végén is megjeleníti.

A `SERVICE_DISABLED` az adott fogyasztóprojektben engedélyezendő API-t, a `USER_PROJECT_DENIED` a kvótaprojekt használati jogosultságát jelzi. A hibakód önmagában nem dönti el az okot. Ha a Google kifejezetten `Firebase Tos Not Accepted` hibát jelez, a saját Google-fiókoddal nyisd meg a [Firebase feltételeinek ellenőrzését](https://console.firebase.google.com/?forceCheckTos=true), és végezd el az ott kért elfogadást. A telepítő nem fogad el jogi feltételeket helyetted, és nem ad új jogosultságokat egy 403-as válasz alapján.

## Firebase: „Failed to replace Run service”

Ha az API/adatbázis ellenőrzése már sikeres, a fájlok feltöltődnek, de a Hosting „finalizing version” lépése `Failed to replace Run service` hibát ad, frissítsd a telepítési ágat. A korábbi beállítás külön `/api` és `/api/**` szabállyal ugyanazt a szolgáltatást kétszer kötötte a Hosting verziójához. A Firebase CLI 14.17.0 [minden ilyen szabályhoz külön, párhuzamos Cloud Run-módosítást indít](https://github.com/firebase/firebase-tools/blob/v14.17.0/src/hosting/runTags.ts), így ezek ütközhetnek. Az új beállítás egyetlen `^/api(/.*)?$` regexszabályt használ, továbbra is `pinTag: true` értékkel; lefedi az `/api` és az alatta lévő útvonalakat is.

```sh
git pull --ff-only
bash scripts/gcp/run-dev.sh --deploy-only
```

Ha a helyi Docker-feltöltés korábban hálózati hibát adott, a fenti parancsnak add át a már ellenőrzött, feltöltött backendkép `--image` paraméterét is az előző szakasz szerint. A módosítás frontend-telepítési beállítás: azonos backendhez nem szükséges új képet feltölteni. Az npm `warn` üzenetei nem bizonyítják a Cloud Run-módosítás elutasításának okát. Más jogosultsági vagy API-hiba ugyanezt az általános Firebase-üzenetet is okozhatja; ismétlődés esetén a Firebase részletes naplójában szereplő Google HTTP-státusz és hibaüzenet alapján kell folytatni.

## Használat és ellenőrzés

A telepítés az új Cloud Run API-t a Hosting módosítása előtt ellenőrzi. A Firebase közzétételének befejezése után a webes ellenőrzés legfeljebb 12 alkalommal, 5 másodperces várakozással kérdezi le újra az oldalt, a runtime-konfigurációt és az API állapotát. Minden kérés külön URL-paramétert kap, és tiltja a gyorsítótárazást. Átmenetileg még korábbi Hosting-útvonal válaszolhat; siker csak az aktuális beágyazott tesztadat-verzióval lehetséges. Tartós eltérésnél a napló kiírja a hibás útvonalat és feltételt, verzióeltérésnél a kapott és az elvárt verziót is. A 401/403 válasz azonnal megállítja az ellenőrzést. A „release complete” után kapott ellenőrzési hiba nem vonja vissza automatikusan a már közzétett kiadást.

A backendbe beágyazott `20261110-test-fixtures-v4` tesztadatcsomag **14 felhasználót, 355 ingatlant és 353 keresést** hoz létre. Ebből 3 fiók ingatlanközvetítő, 11 magánszemély. A megosztott példafiókok közös jelszava **`OtthonraDemo2026!`**.

| Fiók | Fióktípus | E-mail-cím |
|---|---|---|
| Kovács Anna | Magánszemély | `anna@otthonra.local` |
| Nagy Péter | Magánszemély | `peter@otthonra.local` |
| Szabó Eszter | Magánszemély | `eszter@otthonra.local` |
| Varga Dániel | Ingatlanközvetítő | `daniel.kozvetito@otthonra.local` |
| Kiss Kata | Ingatlanközvetítő | `kata.kozvetito@otthonra.local` |
| Farkas Gábor | Ingatlanközvetítő | `gabor.kozvetito@otthonra.local` |
| Tóth Réka | Magánszemély | `reka@otthonra.local` |
| Németh Bence | Magánszemély | `bence@otthonra.local` |
| Molnár Júlia | Magánszemély | `julia@otthonra.local` |
| Varga Márton | Magánszemély | `marton@otthonra.local` |
| Szabó Lilla | Magánszemély | `lilla@otthonra.local` |
| Kiss Balázs | Magánszemély | `balazs@otthonra.local` |
| Teszt Anna | Visszajelzés-próba kereső | `visszajelzes-kereso@otthonra.local` |
| Teszt Péter | Visszajelzés-próba eladó | `visszajelzes-elado@otthonra.local` |

A kibővített készlet kilenc felhasználójának egyenként 12 eladó ingatlanja és 12 keresési igénye van. A közvetítők aktív kereséssel és 100 ingyenes tesztkredittel indulnak, így azonnal próbálható az 1 kredites kedvelés. A magánszemély keresői kedvelése ingyenes, az eladói kedvelés mindkét fióktípusnál 2 kredit. A közvetítői jelzés másik fiókból látható, a jelentéshez pedig bármelyik másik magánszemély mintaprofil használható.

A készlet II./XIII. kerületi, debreceni és hajdúsámsoni lakásokat, solymári és pilisvörösvári házakat, fűtési és parkolási opciókat, egész/fél szobákat, valamint városkörnyéki és több településes kereséseket tartalmaz. Anna, Péter és Eszter eredeti alapmintái is a csomag részei; a hozzájuk illő sok új ajánlatot a további felhasználók biztosítják. Anna és Péter eredeti mintapárjának kölcsönös kedvelésével továbbra is kipróbálható az elérhetőségek feloldása és az üzenetküldés.

A regionális bővítés Budapesthez és mind a 19 vármegyéhez 12 új ingatlant és 12 hozzá illő keresést ad: hat lakást és hat házat, több településsel, eltérő árakkal, méretekkel és egész/fél szobaszámokkal. A keresési korlátok változatosak, köztük elhagyott minimumár, maximum alapterület és maximum szobaszám is szerepel. A landing oldal ezért az egyes vármegyéken belül is többféle élethelyzetből tud válogatni. A bejelentkezési adatok és az eredeti mintapárok változatlanok.

### Automatikus alaphelyzetbe állítás telepítéskor

A normál **Deploy Google Cloud test** workflow telepíti az új API-képet és a webet. A backend az indulásakor, az alkalmazás kiszolgálása előtt tölti fel a beágyazott adatokat; a telepítés után nincs külön API-s feltöltő lépés. Merge után elég **Actions → Deploy Google Cloud test → Run workflow**, a `main` ágon. Külön adatfeltöltő workflow-t vagy parancsot nem kell indítani.

A teszttelepítés `Database__SeedTestFixtures=true` beállítást kap. Ez kizárólag `Deployment__Environment=test` környezetben engedélyezi az automatikus tesztadat-kezelést; a szokásos éles környezetben nem töröl és nem tölt fel adatokat. A szerver ASP.NET környezete a teszttelepítésben is lehet `Production`: a tesztjogosultságot a külön `Deployment__Environment=test` beállítás jelenti.

Minden új Cloud Run-revízió (`K_REVISION`) első indulása alaphelyzetbe állítja a teszt alkalmazásadatait, majd létrehozza a 14 felhasználót, a 355 ingatlant, a 353 keresést, a kezdő krediteket és az aktív profilokat. Az előző tesztállapot összes felhasználója — a kézzel regisztrált fiókok is —, saját hirdetése, keresése, döntése, párosítása, üzenete, jelentése és kreditmozgása törlődik. Így az új telepítés után a korábban végighúzott minták helyett újra végigpróbálható alapállapot fogad.

Az adatbáziszár és a revíziók feltöltési előzménye gondoskodik arról, hogy több párhuzamosan induló példány is csak egyszer hajtsa végre ezt egy új revízióhoz. Az azonos revízió hidegindítása vagy újraindítása nem állítja vissza a tesztelés közbeni módosításokat. Egy korábban már feltöltött régi revízió újraindulása sem törli az újabb revízióval létrejött adatokat. A séma és a feltöltési előzmények megmaradnak; a folyamat az alkalmazás tesztadatait kezeli.

A beágyazott csomag forrása a `scripts/gcp/demo-data.mjs`; a verziózott JSON a `backend/Otthonra.Api/Data/test-fixtures.json` fájlban van. Katalógusmódosításkor a tároló gyökerében generáld újra és ellenőrizd:

```sh
node scripts/gcp/export-demo-data.mjs
node scripts/gcp/export-demo-data.mjs --check
```

A CI a generált fájl és a katalógus egyezését is ellenőrzi. A verzió és a revíziókezelés szerveroldali; a normál teszttelepítésnek nincs szüksége a példafiókokkal végzett külső bejelentkezésekre.

### Külön API-s feltöltő fejlesztői használatra

A `seed-dev.mjs` megmarad opcionális, külön eszközként az azonosított működő tesztoldalhoz. Ez nem része a normál telepítésnek. Például egy futó revízión belül új, elnevezett adatcsomag adható hozzá:

```sh
node scripts/gcp/seed-dev.mjs --batch proba-2 --config /abszolut/utvonal/dev-config.json
```

Ez az eszköz a teszt API ellenőrzése és hitelesítés után dolgozik, nyugtával kerüli a duplikációt, és megőrzi a revízión belüli korábbi adatokat. A hitelesítési korlát miatt legfeljebb 10 belépési/regisztrációs kérést küld 61 másodperces ablakonként, látható várakozással. Az így hozzáadott adatok is törlődnek a következő új teszt Cloud Run-revízió indulásakor.

A megosztott példafiókok kitalált tesztadatokhoz tartoznak. Saját fiókot az **„Új fiókot hozok létre”** gombbal, névvel, e-mail-címmel és legalább 10 karakteres jelszóval is regisztrálhatsz; a sikeres regisztráció azonnal beléptet. Az ilyen saját fiók nulla kredittel indul; a **Krediteim** oldalon ingyenesen adhatsz hozzá tesztkreditet.

A Google Cloudra feltöltött frontend bejelentkezés előtt nyilvános, elsősorban keresési igényeket bemutató ajánlót jelenít meg. A hozzávetőleges régió IP-alapú becsléssel választható ki, helyhozzáférési engedélykérés nélkül; a régió kézzel is módosítható, sikertelen becslésnél országos példák jelennek meg. Az ajánlóban nincsenek elérhetőségek vagy pontos címek. A használathoz bejelentkezés vagy regisztráció szükséges; a fiókok, ingatlanok, keresések, párosítások és üzenetek a valódi tesztadatbázisba kerülnek. Az új fiók első lépésként saját keresést vagy ingatlant hozhat létre, majd aktiválhatja azt.

A felület „Tesztkörnyezet” jelölést mutat. A kreditek ingyenes tesztkreditek: a feltöltés nem indít bankkártyás fizetést. A jogosultságot a backend kizárólag a saját konfigurációjából engedélyezi: `ASPNETCORE_ENVIRONMENT=Production`, `Deployment__Environment=test`, `Credits__EnableDemoTopup=true`. Teszttelepítésben az éles Stripe-kulcsot a szerver elutasítja.

A `deploy-dev.sh` csak akkor írja ki, hogy a tesztalkalmazás kész, ha a saját API és a Hostingen át elért API is a tesztkörnyezetet azonosítja és az adatbázist eléri. A böngészős helyi demó továbbra is külön használható a fejlesztői környezetben; a feltöltött tesztoldal szerverhiba esetén hibát jelez, és megtartja az élő API-módot.

Az alaptelepítés külön tesztadatbázist használ, amelyben a backend indulási lépése hozza létre a fenti példákat. A Codespaces adatait nem importálja automatikusan. Meglévő adatok átviteléhez külön export/import szükséges.

## Mit hoz létre, és mennyibe kerül?

| Erőforrás | Tesztbeállítás |
|---|---|
| Cloud Run | `otthonra-api-dev`, 0 minimum / 2 maximum példány; API és SQL proxy konténer, egyenként 1 CPU / 512 MiB |
| Cloud SQL | `otthonra-mysql-dev`, MySQL 8.4 Enterprise, `db-f1-micro`, egy zóna |
| Adattárhely | Kezdetben 10 GiB SSD, automatikus növekedés legfeljebb 20 GiB-ig |
| Adatbázis | `otthonra_dev`, standard automatikus mentésekkel |
| Hosting | `otthonra-dev-PROJECTNUMBER`, Google által kezelt HTTPS |
| Artifact Registry | `otthonra-dev`, a backend konténerképei |
| Titkok | `otthonra-mysql-dev` és `otthonra-jwt-dev` a Secret Managerben |
| Futtatási identitás | `otthonra-runtime-dev` szolgáltatásfiók |
| Visszatérítések időzítése | `otthonra-refunds-dev` Cloud Scheduler-feladat, óránként, külön OIDC-kérési identitással |
| GitHub-telepítési identitás | `otthonra-deploy-dev` és az `otthonra-dev` Workload Identity pool |

A kis SQL-példány folyamatosan számlázott, tervezett alapköltsége hozzávetőleg **nettó 10–15 USD/hó**. A tényleges díj függ a régiós ártól, tárhelytől és a tárolt mentésektől. A Cloud Run, Hosting, Cloud Scheduler, konténerképek és naplók használata további díjat jelenthet. Az óránkénti ellenőrzés kis API- és adatbázisforgalmat okoz akkor is, ha nincs látogató. A Cloud Run-példány két konténere összesen 2 CPU / 1 GiB erőforrást kap; a proxy nem igényel új, folyamatosan futó SQL-példányt vagy virtuális gépet. A példányszám- és tárhelykorlát nem teljes számlázási költségplafon. A telepítő nem hoz létre költségvetési riasztást; ilyet a Cloud Billing felületén lehet beállítani.

A bootstrap kizárólag a teszt nevű erőforrásokkal dolgozik. Az ismételt futás a saját tulajdonosi jelölésű erőforrásokat használja tovább, és megőrzi a generált jelszavakat. Eltérő tulajdonosi jelölés vagy váratlan konfiguráció esetén hibával megáll. A Cloud SQL törlésvédett; az adatok és a számlázott erőforrások nem tűnnek el a Cloud Shell bezárásakor.

## Későbbi telepítés GitHub Actionsből

Az első Cloud Shelles telepítés a GitHub-változók beállítása és a PR merge-elése előtt is elvégezhető. A telepítési ág a korábbi felületi javításokat is tartalmazza.

A bootstrap az ignorált `.local/gcp/dev-config.json` fájlba menti a **nem titkos** projekt-, erőforrás- és identitásazonosítókat. Ez a fájl nem tartalmaz adatbázis-jelszót vagy JWT-kulcsot. A későbbi GitHub-kiadásokhoz ennek tartalma legyen a `st-agnes/ingatlan` tároló **`GCP_DEV_CONFIG` nevű repository variable** értéke, a Settings → Secrets and variables → Actions → Variables részen.

Ha a Cloud Shellben a GitHub CLI már telepítve és a saját GitHub-fiókoddal hitelesítve van, a változó másolgatás nélkül is beállítható:

```sh
gh variable set GCP_DEV_CONFIG --repo st-agnes/ingatlan < .local/gcp/dev-config.json
```

A workflow neve **Deploy Google Cloud test**, fájlja `.github/workflows/deploy-dev.yml`. Csak kézzel indítható, és csak a `main` vagy `codex/google-cloud-test` ág kijelölt commitját telepíti. Előfeltétele, hogy ugyanarra a commitra sikeres push-alapú `ci.yml` futás tartozzon. A workflow a GitHub Actions felületén a default ágba kerülés után jelenik meg.

A GitHub rövid életű OIDC-hitelesítéssel, Workload Identity Federationön keresztül kap telepítési hozzáférést; nem készül letölthető szolgáltatásfiók-JSON-kulcs. Az identitás feltételei a tároló és tulajdonos állandó GitHub-azonosítójára, a workflow fájljára és az engedélyezett ágakra korlátoznak. A backend képe digest alapján rögzített, a Hosting API-átirányítása a hozzá tartozó Cloud Run-revízióhoz kötött.

A Firebase Hosting telepítőjének jogosultsága jelenleg projektszintű. Új éles Hosting-site bevezetése előtt ezt a hozzáférést újra kell tervezni. Ugyanebben a projektben később létrehozható éles környezet, de az a jelen telepítésnek nem része.

## Frissítés és hibaelhárítás

Ugyanabban a Cloud Shell-másolatban egy későbbi tesztverzió feltöltése:

```sh
cd ingatlan-cloud-test
git pull --ff-only
bash scripts/gcp/deploy-dev.sh
```

Az infrastruktúra bootstrapjét akkor kell ismét futtatni, ha az előkészítés korábban félbeszakadt vagy a konfigurációját tudatosan frissítjük. A telepítők minden Google-parancsban a megadott projektet és a teszt-erőforrásokat választják ki.

| Jelenség | Következő lépés |
|---|---|
| `Cannot find service [otthonra-api-dev]` miatt megáll az előkészítés | Frissítsd a telepítési ágat (`git pull --ff-only`), majd futtasd újra a `run-dev.sh`-t. A javított telepítő az első indításkor létrehozza a hiányzó szolgáltatást; a meglévő SQL-t és titkokat tovább használja. |
| Nincs aktív számlázás | A Cloud Billingben kapcsold az `ingatlan-513620` projektet egy aktív számlázási fiókhoz, majd futtasd újra a bootstrapet. |
| Hiányzó Google-jogosultság | A Cloud Shellben a projektet kezelő Google-fiókot használd. A bootstrapnek API-engedélyezési, infrastruktúra- és IAM-kezelési jogosultságokra van szüksége. |
| ADC-hitelesítés hiánya | Futtasd a `gcloud auth application-default login` parancsot, majd a deployt. |
| API- vagy adatbázis-health hiba | A Cloud Run `otthonra-api-dev` szolgáltatás naplóit nézd meg. A telepítő ilyenkor a frontend feltöltése előtt megáll. |
| GitHub nem talál sikeres CI-t | Várd meg a kiválasztott commit teljes CI-futását; ellenőrizd, hogy push-futás és az engedélyezett ág szerepel. |
| Az oldal saját domainen nem érhető el | Először a telepítő által kiírt `web.app` címet ellenőrizd, majd a Firebase-ben megadott domain- és DNS-állapotot. |

Az éles üzemhez szükséges megerősített fiókkezelés, fizetési ellenőrzés és üzemeltetési eljárások külön feladatok. A tesztkörnyezet telepítése ezek elkészültét nem állítja.

### Egyszerű, ismételhető visszajelzés-próba

A két külön fiók ugyanazt a `OtthonraDemo2026!` jelszót használja. A kereső fiókban az újraindító gomb után az első ingatlan elutasítása rögtön felhozza a nyolcgombos kérdést. Az eladó fiókban a Statisztikák és visszajelzések oldal mutatja a beküldött választ; onnan is újraindítható a próba. A 10 válaszos csomag valódi tesztkredit-könyveléssel készül: 100 kezdő kreditből 10 levonás, 90 maradék. A visszautasított választ a rendes végpont kezeli, a normál felhasználók ritkítása változatlan.

Az újraindító útvonal kizárólag explicit teszttelepítésnél és beágyazott tesztfeltöltésnél létezik. Csak a két kijelölt fiók használhatja; normál éles környezetben a végpont hiányzik, akkor is, ha a feltöltési jelző véletlenül be van kapcsolva. Az újraindítás a próba saját csomagját/párját és hozzájuk tartozó könyvelését kezeli, mások számláit és eseményeit megőrzi.
