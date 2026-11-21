# Gyorsabb, változatlan lefedettségű CI

A **Build and integration tests** minden pull requestnél teljes ellenőrzést végez. A tesztesetek megmaradnak; a független ellenőrzések párhuzamos feladatokba kerültek. A valódi API-, adatbázis-, migrációs, hitelesítési és hosted böngészős tesztek továbbra is MySQL 8.0 és 8.4 mellett futnak.

## Miért volt hosszú?

A 34-es PR sikeres futásában a hosszabb MySQL-feladat 12 perc 53 másodpercig tartott. Merge után a teljes ellenőrzés újraindult, ezért egy módosítás tesztelése összesen közel félórás várakozást jelentett.

- A tároló adott verziója közel 1,4 GB fájlt tartalmazott, nagyrészt korábbi adatgyűjtési archívumot. Egyetlen checkout 47–59 másodpercig tartott, és minden feladat külön letöltötte.
- A MySQL-feladatok a JavaScript- és szimulált böngészős teszteket is egymás után, mindkét adatbázis-verzión megismételték. Ezek egy része külön feladatban is lefutott.
- Az opcionális adatimportáló tesztjében a valódi bejelentkezési korlát szándékos várakozást okoz. Ez körülbelül két perc volt a hosszú feladat végén.
- Egy PR-ághoz a push és a pull request esemény is külön teljes futást indított.

A kiinduló mérés: [34-es PR CI](https://github.com/st-agnes/ingatlan/actions/runs/44927460700).

## Mi változott?

- A JavaScript-, adatforrás- és csomagolási ellenőrzések egyszer futnak; a Docker-kép és a Cloud SQL proxy külön feladatban kap ellenőrzést.
- A szimulált/demo böngészős tesztek három párhuzamos csoportban futnak statikus szerverrel. A valódi frontend–API kapcsolatot ellenőrző hosted tesztek az adatbázisos feladatokban maradnak.
- Az opcionális API-importáló mindkét MySQL-verzión saját ideiglenes adatbázist kap. A hitelesítési korlátok és a hozzájuk tartozó várakozások változatlanok, de már a többi feladattal párhuzamosan telnek.
- A CI a teszteléshez szükséges forrásokat tölti le. A nagy kutatási archívum GitHubon marad; nem törlődik. A szükséges kanonikus poligonok és a postai adatforrások továbbra is szerepelnek a checkoutban.
- A NuGet-csomagok, a rögzített Playwright-böngésző és a Docker-build rétegei gyorsítótárat használhatnak. A csomagok visszaállítása és az ellenőrzések cache-találatnál is megtörténnek. A PR-cache-eket a GitHub áganként korlátozza; az első futás új ágon nem feltétlenül talál használható cache-t.
- A PR-ágra érkező push nem indít még egy azonos CI-t. A pull request esemény, a `main` és `codex/google-cloud-test` ág push-eseményei, valamint a kézi indítás megmaradnak.

## Merge után mi történik?

A `main` új commitja továbbra is saját CI-futást kap. Először azt ellenőrzi, hogy létezik-e sikeres teljes tesztfutás **pontosan ugyanazzal a teljes Git-fával**. Ez az alkalmazás, a tesztek, a workflow-k és az adatfájlok összes verziókezelt tartalmának egyezését jelenti; az azonos PR vagy hasonló fájllista önmagában nem elég.

Az újrafelhasználáshoz legfeljebb 24 órás, futáshoz kötött ellenőrzési bizonylat kell, valamint a megbízható tároló, workflow, tényleges checkout és minden szükséges feladat sikerének ellenőrzése. Ez a korlát a közben frissülő külső buildeszközök miatt is fontos. Újrafelhasznált futás nem készít új teljesteszt-bizonylatot. Hiányzó, lejárt, hibás vagy nem egyező bizonyíték esetén a teljes tesztsor fut le.

Így a szokásos, változatlan tartalmú merge után a második hosszú tesztkör helyett rövid bizonyíték-ellenőrzés történik. Ha közben a `main` más változtatást kapott, és a végső tartalom eltér a tesztelttől, új teljes futás szükséges.

A telepítés ellenőrzése változatlan: a **Deploy Google Cloud test** csak a kiválasztott commit sikeres `main`/kézi CI-je után kér Google-hitelesítést. A PR zöld eredménye önmagában továbbra sem indít telepítést.

## Használat

1. A PR-nél várd meg a teljes ellenőrzés sikerét.
2. Merge után várd meg az új `main` CI-jét. Egyező fájltartalom és érvényes bizonylat esetén ez már a rövid ellenőrzés.
3. Indíts új **Deploy Google Cloud test** futást a `main` ágon.

Ha bármikor ismét minden tesztet le szeretnél futtatni, válaszd az **Actions → Build and integration tests → Run workflow** lehetőséget. A kézi indítás mindig teljes ellenőrzést végez, és a default ágon létrehozott cache-eket a későbbi PR-ek is használhatják.
