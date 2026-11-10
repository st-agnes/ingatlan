# A webes felület és a .NET API összekötése

A webes felület alapértelmezésben böngészőben tárolt demóadatokkal indul. Ez lehetővé teszi a profilváltás, a lapozás, a kölcsönös találat és a kreditfogyás kipróbálását önálló szerver nélkül. A demóban indított kreditfeltöltés nem jár fizetéssel.

A mellékelt fejlesztőkörnyezetben a webes felület ugyanazon az eredeten, `/api` alatt proxyzza a backendet. A kapcsolódási űrlap ezért alapértelmezésben az aktuális webes címet ajánlja fel; továbbított felhős címmel telefonról is ez használandó.

A valódi API használatához indítsd el a MySQL-t és a .NET szervert a projekt üzemeltetési útmutatója szerint. A felület Beállítások oldalán add meg az API alapcímét, majd jelentkezz be vagy regisztrálj. A cím a szerver gyökere legyen; a végén szereplő `/api` részt az adapter eltávolítja, mielőtt összeállítja az útvonalakat.

A `dist/api.js` exportjai:

- `getModel()`: a mentett API-kapcsolat alapján API-adaptert vagy a böngészős demómodellt adja vissza.
- `connectApi(baseUrl, email, password, registerData?)`: belépés, illetve megadott `registerData` esetén regisztráció; sikeres hitelesítés után menti a kapcsolatot és visszaadja az API-adaptert.
- `disconnectApi()`: törli a mentett hitelesítést és visszaadja a demómodellt. A demóadatok megmaradnak.

Az API-adapter a demómodelllel azonos felületet nyújt, de minden adatkezelő metódusa aszinkron. A hívónak `await` használatával kell megvárnia a `getState()`, `feed()`, `matches()` és a módosító műveletek eredményét. Az adapter nem vált át észrevétlenül demóadatokra szerverhiba, lejárt munkamenet vagy hálózati hiba esetén.

A helyi `otthonra.api` kulcs kizárólag az API-címet és a Bearer tokent tartalmazza; jelszó nem kerül mentésre. A kijelentkezés ezt a kulcsot törli. Éles használatkor HTTPS-t és szigorú tartalombiztonsági szabályokat használj; a token tárolási módja a végleges üzemeltetési környezethez igazítható. A forrásadatokhoz való jogosultságot minden esetben a .NET szerver ellenőrzi.

A külön telepített webes felület pontos eredetét a backend engedélyezett CORS-eredetei közé kell felvenni. A HTTPS-en megnyitott webes felülethez HTTPS API-t használj. Fejlesztéskor a frontend és a backend egyaránt futhat helyi HTTP-címen.

A webes árak millió forintban szerepelnek; az adapter a backend teljes forintban tárolt árait két irányban átváltja. Az API-adapternek átadott képcímeknek más kliensekből is elérhetőnek kell lenniük. A demó `/assets/` képei kizárólag a webes demó saját mintaképei.

## Helyválasztás és opcionális mezők

Az ingatlan mentésekor `locationId`, keresési igénynél legalább egy érvényes helyet tartalmazó `locationIds` tömb adandó meg. A felület mindkét oldalon a találatok közül enged választani; a begépelt szöveg önmagában nem helyazonosító. A keresési igényhez több választás megadható és egyenként eltávolítható.

A katalógus a nyilvános `GET /api/locations?q=Deb&limit=8` végponton is elérhető, Bearer token nélkül. Válaszának alakja:

```json
{"items":[{"id":"city:Debrecen","label":"Debrecen","city":"Debrecen","district":null}]}
```

A budapesti kerület például `{"id":"district:Budapest:5","label":"Budapest V. kerület","city":"Budapest","district":"V."}`. A teljes város azonosítója `city:Budapest`. A frontend a közös katalógus helyi modulját használja, ezért az automatikus kiegészítéshez nincs szüksége külső szolgáltatásra. A forrás, licenc és frissítési útmutató a [LOCATION-DATA.md](LOCATION-DATA.md) fájlban található.

A mentési szerződés például:

```js
await model.saveEntity('search', {
  title: 'Közös otthont keresünk',
  locationIds: ['district:Budapest:5', 'district:Budapest:9', 'city:Solymár', 'city:Pilisvörösvár'],
  type: 'Lakás', minPrice: null, maxPrice: 85,
  minArea: 50, maxArea: null, minRooms: 2, maxRooms: null
});
```

