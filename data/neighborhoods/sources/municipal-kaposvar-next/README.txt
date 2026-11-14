Kaposvár – Belváros: forrásfeltárás és tényleges OSM-útadat, új poligon nélkül

Nincs importálandó városrészgeometria és nincs registry-entry.json.
A boundary-obstacles.json részletesen megőrzi, mi hiányzik a 2009-es és a
2026-os, egymástól eltérő határleírás tényleges földrajzi lezárásához.

A teljes helyi PBF-ből 3581 valódi út- és vasútszakasz készült, beleértve a
névtelen kereszteződési ágakat. A koordináták és OSM nodeRef/tag/verzió adatok
változatlanok; a befoglaló téglalap csak az adatkinyerést határolja, nem lesz
városrészpoligon. Az extraction-proof.json rögzíti a teljes PBF és a nyers
kimenet lenyomatát.

A szöveges határleírásokból a jelenlegi úttengelyek nem alkotnak zárt körvonalat.
Az Áchim András utca és Petőfi tér között kb.315m hiányzik a szó szerint
megnevezett utcákból. A köztes Újpiac tér már2007-ben is önálló hivatalos név
volt; elnevezésváltozást nem igazoltunk. A Virág–48-as közötti Árpád-szakaszt
a2023-as FVS kifejezetten megnevezi, de további csomóponti átmenetek és
vasút–út találkozások értelmezése ettől még megoldatlan.

A2009-es listában Gyékényesi, a2026-os jogszabályban Fonyódi vasútvonal szerepel;
a két nyugati határváltozatot nem cseréljük fel és nem keverjük össze. A2009-es
és2008-as forrás-PDF-et a webes olvasó méretkorlát miatt nem nyitotta meg.
Nyers PDF-fájl vagy PDF-hash ezért nincs állítva. Új határt nem rajzoltunk.

Újrahasználható helyi adatok:
  all-local-roads-rails.geojson
  extraction-proof.json
  boundary-obstacles.json

Hálózat nélküli újbóli kinyerés és diagnosztika a tároló gyökerében:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kaposvar-next.py --extract --audit

Az adat ODbL-1.0, © OpenStreetMap contributors. A hivatalos források tényadatai
külön URL-lel hivatkozottak; ez a munka nem igazolja az önkormányzati
kiadványok teljes újraközlésének licencét, a jelenlegi jogi határt vagy a
házszintű címbesorolást.
