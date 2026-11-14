# Kiegészítés: Békéscsaba

Az `additional-features.geojson` 26 további, hozzávetőlegesen becsült városrészt
ad a már meglevő hat színes önkormányzati forráskontúr mellé. A régi
Szolnok–Veszprém 48 rekordos csomag változatlan marad.

A megőrzött önkormányzati térkép sok helynevet és utcát, csatornát, telektömböt
ábrázol, de nem húzza meg mindegyik alvárosrész külön határát. Ezért a köztes
választóvonalak itt kézi **becslések**: a térkép úthálózati/mezőgazdasági
rácsához, vízfolyásaihoz, színes beépítési foltjaihoz és a névvel azonosított
helyek elhelyezkedéséhez igazodó egyszerűsített sokszögek. A leírásuk nem állítja,
hogy a belső vonalak forráspontosságú vagy jogi határok. Kör-, Voronoi- és
szülőpoligon-másolásos pótlás nincs a csomagban.

Öt név közvetlenül a térképen szerepel: Kisrét, Felsőnyomás, Nagyrét, Fürjes,
Kerek. További 21 belső/gazdasági/kertvárosi terület elnevezése és elhelyezkedése
a már archivált, településhez rendelt OSM névpontokból jön. Ezeket a
`bekescsaba-name-position-evidence.json` őrzi, a térképi elhelyezésüket a
`bekescsaba-name-overlay.png` mutatja. A határbecslés minden ilyen névhez
tartalmazza a névpontot, de ez önmagában nem igazolja a határ pontosságát.

A földrajzi transzformáció a korábban megőrzött
`sources/municipal-east/bekescsaba-geometry-proof.json` affin illesztését
használja (EOV, majd WGS84). A szülőtelepülés körvonalának jó illeszkedése nem
igazolja a most becsült belső választóvonalak pontosságát. A teljes abszolút
pontosság ismeretlen.

Újraépítés: `python3 reproduce-additional.py`, NumPy/PyProj/Shapely
függőségekkel. A 26 alakzat érvényes Polygon/MultiPolygon, magyarországi
WGS84 koordinátákkal. A teljes csomag város+név duplikációit a közös exportáló
kezeli. Forrás és licencmegjegyzés minden rekordban szerepel.
