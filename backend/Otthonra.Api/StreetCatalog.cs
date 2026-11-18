using System.Globalization;
using System.IO.Compression;
using System.Text;
using System.Text.Json;

namespace Otthonra.Api;

public sealed record PostalStreet(string Id, string City, string? District, string Name, string Type,
    string StreetName, string Label, string[] PostalCodes, string[] Aliases);

/// <summary>Local postal street identities. Addresses and geocoding remain property specific.</summary>
public static class StreetCatalog
{
    public const int ExpectedCount = 123354;
    public const string ExpectedSourceSha256 = "e6ce188aa0c01399eb31ea8385cebce94292af0890d8d72a663fd5d41f0005ca";
    public const string ExpectedDatasetVersion = "e397f60ecfbbd8c0708137d9f87e19bb3f6634917a3cab7b594f6c1d1ff7a0a7";
    internal const string ResourceName = "Otthonra.Api.Streets.json.gz";
    private static readonly string[] Romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII"];
    private readonly record struct PrefixRow(string Key, int Index);
    private sealed record SearchRow(PostalStreet Street, string Name, string[] Words);
    private sealed record Catalogue(PostalStreet[] Streets, Dictionary<string, PostalStreet> ById,
        Dictionary<string, PostalStreet[]> ByName, HashSet<string> Cities, SearchRow[] SearchRows,
        PrefixRow[] NameFirst, PrefixRow[] CityFirst, string Version);
    private static readonly Lazy<Catalogue> Data = new(Load);
    public static IReadOnlyList<PostalStreet> All => Data.Value.Streets;
    public static string DatasetVersion => Data.Value.Version;
    public static PostalStreet? Get(string? id) => id is not null && Data.Value.ById.TryGetValue(id, out var street) ? street : null;

    internal static Stream OpenRuntimeStream()
    {
        var stream = typeof(StreetCatalog).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("The embedded postal street catalogue is missing.");
        return new GZipStream(stream, CompressionMode.Decompress);
    }

