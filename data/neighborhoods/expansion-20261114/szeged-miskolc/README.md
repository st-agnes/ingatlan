# Szeged és Miskolc – gyors térképalapú bővítés

A `features.geojson` **72 WGS84 alakzatot** tartalmaz: Szeged 45, Miskolc 27. Egyik sem névpont köré rajzolt kör. A már meglévő gyűjteménnyel való név szerinti összevonás az országos export feladata.

Szegeden a Henits László 2013-as értekezésében közölt, KSH 2003 eredetű térkép 42 számozott területét dolgoztuk fel. A 36-os számhoz nem látható külön cella ezen az ábrán. Hat sérült vagy felirattal takart körvonalrésznél egyszerű kézi vonalbecslést használtunk; a többi színezett belső terület képi kiolvasással készült. A Belváros, Újszeged és Ipari övezet tágabb egységeit a megfelelő részek összevonása adja. A városrészek és tágabb csoportok szándékosan átfedhetik egymást.

Miskolcon az önkormányzati dokumentum 17 összevont térképi egysége és a szöveges alkotórészlista adja a keretet. **A 27 kisebb terület új belső határait nagyvonalúan becsültük meg** a képen látható beépítés, főbb területi átmenetek és a leírás alapján. Ezek nem a 32 KSH-városrész eredeti, visszanyert határvonalai. A forrás térképi kerete megmarad, az új elválasztók a `build-miskolc.py` állományban olvashatók. Ez a pontköröknél több helyi információt használó, alacsony bizonyosságú becslés.

Az eredeti térképek, a georeferálási mátrixok, a pixelkoordinátás vonalak, a forráshivatkozások és az újraépítő programok megmaradnak. A pixelkoordinátás fájlok neve `*-native-traces.geojson`; **ezeket nem szabad földrajzi koordinátaként importálni**. A WGS84 kimenetek a `features.geojson`, `szeged-features.geojson` és `miskolc-features.geojson`.

Az abszolút pontosság ismeretlen, az aktuális hivatalos teljességet nem állítjuk. A forrástérképek újrafelhasználási jogát a közzétevő nem jelölte egyértelműen; az OSM kalibrációs helyadatok ODbL forrása ettől külön adat.

Újraépítés a tároló gyökeréből, `numpy`, `Pillow`, `scipy`, `shapely`, `pyproj` függőségekkel:

```sh
python3 data/neighborhoods/expansion-20261114/szeged-miskolc/build-szeged.py
python3 data/neighborhoods/expansion-20261114/szeged-miskolc/build-miskolc.py
python3 data/neighborhoods/expansion-20261114/szeged-miskolc/combine.py
```
