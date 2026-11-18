using System.Globalization;
using System.IO.Compression;
using System.Text.Json;

namespace Otthonra.Api;

/// <summary>Public search metadata, deliberately independent of polygon coordinates.</summary>
public sealed record NeighborhoodArea(string Id, string Name, string City, string Label, string[] Aliases, bool Estimated);

/// <summary>A fictional-fixture coordinate; never a substitute for geocoding a real address.</summary>
public sealed record NeighborhoodPoint(double Latitude, double Longitude);

/// <summary>The versioned search-area names; geometry stays in MySQL, outside the static catalogue.</summary>
public static class NeighborhoodCatalog
{
    public const int ExpectedCount = 4308;
    public const string ExpectedSourceSha256 = "367af069d58c60e171d189e23673fe20fd5cef51792769c161c3eccb87321e4d";
    public const string ExpectedMunicipalitiesSha256 = "fb5f1293628b9eeaabce243ae6ebc884f6bdc93443a2488e5fb213029bf766b7";
    internal const string ResourceName = "Otthonra.Api.Neighborhoods.json.gz";
    private sealed record Catalogue(NeighborhoodArea[] Areas, Dictionary<string, NeighborhoodArea> ById,
        Dictionary<string, NeighborhoodPoint> FixturePoints, Dictionary<string, NeighborhoodPoint> CityFixturePoints);
    private static readonly Lazy<Catalogue> Data = new(Load);
    public static IReadOnlyList<NeighborhoodArea> All => Data.Value.Areas;
    public static string DatasetVersion { get { _ = Data.Value; return ExpectedSourceSha256; } }
    public static NeighborhoodArea? Get(string? id) => id is not null && Data.Value.ById.TryGetValue(id, out var area) ? area : null;

    /// <summary>Only for explicitly synthetic demo/TEST data, never real property assignment.</summary>
    public static NeighborhoodPoint? RepresentativePoint(string? id) => id is not null && Data.Value.FixturePoints.TryGetValue(id, out var point) ? point : null;

    /// <summary>Actual municipality interior point solely for explicitly synthetic demo/TEST properties.</summary>
    public static NeighborhoodPoint? TestPointForCity(string? city) => city is not null && Data.Value.CityFixturePoints.TryGetValue(city, out var point) ? point : null;

    internal static Stream OpenRuntimeStream()
    {
        var stream = typeof(NeighborhoodCatalog).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("The embedded neighborhood search catalogue is missing.");
        return new GZipStream(stream, CompressionMode.Decompress);
    }

