# Utolsó kis csomag: Miskolc és Dunaújváros

23 új, kifejezetten durva becsült poligon: Miskolc 17, Dunaújváros 6. Ezek 24 korábban csak ponttal ismert nevet képviselnek. Miskolc déli ipari és technológiai parkja egyazon terület két neve; ezért egyetlen geometriával, aliasokként kerül be. Az önkormányzati szövegből származó névváltozási tény megmarad.

A teljes átadási fájl a `features.geojson`. A két városi alkönyvtár `features.geojson` fájljai ugyanennek részhalmazai; összevonáskor vagy a teljes fájlt, vagy a két részhalmazt kell felvenni, nem mindhármat.

Minden határhoz megmarad a tényleges helyi úthálózati/földhasználati kontextus, a kézi töréspontlista, a forrás és a korlátozások. A dunaújvárosi becsléseknél önkormányzati/jogi folyosóleírások segítettek, a miskolciaknál tényleges dűlő- és lakótelepi utcakörnyezet. A domboldalak és bővítési területek belső összekötései becsültek. Ezek nem hivatalos vagy ellenőrzött kataszteri városrészhatárok. Körös és városméretű folt nincs.

A két városi `build.py` újraépíti a saját geometriákat, a `combine.py` pedig összeállítja ezt a csomagot. A technikai ellenőrzés érvényes WGS84 Polygon/MultiPolygon alakzatokat és belül lévő saját névpontokat igazol, nem földrajzi pontosságot. A korábbi Miskolc–Ózd 50+7 alakzatot ez a csomag nem módosítja.
