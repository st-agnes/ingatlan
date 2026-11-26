# Ajánlások és távolságalapú megfelelés

A megfelelés a keresési feltételek megsértéséből képzett, súlyozott távolság. A teljesülő vagy nem megadott feltételek eltérése nulla. A részleges eredmény képlete `Q = Σ(w × d²)`, majd `match = round(100 × exp(-sqrt(Q)))`. A teljes egyezés 100, minden részleges eredmény legfeljebb 99. Nincs a kitöltött feltételek számával növekvő nevező: egy új, teljesülő feltétel nem javít fel egy korábbi súlyos eltérést.

Az ár, szobaszám és alapterület eltérése a megfelelő keresési határhoz viszonyított arány. Csak a megkötés megsértése számít: a minimumot meghaladó érték nem hiba. Ezek az eltérések nincsenek 1-re levágva. A kategorikus, logikai és sorrendi paramétereknél a közös C#/JavaScript szabályok határozzák meg az eltérést; a hiányzó adat nem bizonyítja egy megadott feltétel teljesülését.

## Súlyok

| Feltétel | Súly |
|---|---:|
| Helyszín | 1,5 |
| Maximum ár | 1,2 |
| Minimum szobaszám | 1,1 |
| Minimum alapterület | 1 |
| Állapot | 0,36 |
| Emelet és kapcsolódó megkötései | 0,25 |
| Maximum alapterület | 0,16 |
| Maximum szobaszám | 0,16 |
| Minimum ár | 0,09 |
| Lift | 0,09 |
| Erkély, légkondi, saját kert, energetikai minimum | egyenként 0,04 |
| Falazat | 0,0225 |
| Fűtés | 0,0169 |
| Épület kora | 0,0144 |
| Belmagasság, kilátás | egyenként 0,01 |

Az ár és a minimum alapterület súlya közel van egymáshoz. Az eredeti, különálló ár-érték és 0–100-as keresésfókusz-mutató szemantikája megmaradt. Ezek nem adják hozzá magukat a megfelelési százalékhoz.

## Helyszín

A kiválasztott helyek között VAGY kapcsolat van. A pontosan megfelelő helyszín eltérése nulla. Más helyszínű ingatlan esetén a legközelebbi kiválasztott **terület eredeti poligonjától** mért geodéziai távolság számít, 20 km-es skálával: `d = távolság_km / 20`. A városon/városrészen belüli eltérés nulla; nem a középponttól mérünk. A városkörnyék a tagtelepülések területeit jelenti.

Az utcáknak egyelőre nincs közelségi geometriájuk. Vegyes keresésnél a közeli találatokhoz csak a nem utca jellegű kijelölések adnak területet; a kiválasztott, látható utca továbbra is bizonyíthat pontos helyszínegyezést. **Kizárólag utcákat tartalmazó keresésnél a helyszín továbbra is kizáró feltétel.** Rejtett utca nem felel meg utcaválasztásnak. Ismeretlen koordinátával csak a korábbi, bizonyítható pontos helyszínegyezés használható, közelséget nem találgatunk. Az ingatlantípus továbbra is kizáró feltétel.

## MySQL és adatfrissítés

A MySQL szűri, pontozza és rendezi a jelölteket; a backend csak a végső, legfeljebb 50 pár azonosítóját és rangsorolási adatait kapja meg. A teljes hirdetést és az összehasonlítás szövegét csak ezekhez tölti be. Nincs jelöltenkénti hálózati adatbázis-hívás vagy a teljes országos találati halmaz C#-ba olvasása.

Először külön, geodéziai távolságszámítás nélküli SQL keresi a tökéletes találatokat. A részlegesekhez a rendszer 5/20/80/320 km-es, konzervatív földrajzi ablakokat vizsgál, szükség esetén korlátlan SQL-lekérdezéssel. A korábbi pontos helyszínegyezések minden ablakban megmaradnak. Csak akkor áll meg, ha a még nem vizsgált jelöltek legjobb lehetséges kerekített pontszáma már rosszabb az 50. eredményénél; a kedvelési prioritás és a holtversenyek is számítanak. Nincs önkényes legközelebbi-N vagy végleges kilométeres kizárás.

Keresőként a sorrend százalék, korábbi bejövő kedvelés, ár-érték. Eladóként bejövő kedvelés, százalék, keresésfókusz. A teljes és részleges találatok külön fázisban maradnak, a részlegesek előtt aktív profilhoz kötött beleegyezéssel. Eladói nézetben kizárólag a publikus maximum ár, keresői nézetben a tulajdonos tényleges kerete számít.

A natív `MatchingLocationAreas` táblában a 3155 település, 4308 városrész és 23 budapesti kerület teljes geometriája található; a `MatchingLocationMembers` tartalmazza a választások területeit. A `MatchingPropertyPoints` térbeli indexelt pontjai a saját ingatlan szerver által ellenőrzött koordinátáiból készülnek, a mentéssel egy tranzakcióban. Induláskor verziózott, zárolt import és korlátos visszatöltés fut; az eredeti címek, koordináták és meglévő felhasználói adatok megmaradnak. A kanonikus helyazonosítók bináris összehasonlítást kapnak: az eltérő települések, például Komló és Kömlő nem olvadnak össze. A meglévő helyindexek kollációját az additív `20261126-binary-canonical-location-keys` frissítés javítja. Új külső szolgáltatás, API-kulcs vagy Google Cloud erőforrás nem szükséges.

A földrajzi ablakok és indexek csökkentik a vizsgált jelöltek számát, de legrosszabb esetben sok sor kiértékelése továbbra is szükséges. A `LIMIT 50` a továbbított sorok számát korlátozza; nem önmagában bizonyítja a lekérdezés gyorsaságát. Rövid élettartamú ajánlás-gyorsítótár ebben a változatban nem kerül be: az aktuális döntések és módosítások azonnali érvényessége megmarad.

## Böngészős demó és ellenőrzés

A hosted alkalmazás az API MySQL-ben számolt eredményeit használja, és nem pontozza újra a nyilvános DTO-kat. Az önálló helyi demó ugyanazt a pontozási képletet használja, de késleltetetten betöltött, egyszerűsített térképi megjelenítési poligonokból közelíti a távolságot. Hiányzó geometria/koordináta esetén marad a szigorú helyszínegyezés. A demó távolsága ezért nem tekinthető a teljes backendgeometria pontos reprodukciójának.

A közös pontozási példák, .NET- és Node-tesztek mellett a MySQL 8.0/8.4 API smoke ellenőrzi a térbeli táblákat, koordinátaszinkront, poligonhatár-távolságot, adatbázis/képlet paritást, mindkét szerepkört, beleegyezést és a 250 m² helyett 50 m² súlyos eltérés felhígításának tilalmát. A régi sémáról frissítés és az ismételt indulás is a meglévő CI része.
