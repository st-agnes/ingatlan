# Otthonra API · .NET 8 + MySQL 8

Önálló, JWT-hitelesített REST API webes és későbbi mobilkliensekhez. Az árak a teljes HUF-összeget tartalmazzák (79 900 000, nem 79,9). A felhasználó-, ingatlan-, keresés- és párosításazonosítók UUID-k; a helyazonosítók külön, stabil szöveges kulcsok. Az időbélyegek UTC-ben értendők. A frontend API-adaptere a `/api` végpontokhoz csatlakozik.

## Helyi indítás Dockerrel

A projekt gyökerében másold a `.env.example` fájlt `.env` néven, és állíts be egyedi adatbázis-jelszavakat és legalább 32 karakteres véletlen JWT-kulcsot. Ezután:

```sh
docker compose up --build -d
```

Felület: `http://localhost:8080`; API: `http://localhost:5080/api`; állapot: `/api/health`. A felület Beállítások → API-kapcsolat részén add meg a felülettel azonos `http://localhost:8080` címet, és jelentkezz be. A bejelentkezés másik gépen vagy telefonon csak elérhető, HTTPS-sel védett API-címmel működik.

A Development-környezet első üres adatbázisába három példafiók kerül. Jelszavuk: `OtthonraDemo2026!`. Kereső: `anna@otthonra.local`, eladó: `peter@otthonra.local`, harmadik tesztelő: `eszter@otthonra.local`. Péter ingatlanát már ajánlotta Annának; Anna kedvelése kölcsönös párosítást hoz létre. Az adatbázis a `mysql_data` kötetben marad; egy újraindítás nem állítja vissza.

A backend Docker-buildjének kontextusa a tároló gyökere, így a közös `dist/data/settlements.json` is bekerül a buildbe. A Compose ezt beállítja. Önálló build a gyökérből: `docker build -f backend/Dockerfile .`.

Natív futtatás SDK-val és meglévő MySQL-adatbázissal:

```sh
ASPNETCORE_ENVIRONMENT=Development \
ConnectionStrings__MySql='Server=localhost;Database=otthonra;User=otthonra;Password=YOUR_PASSWORD' \
dotnet run --project backend/Otthonra.Api --urls http://localhost:5080
```

## API

A publikus `POST /auth/register` body: `{name,email,password,phone,accountType}`; `POST /auth/login`: `{email,password}`. Az `accountType` értéke `private` vagy `agent`; elhagyva/null esetén a régi kliensekhez `private`. Ismeretlen vagy üres megadott érték HTTP 400. A típus regisztrációkor rögzül, a profilmódosítás nem írja át. A jelszó 10–128 karakter. Válasz: `{accessToken,expiresIn,user}`. A token 12 órás. A `GET /locations` és az állapotjelző is publikus; a fiókhoz kötött végpontoknál `Authorization: Bearer ...` szükséges. Az alábbi útvonalak `/api` relatívak.

