# Opcionális ingatlanadatok és keresési feltételek

A keresésben az állapot, falazat, épületkor, kilátás, fűtéstípus és emelet több értékkel is megadható. Egy mezőn belül bármelyik kijelölt érték megfelelő (VAGY), a különböző mezők feltételeinek együtt kell teljesülniük (ÉS). A belmagasságnál egy feltétel választható. Üres mező vagy üres lista nem szűr. Ha a kereső megadott egy feltételt, az eladó nem megadott adata azt nem teljesíti.

Az ingatlanon ezekből a jellemzőkből mezőnként egy érték választható, mindegyik opcionális. A parkolóhelyek külön listáján több választás is megjelölhető. A belmagasság és az építés ideje a felületen megadott kategória; az épületkor nem konkrét évszám.

| Adat | Ingatlan API-mező | Keresési API-mező | Választható értékek |
|---|---|---|---|
| Állapot | `condition` | `conditions` tömb | Felújítandó, Átlagos, Jó, Új/felújított |
| Falazat | `building` | `buildings` tömb | Tégla, Panel, Csúsztatott zsalu, Vályog, Szilikát, Vegyes falazat, Fa, Könnyűszerkezet, Kő és tégla, Rönkház, Passzívház, Egyéb |
| Építés ideje | `constructionAge` | `constructionAges` tömb | 10 évnél fiatalabb, 10–30 év közötti, 31–40 év közötti, 41–50 év közötti, Több mint 50 éves |
| Kilátás | `view` | `views` tömb | Kertre néző, Utcai, Udvari, Panorámás |
| Belmagasság | `ceilingHeight` | `ceilingHeight` | 3 m alatti, 3 m feletti |
| Emelet | `floor` szám vagy `null` | `floors` számtömb | `-1`: szuterén; `0`: földszint; `0.5`: magasföldszint; `1`–`8`; `9`: 9 vagy afölötti keresési csoport |
| Fűtés típusa | `heatingType` | `heatingTypes` tömb | Gázkazán / cirkó, Gázkonvektor, Távfűtés, Házközponti fűtés, Hőszivattyú, Fűtő klíma, Elektromos fűtés, Fa- / vegyes tüzelésű kazán, Pelletkazán, Kályha / cserépkályha, Kandalló, Egyéb, Nincs fűtés |

A keresési `floors: [9]` minden 9. vagy magasabb emeletet elfogad. A régi keresési 10/11 érték olvasáskor és mentéskor ebbe a csoportba kerül. Az eladói képes választó pontos emeleteket mutat a szuteréntől a 10. emeletig; az „Egyéb” mezőben 11–200 közötti konkrét szám adható meg. Az épület emeleteinek száma hasonlóan, a „Földszintes” (`0`) opciótól választható. Új pontos választásnál `floorIsUpperRange:false`. A korábbi `floor:9, floorIsUpperRange:true` adat továbbra is ismeretlen pontos 9+ emeletet jelent, és változatlan szerkesztéskor megmarad; a zárószint kizárását nem igazolja. A korábbi pontos emelet (`floor:12, floorIsUpperRange:false`) változatlan szerkesztéskor megmarad. A `null` ingatlanemelet nem jelent földszintet. A korábbi konkrét emeletszám szerkesztéskor is megmarad, ha azt nem változtatják meg.

Csak az ingatlanhoz adható meg:

| Adat | API-mező | Típus |
|---|---|---|
| Erkély | `balcony` | `true`, `false` vagy `null`; háznál nem alkalmazható |
| Tetőtéri ingatlan | `isAttic` | `true`, `false` vagy `null`; emelethez kapcsolódó adat |
| Szigetelés az épületen | `insulated` | `true`, `false` vagy `null` |
| Energetikai tanúsítvány | `energyRating`, `energyRatingScheme` | Új besorolás: I–A+++ a `2023` rendszerben; a régi szöveg külön megőrizhető |
| Légkondi | `airConditioning` | `true`, `false` vagy `null` |
| Napelem | `solarPanels` | `true`, `false` vagy `null` |
| Parkolóhely típusa | `parkingTypes` tömb | Utcai parkolás, Udvari beálló, Fedett beálló, Garázs, Mélygarázs, Teremgarázs, Egyéb; több is választható |

