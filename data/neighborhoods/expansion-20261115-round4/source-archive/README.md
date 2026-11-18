# Tartalom szerint deduplikált kutatási forrásarchívum

A negyedik gyűjtési kör nyers térképei, geometriái, forrásoldalai és bizonyítékai
változatlan bájtokkal, tömörített archívumban kerülnek GitHubra. A nagy számú kis
fájl helyett legfeljebb 8 MiB-os bináris részeket tárolunk. A `manifest.json`
minden becsomagolt eredeti útvonalhoz SHA-256-ot, méretet, fájlmódot és
visszaállítási helyet rendel. Az azonos új tartalom egyszer szerepel; ami a
rögzített `19caaea641ae90080ab725fd03a68362530199a9` alapverzióban már megvan,
annak alapverziós fájljára hivatkozunk.

**Klónozás után, a kutatás újraépítése vagy térképi auditja előtt**, a tároló
gyökerében futtasd:

```sh
python3 data/neighborhoods/expansion-20261115-round4/source-archive/materialize.py
python3 data/neighborhoods/expansion-20261115-round4/source-archive/materialize.py --check
```

A parancsokhoz csak Python 3 szabványos könyvtára kell. A visszaállító ellenőrzi
az archívumrészeket, a teljes ZIP-et és minden eredeti fájlt. Meglévő, eltérő
fájlt nem ír felül. A források az eredeti útvonalaikra kerülnek, így a korábbi
szkriptek és bizonyíték-hivatkozások változatlanul használhatók. Az alapverziós
hivatkozásokat először a klón fájljaiból, szükség esetén a helyi Git-előzményből
olvassa; ehhez az alapverzió Git-objektumainak is elérhetőknek kell lenniük.
Hálózatról nem tölt le automatikusan semmit.

A 14 regisztrált bemeneti GeoJSON, az összes Python újraépítési/auditszkript,
a feladatlisták, az összes Markdown-leírás, a fontos folytatási összefoglalók és
a külön Árkosháza-jelölt közvetlen fájlok maradnak.
A meglévő kiadási tesztek és főréteg-ellenőrzés kibontás nélkül is működnek.
A `manifest.json` `directFiles` listája ezek és az archívum publikációs jegyzéke;
csak a becsomagolt, változatlan források kapnak bájtszintű hash-bejegyzést.

Az archívum ismételhetően, rögzített fájlsorrenddel és időbélyeggel készül:

```sh
python3 data/neighborhoods/expansion-20261115-round4/source-archive/build.py --check
```

Az archívum újraépítése az összes eredeti kutatási fájlt igényli, tehát klónozás
után előbb vissza kell állítani őket. A `build.py` csak helyi Git-olvasást végez;
nem módosítja a Git-indexet és nem publikál. Az eredeti helyi forrásfájlokat nem
töröltük. A letölthető poligon-ZIP továbbra is a felhasználható fő adatcsomag;
a nyers kutatási archívum külön, a GitHub-tárolóban található.
