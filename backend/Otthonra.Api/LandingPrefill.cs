using System.Text.Json;

namespace Otthonra.Api;

// These records are a deliberately small public seed, never an entity DTO.
// Prices use the API's HUF unit; the browser adapter handles its form units.
public sealed record LandingSearchPrefill(Location[] Locations, string Type, decimal? MinPrice, decimal? MaxPrice,
    decimal? MinArea, decimal? MaxArea, decimal? MinRooms, decimal? MaxRooms, string[] Conditions,
    string[] Buildings, string[] ConstructionAges, string[] Views, string CeilingHeight, decimal[] Floors,
    string[] HeatingTypes, bool Balcony, bool Elevator, bool ExcludeTopFloor = false,
    bool ExcludeGroundFloorAndBelow = false, bool AirConditioning = false, bool PrivateGarden = false, bool SharedGarden = false);
public sealed record LandingPropertyPrefill(Location[] Locations, string Type, decimal Price, decimal Area, decimal Rooms,
    int? WholeRooms, int? HalfRooms, decimal? LotArea, string Condition, string Building, string ConstructionAge,
    string View, string CeilingHeight, decimal? Floor, string HeatingType, bool Balcony, bool Elevator,
    int? BuildingFloors = null, bool? AirConditioning = null, bool? PrivateGarden = null, bool? SharedGarden = null, bool FloorIsUpperRange = false);

