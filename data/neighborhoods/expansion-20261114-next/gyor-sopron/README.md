# Győr és Sopron — további 34 becsült keresési terület

2026-11-14-i gyűjtési csomag, a meglévő gépi poligonok mellé. A felhasználó által kért gyors, közelítő gyűjtési stratégia szerint készült. Minden végső geometria becslésként jelölt; nincs új kör vagy Voronoi-terület.

## Importálható eredmények

| Fájl | Település | Darab | Módszer |
| --- | --- | ---: | --- |
| `sopron-features.geojson` | Sopron | 19 | Önkormányzati CAD-térkép utcái, telektömbjei és meglevő névpontjai alapján kézzel közelített terület |
| `gyor-surface-features.geojson` | Győr | 10 | Változatlan, ténylegesen megrajzolt OSM lakó- vagy kertes terület a városrész névpontja körül |
| `gyor-manual-features.geojson` | Győr | 5 | Tényleges OSM utca-/vasút-/vízrajz és önkormányzati/helytörténeti szöveg alapján kézzel közelített terület |

Kizárólag ezt a három fájlt kell importálni. A `raw-surface-features.geojson` és `surface-features.geojson` forrásalternatívák; Sopronnál ugyanazokat a neveket is tartalmazzák, amelyeket a külön CAD-becslés már lefed.

Győrnél Ménfő, Csanakfalu, Csanakhegy, Szalmatelep és Újtelep külön kézi becslést kapott. A többi tíz név: Sáráspuszta, Pillangó lakópark, Szarkavár, Kishegy, Sikolya, Szent Erzsébet-telep, Ergényi lakótelep, Szitásdomb, Pataháza és Vízivárosi lakópark.

Sopronnál a korábbi hiánylistából már csak Brandmajor, Óbrennberg és Szilvás nincs ebben a csomagban. Győrnél a korábbi hiánylistából Csikórét, Göcsei-földek, Katona-rét, Koldustelek, Malomsziget és Sörfőző-rét marad további kutatásra. Ezek a nevek a munkakezdéskori hiánylistához viszonyítottak, nem az összes magyar városrész teljességi mutatói.

Kertváros nem új geometria: az `alias-candidates.json` javasolja a meglévő Győrszentiván-Kertváros kereshető neveként történő kezelését. A dokumentum39-es városrendezési körzete és a291.oldali leírás támasztja alá az azonosságot.

## Mit jelentenek a becslések?

A Sopronban használt településrendezési lap tényleges utca- és telektérképet tartalmaz. A19 kisebb lakóterület/városrész finom határait viszont **nem** nyomtatja külön: a megőrzött `sopron-manual-traces.json` vonalai elemzői közelítések. A CAD-lap georeferálása a korábban archivált `municipal-sopron-next/registration.json` mátrixát használja. A feliratok névpontként, a látható utcák és telektömbök tájékozódási pontként szolgáltak.

A tíz győri OSM-felszín geometriája változatlan. Ettől még a felszín nem állítható be hivatalos városrész-határként: némelyik nagyobb összefüggő lakóterület több helynevet foglal magába. Kishegy és Sikolya, Ergényi lakótelep és Szitásdomb, illetve Pataháza és Vízivárosi lakópark ezért ugyanazt a tágabb forrásfelszínt is használhatja. Ezt a `semanticFootprint`, `sourceGeometryUnmodified` és `approximationNote` mezők jelzik. Későbbi részletes térkép vagy szöveges határleírás esetén szűkíthetők.

Az öt kézi győri becslés térképi kapcsolódási pontjait a `gyor-manual-traces.json` sorolja fel. Ménfő és Csanak esetében a Zsellér utca21-nél megőrzött határkő történeti támpont; a teljes történeti községhatár nincs rekonstruálva. Szalmatelepet a2014-es ITS298.oldala a volt Házgyár melletti lakóterületi zárványként írja le. Győrszentiván térképi és291.oldali leírásából a vasút és a főutak által tagolt településszerkezet használható Újtelep közelítéséhez. A bizonytalan szakaszokat az utcahálózat mentén becsültük; nem állítunk jogi vagy kataszteri pontosságot.

## Megőrzött források

- Sopron eredeti önkormányzati CAD-forrása: `data/neighborhoods/sources/municipal-sopron-next/source-pages1-2.pdf`; eredeti URL és SHA a mellette levő `source-extraction-proof.json` fájlban.
- Győr önkormányzati ITS: `data/neighborhoods/sources/municipal-gyor-next/gyor-its.source.pdf`, [forrás](https://gyor.hu/easy-docs/5dc9829cb6d4c).
- [Ménfő/Csanak határkő, Zsellér utca21](https://www.kozterkep.hu/5583/hatarko), valamint a2022-es helytörténeti tanulmány [141.oldala](https://eptorivaros.sze.hu/images/ICOMOS_konyv_2022_kesz.pdf).
- `name-points.geojson`: a két város változatlan OSM helynévpontjai, egyedi forrás-URL-lel.
- `raw-surface-features.geojson`: a kiválasztáskor talált tényleges OSM felszínek teljes geometriája és objektumcímei.
- `gyor-source-roads.geojson`: 13 265 tényleges OSM út-/vasút-/vízvonal, teljes forráskoordinátákkal és objektum-URL-lel. A PBF SHA-ja minden elem metaadataiban szerepel. © OpenStreetMap contributors, ODbL-1.0.
- A kontextus-PNG-k szemléltető forrásnézetek. A finom kézi becslések gépi visszaépítéséhez a JSON-vonalak és a georeferálási mátrixok szolgálnak.

## Hálózat nélkül visszaépíthető

A tároló gyökeréből, a `shapely`, `pyproj`, `numpy` Python-csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/gyor-sopron/build-sopron.py
python3 data/neighborhoods/expansion-20261114-next/gyor-sopron/build-gyor-surfaces.py
python3 data/neighborhoods/expansion-20261114-next/gyor-sopron/build-gyor-manual.py
python3 data/neighborhoods/expansion-20261114-next/gyor-sopron/verify-packet.py
```

A kész csomag visszaépítéséhez nem kell országos PBF és hálózat. A két `extract-*.py` kizárólag az eredeti nyers forráskinyerés megismétlésére szolgál, ha a helyi országos PBF is rendelkezésre áll. A `packet-summary.json` a három végső fájl SHA-ját és a34 érvényes, névpontját tartalmazó poligon integritásellenőrzését rögzíti. Ez nem határpontossági bizonyítvány.
