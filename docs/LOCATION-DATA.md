# Magyar településkatalógus

A `dist/data/settlements.json` a frontend és a .NET backend közös, verziózott
településjegyzéke. A jelenlegi pillanatkép 3155 egyedi magyarországi települést
tartalmaz; Budapest 23 kerülete ebből külön képzett választási lehetőség.
A katalógus használatához futás közben nincs külső API vagy hálózati kérés.

## Forrás és feldolgozás

- Forrás: [Gvwyn/varmegyek – iranyito.txt](https://github.com/Gvwyn/varmegyek/blob/main/iranyito.txt).
- Letöltés: 2026. november 2.
- Rögzített Git blob: `b6dd0735903eb19129410ca42e7d5e3980d697e7`
  ([GitHub blob API](https://api.github.com/repos/Gvwyn/varmegyek/git/blobs/b6dd0735903eb19129410ca42e7d5e3980d697e7)).
- Licenc: [MIT](https://github.com/Gvwyn/varmegyek/blob/main/LICENSE), teljes szövege lent.
- Az upstream README az irányítószámok forrásaként a
  [Magyar Posta táblázatát](https://www.posta.hu/static/internet/download/Iranyitoszam-Internet_uj.xlsx)
  jelöli meg. Koordinátákat és Google Maps adatokat nem veszünk át.
- A szövegfájl sorainak elejéről elhagytuk az irányítószámot, az ismétlődő
  településneveket kiszűrtük, majd hozzáadtuk Budapestet, amely ebben a
  forrásfájlban nem szerepel. A 3154 forrásnév között nincs zárójeles
  településrész vagy postai alkörzet; a neveket változtatás nélkül őriztük meg.
- A 3155-ös darabszám megegyezik a [KSH 2026-os településszámával](https://www.ksh.hu/teruletiatlasz_telepulesek).
  Ez darabszám-ellenőrzés; a fájl az upstream rögzített pillanatképe, nem élő KSH-adatkapcsolat.

A településazonosító `city:<hivatalos írásmódú név>`, például
`city:Hajdúsámson`. A budapesti kerület azonosítója
`district:Budapest:<1–23>`, megjelenítése például „Budapest V. kerület”.
A teljes Budapestet jelentő `city:Budapest` keresés minden budapesti kerületet
elfogad. Külön kerület választásakor csak az adott kerület felel meg.
Több választás között VAGY kapcsolat van.

## Frissítés

Először ellenőrizni kell az upstream forrást és licencét, valamint az új nevek
helyességét; az új pillanatkép forrásazonosítóját itt is rögzíteni kell.
A `settlements.json` legyen az egyetlen szerkesztett adatforrás. A
`dist/locations-data.js` ugyanazt a tömböt exportálja szinkron ES-modulként.
Az alábbi parancs újragenerálja a böngészős másolatot:

```sh
node --input-type=module <<'NODE'
import fs from 'node:fs';
const { settlements } = JSON.parse(fs.readFileSync('dist/data/settlements.json', 'utf8'));
const banner = '// Generated from data/settlements.json. Source and MIT attribution: ./THIRD-PARTY-NOTICES.txt.\n';
fs.writeFileSync('dist/locations-data.js', banner + 'export const settlements = Object.freeze(' + JSON.stringify(settlements, null, 2) + ');\n');
NODE
node tests/locations.test.mjs
```

A .NET a JSON-t beágyazott erőforrásként olvassa; a böngésző ugyanazokat a
neveket a generált modulból kapja. A tesztek a két lista egyezőségét,
az azonosítók egyediségét, a keresést és a kerületi/helységi illesztést ellenőrzik.
Szabad szöveg nem kerül automatikusan a katalógusba: mentéshez érvényes
azonosítójú találatot kell kiválasztani.

## Átvett MIT-licenc

```text
MIT License

Copyright (c) 2024 Gvwyn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Város és környéke csoportok

A keresési igényben a konkrét települések és budapesti kerületek mellett a KSH által lehatárolt **24 városközpontú térség** is választható. A név és a településszám például „Budapest és környéke (81 település)”, illetve „Debrecen és környéke (13 település)”. A darabszám a központot is egyszer tartalmazza; Budapest kerületei nem külön települések. A budapesti csoport ugyanakkor az összes kerületben lévő ingatlant lefedi.

A lehatárolás a KSH aktuális területi nyilvántartásán alapul, nem egy önkényesen megválasztott kilométeres körön. A városközpontok az alábbi teljes listában szerepelnek. Érd a budapesti csoport tagja; a központ nélküli balatoni térséget ebbe a városlistába nem vettük fel. A csoporttal nem rendelkező települések továbbra is konkrét településként választhatók.

| Választható térség | Települések száma |
|---|---:|
| Budapest és környéke | 81 |
| Baja és környéke | 3 |
| Békéscsaba és környéke | 11 |
| Debrecen és környéke | 13 |
| Dunaújváros és környéke | 9 |
| Eger és környéke | 19 |
| Esztergom és környéke | 2 |
| Győr és környéke | 78 |
| Kaposvár és környéke | 30 |
| Kecskemét és környéke | 13 |
| Miskolc és környéke | 41 |
| Nagykanizsa és környéke | 27 |
| Nyíregyháza és környéke | 11 |
| Pécs és környéke | 49 |
| Salgótarján és környéke | 12 |
| Sopron és környéke | 15 |
| Szeged és környéke | 16 |
| Székesfehérvár és környéke | 43 |
| Szekszárd és környéke | 10 |
| Szolnok és környéke | 13 |
| Szombathely és környéke | 63 |
| Tatabánya és környéke | 11 |
| Veszprém és környéke | 27 |
| Zalaegerszeg és környéke | 67 |

### Forrás, licenc és ellenőrzés

- **Forrás: KSH**, [Területi számjelrendszer, 2026 – teljes struktúra XLSX](https://www.ksh.hu/docs/osztalyozasok/teruleti_szamjel/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx); [az adatközlés oldala](https://www.ksh.hu/teruleti_szamjel_menu).
- Letöltés: **2026. november 6.** A teljes forrás SHA-256 azonosítója: `36927d2798ea709f8239d806c9a84881524395f3d6f11dfdd756cc662776e1a5`.
- A feldolgozás a „Név” és „Agglomeráció kódja” oszlopokat használja; csak a közös településkatalógus valódi településsorait veszi át. A budapesti központot és hat szektort egyetlen csoporttá vonja össze. A 24 csoport 664 településtagságot tartalmaz.
- Minden csoport településszáma egyezik a [KSH STADAT 8.1.2.11. – 2026. január 1.](https://www.ksh.hu/stadat_files/fol/hu/fol0016.html) táblával (frissítve: 2026. szeptember 15.). Ez a tábla a 2022. évi népszámlálás alapján készült lehatárolást jelöli meg.
- A KSH nyilvános honlapadatainak licence a [KSH felhasználási feltételei](https://www.ksh.hu/copyright) szerint **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**. A forrás nem egyedi kérésre kiadott belső adatállomány. Csak a településneveket és csoporttagságokat vettük át; a besorolási kódokat alkalmazásazonosítókká alakítottuk, a címkéket és darabszámokat saját megjelenítéshez képezzük. KSH-logót, ábrát vagy tanulmányrészletet nem másoltunk. A forrás aktív hivatkozása a keresési választónál is látható.

A kanonikus fájl `dist/data/agglomerations.json`, a szinkron böngészős másolat `dist/agglomerations-data.js`. A .NET ugyanazt a JSON-t beágyazott erőforrásként kapja. Az előállító kizárólag standard Python-könyvtárakat használ:

```sh
python3 scripts/import-agglomerations.py .local/agglomeration-research/tszj2026-raw.xlsx --check
```

A `--check` az aktuális pillanatképet ellenőrzi írás nélkül; nélküle újragenerálja a JSON-t és a böngészős modult. A forrásfájlt a fenti hivatalos URL-ről kell letölteni az ignorált `.local` könyvtárba. Új kiadásnál a forrás URL-jét, az ellenőrzött darabszámokat, a verziót és a letöltési dátumot is felül kell vizsgálni; az új névnek továbbra is a közös településkatalógusban kell szerepelnie. A `tests/areas.test.mjs` ellenőrzi a két adatfájl egyezését, mind a 24 csoport darabszámát, valamennyi tag érvényességét és a teljes tagság párosítását.

### Mentés és párosítás

A csoport azonosítója `area:<központ>`, például `area:Debrecen`. Egyetlen keresési választásként kerül a meglévő `locationIds` listába; nem bontjuk 81 külön kiválasztásra Budapestet, így az 50 választásos korlát megmarad. A `locations` válaszrekord `kind: "area"` és `settlementCount` mezővel is jelzi a csoportot. Konkrét városnál a `kind` értéke `city`, kerületnél `district`.

A kiválasztott csoport minden tagtelepülése megfelelő helyszín. Több csoport, település és kerület egymás alternatívája (VAGY); az ár-, méret-, típus- és egyéb keresési feltételeknek ettől még teljesülniük kell. A puszta „Debrecen” választás továbbra is csak Debrecenre vonatkozik; a szomszédos településeket az „és környéke” csoport választása vonja be.

Az ingatlan helye továbbra is pontos település vagy budapesti kerület. A keresési csoportokat az eladói választó elrejti, és a backend illetve a JS-modell/API-adapter is elutasítja az ilyen ingatlanhelyet. A `GET /api/locations?q=Debrecen&kind=search` a csoportokat is adja, a `kind=property` csak pontos helyszíneket; az alapérték `search`. A darabszám megjelenítési adat, ezért a `81` keresés nem találja meg a budapesti csoportot.

Ehhez a bővítéshez nincs új adatbázisséma: a meglévő keresési helyazonosító-listát használjuk, a korábbi keresések és ingatlanok változatlan jelentéssel olvashatók. Új backend- és frontendkiadás szükséges az új katalógus telepítéséhez; futás közben nem függ külső adatforrás elérhetőségétől.