Az erkély, légkondi, saját kert, szigetelés és napelem eladói mezői képes Van/Nincs párok. „Nincs megadva” esetén `null`, „Van” esetén `true`, „Nincs” esetén `false` az érték; a kijelölt opció újbóli kattintása visszaállítja a `null` állapotot. A fűtés képes opciókból választható, a parkolóhely továbbra is többértékű lista. Az eladói építéskor rádiógombos, a keresői építéskor változatlanul többválasztásos. A kiegészítő fűtés mező kikerült az aktív felületből; korábban tárolt adatai és régi létrehozási kérései kompatibilisek maradnak. A fő fűtés hiánya nem azonos a „Nincs fűtés” választással. Nyilvános mezőben elérhetőség továbbra sem osztható meg párosítás előtt.

Mentéskor az üres opcionális szöveg `""`, a keresési választás `[]`, a nem megadott logikai érték/emelet `null`. Ismeretlen választási érték hibás kérés (HTTP 400); a listák ismétlődő elemei egyszer tárolódnak. A teljes ingatlan- vagy keresésmódosításnál az opcionális mezők üres értékkel törölhetők.

## Szobák és házak

Az eladói űrlap egész és fél szobákat kér: `wholeRooms` és `halfRooms` nemnegatív egész számok (egyenként legfeljebb 1000). Az összesített `rooms = wholeRooms + halfRooms / 2`, 0-nál nagyobb és legfeljebb 1000; ezt használják a keresési szobaszámhatárok. A bontást külön tároljuk: 2 egész + 3 fél szoba mentés és újraindítás után is ezt jelenti. A régi, csak `rooms` mezőt küldő kliensek használhatók; változatlan összeg mellett a mentett bontás megmarad. Ha mindkét alak szerepel, az összegnek egyeznie kell (a hiányzó vagy 0 összeg kiszámolható a megadott bontásból). A korábbi fél szobákra nem bontható értékeket a rendszer nem kerekíti át.

Ház mentésekor a `lotArea` kötelező, 0-nál nagyobb és legfeljebb 10 000 000 m²; más ingatlantípusnál `null`. Házhoz nem kérünk emeletet, erkélyt és liftet; mentéskor `floor=null`, `balcony=null`, `isAttic=null`, `elevator=false`. Házkereséskor ezek a feltételek szintén rejtettek és törlődnek (`floors=[]`). A korábbi házadatok olvasáskor megmaradnak; hiányzó telekméretet szerkesztéskor kell pótolni.

A számmezők a negatív karakterek bevitelét és beillesztését is blokkolják, külön figyelmeztető szöveg nélkül. A szuterén továbbra is a választható emeletkategóriák egyike.

## Meglévő adatok és frissítés

A `20261105-property-attributes` és az új `20261106-seller-form-details` sémaverzió additívan hozza létre az oszlopokat. Az utóbbi a szobabontást, a kiegészítő fűtést, a parkolóhelylistát és a keresési fűtéslistát adja hozzá. A meglévő hirdetések új mezői üresek vagy ismeretlenek, a korábbi kereséseken nincs új korlátozás. A felhasználók, aktív profilok, döntések, párosítások, beszélgetések és kreditek megmaradnak. `Database__Initialize=true` mellett a frissítés induláskor, adatbáziszárral és ismételhető lépésekkel fut; adatbázis- vagy kötettörlés nem szükséges.

A régi állapotok olvasáskor megfeleltethetők az új kategóriáknak: „Felújított”, „Újszerű” és „Új építésű” → „Új/felújított”; „Jó állapotú” → „Jó”. A migráció nem írja át a régi sorokat. A régi API-val mentett, ismeretlen állapot/falazat/fő fűtés egy másik mező szerkesztésekor megőrizhető, de új ismeretlen választási érték nem hozható létre. A korábbi `parkingType` szöveg egyetlen választásként olvasható, nem daraboljuk fel. A `parkingTypes` lista az elsődleges; `[]` törli a választásokat. A `parkingType` válaszmező kompatibilitási összefűzött címke a régi klienseknek. Változatlan régi parkolószöveg másik mező szerkesztésekor megőrizhető. A böngészős demó mentése azonos tárolókulccsal és azonosítókkal marad használható.

