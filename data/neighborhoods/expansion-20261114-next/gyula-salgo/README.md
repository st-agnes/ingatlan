# Salgótarján és Gyula: további közelítő városrészek

41 bemeneti alakzat: Salgótarján 21, Gyula 20. Egyik sem pont köré képzett kör. A `features.geojson` a közös állomány, a két város külön fájlban is megmarad.

Salgótarjánnál az archivált 2022-es önkormányzati ITS 125. oldalának színezett városrészcsoportjait és kataszteri/utcahálózati hátterét használtuk. A kisebb területek belső elválasztói szándékosan durva kézi becslések. Három történeti csoport a már meglevő forráskomponensek uniója; a névanyag és a felosztási korszak külön megmarad. Nem állítjuk, hogy ezek eredeti KSH finomhatárok. A korábbi nyolc pontosabban körberajzolt profilkontúr változatlan marad a régi forráscsomagban.

Gyulánál a 2025-ös várostérségi SUMP 41. oldalának helyi busz- és utcatérképe jól felismerhető városrészneveket, beépítési széleket, utcákat, folyót és vasutat mutat. Ebből készültek a közelítő elválasztók. A kép nem nyomtatott városrészhatár-térkép: az alakzatok kifejezetten kézi becslések, nem hivatalos körvonalak. Az Újgyula melletti térképszélen kis folytatást becsültünk a látható utcaszerkezetből. A teljes SUMP PDF, a natív kép és a nyers csúcspontlisták itt megmaradnak. A busztérkép forrásmegjelölése MÁV-helyimenetrend és OpenStreetMap; ez az adatban is szerepel.

A Gyula-kép közelítő EOV-elhelyezése 16 kiírt névpozíció és azonos nevű OSM névpont illesztése. A 112,5 méteres illesztési maradék a névhelyek illeszkedése, nem független földrajzi pontosság. Salgótarján a már archivált, szintén közelítő áttekintőkép–EOV illesztést használja. Abszolút pontosságot egyik állomány sem állít. A keresési területek átfedése megengedett, különösen a történeti szülőcsoportok és kisebb telepek között.

## Újraépítés

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/gyula-salgo/build-salgotarjan.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/gyula-salgo/build-gyula.py
python3 data/neighborhoods/expansion-20261114-next/gyula-salgo/combine.py
```

A közös `features.geojson` a két városi GeoJSON `features` tömbjének összefűzése. A `summary.json` rögzíti a kész csomag ellenőrző összegeit. A forrásképekhez viszonyított diagnosztikai előnézetek `*-trace-preview.png` néven találhatók; ezek saját ellenőrző ábrák, nem eredeti hivatalos határábrák. A névpont-diagnosztika mind a 35 elérhető pontos névegyezésű pontot a saját becsült területén belül találta; ez az alkalmazott név-elhelyezési módszer belső ellenőrzése, nem független pontosságigazolás.
