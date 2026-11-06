using System.Globalization;
using System.Text.Json;

namespace Otthonra.Api;

public sealed record Location(string Id, string Label, string City, string? District, string Kind = "city", int? SettlementCount = null);

/// <summary>The same versioned, local municipality and city-area catalogues are used by the web and API.</summary>
public static class LocationCatalog
{
    private static readonly string[] Romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII"];
    private sealed record CatalogueData(Location[] Locations, Dictionary<string, HashSet<string>> AreaMembers);
    private static readonly Lazy<CatalogueData> Catalogue = new(Load);
    private static readonly Lazy<Dictionary<string, Location>> ById = new(() => All.ToDictionary(x => x.Id, StringComparer.Ordinal));
    public static IReadOnlyList<Location> All => Catalogue.Value.Locations;

    private static CatalogueData Load()
    {
        using var stream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Settlements.json")
            ?? throw new InvalidOperationException("The embedded settlement catalogue is missing.");
        using var document = JsonDocument.Parse(stream);
        var names = document.RootElement.GetProperty("settlements").EnumerateArray().Select(x => x.GetString()!)
            .Where(x => !string.IsNullOrWhiteSpace(x)).Distinct(StringComparer.Ordinal).ToArray();
        if (names.Length < 3000 || !names.Contains("Budapest")) throw new InvalidOperationException("The settlement catalogue is incomplete.");
        var knownNames = new HashSet<string>(names, StringComparer.Ordinal);
        var cities = names.Select(name => new Location("city:" + name, name, name, null));
        var districts = Romans.Select((roman, index) => new Location($"district:Budapest:{index + 1}", $"Budapest {roman}. kerület", "Budapest", roman + ".", "district"));
        using var areaStream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Agglomerations.json")
            ?? throw new InvalidOperationException("The embedded city-area catalogue is missing.");
        using var areaDocument = JsonDocument.Parse(areaStream);
        if (areaDocument.RootElement.GetProperty("schemaVersion").GetInt32() != 1)
            throw new InvalidOperationException("The city-area catalogue schema is not supported.");
        var areas = new List<Location>();
        var membersById = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        var areaCities = new HashSet<string>(StringComparer.Ordinal);
        foreach (var area in areaDocument.RootElement.GetProperty("areas").EnumerateArray())
        {
            var id = area.GetProperty("id").GetString();
            var city = area.GetProperty("city").GetString();
            var members = area.GetProperty("settlements").EnumerateArray().Select(x => x.GetString()).ToArray();
            if (city is null || !knownNames.Contains(city) || id != "area:" + city || !areaCities.Add(city)
                || members.Length < 2 || members.Any(x => x is null || !knownNames.Contains(x))
                || members.Distinct(StringComparer.Ordinal).Count() != members.Length || !members.Contains(city))
                throw new InvalidOperationException("A city area contains invalid, duplicated or unknown settlements.");
            var memberSet = new HashSet<string>(members.Select(x => x!), StringComparer.Ordinal);
            if (!membersById.TryAdd(id!, memberSet)) throw new InvalidOperationException("The city-area catalogue contains duplicated IDs.");
            areas.Add(new Location(id!, $"{city} és környéke ({memberSet.Count} település)", city, null, "area", memberSet.Count));
        }
        if (areas.Count == 0) throw new InvalidOperationException("The city-area catalogue is empty.");
        return new CatalogueData(cities.Concat(districts).Concat(areas).ToArray(), membersById);
    }

    public static Location? Get(string? id) => id is not null && ById.Value.TryGetValue(id, out var result) ? result : null;
    public static string Normalize(string? value) => Rules.Normalize(value ?? "");
    private static int? DistrictNumber(string? value)
    {
        var clean = Normalize(value).Replace("BUDAPEST", "").Replace("KERULET", "").Replace(".", "").Trim();
        if (int.TryParse(clean, NumberStyles.None, CultureInfo.InvariantCulture, out var number) && number is >= 1 and <= 23) return number;
        var index = Array.IndexOf(Romans, clean);
        return index < 0 ? null : index + 1;
    }

    public static Location[] ResolveLegacy(string? city, IEnumerable<string?>? districts = null)
    {
        var normalized = Normalize(city);
        var direct = All.FirstOrDefault(x => x.Kind != "area" && Normalize(x.Label) == normalized);
        if (direct?.District is not null) return [direct];
        if (normalized.StartsWith("BUDAPEST ", StringComparison.Ordinal))
        {
            var districtNumber = DistrictNumber(city);
            return districtNumber.HasValue ? [Get($"district:Budapest:{districtNumber}")!] : [];
        }
        var place = All.FirstOrDefault(x => x.Kind == "city" && Normalize(x.City) == normalized);
        if (place is null) return [];
        if (place.City != "Budapest") return [place];
        var requested = districts?.Where(x => !string.IsNullOrWhiteSpace(x)).ToArray() ?? [];
        if (requested.Length == 0) return [place];
        var result = requested.Select(DistrictNumber).ToArray();
        if (result.Any(x => !x.HasValue)) return [];
        return result.Select(x => Get($"district:Budapest:{x}")!).DistinctBy(x => x.Id).ToArray();
    }

