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
| Emelet | `floor` szám vagy `null` | `floors` számtömb | `-1`: szuterén; `0`: földszint; `1`–`10`; `11`: 11 vagy afölötti |
| Fűtés típusa | `heatingType` | `heatingTypes` tömb | Nincs fűtés, Gázkazán, Gázcirkó, Gázkonvektor, Távfűtés, Házközponti fűtés, Elektromos fűtés, Hőszivattyú, Klíma, Vegyes tüzelésű kazán, Cserépkályha, Kandalló, Egyéb |

A keresési `floors: [11]` a ténylegesen 12., 15. vagy magasabb emeleten lévő meglévő ingatlanokat is elfogadja. A `null` ingatlanemelet nem jelent földszintet. A korábbi konkrét emeletszám szerkesztéskor is megmarad, ha azt nem változtatják meg.

Csak az ingatlanhoz adható meg:

| Adat | API-mező | Típus |
|---|---|---|
| Kiegészítő fűtés | `secondaryHeatingType` | Opcionális egyértékű választás, ugyanabból a fűtéslistából |
| Szigetelés az épületen | `insulated` | `true`, `false` vagy `null` |
| Energetikai besorolás | `energyRating` | Opcionális szöveg, legfeljebb 20 karakter; pl. „A+”, „BB” |
| Légkondi | `airConditioning` | `true`, `false` vagy `null` |
| Napelem | `solarPanels` | `true`, `false` vagy `null` |
| Parkolóhely típusa | `parkingTypes` tömb | Utcai parkolás, Udvari beálló, Fedett beálló, Garázs, Mélygarázs, Teremgarázs, Egyéb; több is választható |

Az igen/nem mezőkben a „Nincs megadva” `null`, az „Igen” `true`, a „Nem” `false`; a válasz és a szerkesztő mindhármat külön kezeli. A fűtés legördülő listából választható, a parkolóhely jelölőnégyzetekkel adható meg. Az energetikai besorolás továbbra is rövid szöveg. A keresési fűtésszűrő a fő fűtést vizsgálja, a kiegészítőt nem; a nem megadott fő fűtés nem azonos a „Nincs fűtés” választással. Nyilvános mezőben elérhetőség továbbra sem osztható meg párosítás előtt.

Mentéskor az üres opcionális szöveg `""`, a keresési választás `[]`, a nem megadott logikai érték/emelet `null`. Ismeretlen választási érték hibás kérés (HTTP 400); a listák ismétlődő elemei egyszer tárolódnak. A teljes ingatlan- vagy keresésmódosításnál az opcionális mezők üres értékkel törölhetők.

## Szobák és házak

Az eladói űrlap egész és fél szobákat kér: `wholeRooms` és `halfRooms` nemnegatív egész számok (egyenként legfeljebb 1000). Az összesített `rooms = wholeRooms + halfRooms / 2`, 0-nál nagyobb és legfeljebb 1000; ezt használják a keresési szobaszámhatárok. A bontást külön tároljuk: 2 egész + 3 fél szoba mentés és újraindítás után is ezt jelenti. A régi, csak `rooms` mezőt küldő kliensek használhatók; változatlan összeg mellett a mentett bontás megmarad. Ha mindkét alak szerepel, az összegnek egyeznie kell (a hiányzó vagy 0 összeg kiszámolható a megadott bontásból). A korábbi fél szobákra nem bontható értékeket a rendszer nem kerekíti át.

Ház mentésekor a `lotArea` kötelező, 0-nál nagyobb és legfeljebb 10 000 000 m²; más ingatlantípusnál `null`. Házhoz nem kérünk emeletet, erkélyt és liftet; mentéskor `floor=null`, `balcony=false`, `elevator=false`. Házkereséskor ezek a feltételek szintén rejtettek és törlődnek (`floors=[]`). A korábbi házadatok olvasáskor megmaradnak; hiányzó telekméretet szerkesztéskor kell pótolni.

A számmezők a negatív karakterek bevitelét és beillesztését is blokkolják, külön figyelmeztető szöveg nélkül. A szuterén továbbra is a választható emeletkategóriák egyike.

## Meglévő adatok és frissítés

A `20261105-property-attributes` és az új `20261106-seller-form-details` sémaverzió additívan hozza létre az oszlopokat. Az utóbbi a szobabontást, a kiegészítő fűtést, a parkolóhelylistát és a keresési fűtéslistát adja hozzá. A meglévő hirdetések új mezői üresek vagy ismeretlenek, a korábbi kereséseken nincs új korlátozás. A felhasználók, aktív profilok, döntések, párosítások, beszélgetések és kreditek megmaradnak. `Database__Initialize=true` mellett a frissítés induláskor, adatbáziszárral és ismételhető lépésekkel fut; adatbázis- vagy kötettörlés nem szükséges.

A régi állapotok olvasáskor megfeleltethetők az új kategóriáknak: „Felújított”, „Újszerű” és „Új építésű” → „Új/felújított”; „Jó állapotú” → „Jó”. A migráció nem írja át a régi sorokat. A régi API-val mentett, ismeretlen állapot/falazat/fő fűtés egy másik mező szerkesztésekor megőrizhető, de új ismeretlen választási érték nem hozható létre. A korábbi `parkingType` szöveg egyetlen választásként olvasható, nem daraboljuk fel. A `parkingTypes` lista az elsődleges; `[]` törli a választásokat. A `parkingType` válaszmező kompatibilitási összefűzött címke a régi klienseknek. Változatlan régi parkolószöveg másik mező szerkesztésekor megőrizhető. A böngészős demó mentése azonos tárolókulccsal és azonosítókkal marad használható.

A frissítéshez új backendkép és frontend telepítése szükséges: a korábbi kiadás backendképe nem tartalmazza ezeket a mezőket és szűrési szabályokat. A Google Cloud meglévő adatbázisa helyben frissül. Az alkalmazás élesítésétől függetlenül a mostani telepítés továbbra is tesztkörnyezet.
