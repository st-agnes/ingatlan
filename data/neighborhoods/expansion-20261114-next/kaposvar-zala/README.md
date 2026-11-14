# Kaposvár és Zalaegerszeg: körpótlások kiváltása

85 új terület, kör vagy Voronoi nélkül:

- `features.geojson`: 30 Zalaegerszeg-terület. A 2014-es önkormányzati térkép három tágabb városrészcsoportja, az Ola és Landorhegy már korábban digitalizált forrásalakzata, továbbá 25 finomabb, kifejezetten becsült térképi részterület.
- `kaposvar-features.geojson`: 47 kaposvári finomabb helyi terület. A tárolt OSM út-, vasút- és vízrajz, névpontok, valamint a 2023-as FVS területleírásai alapján kézzel becsült, alacsony bizonyosságú körvonalak.
- `remaining-features.geojson`: 4 további kaposvári külterületi helynév környéke és Zalaegerszeg 4 tágabb külterületi csoportja. Az utóbbiak a forrástérkép földrajzi szektorainak közelítései; külső keretük a tárolt OSM településhatár, a belső városrészcsoportokat kivonjuk.

A 30 + 47 + 8 nem egyetlen hivatalos területfelosztás. A különböző nevű szülőterületek és kisebb egységek szándékosan átfedhetnek. A finomabb becslések határvonalai nincsenek így kinyomtatva az önkormányzati térképen: a látható út- és telekstruktúrából, illetve ismert névpozícióból következtetünk rájuk. A térképi alap jobb támpont, mint a puszta sugárkör, de nem állítunk méteres, jogi vagy felmérési pontosságot.

A 2014-es zalaegerszegi térkép már tárolt illesztését változatlanul használjuk. A kaposvári diagnosztikai úttérkép közvetlen EOV-ábrázolás a változatlan OSM-vonalakból. A kézzel felvett pixellisták, a vetületi paraméterek, a névpontok forrásazonosítói és a programok itt vannak. A hivatkozott korábbi forrásfájlok a tároló `data/neighborhoods/sources/` könyvtárában maradnak.

Újraépítés `numpy`, `pyproj`, `shapely` csomagokkal, a tároló gyökeréből:

```sh
python3 data/neighborhoods/expansion-20261114-next/kaposvar-zala/build.py
python3 data/neighborhoods/expansion-20261114-next/kaposvar-zala/build-kaposvar.py
python3 data/neighborhoods/expansion-20261114-next/kaposvar-zala/build-remaining.py
```

A `qualityScore` relatív kiválasztási súly, nem pontossági százalék. Az `alias-suggestions.json` két, azonos forráscsoportot eltérő hosszúságú néven leíró kaposvári névazonosságot dokumentál; a Kisgát kisebb önálló részterületét nem vonja össze a teljes szülőterülettel.
