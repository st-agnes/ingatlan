# Nyilvános régiók és helyszínek

A bejelentkezés nélküli bemutató 19 vármegye és Budapest között enged választani. A régióazonosítók a KSH területi számjelrendszerének NUTS 2016 kódjai; például Budapest `HU110`, Pest `HU120`, Hajdú-Bihar `HU321`. Ez a helyszínválasztó településeinek csoportosítása, nem ingatlanok pontos helymeghatározása.

A `backend/Otthonra.Api/Data/regions.json` az alkalmazás mind a 3155 ismert települését pontosan egy régióhoz rendeli. A budapesti kerületek Budapesthez tartoznak. A több vármegyét érintő „város és környéke” keresések minden érintett régióban megjelenhetnek, a csoport tényleges településlistája alapján. Egy kártya egy régióban egyszer szerepel.

Forrás: [KSH – Területi számjelrendszer struktúra elemei, 2026](https://www.ksh.hu/docs/osztalyozasok/teruleti_szamjel/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx), letöltve 2026. november 6. A forrásfájl SHA-256 lenyomata a generált JSON-ban található. Licenc: [CC BY 4.0, KSH felhasználási feltételek](https://www.ksh.hu/copyright). Az eredeti vármegyei megnevezések a felületen „vármegye” utótaggal szerepelnek. A generálás nem tartalmaz koordinátákat.

Újragenerálás a teljes, letöltött XLSX állományból, kizárólag a Python szabványos könyvtárával:

```bash
python3 scripts/import-regions.py /path/to/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx
python3 scripts/import-regions.py /path/to/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx --check
```

A generátor a backend beágyazott településbesorolását és a böngésző `dist/regions-data.js` választékát együtt állítja elő. A forrásfájl nincs a tárolóban.

Az anonim `GET /api/public/landing` legfeljebb 8 keresési igényt és 4 ingatlant ad vissza, változatos, véletlenszerűen válogatott nem archivált bejegyzésekből. A válogatás az ingatlantípusokat, árkategóriákat, helyszíneket, alapterületeket és szobaszámokat is figyelembe veszi, hogy a hasonló hirdetések ne szorítsák ki a ritkább lehetőségeket. Nemcsak a megjelenítési sorrend változik: elegendő jelölt esetén a következő lekérés más bejegyzéseket is választ. A jelöltkészlet példányonként 60 másodpercig gyorsítótárazott, a végső válogatás minden lekéréskor újra elkészül. Több Cloud Run-példány között nincs közös látogatói előzmény vagy új személyes adatgyűjtés.

A `?region=HU321` kizárólag az adott régióhoz kapcsolódó adatokat adja; üres régióra üres listák érkeznek. Ismeretlen régióazonosítóra 400-as válasz érkezik. Módosítás vagy archiválás legfeljebb egy perc múlva tükröződhet a nyilvános oldalon. A lekérdezés minimális mezőket olvas folyamatosan, és a régiós szűrés előtt nincs országos darabkorlát.

A kártyák címe generált, típusa ellenőrzött listából származik, és helyszínként kizárólag ismert település, kerület vagy településcsoport neve szerepel. Nyers hirdetésszöveget, címet, tulajdonosi vagy hirdetésazonosítót, kapcsolatfelvételi adatot és felhasználó által megadott fényképet az anonim végpont nem közöl. A kártyák kulcsa csak az adott válasz sorszáma.