| Művelet | Végpont | Adat / eredmény |
|---|---|---|
| Helykiegészítés | `GET /locations?q=Deb&limit=8` | `{items:[{id,label,city,district}]}`; hitelesítés nélkül |
| Nyilvános kezdőoldal | `GET /public/landing?region=HU110` | Hitelesítés nélkül: `{regions,region,scope,searches,properties}`; régió nélkül országos ajánló |
| Profil | `GET`, `PUT /me` | `{id,name,email,phone,accountType,credits,activeKind,activeEntityId,createdAt}`; módosítás: `{name,email,phone}` |
| Saját entitások | `GET /me/entities` | `{properties,searchRequests,reportedOwnerIds,reportedEntities:[{entityKind,entityId,reason}],active:{kind,id}}` |
| Aktiválás | `PUT /me/active` | `{kind:"property"|"search",id}` |
| Ingatlanok | `GET`, `POST /properties`, `PUT`, `DELETE /properties/{id}` | Saját ingatlanok; a törlés archivál |
| Keresések | `GET`, `POST /searches`, `PUT`, `DELETE /searches/{id}` | Saját keresési igények; a törlés archivál |
| Ajánlások | `GET /feed` | `{items:[{property,searchRequest,propertyId,searchRequestId,compatibilityScore,reasons,likedYou}],sellerLikeCost:2,likeCost}` |
| Beérkező kedvelések | `GET /incoming-likes?offset=0&limit=50` | `{active,items,total,offset,limit,hasMore,likeCost}`; az aktív saját entitás kedvelői |
| Jelentés | `POST /reports` | `{entityKind:"property"|"search",entityId,reason}` → `{id,reported:true,reportedOwnerId,alreadyReported}`; első jelentés 201, ismétlés 200 |
| Döntés | `POST /decisions` | `{propertyId,searchRequestId,liked}` → `{matchId,charged,credits}` |
| Párosítások | `GET /matches` | `[{id,createdAt,property,searchRequest,contact:{id,name,email,phone,accountType},messages,unread}]` |
| Üzenet | `POST /matches/{id}/messages` | `{text}` → `{id,matchId,senderId,text,createdAt}` |
| Értesítések | `GET /notifications?offset=0&limit=50` | `{items,total,unreadCount,offset,limit,hasMore}`; csak a saját értesítések |
| Olvasott értesítés | `PUT /notifications/{id}/read` | A saját értesítés; ismétlés megőrzi az első `readAt` értékét |
| Kreditnapló | `GET /credits/ledger` | `[{id,amount,description,createdAt}]` |
| Demófeltöltés | `POST /credits/demo-topup` | `{amount:20|50|100|250}`; kizárólag Development + engedélyező kapcsoló esetén |

Ingatlanmezők: `title,locationId,city,district,neighborhood,address,description,type,price,area,rooms,wholeRooms,halfRooms,lotArea,floor,condition,building,balcony,elevator,images,archived`. Keresésmezők: `title,locationIds,city,districts,description,type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms,balcony,elevator,moveIn,financing,archived`. A `lotArea` házhoz kötelező pozitív telekméret m²-ben, egyébként `null`. Ház mentésekor az emelet, erkély és lift adatai törlődnek. A külön tárolt egész/fél szobákból számolt `rooms` összeg a keresési határok alapja; a korábbi, csak `rooms` mezőt használó kliensek működnek.

Az opcionális állapot-, falazat-, épületkor-, kilátás-, belmagasság- és emeletszűrő, valamint az eladói műszaki adatok pontos mezői, értékei és törlési szabályai: [PROPERTY-PARAMETERS.md](../docs/PROPERTY-PARAMETERS.md). A mezőn belüli több kijelölés VAGY, a mezők közötti kapcsolat ÉS; megadott feltételt ismeretlen eladói adat nem teljesít.

Az új kliensek az ingatlanhoz egy `locationId`, a kereséshez legalább egy elemet tartalmazó `locationIds` tömb értéket küldjenek a katalógusból. Példák: `city:Debrecen`, `city:Hajdúsámson`, `district:Budapest:5`. Ismeretlen azonosító nem menthető. A válaszokban a `location`, illetve `locations` a teljes `{id,label,city,district}` objektumot tartalmazza; a városi hely `district` értéke `null`, a kerületi például `V.`. A régi `city,district,districts` mezők kompatibilitási célból megmaradnak; az explicit kanonikus azonosító az irányadó. Régi kliens esetén csak a katalógusból felismerhető helynév fogadható el.