A kiválasztott helyek között VAGY kapcsolat van; az összes többi keresési feltétel továbbra is érvényes. Ugyanígy választható együtt Debrecen, Hajdúszoboszló és Hajdúsámson. A teljes Budapest minden kerületet elfogad; a Budapest V. kerület választása önmagában csak az V. kerületet. Egy csak városig pontosított budapesti ingatlan nem tekinthető valamely konkrét kerületben lévőnek.

A `getState()`, `feed()` és `matches()` ingatlanadataiban `locationId` és `location`, keresési adataiban `locationIds` és `locations` szerepel. A helyobjektum alakja a fenti katalógusrekorddal azonos. A régi `city`, `district`, `districts` mezők megmaradnak a kompatibilitáshoz; többvárosos keresés megjelenítéséhez a `locations` címkéit használd. Az azonosítók az irányadók. Az adapter a régi API-válaszok ismert település- és kerületneveit is felismeri, az ismeretlen vagy üres, explicit választást mentéskor elutasítja.

A keresési minimumár, maximum alapterület és maximum szobaszám üresen hagyható. A form, a demómodell és az API-adapter `null` értékként kezeli és mentés/visszaolvasás után is megőrzi ezeket. A `null` nyitott korlátot jelent; nem helyettesíthető nullával vagy egy nagy felső határral. A fenti példában az adapter `maxPrice: 85000000` értéket küld a backendnek, a három nyitott korlát pedig `null` marad.

Házhoz a `lotArea` pozitív számként, m²-ben adható meg; az üres mező `null`. Más ingatlantípusra váltáskor a telekméret `null` lesz. A `lotArea` a visszaadott ingatlanadatokon is elérhető.

## Meglévő adatok

A demó továbbra is az `otthonra.demo.v3` kulcsot használja. A modell a korábbi helyadatokat betöltéskor értelmezi, és megőrzi az entitások azonosítóit, döntéseit, párosításait és kreditegyenlegét. A MySQL-adatbázishoz a backend `20261102-locations-and-lot-area` additív `SchemaUpgrade` frissítése tartozik: `Database__Initialize=true` mellett az `EnsureCreated` után fut, meglévő sorok törlése nélkül. A régi helymezők olvasáskor is használhatók; nincs szükség adatbázis- vagy kötettörlésre. Részletek: [backend/README.md](../backend/README.md).


## Pontos és részleges ajánlások

A `GET /api/feed` alapértelmezésben csak a pontos, 100%-os ajánlásokat adja. A válasz az `items`, `likeCost`, `sellerLikeCost` mellett `active`, `stage`, `hasApproximate`, `requiresApproximateConsent` mezőket tartalmaz. A `stage` értéke `exact`, `approximate` vagy `empty`. A `GET /api/feed?includeApproximate=true` is előbb a még el nem bírált pontos találatokat adja; részlegeseket csak ezek elfogyása után. Az üres, hozzájárulást kérő válasz nem feltétlenül jelenti a jelöltek teljes hiányát.

A kártya `compatibilityScore` értéke 0–100, `isExact` jelzi a teljes feltételteljesítést. A `valueForMoney` belső sorrendezési érték, a `searchSpecificity` a keresés 0–100 közötti specializáltsága. A százalékot nem szabad `value || 97` jellegű helyettesítéssel megjeleníteni: a 0 is érvényes. A `reasons` kompatibilitási szövegmező megmarad. Az új `matchDetails` tömb elemei `{key,label,expected,actual,matches}` alakúak: a helyszín és típus mellett minden megadott, alkalmazható feltétel konkrét keresett és tényleges értékét tartalmazzák. Például `{key:"rooms",label:"Szobaszám",expected:"legalább 3 szoba",actual:"2 szoba",matches:false}`. A teljesülő feltételek is szerepelnek `matches:true` jelöléssel. A webes megjelenítés a típust/helyszínt kihagyja, a teljesülő feltételeket rövid jelzéssé alakítja; eltérésnél keresőként csak az idegen ingatlan `actual`, eladóként csak az idegen keresés `expected` értékét mutatja. A saját aktív entitás értékei nem ismétlődnek az összehasonlító sorokban. A specializáltságot a felület `67%` alakban jeleníti meg.

A `POST /api/decisions` részleges párnál explicit `allowApproximate: true` mezőt vár. Ez önmagában nem kerülheti meg a helyszín-/típus-/tulajdonosi szabályokat vagy a még meglévő pontos ajánlásokat. A feltételek közben változhatnak, ezért az elutasítást a kliensnek kezelnie és az ajánlást frissítenie kell. Pontos párnál a régi kérésforma továbbra is megfelelő. A már rögzített döntés azonos újraküldése továbbra is díjmentes.

