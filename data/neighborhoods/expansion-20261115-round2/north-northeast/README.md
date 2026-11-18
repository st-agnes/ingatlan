# Északi gyűjtési csomag – második kör

A `features.geojson` a teljes, egyetlen importálandó csomag. A városi és az első részcsomag ugyanennek részhalmazai, ezért ugyanabba az összevonásba ne kerüljenek be újra.

A csomag 22 alakzatot tartalmaz: Gyöngyös 11, Sátoraljaújhely 11. Gyöngyös mind a 11 kiinduló hiányzó nevéhez szélesebb, lakott/negyed-jellegű területbecslés készült a tényleges utcahálózat, épületek és felszínrajz alapján. A 2016-os önkormányzati ITS releváns oldalai itt megmaradnak. A Mátrai, Pesti és Nyolcvanas lakótelep szöveges leírásai, valamint Duranda Csárda utcához és az északi két statisztikai területhez kötött leírása segítik a névazonosítást. Az utóbbi statisztikai cellák nem lettek teljes városrészhatárként átcímkézve.

Az Északi városrész a város északi, lakott utcai-földhasználati foltjának becslése. A hiányos 19. oldali térkép képkeretével nem zártunk körvonalat; a 28. oldali teljes északi térképet és a tényleges utcai/vineyard peremet használtuk háttérként. A külön szereplő Mátrafüred teljesen más, saját településfoltot kapott. A Gyöngyössolymoshoz átnyúló becsült széleket a meglévő települési határral vágtuk; az eredeti kézi kontúr és a vágás előtti befoglalási hányad megmarad.

Sátoraljaújhely mind a 11 hiányzó neve tényleges utcák, épületek, kertek/szőlők és hegyoldali terepi átmenetek alapján kapott szélesebb, lakott városrészi területbecslést. Ezek nem szűk vízfelületek vagy épületkontúrok. A nyilvános, egyoldalas történeti városrésztérképet forráskutatási háttérként azonosítottuk; annak natív határvonalait a helyi PDF érkezése előtt nem állítjuk elő. A mentett Sátoraljaújhely-geometriák egyértelműen kézi utca-/felszínrajzi becslések.

Minden alakzat alacsony biztonságú becslés, nem hivatalos vagy kataszteri határ. A kerti/erdei/szántóföldi szakaszok összekötései kézzel következtetett vonalak. A nagyobb és kisebb egységek átfedése szándékos. Nem készült pont köré rajzolt kör, sugár vagy téglalap. A forráspont befoglalása technikai konzisztenciajelzés, nem földrajzi pontosságigazolás. A véges kiinduló névjegyzék lefedése nem jelent teljes városi lefedést.

Újraépítés helyi forrásokból `shapely`, `pyproj` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/north-northeast/build-gyongyos.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/north-northeast/build-satoralja.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/north-northeast/build.py
```

A forrásgeometriák veszteségmentes gzip archívumban maradnak. A `source-evidence.json` és a PDF-részlet rögzíti a bizonyítékot, a `validation.json` a technikai ellenőrzéseket, az `unresolved.json` a még gyűjtendő neveket és a pontosság korlátait. © OpenStreetMap contributors, ODbL-1.0.

Az `első részcsomag` rögzített fájlja a `first-batch-features.geojson`: 11 gyöngyösi alakzat. A Kalocsa-nevű forrásarchívumokat másik csapat használhatja; kalocsai alakzat nincs e csomagban.