    private static Catalogue Load()
    {
        // Do not call LocationCatalog here: its public Get also resolves streets.
        using var cityStream = typeof(StreetCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Settlements.json")
            ?? throw new InvalidOperationException("The embedded municipality catalogue is missing.");
        using var cityDocument = JsonDocument.Parse(cityStream);
        var cities = cityDocument.RootElement.GetProperty("settlements").EnumerateArray().Select(x => x.GetString()!)
            .ToHashSet(StringComparer.Ordinal);
        var streets = new List<PostalStreet>();
        var byId = new Dictionary<string, PostalStreet>(StringComparer.Ordinal);
        string? version = null;
        var expectedCount = 0;
        using var stream = OpenRuntimeStream();
        // DeserializeAsyncEnumerable reads one array element at a time; the full
        // decompressed JSON document is never retained beside the indexes.
        var enumerator = JsonSerializer.DeserializeAsyncEnumerable<JsonElement>(stream).GetAsyncEnumerator();
        try
        {
            while (enumerator.MoveNextAsync().AsTask().GetAwaiter().GetResult())
            {
                var element = enumerator.Current;
                if (version is null)
                {
                    ValidateHeader(element);
                    version = element.GetProperty("datasetVersion").GetString()!;
                    expectedCount = element.GetProperty("count").GetInt32();
                    continue;
                }
                var street = ParseRow(element);
                if (!cities.Contains(street.City) || !ValidId(street.Id)
                    || string.IsNullOrWhiteSpace(street.Name) || street.Name.Length > 255 || street.Type.Length > 128
                    || string.IsNullOrWhiteSpace(street.StreetName) || street.StreetName.Length > 384
                    || string.IsNullOrWhiteSpace(street.Label) || street.Label.Length > 600
                    || street.District is not null && (street.City != "Budapest" || !Romans.Any(roman => street.District == roman + "."))
                    || street.PostalCodes.Length == 0 || street.PostalCodes.Any(x => x.Length != 4 || x.Any(c => c is < '0' or > '9'))
                    || street.PostalCodes.Distinct(StringComparer.Ordinal).Count() != street.PostalCodes.Length
                    || street.Aliases.Any(x => string.IsNullOrWhiteSpace(x) || x.Length > 384)
                    || !byId.TryAdd(street.Id, street))
                    throw new InvalidOperationException("The postal street catalogue contains invalid or duplicate metadata.");
                streets.Add(street);
            }
        }
        finally { enumerator.DisposeAsync().AsTask().GetAwaiter().GetResult(); }
        if (version is null || streets.Count != expectedCount)
            throw new InvalidOperationException("The postal street catalogue is incomplete.");

        var byName = new Dictionary<string, List<PostalStreet>>(StringComparer.Ordinal);
        var rows = new SearchRow[streets.Count];
        var nameFirst = new List<PrefixRow>(streets.Count * 3);
        var cityFirst = new List<PrefixRow>(streets.Count * 2);
        for (var index = 0; index < streets.Count; index++)
        {
            var street = streets[index];
            var names = street.Aliases.Append(street.StreetName).Select(Text).Distinct(StringComparer.Ordinal).ToArray();
            foreach (var name in street.Aliases.Append(street.StreetName).Select(StreetKey).Distinct(StringComparer.Ordinal))
            {
                var key = NameKey(street.City, name);
                if (!byName.TryGetValue(key, out var entries)) byName[key] = entries = [];
                entries.Add(street);
            }
            var city = Text(street.City);
            var district = street.District is null ? "" : Text(street.District) + " " + DistrictNumber(street.District)?.ToString(CultureInfo.InvariantCulture);
            var words = names.Append(city).Append(district).Concat(street.PostalCodes).SelectMany(x => x.Split(' ', StringSplitOptions.RemoveEmptyEntries)).Distinct(StringComparer.Ordinal).ToArray();
            rows[index] = new SearchRow(street, Text(street.StreetName), words);
            // Suffix entries allow a second given-name word to be the first
            // typed word without scanning every street in the country.
            foreach (var name in names)
            {
                var parts = name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                for (var position = 0; position < parts.Length; position++)
                    nameFirst.Add(new PrefixRow(string.Join(' ', parts.Skip(position)) + " " + city, index));
            }
            cityFirst.Add(new PrefixRow(city + " " + rows[index].Name, index));
            if (street.District is not null)
            {
                cityFirst.Add(new PrefixRow(Text(street.District) + " " + city + " " + rows[index].Name, index));
                cityFirst.Add(new PrefixRow(DistrictNumber(street.District)!.Value.ToString(CultureInfo.InvariantCulture) + " " + city + " " + rows[index].Name, index));
            }
            foreach (var postal in street.PostalCodes) cityFirst.Add(new PrefixRow(postal + " " + rows[index].Name, index));
        }
        static PrefixRow[] Sorted(List<PrefixRow> rows)
        {
            rows.Sort(static (left, right) => {
                var order = string.CompareOrdinal(left.Key, right.Key);
                return order == 0 ? left.Index.CompareTo(right.Index) : order;
            });
            return rows.ToArray();
        }
        return new Catalogue(streets.ToArray(), byId, byName.ToDictionary(x => x.Key, x => x.Value.ToArray(), StringComparer.Ordinal),
            cities, rows, Sorted(nameFirst), Sorted(cityFirst), version);
    }

    internal static void ValidateHeader(JsonElement header)
    {
        if (header.GetProperty("schemaVersion").GetInt32() != 1
            || header.GetProperty("count").GetInt32() != ExpectedCount
            || header.GetProperty("sourceSha256").GetString() is not { Length: 64 } hash
            || hash.Any(c => !"0123456789abcdef".Contains(c))
            || hash != ExpectedSourceSha256
            || header.GetProperty("datasetVersion").GetString() is not { Length: 64 } version
            || version.Any(c => !"0123456789abcdef".Contains(c))
            || version != ExpectedDatasetVersion)
            throw new InvalidOperationException("The postal street dataset version or count is invalid.");
    }

    internal static PostalStreet ParseRow(JsonElement row) => new(
        row.GetProperty("id").GetString()!, row.GetProperty("city").GetString()!,
        row.GetProperty("district").ValueKind == JsonValueKind.Null ? null : row.GetProperty("district").GetString(),
        row.GetProperty("name").GetString()!, row.GetProperty("type").GetString()!,
        row.GetProperty("streetName").GetString()!, row.GetProperty("label").GetString()!,
        row.GetProperty("postalCodes").EnumerateArray().Select(x => x.GetString()!).ToArray(),
        row.GetProperty("aliases").EnumerateArray().Select(x => x.GetString()!).ToArray());

    private static bool ValidId(string id) => id.Length == 31 && id.StartsWith("street:", StringComparison.Ordinal)
        && !id.Skip(7).Any(c => !"0123456789abcdef".Contains(c));

    private static string Text(string? value)
    {
        var normalized = Rules.Normalize(value ?? "");
        return string.Join(' ', new string(normalized.Select(c => char.IsLetterOrDigit(c) ? c : ' ').ToArray())
            .Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private static string StreetKey(string? value)
    {
        var key = Text(value);
        return key == "U" ? "UTCA" : key.EndsWith(" U", StringComparison.Ordinal) ? key[..^1] + "UTCA" : key;
    }

    private static string NameKey(string city, string name) => Text(city) + "\0" + name;
    private static int? DistrictNumber(string? value)
    {
        var clean = Text(value).Replace("BUDAPEST", "", StringComparison.Ordinal).Replace("KERULET", "", StringComparison.Ordinal).Trim();
        if (int.TryParse(clean, NumberStyles.None, CultureInfo.InvariantCulture, out var number) && number is >= 1 and <= 23) return number;
        var index = Array.IndexOf(Romans, clean);
        return index < 0 ? null : index + 1;
    }

    /// <summary>Exact scoped identity only; this never changes address text or geocoding.</summary>
    public static PostalStreet? ResolveProperty(Property property, string? requestedStreetId = null)
    {
        var city = Text(property.City);
        var streetKey = StreetKey(property.Street);
        var district = string.IsNullOrWhiteSpace(property.District) ? null : DistrictNumber(property.District);
        var validDistrict = string.IsNullOrWhiteSpace(property.District) || district.HasValue;
        string? locationCity = null;
        var validLocation = true;
        if (!string.IsNullOrWhiteSpace(property.LocationId))
        {
            if (property.LocationId.StartsWith("city:", StringComparison.Ordinal)) locationCity = property.LocationId[5..];
            else if (property.LocationId.StartsWith("district:Budapest:", StringComparison.Ordinal)
                && int.TryParse(property.LocationId[18..], NumberStyles.None, CultureInfo.InvariantCulture, out var number) && number is >= 1 and <= 23
                && property.LocationId == "district:Budapest:" + number.ToString(CultureInfo.InvariantCulture))
            {
                locationCity = "Budapest";
                validDistrict = validDistrict && (!district.HasValue || district == number);
                district = number;
            }
            else validLocation = false;
        }
        var postal = property.PostalCode?.Trim() ?? "";
        bool InScope(PostalStreet candidate) => Text(candidate.City) == city && validDistrict && validLocation
            && (locationCity is null || candidate.City == locationCity)
            && (!district.HasValue || candidate.District is not null && DistrictNumber(candidate.District) == district)
            && (postal.Length == 0 || candidate.PostalCodes.Contains(postal, StringComparer.Ordinal));
        if (requestedStreetId is not null)
        {
            var selected = Get(requestedStreetId);
            if (selected is null || !InScope(selected) || !selected.Aliases.Append(selected.StreetName).Any(name => StreetKey(name) == streetKey))
                throw new ApiException(400, "A kiválasztott közterület nem egyezik az ingatlan címével.");
            return selected;
        }
        if (city.Length == 0 || streetKey.Length == 0 || !validDistrict || !validLocation) return null;
        if (!Data.Value.ByName.TryGetValue(city + "\0" + streetKey, out var candidates)) return null;
        var matches = candidates.Where(InScope).Take(2).ToArray();
        return matches.Length == 1 ? matches[0] : null;
    }

    public static PostalStreet[] Search(string? query, int limit = 12, string? locationId = null)
    {
        if ((query?.Length ?? 0) > 200) throw new ApiException(400, "A közterület keresőszövege legfeljebb 200 karakter lehet.");
        var data = Data.Value;
        string? city = null;
        string? district = null;
        if (locationId is not null)
        {
            if (locationId.StartsWith("city:", StringComparison.Ordinal) && data.Cities.Contains(locationId[5..])) city = locationId[5..];
            else if (locationId.StartsWith("district:Budapest:", StringComparison.Ordinal)
                && int.TryParse(locationId[18..], NumberStyles.None, CultureInfo.InvariantCulture, out var number) && number is >= 1 and <= 23
                && locationId == "district:Budapest:" + number.ToString(CultureInfo.InvariantCulture))
            { city = "Budapest"; district = Romans[number - 1] + "."; }
            else throw new ApiException(400, "A közterülethez egy konkrét települést vagy budapesti kerületet válassz.");
        }
        var text = Text(query);
        if (text.Length == 0) return [];
        var words = text.Split(' ');
        var candidates = new HashSet<int>();
        AddPrefix(data.NameFirst, words[0], candidates);
        AddPrefix(data.CityFirst, words[0], candidates);
        limit = Math.Clamp(limit, 1, 25);
        return candidates.Select(index => data.SearchRows[index])
            .Where(row => (city is null || row.Street.City == city) && (district is null || row.Street.District == district)
                && words.All(word => row.Words.Any(part => part.StartsWith(word, StringComparison.Ordinal))))
            .OrderBy(row => row.Name == text ? 0 : row.Name.StartsWith(text, StringComparison.Ordinal) ? 1 : 2)
            .ThenBy(row => row.Street.Label, StringComparer.Ordinal).ThenBy(row => row.Street.Id, StringComparer.Ordinal)
            .Take(limit).Select(row => row.Street).ToArray();
    }

    private static void AddPrefix(PrefixRow[] rows, string prefix, HashSet<int> candidates)
    {
        var low = 0;
        var high = rows.Length;
        while (low < high)
        {
            var middle = low + (high - low) / 2;
            if (StringComparer.Ordinal.Compare(rows[middle].Key, prefix) < 0) low = middle + 1;
            else high = middle;
        }
        for (var index = low; index < rows.Length && rows[index].Key.StartsWith(prefix, StringComparison.Ordinal); index++)
            candidates.Add(rows[index].Index);
    }
}