    private static Catalogue Load()
    {
        using var stream = OpenRuntimeStream();
        using var reader = new StreamReader(stream);
        // The generated runtime is normal JSON, with one catalogue header on
        // its own first array-element line. Stop here: do not load geometries.
        if (reader.ReadLine() != "[") throw new InvalidOperationException("The neighborhood runtime format is invalid.");
        var line = reader.ReadLine() ?? throw new InvalidOperationException("The neighborhood metadata is missing.");
        using var document = JsonDocument.Parse(line.TrimEnd(','));
        ValidateHeader(document.RootElement);
        var areas = new List<NeighborhoodArea>(ExpectedCount);
        var byId = new Dictionary<string, NeighborhoodArea>(ExpectedCount, StringComparer.Ordinal);
        var points = new Dictionary<string, NeighborhoodPoint>(ExpectedCount, StringComparer.Ordinal);
        foreach (var row in document.RootElement.GetProperty("areas").EnumerateArray())
        {
            var area = new NeighborhoodArea(row.GetProperty("id").GetString()!, row.GetProperty("name").GetString()!,
                row.GetProperty("city").GetString()!, row.GetProperty("label").GetString()!,
                row.GetProperty("aliases").EnumerateArray().Select(alias => alias.GetString()!).ToArray(), row.GetProperty("estimated").GetBoolean());
            if (area.Id.Length != 37 || !area.Id.StartsWith("neighborhood:", StringComparison.Ordinal)
                || area.Id.Skip(13).Any(character => !"0123456789abcdef".Contains(character))
                || string.IsNullOrWhiteSpace(area.Name) || string.IsNullOrWhiteSpace(area.City) || string.IsNullOrWhiteSpace(area.Label)
                || area.Aliases.Any(string.IsNullOrWhiteSpace) || !byId.TryAdd(area.Id, area))
                throw new InvalidOperationException("The neighborhood catalogue contains invalid or duplicate metadata.");
            var coordinate = row.GetProperty("representativePoint").EnumerateArray().Select(value => value.GetDouble()).ToArray();
            if (coordinate.Length != 2 || !double.IsFinite(coordinate[0]) || !double.IsFinite(coordinate[1])
                || coordinate[0] is < 16 or > 23 || coordinate[1] is < 45 or > 49)
                throw new InvalidOperationException("A neighborhood fixture coordinate is invalid.");
            points.Add(area.Id, new NeighborhoodPoint(coordinate[1], coordinate[0]));
            areas.Add(area);
        }
        if (areas.Count != ExpectedCount) throw new InvalidOperationException("The neighborhood catalogue is incomplete.");
        if (document.RootElement.GetProperty("testMunicipalitySourceSha256").GetString() != ExpectedMunicipalitiesSha256)
            throw new InvalidOperationException("The synthetic municipality point source is invalid.");
        var cityPoints = new Dictionary<string, NeighborhoodPoint>(StringComparer.Ordinal);
        foreach (var row in document.RootElement.GetProperty("testCityPoints").EnumerateObject())
        {
            var coordinate = row.Value.EnumerateArray().Select(value => value.GetDouble()).ToArray();
            if (coordinate.Length != 2 || !double.IsFinite(coordinate[0]) || !double.IsFinite(coordinate[1])
                || coordinate[0] is < 16 or > 23 || coordinate[1] is < 45 or > 49)
                throw new InvalidOperationException("A synthetic municipality coordinate is invalid.");
            cityPoints.Add(row.Name, new NeighborhoodPoint(coordinate[1], coordinate[0]));
        }
        if (cityPoints.Count != 3155) throw new InvalidOperationException("The synthetic municipality point catalogue is incomplete.");
        return new Catalogue(areas.ToArray(), byId, points, cityPoints);
    }

    internal static void ValidateHeader(JsonElement header)
    {
        if (header.GetProperty("schemaVersion").GetInt32() != 1 || header.GetProperty("featureCount").GetInt32() != ExpectedCount
            || header.GetProperty("sourceSha256").GetString() != ExpectedSourceSha256
            || header.GetProperty("coordinateSystem").GetString() != "EPSG:4326"
            || header.GetProperty("coordinateOrder").GetString() != "longitude,latitude")
            throw new InvalidOperationException("The neighborhood dataset version, count or coordinate system is invalid.");
    }

    public static NeighborhoodArea[] Search(string? query, int limit = 8)
    {
        var value = SearchText(query ?? "");
        if (value.Length == 0) return [];
        var words = value.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return All.Select(area => new { Area = area, Labels = area.Aliases.Append(area.Name).Append(area.Label).Append(area.City + " " + area.Name).Select(SearchText).ToArray() })
            .Where(candidate => candidate.Labels.Any(label => label.Contains(value, StringComparison.Ordinal))
                || words.All(word => candidate.Labels.Any(label => label.Split(' ', StringSplitOptions.RemoveEmptyEntries).Any(part => part.StartsWith(word, StringComparison.Ordinal)))))
            .OrderBy(candidate => candidate.Labels.Any(label => label == value) ? 0 : candidate.Labels.Any(label => label.StartsWith(value, StringComparison.Ordinal)) ? 1 : 2)
            .ThenBy(candidate => candidate.Area.Label, StringComparer.Create(CultureInfo.GetCultureInfo("hu-HU"), false))
            .Take(Math.Clamp(limit, 1, 25)).Select(candidate => candidate.Area).ToArray();
    }

    private static string SearchText(string text) => string.Join(' ', new string(Rules.Normalize(text)
        .Select(character => char.IsLetterOrDigit(character) ? character : ' ').ToArray()).Split(' ', StringSplitOptions.RemoveEmptyEntries));
}
