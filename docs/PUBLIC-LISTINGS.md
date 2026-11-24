# Publikus hirdetésoldalak

A kezdőoldal keresési igényeiből és eladó ingatlanjaiból a teljes kártyára kattintva nyílik meg az adott hirdetés adatlapja. A külön, hangsúlyos „Ilyen ingatlanom van” és „Ilyen otthont keresek” gomb továbbra is közvetlenül indítja a megfelelő űrlapot.

Az adatlapok bejelentkezés nélkül is elérhetők. Megjelenik a hirdető keresztneve, a kis fióktípusikon, a felhasználó által megadott cím, az ismert paraméterek, a leírás és ingatlannál az összes megosztható kép. A fióktípusikon kattintásra, egérrel fölé állva és billentyűzetes fókuszban is magyarázatot ad. A címláthatósági beállítások ezeken az oldalakon is érvényesek; telefon, e-mail, nyers koordináta és más belső címadat nem kerül a nyilvános válaszba.

## URL és API

A böngészős útvonal `#listing/property/{sourceKey}` vagy `#listing/search/{sourceKey}`. A `sourceKey` a korábbi kezdőoldali folyamatból ismert, stabil, átlátszatlan hirdetéskulcs. Nem a felhasználó vagy a belső ingatlan/keresés azonosítója.

A frontend az anonim `GET /api/public/listings/{kind}/{key}` végpontot hívja. A válasz:

- `kind`, `key`, `sourceKey`, `title`, `ownerFirstName`, `ownerAccountType`;
- `listing`: a teljes, szűrt publikus adatlap;
- `prefill`: a meglévő, ellenkező szerepű űrlapot előkészítő adatok;
- `clonePrefill`: kizárólag keresésnél a teljes keresési feltételrendszer másolható adatai.

Az API az árakat forintban küldi, a böngésző millió forintos űrlapegységre vált. A keresés indexelt, tárolt publikus kulcsot használ. A válasz `no-store`; a hibás, megszűnt vagy archivált hirdetés 404-et ad. A böngésző ilyenkor visszautat ajánl a kezdőoldalra. Régi kérés későn érkező válasza nem írhatja felül az időközben megnyitott másik lapot vagy regisztrációt.

## Címvédelem

Az eladó továbbra is pontos címet ad meg. A teljes cím és a geokódolt koordináta a saját ingatlanadat része marad.

| Beállítás | Publikusan látható cím | Utcára szűkített keresés |
|---|---|---|
| Közterület elrejtve | A helyszín általános adatai | Az adott utca alapján nem található |
| Közterület látható, házszám rejtett | A közterület neve | A közterület alapján található |
| Mindkettő látható | Közterület és házszám | A közterület alapján található |

Az utca rejtése a házszámot is elrejti. A városrészre, településre vagy agglomerációra keresés továbbra is a tényleges belső helyadat alapján működik. Több helyszín VAGY kapcsolatban áll: egy rejtett utca önmagában nem találat, de ugyanazon keresés másik, megfelelő városrészválasztása igen.

## Indulás egy hirdetésből

A keresési igény nyilvános árkerete a publikus maximumot használja. A kereső tényleges maximuma nem része az anonim válasznak, az eladóknak küldött keresési adatnak vagy az űrlap-előtöltésnek. Másoláskor a publikus keret lesz az új keresés kiinduló tényleges és publikus maximuma; a másoló ezeket később saját igénye szerint módosíthatja.

Eladó ingatlannál az „Ilyen otthont keresek” a korábbi, ingatlan alapján számított keresési piszkozatot készíti elő. Keresési igénynél az „Ilyen ingatlanom van” továbbra is csak az egyértelmű, konkrét értékeket veszi át az eladói űrlaphoz.

A keresési adatlap „Én is ilyet keresek” gombja az összes keresési feltételt, helyszínt és további elképzelést átveszi egy szerkeszthető keresési piszkozatba. A név a szokásos rövid automatikus név. A felhasználó végigmegy a lépéseken, majd a jelenlegi azonnali belépéses regisztrációval vagy saját fiókjában mentheti.

A másolás eredetét a forrás keresés kulcsa és a `copy` mód együtt azonosítja. Ugyanabból a keresésből ugyanazzal a móddal indulva a korábbi szerkesztett piszkozat folytatódik. Másik hirdetés vagy másik szerep esetén a régi piszkozat a már megszokott módon, külön felülírási kérdés nélkül cserélődik. Az egyszeri mentés és a több böngészőfül közötti védelem megmarad.

## Tesztelés és kiadás

A kezdőoldal legfeljebb 16 keresést és 8 ingatlant válogat ki a ténylegesen elérhető rekordokból. A v8 tesztkészlet minden vármegyében és Budapesten 16 régiós keresést biztosít, eltérő paraméterekkel. Az eredeti 12 regionális eladó ingatlanból 8 választható ki. A kiválasztás továbbra is változatos, frissítéskor újraválogatott.

Az új kliensfájlok `energy-rating.js`, `public-listings.js` és `public-listings.css`; mindhárom kötelező Hosting-állomány. A statikus CI futtatja a publikus megjelenítés egységtesztjét és az onboarding böngészős csoportjában egyszer a publikus adatlapfolyamatokat. A két MySQL-verzió integrációja külön ellenőrzi a címvédelmet, szűrést, új mezőket és újraindítás utáni megőrzést.

A szokásos Google Cloud TEST kiadáshoz új API-kép és frontend szükséges. Új secret, konfiguráció vagy erőforrás nem kell.
