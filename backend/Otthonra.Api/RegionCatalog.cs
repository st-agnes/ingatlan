using System.Text.Json;

namespace Otthonra.Api;

public sealed record LandingRegion(string Id, string Label);

/// <summary>Official KSH county membership, including areas that cross a county boundary.</summary>
public static class RegionCatalog
{
    private sealed record Data(LandingRegion[] Regions, Dictionary<string, string> Cities,
        Dictionary<string, string[]> Areas);
    private static readonly Lazy<Data> Catalogue = new(Load);
    public static IReadOnlyList<LandingRegion> All => Catalogue.Value.Regions;

    public static LandingRegion? Get(string? id) => All.FirstOrDefault(region => region.Id == id);

    public static string[] ForLocation(Location location)
    {
        if (location.Kind == "area")
            return Catalogue.Value.Areas.TryGetValue(location.Id, out var areas) ? areas.ToArray() : [];
        return Catalogue.Value.Cities.TryGetValue(location.City, out var county) ? [county] : [];
    }

    public static string[] ForLocations(IEnumerable<Location> locations) => locations.SelectMany(ForLocation)
        .Distinct(StringComparer.Ordinal).ToArray();

    private static Data Load()
    {
        var assembly = typeof(RegionCatalog).Assembly;
        using var stream = assembly.GetManifestResourceStream("Otthonra.Api.Regions.json")
            ?? throw new InvalidOperationException("The embedded KSH region catalogue is missing.");
        using var document = JsonDocument.Parse(stream);
        if (document.RootElement.GetProperty("schemaVersion").GetInt32() != 1)
            throw new InvalidOperationException("The region catalogue schema is not supported.");
        var cities = new Dictionary<string, string>(StringComparer.Ordinal);
        var regions = new List<LandingRegion>();
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in document.RootElement.GetProperty("regions").EnumerateArray())
        {
            var id = row.GetProperty("id").GetString()!;
            var label = row.GetProperty("label").GetString()!;
            if (string.IsNullOrWhiteSpace(id) || string.IsNullOrWhiteSpace(label) || !ids.Add(id))
                throw new InvalidOperationException("The region catalogue contains invalid or duplicate regions.");
            regions.Add(new LandingRegion(id, label));
            foreach (var town in row.GetProperty("settlements").EnumerateArray())
                if (!cities.TryAdd(town.GetString()!, id))
                    throw new InvalidOperationException("A municipality belongs to multiple counties.");
        }
        var known = LocationCatalog.All.Where(location => location.Kind == "city").Select(location => location.City).ToHashSet(StringComparer.Ordinal);
        if (regions.Count != 20 || !known.SetEquals(cities.Keys))
            throw new InvalidOperationException("County membership must cover every canonical municipality exactly once.");
        using var areaStream = assembly.GetManifestResourceStream("Otthonra.Api.Agglomerations.json")
            ?? throw new InvalidOperationException("The embedded city-area catalogue is missing.");
        using var areaDocument = JsonDocument.Parse(areaStream);
        var areas = areaDocument.RootElement.GetProperty("areas").EnumerateArray().ToDictionary(
            area => area.GetProperty("id").GetString()!,
            area => area.GetProperty("settlements").EnumerateArray().Select(town => cities[town.GetString()!])
                .Distinct(StringComparer.Ordinal).ToArray(), StringComparer.Ordinal);
        return new Data(regions.ToArray(), cities, areas);
    }
}
