# A november 15-i gyűjtés második köre

Kiinduló mentés: `3f6e793d9229b2eac3a3d0a73fe3664c3b24c542`:
3771 kiválasztott terület, 567 település, 510 külön tartalékkör.

Ebben a körben hat elkülönített csomag készült, összesen **128 új forrásjelölttel**:

| Csomag | Területek | Poligonok |
| --- | --- | ---: |
| `pest-northwest` | Szentendre, Gödöllő, Budakeszi, Piliscsaba | 29 |
| `west-planning` | Keszthely, Tata, Dombóvár | 13 |
| `north-northeast` | Gyöngyös, Sátoraljaújhely | 22 |
| `east-small` | Hosszúpályi, Monostorpályi, Mátészalka, Orosháza | 26 |
| `dorog-jaszbereny` | Dorog, Jászberény | 17 |
| `south-danube` | Fonyód, Dunaföldvár, Kalocsa | 21 |

Dombóváron a `Gunaras` és `Gunarasfürdő` elnevezés azonosságát az önkormányzat
névhasználati oldala igazolja; a rövid név alias lett, külön másolatgeometria nélkül.

## Források és bizonytalanság

A csomagok ténylegesen archivált OSM utakat, címcsoportokat, vízfolyásokat,
beépített vagy ipari felszíneket, korábbi helyi forrástérképeket és önkormányzati
utcahatár-leírásokat használnak. A kézi nyomvonalak és a felhasznált bizonyítékok
csomagonként megmaradnak. A dorogi végső becslések mind a 213 archivált,
lakótelepnévvel megjelölt címhelyet befoglalják; a kezdeti kisebb kiterjedés
diagnosztikai előzményként megmarad, de nem importforrás.

Az alakzatok **becsült, alacsony bizonyosságú keresési területek**, nem ellenőrzött
mai jogi városrészhatárok. A Tata külterületét leíró réteg natív térképi poligont
használ, a térképi illesztés közelítő. Remeteség és Perekac külön jelölt részleges
felszín; teljes hagyományos kiterjedésük nem ismert. A falusias külterületek
szántó-/kert-/dűlőhatár-becslései további finomításra szorulhatnak.

A központi PDF-letöltési eszközhívás nem tért vissza és megszakadt. A
`download-jobs.json` a kért, de ebben a körben helyben le nem töltött bináris
források jegyzéke, **nem felhasználási vagy sikeres letöltési igazolás**.
A csomagok pontosan jelzik, ha csak keresővel olvasható forrásszöveg vagy
korábbi helyi térkép állt rendelkezésre; nem állítanak nem látott PDF-ből
végzett poligondigitalizálást. A PDF-ek további forrásváltozatokhoz használhatók.

## Folytatás és megőrzés

- A kész, regisztrált állományok és ellenőrző összegeik:
  [WORK-STATE.json](WORK-STATE.json).
- Közös fő réteg: [search-areas.geojson](../search-areas.geojson.gz).
- Településenkénti darabszámok: [search-areas-report.csv](../search-areas-report.csv).
- A még hiányzó nevek: az `expansion-20261114/inventory/known-names.json` és
  `municipality-backlog.json` állományokban.

Csak a hat csomag egyenkénti `features.geojson` fájlja regisztrálandó. A részrétegek,
képpontkoordinátás munkafájlok és diagnosztikai előzmények nem további importok.
A stabil azonosítók, a névváltozatok és a régi forrásváltozatok megmaradnak.

Kecskemét és Győr további 15 nevének helyi feldolgozása ebben a mentésben nem
kezdődött el. Körmend és a nyugati csomag tíz nyitott neve, valamint Pomáz és
Dabas előkészített út-/felszínadatai folytatható munkát jelentenek; nem tekintjük
őket forráshiány miatt végleg megoldhatatlannak. Az országos gyűjtés nincs kész.

Az összevont adatok MySQL-importálásra előkészített külön kutatási állományok;
ez a gyűjtés nem telepíti az alkalmazást és nem módosítja a Cloud-adatbázist.
