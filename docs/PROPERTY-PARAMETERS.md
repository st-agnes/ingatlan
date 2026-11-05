# Opcionális ingatlanadatok és keresési feltételek

A keresésben az állapot, falazat, épületkor, kilátás és emelet több értékkel is megadható. Egy mezőn belül bármelyik kijelölt érték megfelelő (VAGY), a különböző mezők feltételeinek együtt kell teljesülniük (ÉS). A belmagasságnál egy feltétel választható. Üres mező vagy üres lista nem szűr. Ha a kereső megadott egy feltételt, az eladó nem megadott adata azt nem teljesíti.

Az ingatlanon mezőnként egy érték választható, mindegyik opcionális. A belmagasság és az építés ideje a felületen megadott kategória; az épületkor nem konkrét évszám.

| Adat | Ingatlan API-mező | Keresési API-mező | Választható értékek |
|---|---|---|---|
| Állapot | `condition` | `conditions` tömb | Felújítandó, Átlagos, Jó, Új/felújított |
| Falazat | `building` | `buildings` tömb | Tégla, Panel, Csúsztatott zsalu, Vályog, Szilikát, Vegyes falazat, Fa, Könnyűszerkezet, Kő és tégla, Rönkház, Passzívház, Egyéb |
| Építés ideje | `constructionAge` | `constructionAges` tömb | 10 évnél fiatalabb, 10–30 év közötti, 31–40 év közötti, 41–50 év közötti, Több mint 50 éves |
| Kilátás | `view` | `views` tömb | Kertre néző, Utcai, Udvari, Panorámás |
| Belmagasság | `ceilingHeight` | `ceilingHeight` | 3 m alatti, 3 m feletti |
| Emelet | `floor` szám vagy `null` | `floors` számtömb | `-1`: szuterén; `0`: földszint; `1`–`10`; `11`: 11 vagy afölötti |

A keresési `floors: [11]` a ténylegesen 12., 15. vagy magasabb emeleten lévő meglévő ingatlanokat is elfogadja. A `null` ingatlanemelet nem jelent földszintet. A korábbi konkrét emeletszám szerkesztéskor is megmarad, ha azt nem változtatják meg.

Csak az ingatlanhoz adható meg:

| Adat | API-mező | Típus |
|---|---|---|
| Fűtés típusa | `heatingType` | Opcionális szöveg, legfeljebb 80 karakter; pl. „Hőszivattyú és padlófűtés” |
| Szigetelés az épületen | `insulated` | `true`, `false` vagy `null` |
| Energetikai besorolás | `energyRating` | Opcionális szöveg, legfeljebb 20 karakter; pl. „A+”, „BB” |
| Légkondi | `airConditioning` | `true`, `false` vagy `null` |
| Napelem | `solarPanels` | `true`, `false` vagy `null` |
| Parkolóhely típusa | `parkingType` | Opcionális szöveg, legfeljebb 80 karakter; pl. „Udvari beálló”, „Mélygarázs” |

Az igen/nem mezőkben a „Nincs megadva” `null`, az „Igen” `true`, a „Nem” `false`; a válasz és a szerkesztő mindhármat külön kezeli. A fűtés, besorolás és parkolóhely szabad szövege támogatja az összetett fűtéseket és a korábbi energetikai jelöléseket is. Nyilvános mezőben elérhetőség továbbra sem osztható meg párosítás előtt.

Mentéskor az üres opcionális szöveg `""`, a keresési választás `[]`, a nem megadott logikai érték/emelet `null`. Ismeretlen választási érték hibás kérés (HTTP 400); a listák ismétlődő elemei egyszer tárolódnak. A teljes ingatlan- vagy keresésmódosításnál az opcionális mezők üres értékkel törölhetők.

## Meglévő adatok és frissítés

Az új `20261105-property-attributes` sémaverzió additívan hozza létre az oszlopokat. A meglévő hirdetések új mezői üresek vagy ismeretlenek, a korábbi kereséseken nincs új korlátozás. A felhasználók, aktív profilok, döntések, párosítások, beszélgetések és kreditek megmaradnak. `Database__Initialize=true` mellett a frissítés induláskor, adatbáziszárral és ismételhető lépésekkel fut; adatbázis- vagy kötettörlés nem szükséges.

A régi állapotok olvasáskor megfeleltethetők az új kategóriáknak: „Felújított”, „Újszerű” és „Új építésű” → „Új/felújított”; „Jó állapotú” → „Jó”. A migráció nem írja át a régi sorokat. A régi API-val mentett, ismeretlen állapot/falazat egy másik mező szerkesztésekor megőrizhető, de új ismeretlen választási érték nem hozható létre. A böngészős demó mentése azonos tárolókulccsal és azonosítókkal marad használható.

A frissítéshez új backendkép és frontend telepítése szükséges: a korábbi kiadás backendképe nem tartalmazza ezeket a mezőket és szűrési szabályokat. A Google Cloud meglévő adatbázisa helyben frissül. Az alkalmazás élesítésétől függetlenül a mostani telepítés továbbra is tesztkörnyezet.