    public static Location ResolvePropertyInput(string? id, string? city, string? district)
    {
        var result = id is not null ? Get(id) : ResolveLegacy(city, string.IsNullOrWhiteSpace(district) ? [] : [district]).SingleOrDefault();
        if (result is null || result.Kind == "area") throw new ApiException(400, "Az ingatlanhoz egy konkrét települést vagy budapesti kerületet válassz.");
        return result;
    }

    public static Location[] ResolveSearchInput(string[]? ids, string? city, string[]? districts)
    {
        if (ids is null)
        {
            var legacy = ResolveLegacy(city, districts);
            if (legacy.Length == 0) throw new ApiException(400, "Válassz legalább egy helyszínt a listából.");
            return legacy;
        }
        if (ids.Length is 0 or > 50) throw new ApiException(400, "Legalább egy, legfeljebb 50 helyszínt választhatsz.");
        var result = ids.Select(Get).ToArray();
        if (result.Any(x => x is null)) throw new ApiException(400, "A kiválasztott helyszín nem található a településlistában.");
        return result.Select(x => x!).DistinctBy(x => x.Id).ToArray();
    }

    public static Location? ForProperty(Property property)
    {
        // Even malformed persisted area IDs must never become a precise home
        // location through the old center-city fallback.
        if (property.LocationId?.StartsWith("area:", StringComparison.Ordinal) == true) return null;
        return Get(property.LocationId)
            ?? ResolveLegacy(property.City, string.IsNullOrWhiteSpace(property.District) ? [] : [property.District]).FirstOrDefault();
    }

    public static Location[] ForSearch(SearchRequest search)
    {
        var ids = Dto.Strings(search.LocationIdsJson);
        if (ids.Length > 0)
        {
            var result = ids.Select(Get).ToArray();
            return result.Any(x => x is null) ? [] : result.Select(x => x!).DistinctBy(x => x.Id).ToArray();
        }
        return ResolveLegacy(search.City, Dto.Strings(search.DistrictsJson));
    }

    public static bool Matches(Property property, SearchRequest search)
    {
        var place = ForProperty(property);
        if (place is null || place.Kind == "area") return false;
        return ForSearch(search).Any(wanted => wanted.Kind == "area"
            ? Catalogue.Value.AreaMembers.TryGetValue(wanted.Id, out var members) && members.Contains(place.City)
            : wanted.City == place.City && (wanted.District is null || wanted.District == place.District));
    }

    public static Location[] Search(string? query, int limit = 8, string? kind = null)
    {
        kind = kind?.Trim().ToLowerInvariant() ?? "search";
        if (kind is not ("property" or "search")) throw new ApiException(400, "Érvénytelen helyszínválasztási típus.");
        var candidates = All.Where(x => kind == "search" || x.Kind != "area");
        var value = Normalize(query);
        limit = Math.Clamp(limit, 1, 25);
        if (value.Length == 0) return candidates.Where(x => x.Kind == "city").OrderBy(x => x.City == "Budapest" ? 0 : 1).ThenBy(x => x.Label, StringComparer.Create(CultureInfo.GetCultureInfo("hu-HU"), false)).Take(limit).ToArray();
        var directDistrict = value.StartsWith("BUDAPEST", StringComparison.Ordinal) ? DistrictNumber(query) : null;
        var words = value.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return candidates.Select(x => new {
                Location = x, DisplayLabel = Normalize(x.Label), Label = Normalize(x.Kind == "area" ? $"{x.City} és környéke" : x.Label), City = Normalize(x.City),
                Words = Normalize(x.Kind == "area" ? $"{x.City} és környéke {x.City} agglomeráció {x.City} térsége" : x.Label).Split(' ', StringSplitOptions.RemoveEmptyEntries)
            })
            .Where(x => x.DisplayLabel == value || x.Label.Contains(value, StringComparison.Ordinal)
                || words.All(word => x.Words.Any(part => part.StartsWith(word, StringComparison.Ordinal)))
                || directDistrict.HasValue && x.Location.Id == $"district:Budapest:{directDistrict}")
            .OrderBy(x => directDistrict.HasValue && x.Location.Id == $"district:Budapest:{directDistrict}" ? -1
                : x.DisplayLabel == value || x.Label == value ? 0 : x.Location.Kind == "area" && x.City == value ? 1 : x.Label.StartsWith(value, StringComparison.Ordinal) ? 2 : 3)
            .ThenBy(x => x.Location.Label, StringComparer.Create(CultureInfo.GetCultureInfo("hu-HU"), false)).Take(limit).Select(x => x.Location).ToArray();
    }
}
