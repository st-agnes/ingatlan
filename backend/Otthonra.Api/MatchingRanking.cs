using System.Text.Json;
using System.Text.RegularExpressions;
using System.Globalization;

namespace Otthonra.Api;

public sealed record MatchCriterion(string Key, string Label, string Expected, string Actual, bool Matches);
public sealed record MatchEvaluation(bool Eligible, bool IsExact, int Score, string[] Reasons)
{
    public MatchCriterion[] MatchDetails { get; init; } = [];
}

/// <summary>Parsed search filters are reused for every candidate in one request.</summary>
public sealed class CompiledSearch
{
    public SearchRequest Source { get; }
    public string NormalizedType { get; }
    public IReadOnlySet<string> Cities { get; }
    public IReadOnlySet<string> DistrictIds { get; }
    public int Specificity { get; internal set; }
    internal bool House => NormalizedType == "HAZ";
    internal HashSet<string> Conditions { get; }
    internal HashSet<string> Buildings { get; }
    internal HashSet<string> Heating { get; }
    internal HashSet<string> Ages { get; }
    internal HashSet<string> Views { get; }
    internal int[] Floors { get; }
    internal int? ConditionMinimum { get; }

    internal CompiledSearch(SearchRequest input, HashSet<string> cities, HashSet<string> districtIds)
    {
        Source = new SearchRequest {
            Id = input.Id, OwnerId = input.OwnerId, Type = input.Type, Archived = input.Archived,
            City = input.City, DistrictsJson = input.DistrictsJson, LocationIdsJson = input.LocationIdsJson,
            MinPrice = input.MinPrice, MaxPrice = input.MaxPrice, MinArea = input.MinArea, MaxArea = input.MaxArea,
            MinRooms = input.MinRooms, MaxRooms = input.MaxRooms, Balcony = input.Balcony, Elevator = input.Elevator,
            CeilingHeight = MatchingRanking.Canonical(input.CeilingHeight, PropertyAttributes.CeilingHeights), ConditionsJson = input.ConditionsJson, BuildingsJson = input.BuildingsJson,
            ConstructionAgesJson = input.ConstructionAgesJson, ViewsJson = input.ViewsJson,
            FloorsJson = input.FloorsJson, HeatingTypesJson = input.HeatingTypesJson
        };
        NormalizedType = Rules.Normalize(input.Type);
        Cities = cities; DistrictIds = districtIds;
        Conditions = Dto.Strings(input.ConditionsJson).Select(PropertyAttributes.NormalizeCondition).ToHashSet(StringComparer.Ordinal);
        Buildings = Dto.Strings(input.BuildingsJson).Select(PropertyAttributes.NormalizeBuilding).ToHashSet(StringComparer.Ordinal);
        Heating = Dto.Strings(input.HeatingTypesJson).Select(PropertyAttributes.NormalizeHeating).ToHashSet(StringComparer.Ordinal);
        Ages = Dto.Strings(input.ConstructionAgesJson).Select(value => MatchingRanking.Canonical(value, PropertyAttributes.ConstructionAges)).ToHashSet(StringComparer.Ordinal);
        Views = Dto.Strings(input.ViewsJson).Select(value => MatchingRanking.Canonical(value, PropertyAttributes.Views)).ToHashSet(StringComparer.Ordinal);
        Floors = PropertyAttributes.Floors(input.FloorsJson);
        ConditionMinimum = Conditions.Count == 0 ? null : Conditions.Min(value => Array.IndexOf(PropertyAttributes.Conditions, value));
    }
}

/// <summary>Location/type are hard gates. Remaining explicitly selected criteria determine a weighted percentage.</summary>
public static class MatchingRanking
{
    // Keep these formulas and weights aligned with dist/matching.js; tests cover both implementations.
    private const decimal MaxPriceWeight = 32m, MinRoomsWeight = 22m, MinAreaWeight = 16m,
        ConditionWeight = 10m, FloorWeight = 7m, ElevatorWeight = 5m, BalconyWeight = 4m,
        BuildingWeight = 3m, HeatingWeight = 2.5m, AgeWeight = 2m, CeilingWeight = 1.5m,
        MaxAreaWeight = 1.25m, MaxRoomsWeight = 1m, MinPriceWeight = .75m, ViewWeight = .5m;
    private static readonly Lazy<Dictionary<string, string[]>> AreaMembers = new(() => {
        using var stream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Agglomerations.json")
            ?? throw new InvalidOperationException("The embedded city-area catalogue is missing.");
        using var data = JsonDocument.Parse(stream);
        return data.RootElement.GetProperty("areas").EnumerateArray().ToDictionary(
            row => row.GetProperty("id").GetString()!, row => row.GetProperty("settlements").EnumerateArray()
                .Select(value => value.GetString()!).ToArray(), StringComparer.Ordinal);
    });
    private static readonly Regex TopEnergy = new(@"^(AA?|A[1-4])\+{0,3}$", RegexOptions.CultureInvariant);
    private static readonly Regex GoodEnergy = new(@"^BB?\+{0,3}$", RegexOptions.CultureInvariant);
    private static readonly Regex AverageEnergy = new(@"^CC?\+{0,3}$", RegexOptions.CultureInvariant);

