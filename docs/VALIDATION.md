# Átadási ellenőrzések

## Sikeres

| Ellenőrzés | Eredmény |
|---|---|
| `node tests/model.test.mjs` | 9/9 sikeres |
| `node tests/frontend.test.mjs` | 7/7 sikeres, offline szimulált DOM |
| `node tests/api.test.mjs` | 8/8 sikeres, mock HTTP-válaszok |
| JavaScript szintaktikai ellenőrzése | Sikeres |
| JSON-konfigurációk és .csproj XML-fájlok beolvasása | Sikeres |
| Helyi indítószkript elkülönített ideiglenes könyvtárban | Sikeres: 8 változó, helyes sortörések, 0600 jogosultság, meglévő fájl megőrzése |
| API-útvonalak, DTO-k és árkonverzió kézi egyeztetése | Sikeres |

A modelltesztek a kemény keresési feltételeket, saját entitások kizárását, végleges döntéseket, kölcsönös találatot, kapcsolatvédelmet, egyszeri kreditlevonást, elégtelen egyenlegnél teljes visszagörgetést és újratöltés utáni megőrzést ellenőrzik.

A felületi tesztek a fő nézetek megjelenítését, a profilváltást, a kedvelést, az üzenetküldést, a profil/keresés mentését és a megszakított húzási mozdulatot ellenőrzik egy függőség nélküli DOM-szimulációban. Ez nem valódi böngészőteszt.

Az adaptertesztek tényleges backend-formátumú JSON-mintákkal ellenőrzik a típusokat, teljes HUF és millió Ft közötti átváltást, hitelesítést, döntési előzményeket, párosítási adatokat, fizetési átirányítást és hibakezelést. Futó .NET API-t nem érnek el.

## Nem futtatott

- .NET build és xUnit-tesztek: a .NET SDK nem állt rendelkezésre, a telepítéshez szükséges hálózati műveletek elakadtak.
- MySQL-integrációs smoke és párhuzamos tranzakciótesztek: a backend nem indult el ebben a környezetben.
- Valódi böngészős megjelenés és képernyőkép: a sandbox a helyi HTTP-szerver és a Chromium szükséges socketműveleteit elutasította.
- Stripe tesztfizetés és webhook: nincs beállított szolgáltatói kulcs; fizetés nem történt.
- Online közzététel: a Sites-forrás feltöltéséhez szükséges hálózati kapcsolat nem volt elérhető; működő publikált URL nem készült.

A C#-kód és a fizetési integráció forrásként átadva szerepel. A fenti futtatási ellenőrzések elvégzése előtt a szerveroldal és a fizetés nem tekinthető futás közben igazoltnak.
