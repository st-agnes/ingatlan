# Hajdúböszörmény – Belváros

Egyetlen, 0,542 km²-es, teljes központi területet lefedő WGS84 Polygon. Importálandó fájl: `features.geojson`. A becslés a Kiskörúton belüli Belváros központi egységét követi; nem egy apró épület vagy pont körüli pótlás.

Az önkormányzat 25/2025. (VI. 30.) rendeletének 4. § 6. pontja kilenc utcával/térrel határozza meg a Kiskörút központi területét: Bethlen Gábor utca, Újfehértói utca, Ady Endre tér, Korpona utca, Kálvin tér, Szent István tér, Árpád utca, Vörösmarty Mihály utca, Polgári utca. A 35/2019. településképi rendelet 15. § (2) a)–b) külön nevezi meg a Belvárost és a Kiskörúton kívüli vegyes karakterű településrészt. Az elolvasott szöveg és a forráshelyek a `source-definition.json` fájlban maradnak; natív önkormányzati PDF-geometriát nem állítunk.

A kilenc név tényleges, archivált OSM-útvonalai és egy rövid, névtelen körforgalmi csatlakozás zárt külső kört alkotnak. Mind a kilenc forrásutca képviselve van a 18 külső forrásút-darabon. Az Újfehértói út a jelenlegi OSM-ben `út`, a rendeletben `utca` néven szerepel. A külső határ összes éle tényleges forrásútvonalon fekszik; nem készült mesterséges lezárás, illesztés, kör, sugár vagy pontból generált téglalap. A négy belső parkoló-/úthurkot kitöltöttük, mert az általuk közrefogott belső terület is a központhoz tartozik.

Az utcai középvonalak használata városrészi keresési becslés, nem telekhatáros jogi lehatárolás. Ezért az alakzat továbbra is alacsony biztonságú becslés, annak ellenére, hogy a tényleges külső útgeometria megmarad. A Belváros esetleges tágabb történeti vagy szabályozási értelmezése nincs e csomaggal teljes körűen megállapítva.

Újraépítés kizárólag a helyi forrásokból, `shapely` és `pyproj` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/hajduboszormeny/build.py
```

A `summary.json` és `validation.json` ellenőrzi a geometriát, a teljes települési befoglalást, a névpont befoglalását, a kilenc forrásutca jelenlétét és a forrásvonalhoz tartozó külső éleket. A forráspont csak a megfelelő teljes kör kiválasztását segíti. © OpenStreetMap contributors, ODbL-1.0.
