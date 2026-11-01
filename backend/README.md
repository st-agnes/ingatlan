# Otthonra API · .NET 8 + MySQL 8

Önálló, JWT-hitelesített REST API webes és későbbi mobilkliensekhez. Az árak a teljes HUF-összeget tartalmazzák (79 900 000, nem 79,9). Az azonosítók UUID-k; az időbélyegek UTC-ben értendők. A frontend API-adaptere a `/api` végpontokhoz csatlakozik.

## Helyi indítás Dockerrel

A projekt gyökerében másold a `.env.example` fájlt `.env` néven, és állíts be egyedi adatbázis-jelszavakat és legalább 32 karakteres véletlen JWT-kulcsot. Ezután:

```sh
docker compose up --build -d
```

Felület: `http://localhost:8080`; API: `http://localhost:5080/api`; állapot: `/api/health`. A felület Beállítások → API-kapcsolat részén add meg a `http://localhost:5080` címet, és jelentkezz be. A bejelentkezés másik gépen vagy telefonon csak elérhető, HTTPS-sel védett API-címmel működik.

A Development-környezet első üres adatbázisába három példafiók kerül. Jelszavuk: `OtthonraDemo2026!`. Kereső: `anna@otthonra.local`, eladó: `peter@otthonra.local`, harmadik tesztelő: `eszter@otthonra.local`. Péter ingatlanát már ajánlotta Annának; Anna kedvelése kölcsönös párosítást hoz létre. Az adatbázis a `mysql_data` kötetben marad; egy újraindítás nem állítja vissza.

Natív futtatás SDK-val és meglévő MySQL-adatbázissal:

```sh
ASPNETCORE_ENVIRONMENT=Development \
ConnectionStrings__MySql='Server=localhost;Database=otthonra;User=otthonra;Password=YOUR_PASSWORD' \
dotnet run --project backend/Otthonra.Api --urls http://localhost:5080
```

## API

A publikus `POST /auth/register` body: `{name,email,password,phone}`; `POST /auth/login`: `{email,password}`. A jelszó 10–128 karakter. Válasz: `{accessToken,expiresIn,user}`. A token 12 órás; a többi végpontnál `Authorization: Bearer ...` szükséges. Az alábbi útvonalak `/api` relatívak.

| Művelet | Végpont | Adat / eredmény |
|---|---|---|
| Profil | `GET`, `PUT /me` | `{id,name,email,phone,credits,activeKind,activeEntityId,createdAt}`; módosítás: `{name,email,phone}` |
| Saját entitások | `GET /me/entities` | `{properties,searchRequests,active:{kind,id}}` |
| Aktiválás | `PUT /me/active` | `{kind:"property"|"search",id}` |
| Ingatlanok | `GET`, `POST /properties`, `PUT`, `DELETE /properties/{id}` | Saját ingatlanok; a törlés archivál |
| Keresések | `GET`, `POST /searches`, `PUT`, `DELETE /searches/{id}` | Saját keresési igények; a törlés archivál |
| Ajánlások | `GET /feed` | `{items:[{property,searchRequest,propertyId,searchRequestId,compatibilityScore,reasons,likedYou}],sellerLikeCost:2}` |
| Döntés | `POST /decisions` | `{propertyId,searchRequestId,liked}` → `{matchId,charged,credits}` |
| Párosítások | `GET /matches` | `[{id,createdAt,property,searchRequest,contact:{id,name,email,phone},messages,unread}]` |
| Üzenet | `POST /matches/{id}/messages` | `{text}` → `{id,matchId,senderId,text,createdAt}` |
| Kreditnapló | `GET /credits/ledger` | `[{id,amount,description,createdAt}]` |
| Demófeltöltés | `POST /credits/demo-topup` | `{amount:20|50|100|250}`; kizárólag Development + engedélyező kapcsoló esetén |

Ingatlanmezők: `title,city,district,neighborhood,address,description,type,price,area,rooms,floor,condition,building,balcony,elevator,images,archived`. Keresésmezők: `title,city,districts,description,type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms,balcony,elevator,moveIn,financing,archived`. A min/max korlátok null értéke nyitott határt jelent. A `balcony/elevator=true` kötelező feltétel, a false nem zárja ki az adott tulajdonságot. A település és ingatlantípus egyezése kötelező, a kerületlista üresen bármely kerületet elfogad. A keresőoldali kedvelés ingyenes. Az eladói kedvelés 2 kredit. Saját entitások egymással nem párosíthatók.

A döntések egy adott ingatlan–keresés párra és oldalra véglegesek. Újraküldött azonos döntés idempotens és 0 további kreditet von le; ellentétes újraküldés 409. A döntés, a kreditlevonás, a napló és a kölcsönös párosítás egyetlen MySQL-tranzakcióban történik, sorzárolással és adatbázis egyediségi korlátokkal. Az elutasított és már kedvelt párok nem kerülnek vissza az ajánlásokba. Az aktiválás jogosultságot nem ad más felhasználó adatainak módosításához.

## Adatvédelem és élesítés

A feed és a publikus kártyák nem tartalmaznak felhasználói elérhetőséget vagy pontos utca/házszámot. A párosítási végpont csak a saját párosításokat adja vissza, és csak ott oldja fel a kapcsolatot. A jelszavak véletlen sóval, 210 000 iterációs PBKDF2-SHA256-tal tárolódnak. A publikus leírásban az e-mail-címet és szokásos magyar telefonszámformátumokat a rendszer elutasítja; képek tartalmának moderálása külön integráció.

Éles környezetben `ASPNETCORE_ENVIRONMENT=Production`, egyedi titkok, HTTPS reverse proxy és pontos CORS-origin szükséges. Kapcsold ki a demóseedet és a demófeltöltést; a feltöltési végpont Production módban akkor sem kerül regisztrálásra, ha a kapcsoló true. A Docker-alapértékek helyi fejlesztéshez készültek. A sémát az első létrehozáskor az EF `EnsureCreated` készíti el (`Database__Initialize=true`); ez nem sémafrissítési stratégia. Későbbi éles sémaváltozás előtt verziózott EF-migrációt és mentést kell készíteni. A titkok nem kerülnek a frontendbe.

A bankkártyás vásárláshoz Stripe Checkout és aláírt, idempotens webhook-integráció készült, külön PaymentOrders nyilvántartással. Beállítás és ellenőrzés: [PAYMENTS.md](../docs/PAYMENTS.md). Saját Stripe-kulcsok és elérhető webhook szükségesek; valódi fizetést az átadási környezetben nem indítottunk. Fejlesztésben külön demókredit-feltöltés is elérhető. E-mail-hitelesítés, jelszó-visszaállítás, képfeltöltés/tárolás, képek moderálása és üzemi monitoring további integráció.

## Ellenőrzések

`dotnet test backend/Otthonra.Tests/Otthonra.Tests.csproj` futtatja a szűrés és adatvédelmi szabályok egységtesztjeit. A `backend/smoke.mjs` két saját tesztfiókkal ellenőrzi a regisztrációt, kompatibilitást, idegen jogosultságot, párosítás előtti kontaktzárat, eladói levonás egyszeriségét, párosítást és üzenetküldést egy futó Development API-n:

```sh
node backend/smoke.mjs http://localhost:5080
```

A smoke teszt kizárólag új, véletlen nevű tesztfiókokat hoz létre. Éles rendszeren ne futtasd. A MySQL-hálózati és párhuzamossági ellenőrzéshez futó MySQL szükséges.