A keresés `locationIds` listájában `area:<központ>` csoport is választható, például `area:Budapest`. Ez egyetlen választásként marad meg, és minden tagtelepülés ingatlanját lefedi; a budapesti csoport minden kerületre érvényes. A válaszban a csoport `kind: "area"` és `settlementCount` adatot is kap. A `GET /locations?kind=search` alapértelmezésben csoportokat is javasol, a `kind=property` kizárólag pontos várost/kerületet ad. Ingatlanhoz csoport nem menthető. Katalógus, forrás és darabszámok: [LOCATION-DATA.md](../docs/LOCATION-DATA.md#város-és-környéke-csoportok).

A keresés helyei között VAGY kapcsolat van: `['district:Budapest:5','district:Budapest:9','city:Solymár','city:Pilisvörösvár']` bármelyike megfelelhet. A `city:Budapest` a város összes kerületét elfogadja; egy konkrét kerület csak önmagát. A többi keresési feltételnek is teljesülnie kell. A közös, hálózati szolgáltatás nélkül használható katalógus forrása: [LOCATION-DATA.md](../docs/LOCATION-DATA.md).

A min/max korlátok `null` értéke nyitott határt jelent. A `minPrice`, `maxArea`, `maxRooms` elhagyható; a kliens az üres mezőket `null` értékként küldi, és visszaolvasáskor is megőrzi. A `balcony/elevator=true` kötelező feltétel, a false nem zárja ki az adott tulajdonságot. Az ingatlantípus egyezését is ellenőrzi a rendszer. A keresőoldali kedvelés magánszemélynek ingyenes, közvetítőnek 1 kredit. Az eladói kedvelés mindkét fióktípusnak 2 kredit; az elutasítás ingyenes. A levonást a szerveren tárolt felhasználói típus szabja meg. Saját entitások egymással nem párosíthatók. Két `agent` fiók egymás hirdetését vagy keresését egyik szerepben sem kapja az ajánlások között; a szerver a közvetlen `POST /decisions` kérést is HTTP 400-zal utasítja el, levonás és új döntés nélkül. Az ellenőrzés a tulajdonosok szerveren tárolt fióktípusából történik.

A döntések egy adott ingatlan–keresés párra és oldalra véglegesek. Engedélyezett fiókpárnál az újraküldött azonos döntés idempotens és 0 további kreditet von le; ellentétes újraküldés 409. A döntés, a kreditlevonás, a napló és a kölcsönös párosítás egyetlen MySQL-tranzakcióban történik, sorzárolással és adatbázis egyediségi korlátokkal. Az elutasított és már kedvelt párok nem kerülnek vissza az ajánlásokba. Az aktiválás jogosultságot nem ad más felhasználó adatainak módosításához.

## Fióktípus és jelentések

A publikus ingatlan- és keresésválaszok `ownerAccountType` mezője a tulajdonos tényleges fióktípusából készül, nem a kliens által küldött hirdetésadatból. Felfedezéskor a másik fél típusa „Magánszemély” vagy „Ingatlanközvetítő” jelölést kap. Saját entitásokon a felület elhagyja az ismételt típusjelzést; a teljes profil típusa a beállításokban továbbra is látható. Egy típusjelzés sem oldja fel az elérhetőségek zárolását. A közvetítő–közvetítő kizárás az ajánlásokra, az új döntésekre és a beérkező kedvelések listájára is érvényes; a korábbi párosításokat és beszélgetéseket nem törli.

Hitelesített felhasználó bármely másik fiók létező, nem archivált ingatlanánál vagy keresésénél jelenthet szabálytalanságot. A cél tulajdonosát a szerver keresi ki; saját entitás nem jelenthető. A `POST /reports` `reason` mezőjének értékei:

| Kód | Felületi szöveg | Jelenthető tulajdonos |
|---|---|---|
| `suspected_agent` | A hirdető ingatlanközvetítő | Csak `private` |
| `misleading_content` | Hamis, megtévesztő tartalom | `private` vagy `agent` |
| `duplicate_listing` | Duplikált hirdetés | `private` vagy `agent` |
| `other_violation` | Egyéb szabálytalanság | `private` vagy `agent` |
| `no_longer_current` | A hirdetés már nem aktuális | `private` vagy `agent` |

A régi kliensek elhagyott vagy `null` oka `suspected_agent`; a megadott üres vagy ismeretlen kód hibás kérés (HTTP 400). Az „Ingatlanközvetítő” ok eleve közvetítő tulajdonosnál szintén 400. A három általános ok akkor is használható másik közvetítő korábbi hirdetésénél, ha az új ajánlások között a közvetítő–közvetítő szabály miatt nem jelenhet meg.

A `UserReports` tárolja a bejelentőt, a jelentett fiókot, a forrásentitást, a választott okot és az UTC `CreatedAt` időbélyeget. A `(ReporterId,EntityKind,EntityId,Reason)` egyediség miatt azonos forrás és ok ismételt/párhuzamos jelentése ugyanazt a nyugtát adja (elsőként 201, ismétléskor 200). Másik hirdetés vagy másik ok külön jelentés. A gomb további ok jelzésére is elérhető marad.

A jelentés válasza és a felület nem tartalmaz jelentési időbélyeget. A `/me/entities` `reportedEntities` mezője kizárólag az aktuális bejelentő saját `{entityKind,entityId,reason}` összefoglalóit adja vissza. A `reportedOwnerIds` kompatibilitási mező marad; abból nem szabad másik hirdetést vagy okot letiltani. Más bejelentők és nyilvános jelentésszám nem érhető el. A jelentés nem módosít automatikusan fióktípust, kreditet vagy láthatóságot.

## Beérkező kedvelések

A `GET /incoming-likes?offset=0&limit=50` mindig a hitelesített felhasználó aktuálisan aktív, saját ingatlanját vagy keresését kedvelő másik oldali döntéseket listázza. Nem fogad másik tulajdonoshoz tartozó entitásazonosítót a lista céljaként. Aktív profil hiányában üres lapot ad; saját, archivált és közvetítő–közvetítő ellenfelek nem kerülnek bele. Az `offset` tartománya 0–1 000 000, a `limit` tartománya 1–100; hibás lapozási érték HTTP 400. A rendezés a beérkezés időpontja, majd a döntésazonosító szerint csökkenő.

A válasz `{active:{kind,id}|null,items,total,offset,limit,hasMore,likeCost}`. Az `items` az ajánlások publikus páradatait tartalmazza, kiegészítve `likedAt`, `myDecision:null|"liked"|"passed"`, `matchId` és `compatible` mezőkkel. A már viszonzott vagy elutasított kedvelés is megmarad a listán. Ha időközben módosultak a feltételek, `compatible:false` jelzi az eltérést; ilyen új párosítás nem kezdeményezhető. Meglévő találat beszélgetése továbbra is elérhető.

A „Kedveltek” menüpont minden fióktípusnak ingyenesen böngészhető, lapozható, és aktív profilváltáskor az új profil listájára vált. A megnyitás nem hoz létre döntést vagy párosítást. Viszonzáskor a meglévő `/decisions` útvonal, tulajdonosi ellenőrzés és 0/1/2 kredites díjazás érvényes. A listában nincs telefonszám, e-mail-cím vagy pontos cím; kapcsolatot csak a kölcsönös találat `/matches` válasza ad.

## Adatvédelem és élesítés

A feed és a publikus kártyák nem tartalmaznak felhasználói elérhetőséget vagy pontos utca/házszámot. A párosítási végpont csak a saját párosításokat adja vissza, és csak ott oldja fel a kapcsolatot. A jelszavak véletlen sóval, 210 000 iterációs PBKDF2-SHA256-tal tárolódnak. A publikus leírásban az e-mail-címet és szokásos magyar telefonszámformátumokat a rendszer elutasítja; képek tartalmának moderálása külön integráció.

Éles környezetben `ASPNETCORE_ENVIRONMENT=Production`, egyedi titkok, HTTPS reverse proxy és pontos CORS-origin szükséges. Kapcsold ki a demóseedet és a demófeltöltést; a feltöltési végpont Production módban akkor sem kerül regisztrálásra, ha a kapcsoló true. A Docker-alapértékek helyi fejlesztéshez készültek. A titkok nem kerülnek a frontendbe.

## Meglévő adatbázis frissítése

`Database__Initialize=true` esetén az indulás először `EnsureCreated` hívást végez az új adatbázishoz, majd a `SchemaUpgrade.ApplyAsync` fut le a meglévő adatbázison is. A `20261102-locations-and-lot-area` verzió additívan létrehozza a `Properties.LocationId`, `Properties.LotArea` és `SearchRequests.LocationIdsJson` oszlopokat, és a verziót a `__OtthonraSchemaVersions` táblában rögzíti. A lépések ismételhetők, az adatbázis-zár összehangolja a párhuzamos indításokat. Meglévő felhasználót, hirdetést, keresést, döntést, párosítást vagy kreditet nem töröl.

A `20261107-account-types-and-reports` a `Users.AccountType` oszlopot (`private` alapértékkel) és a `UserReports` táblát hozza létre additívan. A korábbi fiókok, kreditek és kapcsolatok megmaradnak; az új jelentéstábla a meglévő `EnsureCreated` adatbázishoz is létrejön. A `20261107-interactions-and-report-reasons` ugyanazon sémazár alatt az új bejelentő–entitás–ok egyedi indexre cseréli a korábbi bejelentő–fiók indexet. A meglévő jelentések azonosítói, `suspected_agent` okai és időbélyegei megmaradnak; az ismételt indulás nem írja át őket.

A `20261106-seller-form-details` szintén additívan adja hozzá a `WholeRooms`, `HalfRooms`, `SecondaryHeatingType`, `ParkingTypesJson` és `HeatingTypesJson` oszlopokat. A fűtésválasztások közösek az eladói és keresési oldalon; a keresés csak a fő fűtést szűri. A parkolóhely többértékű, a régi szöveges mező kompatibilis marad. Részletek: [Ingatlanparaméterek](../docs/PROPERTY-PARAMETERS.md).

A `20261105-property-attributes` verzió ugyanazzal a zárral és ismételhető módon adja hozzá az opcionális attribútumoszlopokat; a korábbi kereséseken üres listák jelentenek korlátozás nélküli feltételeket, a három eladói logikai mezőn a `NULL` ismeretlent jelent.

A meglévő sorokban a `LocationId` alapértéke üres szöveg, a `LotArea` és a `LocationIdsJson` értéke `NULL`. A régi helymezőket olvasáskor a közös katalógus alapján értelmezi a rendszer, ezért előzetes adatsor-átírás nem szükséges. Az új verziót a meglévő `mysql_data` kötettel kell újraindítani; kötet- vagy adatbázistörlés nem szükséges. Éles frissítés előtt készüljön mentés. Ha az inicializálás ki van kapcsolva, a telepítés részeként engedélyezni kell a frissítéshez, megfelelő sémamódosítási adatbázis-jogosultsággal. A további sémaváltozásokhoz is verziózott, adatmegőrző frissítés szükséges.

A bankkártyás vásárláshoz Stripe Checkout és aláírt, idempotens webhook-integráció készült, külön PaymentOrders nyilvántartással. Beállítás és ellenőrzés: [PAYMENTS.md](../docs/PAYMENTS.md). Saját Stripe-kulcsok és elérhető webhook szükségesek; valódi fizetést az átadási környezetben nem indítottunk. Fejlesztésben külön demókredit-feltöltés is elérhető. E-mail-hitelesítés, jelszó-visszaállítás, képfeltöltés/tárolás, képek moderálása és üzemi monitoring további integráció.

## Ellenőrzések

`dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj` futtatja a szűrés és adatvédelmi szabályok egységtesztjeit. A `backend/smoke.mjs` három saját tesztfiókkal ellenőrzi a regisztrációt, kompatibilitást, idegen jogosultságot, párosítás előtti kontaktzárat, eladói levonás egyszeriségét, párosítást és üzenetküldést egy futó Development API-n:

```sh
node backend/smoke.mjs http://localhost:5080
```

A korábbi .NET-, JavaScript-, Docker- és MySQL-ellenőrzések bizonyítékai: [VALIDATION.md](../docs/VALIDATION.md). A CI az új funkciók mellett a régi sémájú adatbázis frissítését, az adatok megőrzését és az ismételt indulást is sikeresen ellenőrizte. A smoke tesztek kizárólag tesztadatbázison futtathatók; éles rendszeren ne futtasd őket. A MySQL-hálózati és párhuzamossági ellenőrzéshez futó MySQL szükséges.

Az opcionális paraméterek tényleges API/MySQL körútját a `backend/attributes-smoke.mjs` ellenőrzi; újraindítás után a `--verify` kapcsolóval ellenőrzi az értékek megőrzését. A CI ezt és a desktop/tablet/mobil mezőkezelést is futtatja.

Az eladói mezők valódi API/MySQL ellenőrzése: `node backend/seller-form-smoke.mjs http://127.0.0.1:3000`, újraindítás után ugyanez `--verify` kapcsolóval. Kizárólag eldobható helyi/CI adatbázison futtatandó; a szkript új tesztfiókokat és adatokat hoz létre.

## Nyilvános ajánló és kredit-visszatérítés

A `GET /api/public/landing` legfeljebb 8 keresést és 4 eladó ingatlant emel ki. A `region` opcionális, a válasz 20 elemű `regions` katalógusának NUTS3 azonosítója (például `HU110` Budapest, `HU321` Hajdú-Bihar); ismeretlen kód 400. Régióban nem elérhető kínálatnál üres lista jön vissza, más térség adatai nem kapnak helyi címkét. A nyilvános előnézet kizárólag generált címeket, katalógusbeli helyeket, számos feltételeket és fióktípust tartalmaz; a hirdetés eredeti szabad szövegei, képei, forrásazonosítói, tulajdonosa, címe és elérhetőségei kimaradnak. A rövid szerveres gyorsítótár a jelölteket tárolja legfeljebb egy percig; a változatos, véletlenszerű válogatás minden lekéréskor újra elkészül. A típus, árkategória, méret, szobaszám és helyszín alapján eltérő példákat részesít előnyben, és elegendő jelölt esetén a következő válaszban a tagság is változik, nem csak a sorrend.

A frontend engedélykérés nélküli, hozzávetőleges becslése a [GeoJS](https://www.geojs.io/docs/v1/endpoints/geo/) szolgáltatástól kizárólag az országot és a vármegyét használja; az IP-címet és koordinátákat nem menti és nem továbbítja az API-nak. A látogató IP-címe a szolgáltató számára a kérés miatt ismert; [adatkezelés](https://www.geojs.io/privacy/). Három másodperc után vagy ismeretlen hely esetén országos ajánló marad. A kézi régióválasztás felülírja a becslést.

A visszatérítési határidő a szerver UTC `CreatedAt` értéke + 14×24 óra. Csak a `Liked=true`, `Charged>0` kedvelések díja jár vissza, ha a másik oldal a határidőig sem kedveléssel, sem elutasítással nem válaszolt. A későbbi reakció nem szünteti meg a már esedékes visszatérítést; egy későbbi kedvelés párosítást is létrehozhat. A döntés végleges marad, és az eredeti terhelés a naplóban megmarad. A `CreditEntries.RefundedDecisionId` külön egyediségi kulcs, a `Decision.RefundedAt` és egy `UserNotifications` sor egyetlen tranzakcióban készül a pozitív jóváírással.

Az értesítés alakja `{id,kind:'like_refund',amount,text,decisionId,createdAt,readAt}`. A más felhasználóhoz tartozó értesítés olvasása 404; ismételt olvasás megőrzi az első időpontot. A `/me` az `unreadNotificationCount` mezőt is adja. A kreditnapló `kind` és `refundedDecisionId` adata megkülönbözteti a visszatérítést az eredeti terheléstől.

A felhasználói olvasások és az időszakos feldolgozó mellett Cloud Scheduler óránként hívja a `/internal/refunds/run` végpontot. Ez külön Google OIDC-hitelesítést, pontos audience-t és a beállított, ellenőrzött szolgáltatásfiókot követel; alkalmazás-felhasználói token nem jogosít rá. Hiányzó `Scheduler__Audience` vagy `Scheduler__ServiceAccountEmail` esetén a végpont nincs regisztrálva. A telepítő a meglévő, nullára skálázható teszt API-hoz hozza létre az ütemezést. Részletek: [teszttelepítés](../docs/GOOGLE-CLOUD-TEST.md).

A `20261108-public-landing-and-like-refunds` additív sémafrissítés hozza létre az értesítéseket és a visszatérítési oszlopokat/indexeket. A normál frissítés meglévő alkalmazásadatot nem töröl; a külön engedélyezett teszt-revízió-visszaállítás az értesítéseket is törli.