    private static readonly HashSet<string> ValueBuildings = ["Tégla", "Kő és tégla", "Fa", "Rönkház", "Könnyűszerkezet"];
    private static readonly HashSet<string> ValueHeating = ["Gázkazán", "Gázcirkó", "Távfűtés", "Házközponti fűtés"];

    internal static string Canonical(string? value, string[] options)
    {
        var text = value?.Trim() ?? "";
        if (options.Contains(text)) return text;
        var normalized = Rules.Normalize(text);
        return options.FirstOrDefault(option => Rules.Normalize(option) == normalized) ?? text;
    }
    private static int ConditionIndex(string? value) => Array.IndexOf(PropertyAttributes.Conditions,
        PropertyAttributes.Conditions.Contains(value) ? value : PropertyAttributes.NormalizeCondition(value));
    private static decimal Unit(decimal value) => Math.Clamp(value, 0m, 1m);
    private static decimal CategoryLoss(string? value, HashSet<string> selected, string[] options) =>
        selected.Count == 0 ? 0m : options.Contains(value) && selected.Contains(value!) ? 0m : 1m;

    public static CompiledSearch Prepare(SearchRequest search)
    {
        var cities = new HashSet<string>(StringComparer.Ordinal);
        var districts = new HashSet<string>(StringComparer.Ordinal);
        foreach (var location in LocationCatalog.ForSearch(search))
        {
            if (location.Kind == "area")
            {
                if (AreaMembers.Value.TryGetValue(location.Id, out var members)) cities.UnionWith(members);
            }
            else if (location.District is not null) districts.Add(location.Id);
            else cities.Add(location.City);
        }
        districts.RemoveWhere(id => cities.Contains(LocationCatalog.Get(id)!.City));
        var prepared = new CompiledSearch(search, cities, districts);
        prepared.Specificity = SpecificityOf(prepared);
        return prepared;
    }

    private static bool Eligible(Property property, CompiledSearch search)
    {
        if (property.Archived || search.Source.Archived || property.OwnerId == search.Source.OwnerId) return false;
        if (search.NormalizedType.Length > 0 && Rules.Normalize(property.Type) != search.NormalizedType) return false;
        if (!string.IsNullOrWhiteSpace(property.LocationId) && LocationCatalog.Get(property.LocationId) is null) return false;
        var location = LocationCatalog.ForProperty(property);
        return location is not null && location.Kind != "area"
            && (search.Cities.Contains(location.City) || search.DistrictIds.Contains(location.Id));
    }

