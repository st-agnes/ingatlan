Kecskemét, 77. ábra — külön befogadási helyesbítés

A municipal-kecskemet-native77-first csomag változatlanul fagyasztott.
Az eredeti csomag hét archivált jelöltet tartalmaz; a tényleges projektvalidátor
hat becsült rekordot fogad el, a középső Szent László-forráscellát karanténba teszi.
A korábbi 7/7 befogadhatósági állítás túl tág volt: a Shapely-validitás és az
eredeti forrásélek megőrzése nem helyettesíti a projekt saját validátorát.

Az ok az eredeti natív forrásban létezik. A Kósafalu-lyuk a középső cella külső
héját a pontos (207.51, 568.81) natív pontban érinti. Ugyanez Rendőrfalu egyik
csomópontja. A lyuknak nincs pozitív területe a külső héjon kívül, és az outer/
hole szerepek sem cserélődtek fel. A pontérintést a projekt szándékosan
hole_outside_shell indokkal utasítja el. Nem vetületi vagy kerekítési hiba.

A geometriát nem javítjuk, nem töröljük a lyukat és nem kényszerítjük be az
exportba. A megőrzött forráscella külön karanténban marad; a másik hat rekord
változatlanul csak a becsült rétegre alkalmas. Új geometriát vagy registry-entryt
ez a helyesbítés nem hoz létre, globális regisztert nem módosít.

Két külön parser olvassa újra az eredeti Form streamet, ellenőrzi a pontos
decimális pontismétlést és meghívja a változatlan scripts/neighborhoods/build.mjs
valódi validateGeometry függvényét. Mindkettő eredménye: hat PASS, egy elutasítás.
A fagyasztott első csomag összes ellenőrzőösszege változatlan.

PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-native77-admission-review/audit-admission.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-native77-admission-review/audit-independent.py --check
