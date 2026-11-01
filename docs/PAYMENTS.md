# Bankkártyás kreditvásárlás · Stripe Checkout

A .NET API Stripe Checkout fizetési integrációt tartalmaz. Az integráció használatához saját Stripe-fiók, teszteléshez tesztkulcsok, éles vásárláshoz éles kulcsok és HTTPS-en elérhető webhook szükséges. A kulcsokat kizárólag a backend környezetében kell beállítani; nem kerülnek a webes forrásba.

Szerveroldali változók:

```text
Stripe__SecretKey=sk_test_...
Stripe__WebhookSecret=whsec_...
Stripe__SuccessUrl=https://sajat-felulet.hu/?payment=success#credits
Stripe__CancelUrl=https://sajat-felulet.hu/?payment=cancel#credits
```

Fejlesztéskor a visszatérési cím lehet `http://localhost:8080/#credits`. Éles környezetben HTTPS szükséges. A visszatérési URL soha nem ír jóvá kreditet: ezt kizárólag az aláírt Stripe-esemény teheti meg. Kulcsok vagy megfelelő visszatérési címek nélkül a vásárlási végpont 503-as hibával válaszol, pénzlevonás nélkül.

## Kliens és webhook

A bejelentkezett kliens `POST /api/credits/checkout` kérést küld `{ "amount": 20 }`, `{ "amount": 60 }` vagy `{ "amount": 150 }` törzzsel. Az árak kizárólag a szerveren vannak meghatározva: 1 990 / 4 990 / 9 990 Ft. A válasz `{orderId,checkoutUrl}`; a kliens a Stripe által visszaadott biztonságos Checkout-oldalra navigál. Kártyaadatok az Otthonra szerveréhez nem jutnak el. A Stripe HUF kártyaterhelés két tizedes jegyű legkisebb egységét használjuk: az 1 990 Ft értéke a Stripe API-ban 199000. Ez eltér a HUF-kifizetések speciális kerekítési szabályától.

A Stripe webhook célja:

```text
POST https://sajat-api.hu/api/payments/stripe/webhook
```

Engedélyezett események: `checkout.session.completed`, `checkout.session.async_payment_succeeded`. A feldolgozás csak `payment_status=paid` állapotnál ad kreditet. Az API ellenőrzi a nyers törzs HMAC-SHA256 aláírását, az időbélyeg legfeljebb 5 perces eltérését, a rendelésazonosítót, a felhasználóazonosítót, a Checkout-munkamenetet, az összeget és a pénznemet. A rendelés és a felhasználó zárolása, az egyenlegmódosítás és a naplóbejegyzés egy MySQL-tranzakcióban történik. Ismételt esemény nem ad újabb kreditet; a napló elsődleges kulcsaként használt rendelésazonosító külön egyediségi védelmet ad.

A fizetés elindításának hálózati ismétléseihez a Stripe-kérés rendeléshez kötött `Idempotency-Key` fejlécet használ. A fizetési megbízások a `PaymentOrders` táblában maradnak, így az elakadt vagy visszamondott fizetések később egyeztethetők. A jelen verzió nem tartalmaz visszatérítési vagy chargeback-kezelő adminisztrációt; indulás előtt a szolgáltatóval ezeket az üzleti folyamatokat is meg kell határozni.

## Beüzemelési ellenőrzés

A sémát új adatbázisnál az EF `EnsureCreated` hozza létre. Már létező adatbázishoz a `PaymentOrders` táblát verziózott EF-migrációval kell hozzáadni; az `EnsureCreated` nem frissít meglévő sémát.

Saját Stripe tesztmódban ellenőrizendő: sikeres fizetés egyszeri jóváírással, visszamondott fizetés jóváírás nélkül, hibás/lejárt aláírás elutasítása, ugyanazon esemény ismételt és párhuzamos kézbesítése, eltérő összeg elutasítása. A munkakörnyezetben nem állt rendelkezésre Stripe-kulcs vagy futó .NET/MySQL, ezért élő vagy tesztmódú Stripe-végpontot nem hívtunk, és fizetés nem történt.