    public static bool CanRecommend(Property property, SearchRequest search) => Eligible(property, Prepare(search));
    public static MatchEvaluation Evaluate(Property property, CompiledSearch search, bool includeReasons = true)
    {
        if (!Eligible(property, search)) return new(false, false, 0, []);
        var s = search.Source;
        decimal weight = 0m, loss = 0m;
        var different = false;
        List<string>? differences = includeReasons ? [] : null;
        void Add(decimal criterionWeight, bool active, decimal penalty, string label)
        {
            if (!active) return;
            var amount = Unit(penalty);
            weight += criterionWeight; loss += criterionWeight * amount;
            if (amount <= 0) return;
            different = true;
            differences?.Add(label + ": eltérés a kereséstől");
        }
        void Minimum(decimal value, decimal? minimum, decimal criterionWeight, string label) =>
            Add(criterionWeight, minimum is > 0, ((minimum ?? 0) - value) / (minimum is > 0 ? minimum.Value : 1m), label);
        void Maximum(decimal value, decimal? maximum, decimal criterionWeight, string label) =>
            Add(criterionWeight, maximum.HasValue, maximum is > 0 ? (value - maximum.Value) / maximum.Value : value > (maximum ?? 0) ? 1m : 0m, label);
        Minimum(property.Price, s.MinPrice, MinPriceWeight, "Minimumár");
        Maximum(property.Price, s.MaxPrice, MaxPriceWeight, "Maximumár");
        Minimum(property.Rooms, s.MinRooms, MinRoomsWeight, "Minimum szobaszám");
        Maximum(property.Rooms, s.MaxRooms, MaxRoomsWeight, "Maximum szobaszám");
        Minimum(property.Area, s.MinArea, MinAreaWeight, "Minimum alapterület");
        Maximum(property.Area, s.MaxArea, MaxAreaWeight, "Maximum alapterület");
        var condition = ConditionIndex(property.Condition);
        Add(ConditionWeight, search.Conditions.Count > 0, condition < 0 || search.ConditionMinimum < 0 ? 1m
            : ((search.ConditionMinimum ?? 0) - condition) / 3m, "Állapot");
        var floorLoss = property.Floor.HasValue && search.Floors.Length > 0
            ? search.Floors.Min(wanted => wanted == 11 && property.Floor.Value >= 11 ? 0m : Math.Abs(wanted - property.Floor.Value) / 5m) : 1m;
        Add(FloorWeight, !search.House && search.Floors.Length > 0, floorLoss, "Emelet");
        Add(ElevatorWeight, !search.House && s.Elevator, property.Elevator ? 0 : 1, "Lift");
        Add(BalconyWeight, !search.House && s.Balcony, property.Balcony ? 0 : 1, "Erkély");
        Add(BuildingWeight, search.Buildings.Count > 0, CategoryLoss(Canonical(property.Building, PropertyAttributes.Buildings), search.Buildings, PropertyAttributes.Buildings), "Falazat");
        Add(HeatingWeight, search.Heating.Count > 0, CategoryLoss(Canonical(property.HeatingType, PropertyAttributes.HeatingTypes), search.Heating, PropertyAttributes.HeatingTypes), "Fűtés típusa");
        var age = Array.IndexOf(PropertyAttributes.ConstructionAges, Canonical(property.ConstructionAge, PropertyAttributes.ConstructionAges));
        var ageLoss = age < 0 || search.Ages.Count == 0 ? 1m : search.Ages.Min(value => Math.Abs(Array.IndexOf(PropertyAttributes.ConstructionAges, value) - age) / 4m);
        Add(AgeWeight, search.Ages.Count > 0, ageLoss, "Építési kor");
        var ceiling = Canonical(property.CeilingHeight, PropertyAttributes.CeilingHeights);
        Add(CeilingWeight, !string.IsNullOrEmpty(s.CeilingHeight), PropertyAttributes.CeilingHeights.Contains(ceiling) && ceiling == s.CeilingHeight ? 0 : 1, "Belmagasság");
        Add(ViewWeight, search.Views.Count > 0, CategoryLoss(Canonical(property.View, PropertyAttributes.Views), search.Views, PropertyAttributes.Views), "Kilátás");
        var exact = !different;
        var score = exact ? 100 : Math.Clamp((int)Math.Round(100m * (1m - loss / (weight > 0m ? weight : 1m)), MidpointRounding.AwayFromZero), 0, 99);
        return new(true, exact, score, !includeReasons ? [] : exact
            ? ["Megfelelő elhelyezkedés", "A megadott árkereten belül", "Megfelelő alapterület és szobaszám"] : differences!.ToArray()) {
                MatchDetails = includeReasons ? Explain(property, search) : []
            };
    }

    private static readonly CultureInfo Hungarian = CultureInfo.GetCultureInfo("hu-HU");
    private static string Number(decimal value) => value.ToString("0.######", Hungarian);
    private static string Floor(int value, bool bucket = false) => value switch {
        -1 => "Szuterén", 0 => "Földszint", 11 when bucket => "11. emelet vagy afölötti", _ => value + ". emelet"
    };
    private static string Known(string value, string[] options) => options.Contains(value) ? value : "Nincs megadva";

