using System.Globalization;
using System.Text.Json;

namespace Otthonra.Api;

public sealed record Location(string Id, string Label, string City, string? District);

/// <summary>The same versioned, local municipality catalogue is used by the web and API.</summary>
public static class LocationCatalog
{
    private static readonly string[] Romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII"];
    private static readonly Lazy<Location[]> Catalogue = new(Load);
    private static readonly Lazy<Dictionary<string, Location>> ById = new(() => Catalogue.Value.ToDictionary(x => x.Id, StringComparer.Ordinal));
    public static IReadOnlyList<Location> All => Catalogue.Value;

    private static Location[] Load()
    {
        using var stream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Settlements.json")
            ?? throw new InvalidOperationException("The embedded settlement catalogue is missing.");
        using var document = JsonDocument.Parse(stream);
        var names = document.RootElement.GetProperty("settlements").EnumerateArray().Select(x => x.GetString()!)
            .Where(x => !string.IsNullOrWhiteSpace(x)).Distinct(StringComparer.Ordinal).ToArray();
        if (names.Length < 3000 || !names.Contains("Budapest")) throw new InvalidOperationException("The settlement catalogue is incomplete.");
        var cities = names.Select(name => new Location("city:" + name, name, name, null));
        var districts = Romans.Select((roman, index) => new Location($"district:Budapest:{index + 1}", $"Budapest {roman}. kerület", "Budapest", roman + "."));
        return cities.Concat(districts).ToArray();
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
        var direct = Catalogue.Value.FirstOrDefault(x => Normalize(x.Label) == normalized);
        if (direct?.District is not null) return [direct];
        if (normalized.StartsWith("BUDAPEST ", StringComparison.Ordinal))
        {
            var districtNumber = DistrictNumber(city);
            return districtNumber.HasValue ? [Get($"district:Budapest:{districtNumber}")!] : [];
        }
        var place = Catalogue.Value.FirstOrDefault(x => x.District is null && Normalize(x.City) == normalized);
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
        return result ?? throw new ApiException(400, "Válassz egy települést vagy budapesti kerületet a listából.");
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

    public static Location? ForProperty(Property property) => Get(property.LocationId)
        ?? ResolveLegacy(property.City, string.IsNullOrWhiteSpace(property.District) ? [] : [property.District]).FirstOrDefault();

    public static Location[] ForSearch(SearchRequest search)
    {
        var ids = Dto.Strings(search.LocationIdsJson);
        if (ids.Length > 0) return ids.Select(Get).Where(x => x is not null).Select(x => x!).DistinctBy(x => x.Id).ToArray();
        return ResolveLegacy(search.City, Dto.Strings(search.DistrictsJson));
    }

    public static bool Matches(Property property, SearchRequest search)
    {
        var place = ForProperty(property);
        return place is not null && ForSearch(search).Any(wanted => wanted.City == place.City && (wanted.District is null || wanted.District == place.District));
    }

    public static Location[] Search(string? query, int limit = 8)
    {
        var value = Normalize(query);
        limit = Math.Clamp(limit, 1, 25);
        if (value.Length == 0) return Catalogue.Value.Where(x => x.District is null).OrderBy(x => x.City == "Budapest" ? 0 : 1).ThenBy(x => x.Label, StringComparer.Create(CultureInfo.GetCultureInfo("hu-HU"), false)).Take(limit).ToArray();
        var directDistrict = value.StartsWith("BUDAPEST", StringComparison.Ordinal) ? DistrictNumber(query) : null;
        return Catalogue.Value.Select(x => new { Location = x, Label = Normalize(x.Label) })
            .Where(x => x.Label.Contains(value, StringComparison.Ordinal) || (directDistrict.HasValue && x.Location.Id == $"district:Budapest:{directDistrict}"))
            .OrderBy(x => directDistrict.HasValue && x.Location.Id == $"district:Budapest:{directDistrict}" ? 0 : x.Label == value ? 1 : x.Label.StartsWith(value, StringComparison.Ordinal) ? 2 : 3)
            .ThenBy(x => x.Location.Label, StringComparer.Create(CultureInfo.GetCultureInfo("hu-HU"), false)).Take(limit).Select(x => x.Location).ToArray();
    }
}
