Kecskemét – Városközpont: forrásalapú kiegészítés

Importálandó fájl: kecskemet-varoskozpont.geojson
Központi regiszterhez: registry-entry.json

Egy új finom városrészjelölt,139 eredeti OSM-koordinátával,40 eredeti úttal,
kb.290752m² területtel. Érvényes, lyukmentes, teljesen Kecskeméten belüli,
és belső területe nem fedi át a korábbi négy kecskeméti körvonalat.

A 2021-es önkormányzati leírás143.nyomtatott oldala hét határoló utcát sorol.
A 73.ábra141.nyomtatott oldali határvonalának keleti oldala a mai Bajcsy-
Zsilinszky Endre körút, amit a szomszédos Erzsébetváros szövege is alátámaszt.
További jelenlegi tér-/utcanév-átmenetek: Piaristák tere, Széchenyi tér,
Szilády Károly utca és Kölcsey utca. Ezek nem újonnan rajzolt összekötések.

Az alul-/felüljárókat és föld alatti parkolóutakat topológiaépítés előtt kizárjuk.
A névtelen belső parkolók/szervizhurkok nem városrészhatárok: ennél a körvonalnál
csak tényleges körforgalmi vagy főút-/bekötőút-szakaszokat engedünk névtelenül.
A kimenetben nem távolítunk el lyukakat, nem javítunk gyűrűt és nem pótolunk
hiányzó élt. Minden kimeneti él egymást követő eredeti OSM-csomópontokat köt össze.

A Városközpont pontos nevű jelenlegi OSM-névpontját nem találtuk. A belül lévő
Belváros-pont tágabb egység, nem helyettesíti. A finom név bizonyítéka a2021-es
önkormányzati szöveg és ábra; a mai név külön ellenőrzése hiányzik. Sem aktuális
jogi/kataszteri határt, sem abszolút helyzeti pontosságot nem állítunk. A cím-
hozzárendelés kikapcsolt. Az összehasonlító képek illesztése csak szemléltetés;
egyetlen földrajzi kimeneti koordináta sem ebből származik.

Reprodukció a tároló gyökeréből:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-offline-more.py --check
Előállítás ugyanígy --check nélkül. A --check nem ír adatfájlt.

Nyers utak: ../municipal-offline-next/kecskemet-all-local-roads.geojson.
Forrásoldalak és a teljes eredeti kiadói PDF-hash: ../municipal-maps-next/.
A trace-proof.json pontos bemeneti/kimeneti hash-eket és ellenőrzéseket tartalmaz.
A south-source-review.json független szemantikai/vizuális ellenőrzés.
Geometria: ODbL-1.0, ©OpenStreetMap contributors. Az önkormányzati illusztráció
újraközlésének joga nincs külön igazolva.

FIGYELEM: *-ordered-diagnostic.geojson, *-candidate-*.geojson és explore*.py
csak diagnosztika, nem importálandó. A Katona József téren át levágó alternatív
Városközpont belső területet hagy ki; kifejezetten elvetettük. A Kossuthváros
rövid útvonallánca érvénytelen, önmetsző. Ezek nem helyettesítik a jóváhagyott
forrásértelmezést. Árpádváros és Kossuthváros parkolóút-határa egyelőre nem
szerepel az exportban; a hiány nem jelenti azt, hogy nincs további forrás.