A böngészős modell és adapter `recommendations({includeApproximate})` metódusa visszaadja a szakaszadatokat, míg a korábbi `feed(options)` továbbra is kártyatömböt ad. A `decide(item, liked, {allowApproximate})` adja tovább az explicit engedélyt. Az engedélyt a kliens az aktív entitáshoz és aktuális feltételeihez köti; váltás, szerkesztés és kijelentkezés után újra kell kérnie.

A Kedveltek listájában a `compatible` a kizáró feltételek szerinti jogosultságot, az `isExact` a teljes egyezést jelzi. Korábbi, részleges pár látható maradhat, de az arra adott új döntéshez ugyanaz a hozzájárulási szabály tartozik. Kontaktadat továbbra is kizárólag kölcsönös kedvelés után érhető el.

A nyilvános ingatlan-/keresés-DTO-k és a bejelentkezés nélküli landing kártyái `ownerFirstName` mezőt adnak. Ezt a tulajdonos mentett nevéből a szerver származtatja; hirdetésadatból nem fogadja el. A landing `title` mezője a valódi hirdetés biztonságosan megjeleníthető címe, elérhetőséget tartalmazó vagy üres címnél helyettesítő szöveggel. A nyilvános DTO-k nem adnak vissza teljes nevet, telefonszámot, emailt vagy pontos címmezőt. A részleges ajánlások kapuján egyetlen megnyitó gomb van; kattintás nélkül a hozzájárulás hamis marad.

## Eladói statisztikák és visszajelzéscsomagok

- `GET /api/properties/{id}/insights?offset=0&limit=50`: tulajdonosi statisztikák, válaszok/ok szerinti összesítés, aktív csomag és legutóbbi csomagok. A `stats` mezői: `uniqueViewers`, `buyerLikes`, `sellerLikes`, `matchedViewers`, `matchRate`. A megjelenések egyedi emberek; a ráta a megjelenést kapott, párosított emberek aránya (0–100%). A nézet nem tartalmazza a válaszolók azonosítóját vagy elérhetőségét.
- `POST /api/impressions {propertyId,searchRequestId}`: kizárólag a valóban látható ingatlankártyához. A saját aktív keresést és az ajánlhatóságot a backend ellenőrzi; ismétlésnél `recorded:false`. A feed lekérése nem mérés.
- `POST /api/properties/{id}/feedback-packages {size,requestId}`: `size` csak 10, 20, 50; a GUID `requestId` ugyanahhoz a vásárlási szándékhoz újrapróbáláskor változatlan. Válasz: `{package,charged,credits}`. Azonos kérés díjmentes ismétlés, eltérő adatokkal újrahasznált kulcs 409. Másik aktív időszak 409, kevés kredit 402. A csomag azonnal engedélyezett, 14 napos; teljes kvóta mellett is a határidejéig blokkolja az új vásárlást.
- `PUT /api/properties/{id}/feedback {enabled}`: új visszajelzéskérések szüneteltetése/folytatása. A határidő változatlan; a már kiküldött kérdések érvényes válaszai továbbra is beszámíthatók.
- `GET /api/feedback/pending`: `{feedbackPrompt:null|prompt}`. A webes adapter/demó `pendingFeedback()` metódusa a belső `prompt|null` értéket adja, nem a borítékot. A döntés végpontja is `feedbackPrompt` mezőt ad vissza. A következő kártya megjelenítése előtt ezt kezelni kell.
- `POST /api/feedback/{id} {reason}`: az első válasz végleges; azonos válasz ismétlése díjmentes/idempotens, másik válasz 409, lejárt kérés 410. A válaszadó kreditegyenlege nem változik. A `decline` válasz `accepted:false` és nem számít a megvett válaszok közé.

Az okazonosítók: `insufficient_information`, `layout`, `lighting`, `location`, `view`, `incorrect_parameters`, `other`, `decline`. A feliratokat és a csomagméreteket a közös `feedback.js` definiálja. Egy kérés legfeljebb 15 percig tart helyet a kvótában, a csomag határidejét nem lépheti túl. Egy ember egy csomaghoz egy kérdést kaphat, függetlenül a keresési profiljai számától. A mintavétel egy kicsi, felhasználóhoz kötött elutasításszámlálót használ, nem új, költséges ajánlóalgoritmust.

A `feedback_refund` értesítéseknek `feedbackPackageId` hivatkozásuk és `decisionId:null` értékük van. A kreditnapló külön `feedback_package` és `feedback_refund` típusokat és csomaghivatkozásokat ad. A háttérfeldolgozás és a tulajdonosi olvasás is elindítja a lejárt csomagok egyszeri elszámolását, így a visszatérítés független az egyes Cloud Run példányok élettartamától.
