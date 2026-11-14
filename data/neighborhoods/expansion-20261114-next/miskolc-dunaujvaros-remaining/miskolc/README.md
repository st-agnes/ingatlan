# Miskolc: a következő 18 névhez 17 becsült terület

A csomag a korábbi miskolci és ózdi alakzatokat változatlanul hagyva pótolja a megmaradt 18 ponttal ismert miskolci nevet. A Déli Ipari Park és a Déli Technológiai Park ugyanaz a hely: az önkormányzati 2024-es megalapozó vizsgálat 41. oldalán a korábbi név mellett leírja a 2020-ban kapott Technológiai Park címet. Egy geometria készül a névváltozatokkal; a ténykivonat és az URL a `municipal-name-facts.json` fájlban szerepel.

Az alap a megőrzött országos OSM PBF egyetlen helyi kiolvasása: 11 762 tényleges út-, vasút- és vízvonal, illetve 33 253 zárt területi alakzat. Ezekből négy áttekintő kép készül, a területek durva kézi töréspontjai a `manual-traces.json` fájlban vannak. A pont az elnevezést és a belső konzisztenciát segíti; a rajzot a tényleges környék úthálózata, beépítési és földhasználati szerkezete adja. A kontúrok következtetett összekötéseket is tartalmaznak, nem natív forráspoligonok és nem hivatalos ingatlannyilvántartási határok.

Hat déli domboldali becslés az eredeti 228357127 számú kiskertes OSM-terület külső kontúrjára is metsződik. A belső felosztásuk kézi becslés a dűlőutak alapján. A déli ipari park az eredeti 326611316 számú iparterület és a Gábor Dénes/Doni út menti bővítési sáv becsült foltjának uniója. Az újabb bővítési szél nem a hivatalos park ingatlanhatára. Az összes kimenet az eredeti miskolci településhatáron belülre van vágva.

A `context-evidence.json` az érintett tényleges forrásvonalakat sorolja fel. Ez technikai nyomkövetés, nem bizonyítja, hogy minden ilyen út a városrész határa. A névpontok belső elhelyezkedése és a geometriák érvényessége szintén nem független földrajzi pontosságmérés. A nagyobb és kisebb városrészfelosztások átfedése megengedett.

Újraépítés a mentett kontextusból, további országos olvasás vagy hálózat nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python data/neighborhoods/expansion-20261114-next/miskolc-dunaujvaros-remaining/miskolc/build.py
```

A `plot-context.py` újrarajzolja a forrásképeket. Az `extract-context.py` csak akkor kell, ha a teljes helyi nyers kontextust az azonos SHA256-ú országos PBF-ből újra ki akarjuk olvasni; az eredeti pillanatfelvétel lenyomata és licence a `pbf-source.json` fájlban megmarad. A tényleges forrásvonalak és területek is itt vannak.

Nincs körös vagy egységes sugarú pótlás. Három pont nélkül maradt nevet ebben a csomagban nem találtunk ki: Martin kertvárosi felüljáró, Szondi telep–Csorbatelep, Vologda–Jókai lakótelep. A visszaállítható munkalista a `target-names.json`.