    // Built only for cards actually returned, never during the lean ranking scan.
    // The requested value remains separate from the listing's value so both
    // successful and unsuccessful criteria can be rendered without guessing.
    private static MatchCriterion[] Explain(Property p, CompiledSearch q)
    {
        var s = q.Source;
        var details = new List<MatchCriterion>();
        void Add(string key, string label, string expected, string actual, bool matches) =>
            details.Add(new(key, label, expected, actual, matches));
        void Bounds(string key, string label, decimal actual, decimal? minimum, decimal? maximum, string unit)
        {
            var min = minimum is > 0;
            if (!min && !maximum.HasValue) return;
            var expected = min && maximum.HasValue ? Number(minimum!.Value) + "–" + Number(maximum.Value) + " " + unit
                : min ? "legalább " + Number(minimum!.Value) + " " + unit
                : "legfeljebb " + Number(maximum!.Value) + " " + unit;
            Add(key, label, expected, Number(actual) + " " + unit,
                (!min || actual >= minimum!.Value) && (!maximum.HasValue || actual <= maximum.Value));
        }
        void Category(string key, string label, string actual, HashSet<string> selected, string[] options)
        {
            if (selected.Count == 0) return;
            var expected = options.Where(selected.Contains).ToArray();
            Add(key, label, expected.Length > 0 ? string.Join(" vagy ", expected) : "Ismeretlen feltétel",
                Known(actual, options), options.Contains(actual) && selected.Contains(actual));
        }
        var location = LocationCatalog.ForProperty(p)!;
        Add("location", "Helyszín", string.Join(" vagy ", LocationCatalog.ForSearch(s).Select(value => value.Label)), location.Label, true);
        if (q.NormalizedType.Length > 0) Add("type", "Ingatlantípus", s.Type, p.Type, true);
        Bounds("price", "Ár", p.Price / 1_000_000m, s.MinPrice / 1_000_000m, s.MaxPrice / 1_000_000m, "M Ft");
        Bounds("rooms", "Szobaszám", p.Rooms, s.MinRooms, s.MaxRooms, "szoba");
        Bounds("area", "Alapterület", p.Area, s.MinArea, s.MaxArea, "m²");
        if (q.Conditions.Count > 0)
        {
            var actual = ConditionIndex(p.Condition);
            var minimum = q.ConditionMinimum ?? -1;
            Add("condition", "Állapot", minimum >= 0 ? PropertyAttributes.Conditions[minimum] + " vagy jobb" : "Ismeretlen feltétel",
                actual >= 0 ? PropertyAttributes.Conditions[actual] : "Nincs megadva", actual >= 0 && minimum >= 0 && actual >= minimum);
        }
        if (!q.House && q.Floors.Length > 0)
            Add("floor", "Emelet", string.Join(" vagy ", q.Floors.Select(value => Floor(value, bucket: true))),
                p.Floor.HasValue ? Floor(p.Floor.Value) : "Nincs megadva",
                p.Floor.HasValue && q.Floors.Any(value => value == p.Floor.Value || value == 11 && p.Floor.Value >= 11));
        if (!q.House && s.Elevator) Add("elevator", "Lift", "Van lift", p.Elevator ? "Van lift" : "Nincs lift", p.Elevator);
        if (!q.House && s.Balcony) Add("balcony", "Erkély", "Van erkély", p.Balcony ? "Van erkély" : "Nincs erkély", p.Balcony);
        Category("building", "Falazat", Canonical(p.Building, PropertyAttributes.Buildings), q.Buildings, PropertyAttributes.Buildings);
        Category("heatingType", "Fűtés típusa", Canonical(p.HeatingType, PropertyAttributes.HeatingTypes), q.Heating, PropertyAttributes.HeatingTypes);
        Category("constructionAge", "Építési kor", Canonical(p.ConstructionAge, PropertyAttributes.ConstructionAges), q.Ages, PropertyAttributes.ConstructionAges);
        if (!string.IsNullOrEmpty(s.CeilingHeight))
        {
            var actual = Canonical(p.CeilingHeight, PropertyAttributes.CeilingHeights);
            Add("ceilingHeight", "Belmagasság", s.CeilingHeight, Known(actual, PropertyAttributes.CeilingHeights),
                PropertyAttributes.CeilingHeights.Contains(actual) && actual == s.CeilingHeight);
        }
        Category("view", "Kilátás", Canonical(p.View, PropertyAttributes.Views), q.Views, PropertyAttributes.Views);
        return details.ToArray();
    }

