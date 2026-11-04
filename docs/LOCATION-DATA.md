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
