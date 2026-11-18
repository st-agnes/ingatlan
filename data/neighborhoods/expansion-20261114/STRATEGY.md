# Gyűjtési stratégia – 2026. november 14.

A felhasználó által megadott cél: kereshető, településhez rendelt városrésznevek és poligonok; később MySQL-ben tárolva egy cím koordinátájának területi besorolására. Elsőbbséget kap a nagyvárosok minél teljesebb lefedése.

1. A gépi poligonokat külön földrajzi vagy mai névellenőrzés nélkül átvesszük. Az olvasható név, az értelmezhető koordinátarendszer és a feldolgozható geometria technikai követelmény marad.
2. Történeti, tervezési, szűkebb és tágabb felosztások egyaránt hasznosak. Különböző nevű területek átfedhetnek. Nem készítünk mesterséges, egymást kizáró városrészhálózatot.
3. Térképből és leírásból közelítő poligon is megfelel. Takart vonalszakaszok egyszerű folytatással becsülhetők; a módszert és a forrást megőrizzük.
4. Ha kizárólag névpont áll rendelkezésre, külön jelölt, dokumentált sugarú kör lehet a végső tartalék. A köröket nem számítjuk forrásból származó határvonalnak.
5. Ugyanazon település ugyanazon városrésze a végső keresési állományban egyszer szerepel. A forrásváltozatok megmaradnak; a kiválasztás rangsorát és az összevont névváltozatokat naplózzuk.
6. Az országos 80–90% cél, nem igazolt jelenlegi állapot. A kimutatás külön közli a poligonnal rendelkező ismert neveket, a csak ponttal ismert neveket és az ismeretlen teljes darabszámot.

Az eddigi kutatási állományok változatlanul megmaradnak. Az új stratégia új, egységes keresési exportot eredményez; a régi, szigorúbb kutatási statisztikák nem ennek a felhasználási szabálynak a mérőszámai.

## Mentés és folytatás

- GitHub ág: `codex/neighborhood-research-506-191`.
- Az új forráscsomagok ebben a könyvtárban, részfeladatonként külön alkönyvtárban vannak.
- A gépi állapot és a következő lépések: `WORK-STATE.json`.
- A teljesülő adatcsomagok közben is commitot és GitHub-mentést kapnak.
- Nem történik alkalmazás- vagy Google Cloud-telepítés; ez az adatgyűjtés és az importálható állomány előkészítése.
