using System.Globalization;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Otthonra.Api;

public sealed class ApiException(int status, string message) : Exception(message) { public int Status { get; } = status; }
public static class Rules
{
    public const int SellerLikeCost = 2;
    public const int AgentSearchLikeCost = 1;
    public static Guid UserId(this ClaimsPrincipal principal) => Guid.Parse(principal.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new ApiException(401, "Bejelentkezés szükséges."));
    public static string Required(string? value, string field, int max = 255)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Trim().Length > max) throw new ApiException(400, $"A(z) {field} kötelező, legfeljebb {max} karakter lehet.");
        return value.Trim();
    }
    public static string Optional(string? value, int max = 255)
    {
        if ((value?.Length ?? 0) > max) throw new ApiException(400, $"A szöveg legfeljebb {max} karakter lehet.");
        return value?.Trim() ?? "";
    }
    public static string Email(string? value)
    {
        var email = Required(value, "e-mail-cím").ToLowerInvariant();
        if (!new System.ComponentModel.DataAnnotations.EmailAddressAttribute().IsValid(email)) throw new ApiException(400, "Érvénytelen e-mail-cím.");
        return email;
    }
    public static void Password(string? value)
    {
        if (value is null || value.Length < 10 || value.Length > 128) throw new ApiException(400, "A jelszó 10–128 karakter hosszú legyen.");
    }
    public static string PublicText(string? value, int max = 5000)
    {
        var text = Optional(value, max);
        if (Regex.IsMatch(text, @"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}") || Regex.IsMatch(text, @"(?:\+?36|06)[\s().-]*(?:\d[\s().-]*){8,9}"))
            throw new ApiException(400, "Elérhetőséget csak kölcsönös párosítás után lehet megosztani. A nyilvános szövegből távolítsd el az e-mail-címet és telefonszámot.");
        return text;
    }
    public static string Normalize(string value) => string.Concat(value.Normalize(NormalizationForm.FormD).Where(c => CharUnicodeInfo.GetUnicodeCategory(c) != UnicodeCategory.NonSpacingMark)).ToUpperInvariant().Trim();
    public static bool Compatible(Property p, SearchRequest s) => MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s), includeReasons: false).IsExact;
    public static bool Within(decimal value, decimal? min, decimal? max) => (!min.HasValue || value >= min.Value) && (!max.HasValue || value <= max.Value);
    public static void Range(decimal? min, decimal? max, string name)
    {
        if (min < 0 || max < 0 || min > max) throw new ApiException(400, $"Érvénytelen {name} tartomány.");
    }
    public static int Score(Property p, SearchRequest s) => MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s), includeReasons: false).Score;
    public static string[] Reasons(Property p, SearchRequest s) => MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Reasons;
    // Explicit counts preserve compositions such as 2 whole + 3 half rooms.
    // Only lossless half-step legacy totals can be displayed as separate counts.
    public static (int? WholeRooms, int? HalfRooms) RoomCounts(Property property)
    {
        if (property.WholeRooms.HasValue || property.HalfRooms.HasValue)
            return (property.WholeRooms, property.HalfRooms);
        return LegacyRoomCounts(property.Rooms);
    }
    private static (int? WholeRooms, int? HalfRooms) LegacyRoomCounts(decimal rooms)
    {
        if (rooms <= 0 || rooms > 1000 || rooms * 2 % 1 != 0) return (null, null);
        var whole = (int)decimal.Truncate(rooms);
        return (whole, (int)((rooms - whole) * 2));
    }
    public static void Apply(Property p, PropertyInput i)
    {
        p.Title = Required(PublicText(i.Title, 150), "cím", 150); p.Type = Required(PublicText(i.Type, 50), "ingatlantípus", 50);
        var location = LocationCatalog.ResolvePropertyInput(i.LocationId, i.City, i.District);
        p.LocationId = location.Id; p.City = location.City; p.District = location.District ?? "";
        var house = Normalize(p.Type) == "HAZ";
        var explicitRoomCounts = i.WholeRooms.HasValue || i.HalfRooms.HasValue;
        var wholeRooms = i.WholeRooms ?? 0;
        var halfRooms = i.HalfRooms ?? 0;
        var rooms = explicitRoomCounts ? (decimal)wholeRooms + halfRooms / 2m : i.Rooms;
        if (i.Price <= 0 || i.Price > 1_000_000_000_000m || i.Area <= 0 || i.Area > 1_000_000 || rooms <= 0 || rooms > 1000
            || wholeRooms < 0 || wholeRooms > 1000 || halfRooms < 0 || halfRooms > 1000
            || i.Rooms < 0 || explicitRoomCounts && i.Rooms > 0 && i.Rooms != rooms
            || !house && (i.Floor < -5 || i.Floor > 200 || (i.Floor < -1 && i.Floor != p.Floor)))
            throw new ApiException(400, "Az ár, alapterület, szobaszám vagy emelet érvénytelen.");
        if (house && (!i.LotArea.HasValue || i.LotArea <= 0 || i.LotArea > 10_000_000))
            throw new ApiException(400, "Ház esetén a telekméret kötelező, pozitív szám legyen, legfeljebb 10 000 000 m².");
        var savedCounts = explicitRoomCounts ? (WholeRooms: (int?)wholeRooms, HalfRooms: (int?)halfRooms)
            : rooms == p.Rooms && (p.WholeRooms.HasValue || p.HalfRooms.HasValue) ? RoomCounts(p)
            : LegacyRoomCounts(rooms);
        p.Price = i.Price; p.Area = i.Area; p.Rooms = rooms; p.Floor = house ? null : i.Floor;
        p.WholeRooms = savedCounts.WholeRooms;
        p.HalfRooms = savedCounts.HalfRooms;
        p.LotArea = house ? i.LotArea : null;
        p.Neighborhood = PublicText(i.Neighborhood, 100); p.Address = Optional(i.Address, 255); p.Description = PublicText(i.Description);
        PropertyAttributes.Apply(p, i); p.Balcony = !house && i.Balcony; p.Elevator = !house && i.Elevator; p.Archived = i.Archived;
        var images = i.Images ?? [];
        if (images.Length > 12 || images.Any(x => !Uri.TryCreate(x, UriKind.Absolute, out var uri) || uri.Scheme != "https" || x.Length > 2000)) throw new ApiException(400, "Legfeljebb 12 HTTPS-képhivatkozás adható meg.");
        p.ImagesJson = System.Text.Json.JsonSerializer.Serialize(images);
        if (p.ImagesJson.Length > 10000) throw new ApiException(400, "A képhivatkozások összesen legfeljebb 10 000 karakter hosszúak lehetnek.");
    }
    public static void Apply(SearchRequest s, SearchInput i)
    {
        s.Title = Required(PublicText(i.Title, 150), "megnevezés", 150); s.Type = Required(PublicText(i.Type, 50), "ingatlantípus", 50);
        Range(i.MinPrice, i.MaxPrice, "ár"); Range(i.MinArea, i.MaxArea, "alapterület"); Range(i.MinRooms, i.MaxRooms, "szobaszám");
        s.MinPrice = i.MinPrice; s.MaxPrice = i.MaxPrice; s.MinArea = i.MinArea; s.MaxArea = i.MaxArea; s.MinRooms = i.MinRooms; s.MaxRooms = i.MaxRooms;
        var districts = i.Districts ?? [];
        if (districts.Length > 50 || districts.Any(x => x is null || x.Length > 50)) throw new ApiException(400, "Érvénytelen kerületlista.");
        var locations = LocationCatalog.ResolveSearchInput(i.LocationIds, i.City, districts);
        s.LocationIdsJson = System.Text.Json.JsonSerializer.Serialize(locations.Select(x => x.Id));
        s.City = locations[0].City;
        var sameCity = locations.Where(x => x.City == s.City).ToArray();
        s.DistrictsJson = System.Text.Json.JsonSerializer.Serialize(sameCity.Any(x => x.District is null) ? Array.Empty<string>() : sameCity.Select(x => x.District!).Distinct());
        PropertyAttributes.Apply(s, i);
        s.Description = PublicText(i.Description); s.MoveIn = PublicText(i.MoveIn, 100); s.Financing = PublicText(i.Financing, 255); s.Balcony = Normalize(s.Type) != "HAZ" && i.Balcony; s.Elevator = Normalize(s.Type) != "HAZ" && i.Elevator; s.Archived = i.Archived;
    }
}
public static class Passwords
{
    public static string Hash(string password)
    {
        var salt = RandomNumberGenerator.GetBytes(16);
        var key = Rfc2898DeriveBytes.Pbkdf2(password, salt, 210_000, HashAlgorithmName.SHA256, 32);
        return $"210000.{Convert.ToBase64String(salt)}.{Convert.ToBase64String(key)}";
    }
    public static bool Verify(string password, string hash)
    {
        try { var parts = hash.Split('.'); var expected = Convert.FromBase64String(parts[2]); return CryptographicOperations.FixedTimeEquals(Rfc2898DeriveBytes.Pbkdf2(password, Convert.FromBase64String(parts[1]), int.Parse(parts[0]), HashAlgorithmName.SHA256, expected.Length), expected); }
        catch (Exception e) when (e is FormatException or IndexOutOfRangeException or ArgumentException) { return false; }
    }
}