internal static class LandingPrefill
{
    private static readonly Lazy<Dictionary<string, double>> NeighborhoodFootprints = new(LoadFootprints);
    private static decimal? Bound(decimal? value) => value >= 0 ? value : null;
    private static string Choice(string? value, string[] options, bool condition = false)
    {
        if (value is null || value.Length > 100) return "";
        var normalized = Rules.Normalize(condition ? PropertyAttributes.NormalizeCondition(value) : value);
        return options.FirstOrDefault(option => Rules.Normalize(option) == normalized) ?? "";
    }
    private static string[] Choices(string? json, string[] options, bool condition = false)
    {
        if (string.IsNullOrWhiteSpace(json) || json.Length > 8192) return [];
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Array) return [];
            return document.RootElement.EnumerateArray().Where(value => value.ValueKind == JsonValueKind.String)
                .Select(value => Choice(value.GetString(), options, condition)).Where(value => value.Length > 0)
                .Distinct(StringComparer.Ordinal).Take(options.Length).ToArray();
        }
        catch (JsonException) { return []; }
    }
    private static decimal[] Floors(string? json)
    {
        if (string.IsNullOrWhiteSpace(json) || json.Length > 1024) return [];
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Array) return [];
            return document.RootElement.EnumerateArray().Where(value => value.ValueKind == JsonValueKind.Number)
                .Select(value => value.TryGetDecimal(out var floor) ? floor : decimal.MinValue)
                .Where(value => value == .5m || value is >= -1 and <= 11 && decimal.Truncate(value) == value)
                .Select(value => value >= 9m ? 9m : value).Distinct().Take(12).ToArray();
        }
        catch (JsonException) { return []; }
    }

    public static LandingSearchPrefill Search(SearchRequest search, Location[] locations)
    {
        var type = PublicLanding.SafeType(search.Type);
        var house = type == "Ház";
        return new(CloneLocations(locations), type, Bound(search.MinPrice), Bound(search.MaxPrice), Bound(search.MinArea),
            Bound(search.MaxArea), Bound(search.MinRooms), Bound(search.MaxRooms),
            Choices(search.ConditionsJson, PropertyAttributes.Conditions, condition: true),
            Choices(search.BuildingsJson, PropertyAttributes.Buildings),
            Choices(search.ConstructionAgesJson, PropertyAttributes.ConstructionAges),
            Choices(search.ViewsJson, PropertyAttributes.Views), Choice(search.CeilingHeight, PropertyAttributes.CeilingHeights),
            house ? [] : Floors(search.FloorsJson), Choices(search.HeatingTypesJson, PropertyAttributes.HeatingTypes),
            !house && search.Balcony, !house && search.Elevator, !house && search.ExcludeTopFloor,
            !house && search.ExcludeGroundFloorAndBelow, search.AirConditioning,
            type == "Lakás" && search.PrivateGarden, false);
    }

    public static LandingPropertyPrefill Property(Property property, Location location)
    {
        var type = PublicLanding.SafeType(property.Type);
        var house = type == "Ház";
        var rooms = Rules.RoomCounts(property);
        return new(CloneLocations([PropertyLocation(property, location)]), type, property.Price, property.Area, property.Rooms,
            rooms.WholeRooms is >= 0 and <= 1000 ? rooms.WholeRooms : null,
            rooms.HalfRooms is >= 0 and <= 1000 ? rooms.HalfRooms : null,
            house ? Bound(property.LotArea) : null, Choice(property.Condition, PropertyAttributes.Conditions, condition: true),
            Choice(property.Building, PropertyAttributes.Buildings), Choice(property.ConstructionAge, PropertyAttributes.ConstructionAges),
            Choice(property.View, PropertyAttributes.Views), Choice(property.CeilingHeight, PropertyAttributes.CeilingHeights),
            !house && PropertyAttributes.KnownFloor(property.Floor) ? property.Floor : null,
            Choice(property.HeatingType, PropertyAttributes.HeatingTypes), !house && property.Balcony, !house && property.Elevator,
            !house && property.BuildingFloors is >= 0 and <= 200 ? property.BuildingFloors : null,
            property.AirConditioning, type == "Lakás" ? property.PrivateGarden : null, null, !house && property.FloorIsUpperRange && property.Floor == 9m);
    }

    private static Location PropertyLocation(Property property, Location fallback)
    {
        // Membership is computed by the server when an address is geocoded.
        // Never infer it from owner text, a street, or a representative point.
        if (string.IsNullOrWhiteSpace(property.NeighborhoodIdsJson) || property.NeighborhoodIdsJson.Length > 16384) return fallback;
        try
        {
            var areas = Dto.Strings(property.NeighborhoodIdsJson).Take(NeighborhoodCatalog.ExpectedCount)
                .Select(NeighborhoodCatalog.Get).Where(area => area is not null && area.City == fallback.City)
                .Select(area => area!).Where(area => IsFineNeighborhood(area, fallback))
                .DistinctBy(area => area.Id).ToArray();
            if (areas.Length == 0) return fallback;
            var selected = areas.Where(area => NeighborhoodFootprints.Value.ContainsKey(area.Id))
                .OrderBy(area => NeighborhoodFootprints.Value[area.Id]).ThenBy(area => area.Id, StringComparer.Ordinal).FirstOrDefault();
            return selected is null ? fallback : LocationCatalog.Get(selected.Id)!;
        }
        catch (JsonException) { return fallback; }
    }
    private static bool IsFineNeighborhood(NeighborhoodArea area, Location location)
    {
        var name = Rules.Normalize(area.Name);
        if (name == Rules.Normalize(location.City)) return false;
        // The catalogue intentionally includes overlapping city-side and ward
        // polygons. A neighborhood seed should use a finer named quarter.
        return location.City != "Budapest" || name is not ("BUDA" or "PEST") && !name.EndsWith("KERULET", StringComparison.Ordinal);
    }

    public static Location[] CloneLocations(Location[] locations) => locations.Select(location => location with {
        PostalCodes = location.PostalCodes?.ToArray()
    }).ToArray();
    public static LandingSearchPrefill? Clone(LandingSearchPrefill? seed) => seed is null ? null : seed with {
        Locations = CloneLocations(seed.Locations), Conditions = seed.Conditions.ToArray(), Buildings = seed.Buildings.ToArray(),
        ConstructionAges = seed.ConstructionAges.ToArray(), Views = seed.Views.ToArray(), Floors = seed.Floors.ToArray(),
        HeatingTypes = seed.HeatingTypes.ToArray()
    };
    public static LandingPropertyPrefill? Clone(LandingPropertyPrefill? seed) => seed is null ? null : seed with {
        Locations = CloneLocations(seed.Locations)
    };

    private static Dictionary<string, double> LoadFootprints()
    {
        // Retain one scalar per canonical area, not geometry or coordinates.
        // Streaming keeps the large runtime document out of the landing cache.
        var result = new Dictionary<string, double>(NeighborhoodCatalog.ExpectedCount, StringComparer.Ordinal);
        using var stream = NeighborhoodCatalog.OpenRuntimeStream();
        var enumerator = JsonSerializer.DeserializeAsyncEnumerable<JsonElement>(stream).GetAsyncEnumerator();
        try
        {
            while (enumerator.MoveNextAsync().AsTask().GetAwaiter().GetResult())
            {
                var row = enumerator.Current;
                if (!row.TryGetProperty("geometry", out var geometry)) continue;
                var id = row.GetProperty("id").GetString()!;
                if (NeighborhoodCatalog.Get(id) is null) continue;
                var coordinates = geometry.GetProperty("coordinates");
                var area = geometry.GetProperty("type").GetString() == "Polygon" ? PolygonArea(coordinates)
                    : coordinates.EnumerateArray().Sum(PolygonArea);
                if (double.IsFinite(area) && area > 0) result.Add(id, area);
            }
        }
        finally { enumerator.DisposeAsync().AsTask().GetAwaiter().GetResult(); }
        return result;
    }
    private static double PolygonArea(JsonElement rings)
    {
        double result = 0;
        var outer = true;
        foreach (var ring in rings.EnumerateArray())
        {
            double area = 0;
            JsonElement? previous = null;
            foreach (var point in ring.EnumerateArray())
            {
                if (previous is { } last)
                    area += (point[0].GetDouble() - last[0].GetDouble())
                        * (Math.Sin(point[1].GetDouble() * Math.PI / 180) + Math.Sin(last[1].GetDouble() * Math.PI / 180));
                previous = point;
            }
            result += (outer ? 1 : -1) * Math.Abs(area);
            outer = false;
        }
        return Math.Max(0, result);
    }
}