    public static decimal ValueForMoney(Property property)
    {
        var p = property;
        if (p.Area <= 0 || p.Price <= 0) return 0;
        var house = Rules.Normalize(p.Type) == "HAZ";
        decimal quality = Math.Max(0, ConditionIndex(p.Condition)) / 3m * .05m;
        var building = Canonical(p.Building, PropertyAttributes.Buildings);
        quality += building == "Passzívház" ? .02m : ValueBuildings.Contains(building) ? .015m : building == "Panel" ? .01m : PropertyAttributes.Buildings.Contains(building) ? .005m : 0m;
        var age = Array.IndexOf(PropertyAttributes.ConstructionAges, Canonical(p.ConstructionAge, PropertyAttributes.ConstructionAges));
        quality += age < 0 ? 0m : (4 - age) / 4m * .025m;
        quality += Canonical(p.View, PropertyAttributes.Views) switch { "Panorámás" => .015m, "Kertre néző" => .01m, "Udvari" => .005m, _ => 0m };
        var heating = Canonical(p.HeatingType, PropertyAttributes.HeatingTypes);
        quality += heating == "Hőszivattyú" ? .025m : ValueHeating.Contains(heating) ? .015m : PropertyAttributes.HeatingTypes.Contains(heating) && heating != "Nincs fűtés" ? .005m : 0m;
        var secondary = Canonical(p.SecondaryHeatingType, PropertyAttributes.HeatingTypes);
        quality += PropertyAttributes.HeatingTypes.Contains(secondary) && secondary != "Nincs fűtés" ? .005m : 0m;
        quality += p.Insulated == true ? .015m : 0m;
        var energy = Rules.Normalize(p.EnergyRating);
        quality += TopEnergy.IsMatch(energy) ? .02m : GoodEnergy.IsMatch(energy) ? .015m : AverageEnergy.IsMatch(energy) ? .005m : 0m;
        quality += p.AirConditioning == true ? .01m : 0m;
        quality += p.SolarPanels == true ? .015m : 0m;
        var parking = PropertyAttributes.Parking(p);
        quality += parking.Any(value => value is "Garázs" or "Mélygarázs" or "Teremgarázs") ? .015m
            : parking.Any(value => value is "Fedett beálló" or "Udvari beálló") ? .01m : 0m;
        quality += Canonical(p.CeilingHeight, PropertyAttributes.CeilingHeights) == "3 m feletti" ? .005m : 0m;
        quality += !house && p.Floor is >= 0 and <= 3 ? .005m : 0m;
        quality += !house && p.Balcony ? .01m : 0m;
        quality += !house && p.Elevator ? .01m : 0m;
        quality += Math.Min(1m, Math.Max(0m, p.Rooms) / (p.Area / 25m)) * .005m;
        var land = house ? Math.Max(0m, p.LotArea ?? 0m) : 0m;
        var effectiveArea = p.Area + .04m * Math.Min(land, 5m * p.Area);
        return effectiveArea / (p.Price / 1_000_000m) * (1m + Math.Min(.25m, quality));
    }

    public static int Specificity(SearchRequest search) => Prepare(search).Specificity;
    private static int SpecificityOf(CompiledSearch search)
    {
        var s = search.Source;
        var coverage = search.Cities.Count + search.DistrictIds.Count / 23d;
        decimal selected = coverage > 0 ? (decimal)(8d / (1d + Math.Log2(1d + coverage))) : 0m, total = 8m;
        void Add(decimal weight, decimal strength) { total += weight; selected += weight * Unit(strength); }
        void Bounds(decimal? minimum, decimal? maximum, decimal minWeight, decimal maxWeight)
        {
            var min = minimum is > 0; var max = maximum.HasValue;
            var strength = min && max ? .5m + .5m * Unit(maximum is > 0 ? minimum!.Value / maximum.Value : 1m) : .5m;
            Add(minWeight, min ? strength : 0m); Add(maxWeight, max ? strength : 0m);
        }
        static decimal Category(int count, int options) => count == 0 ? 0m : (decimal)(1d / Math.Sqrt(Math.Min(count, options)));
        Bounds(s.MinPrice, s.MaxPrice, MinPriceWeight, MaxPriceWeight);
        Bounds(s.MinArea, s.MaxArea, MinAreaWeight, MaxAreaWeight);
        Bounds(s.MinRooms, s.MaxRooms, MinRoomsWeight, MaxRoomsWeight);
        Add(ConditionWeight, search.ConditionMinimum.HasValue ? (search.ConditionMinimum.Value + 1m) / 4m : 0m);
        Add(BuildingWeight, Category(search.Buildings.Count, PropertyAttributes.Buildings.Length));
        Add(HeatingWeight, Category(search.Heating.Count, PropertyAttributes.HeatingTypes.Length));
        Add(AgeWeight, Category(search.Ages.Count, PropertyAttributes.ConstructionAges.Length));
        Add(ViewWeight, Category(search.Views.Count, PropertyAttributes.Views.Length));
        Add(CeilingWeight, string.IsNullOrEmpty(s.CeilingHeight) ? 0m : 1m);
        if (!search.House)
        {
            Add(FloorWeight, Category(search.Floors.Length, 13));
            Add(ElevatorWeight, s.Elevator ? 1m : 0m); Add(BalconyWeight, s.Balcony ? 1m : 0m);
        }
        return Math.Clamp((int)Math.Round(100m * selected / total, MidpointRounding.AwayFromZero), 0, 100);
    }
}