A frissítéshez új backendkép és frontend telepítése szükséges: a korábbi kiadás backendképe nem tartalmazza ezeket a mezőket és szűrési szabályokat. A Google Cloud meglévő adatbázisa helyben frissül. Az alkalmazás élesítésétől függetlenül a mostani telepítés továbbra is tesztkörnyezet.

A `buildingFloors` az épület legfelső emeletszáma (0: csak földszint/magasföldszint). A magasföldszint `floor:0.5`, és 0-szintes épületben zárószintnek számít. Az új `20261124-raised-and-upper-floor-range` sémabővítés megőrzi a korábbi egész emeletértékeket.

A keresési szobaszámok korlát nélkül indulnak, pluszra 1-re váltanak, majd 0,5-ös lépésekkel állíthatók. Mínusz 1-ről visszatér a korlát nélküli állapothoz. A költözési idő négy képes opcióból választható, és újbóli kattintással törölhető.

A leírásban elérhetőség nem adható meg. A felület és a backend közös példakészlettel ellenőrzi a telefonszámok és e-mail-címek szokásos tagolt, Unicode- és szöveges alakjait; a privát profil telefonszáma és e-mail-címe ettől külön adat.


## Tetőtér és energetikai minimum

A keresés `atticPreference` értéke üres (nincs feltétel), `only` (tetőtér) vagy `exclude` (kivéve tetőtér). Ezek közül egyszerre egy állhat fenn. Az ismeretlen `isAttic:null` egyik konkrét feltételt sem teljesíti tökéletesen. A tetőtér a meglévő emeletfeltételekkel együtt, legfeljebb a 7-es emeletsúlyon befolyásolja a részleges egyezést.

Az energetikai csúszka sorrendje: **Nincs megadva → I → H → G → F → E → D → C → B → A → A+ → A++ → A+++**. A fehér kezdőállapot nem ad meg tanúsítványt. A többi állapot a jelenlegi magyar energetikai minőség besorolása, a hivatalos színekkel; a CO₂-besorolást nem keverjük ide. A keresés `minEnergyRating` mezője ugyanebből a skálából ad minimumot, a fűtéstípus után. Egy B minimum tehát B-t, A-t és a jobb A-kategóriákat is elfogadja. A részleges egyezés energetikai súlya 3.

A jelenlegi rendszerben megadott ingatlanon `energyRatingScheme:"2023"` szerepel. A korábban, rendszerjelölés nélkül tárolt A/A+, AA/BB stb. értékek megmaradnak, de nem alakíthatók át pusztán a betűk alapján új tanúsítvánnyá. Az ilyen adat nem igazol új energetikai minimumot. Az eladó új választással megadhatja az aktuális tanúsítványt; változatlan szerkesztés nem írja át a régi besorolást.

## Címvédelem és publikus adatlapok

A teljes címet továbbra is házszámig kérjük, és az ellenőrzött koordinátát belsőleg tároljuk a városrész szerinti kereséshez. A helyszín kiválasztása után a város neve szerkesztésikonnal jelenik meg; kattintásra nyílik újra a keresőmező. Irányítószámot a felhasználónak nem kell külön megadnia, a meglévő adatot belsőleg megőrizzük vagy címváltozáskor frissítjük.

A `hideStreet` és `hideHouseNumber` alapértéke `true`. Ha az utca rejtett, a házszám is rejtett. Ha csak a házszám rejtett, a közterület neve megjelenhet. Rejtett utcájú ingatlan kizárólag utcára szűkített keresésben nem szerepelhet; ugyanazon keresés másik település- vagy városrészválasztása továbbra is önálló VAGY lehetőség. A nyers koordináták, szolgáltatói azonosítók és az owner-only `addressDetails` nem nyilvánosak.

A `20261124-public-listings-and-energy` sémafrissítés az új mezőket, a nullable erkélyt, az indexelt publikus kulcsot és a létrehozási hash verzióját adja hozzá. A régi v1 létrehozási kérés erkélymező nélküli false ujjlenyomatát szükség esetén kompatibilisen egyeztetjük; új v2 kéréseknél a `null` és `false` különböző. További publikus API- és piszkozatfolyamat: [PUBLIC-LISTINGS.md](PUBLIC-LISTINGS.md).
