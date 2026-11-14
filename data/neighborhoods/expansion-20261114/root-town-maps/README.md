# Komló és Szigetszentmiklós: gyors térképi becslés

15 alakzat: Komló 2016-os ITS-ének 10 színezett városrészcsoportja, valamint Szigetszentmiklós 2015-ös megalapozó vizsgálatának 5 negyede. A két teljes forrás-PDF, a kézzel megadott képpontkontúrok és a feldolgozó program itt maradnak.

A kontúrok a látható színezést követő egyszerűsített közelítések. A várost bemutató térképi keretet az OSM településhatár EOV-kiterjedéséhez illesztjük, és WGS84-re alakítjuk. Ez gyors, északi tájolást feltételező elhelyezés; független pontosságmérés nem történt. A takart vagy nehezen követhető részek egyszerű összekötések. A `qualityScore:20` a többi azonos nevű változat közötti relatív választást segíti, nem százalékos pontosság.

A szülőterület felsorolt tagjai nem kapják meg a teljes szülő poligonját saját határként. Például a Nyugati városrészhez tartozó Kökönyös és Mecsekfalu külön nevű kisebb terület, nem a teljes Nyugati városrész szinonimája. A különböző nevű területek átfedhetnek.

Újraépítés `pyproj` és `shapely` Python-csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114/root-town-maps/build.py
```

A forrás URL-je, éve, oldalszáma és SHA-256-a a rekordban, a nyers képpontlista a `trace-specifications.json` fájlban található. Kör alakú tartalék nincs ebben a csomagban.
