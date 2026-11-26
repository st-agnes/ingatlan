using System.Text.Json;
using System.Text.RegularExpressions;
using System.Globalization;

namespace Otthonra.Api;

public sealed record MatchCriterion(string Key, string Label, string Expected, string Actual, bool Matches);
public sealed record MatchEvaluation(bool Eligible, bool IsExact, int Score, string[] Reasons)
{
    public MatchCriterion[] MatchDetails { get; init; } = [];
    public double DistanceSquared { get; init; }
    public double? LocationDistanceKm { get; init; }
}

/// <summary>Parsed search filters are reused for every candidate in one request.</summary>
public sealed class CompiledSearch
{
    public SearchRequest Source { get; }
    public string NormalizedType { get; }
    public IReadOnlySet<string> Cities { get; }
    public IReadOnlySet<string> DistrictIds { get; }
    public IReadOnlySet<string> NeighborhoodIds { get; }
    public IReadOnlySet<string> StreetIds { get; }
    public bool HasNonStreetLocations => Cities.Count > 0 || DistrictIds.Count > 0 || NeighborhoodIds.Count > 0;
    public int Specificity { get; internal set; }
    internal bool House => NormalizedType == "HAZ";
    internal bool Flat => NormalizedType == "LAKAS";
    internal HashSet<string> Conditions { get; }
    internal HashSet<string> Buildings { get; }
    internal HashSet<string> Heating { get; }
    internal HashSet<string> Ages { get; }
    internal HashSet<string> Views { get; }
    internal decimal[] Floors { get; }
    internal int? ConditionMinimum { get; }

    internal CompiledSearch(SearchRequest input, HashSet<string> cities, HashSet<string> districtIds, HashSet<string> neighborhoodIds,
        HashSet<string> streetIds, bool sellerPerspective = false)
    {
        NormalizedType = Rules.Normalize(input.Type);
        Source = new SearchRequest {
            Id = input.Id, OwnerId = input.OwnerId, Type = input.Type, Archived = input.Archived,
            City = input.City, DistrictsJson = input.DistrictsJson, LocationIdsJson = input.LocationIdsJson,
            MinPrice = input.MinPrice, MaxPrice = sellerPerspective ? SearchBudgets.PublicMaximum(input) : input.MaxPrice,
            MinArea = input.MinArea, MaxArea = input.MaxArea,
            MinRooms = input.MinRooms, MaxRooms = input.MaxRooms, Balcony = input.Balcony, Elevator = input.Elevator,
            CeilingHeight = MatchingRanking.Canonical(input.CeilingHeight, PropertyAttributes.CeilingHeights), ConditionsJson = input.ConditionsJson, BuildingsJson = input.BuildingsJson,
            ConstructionAgesJson = input.ConstructionAgesJson, ViewsJson = input.ViewsJson,
            FloorsJson = input.FloorsJson, HeatingTypesJson = input.HeatingTypesJson,
            ExcludeTopFloor = !House && input.ExcludeTopFloor,
            ExcludeGroundFloorAndBelow = !House && input.ExcludeGroundFloorAndBelow,
            AirConditioning = input.AirConditioning,
            PrivateGarden = Flat && input.PrivateGarden,
            SharedGarden = false, AtticPreference = House ? "" : input.AtticPreference, MinEnergyRating = input.MinEnergyRating
        };
        Cities = cities; DistrictIds = districtIds; NeighborhoodIds = neighborhoodIds; StreetIds = streetIds;
        Conditions = Dto.Strings(input.ConditionsJson).Select(PropertyAttributes.NormalizeCondition).ToHashSet(StringComparer.Ordinal);
        Buildings = Dto.Strings(input.BuildingsJson).Select(PropertyAttributes.NormalizeBuilding).ToHashSet(StringComparer.Ordinal);
        Heating = Dto.Strings(input.HeatingTypesJson).Select(PropertyAttributes.NormalizeHeating).ToHashSet(StringComparer.Ordinal);
        Ages = Dto.Strings(input.ConstructionAgesJson).Select(value => MatchingRanking.Canonical(value, PropertyAttributes.ConstructionAges)).ToHashSet(StringComparer.Ordinal);
        Views = Dto.Strings(input.ViewsJson).Select(value => MatchingRanking.Canonical(value, PropertyAttributes.Views)).ToHashSet(StringComparer.Ordinal);
        Floors = PropertyAttributes.Floors(input.FloorsJson);
        ConditionMinimum = Conditions.Count == 0 ? null : Conditions.Min(value => Array.IndexOf(PropertyAttributes.Conditions, value));
    }
}

/// <summary>Weighted distance from the accepted criteria; only verified geographic distances can widen locations.</summary>
public static class MatchingRanking
{
    // Keep these formulas and weights aligned with dist/matching.js; tests cover both implementations.
    public const decimal MaxPriceWeight = 1.2m, MinRoomsWeight = 1.1m, MinAreaWeight = 1m,
        ConditionWeight = .36m, FloorWeight = .25m, ElevatorWeight = .09m, BalconyWeight = .04m,
        BuildingWeight = .0225m, HeatingWeight = .0169m, AgeWeight = .0144m, CeilingWeight = .01m,
        MaxAreaWeight = .16m, MaxRoomsWeight = .16m, MinPriceWeight = .09m, ViewWeight = .01m,
        AirConditioningWeight = .04m, PrivateGardenWeight = .04m, EnergyWeight = .04m, LocationWeight = 1.5m;
    public const double LocationDistanceScaleKm = 20d;

    // Search focus measures narrowness rather than compatibility. Keep its
    // established weights stable when changing the independent distance model.
    private static readonly Dictionary<string, decimal> FocusWeights = new(StringComparer.Ordinal) {
        ["maxPrice"] = 32m, ["minRooms"] = 22m, ["minArea"] = 16m, ["condition"] = 10m,
        ["floor"] = 7m, ["elevator"] = 5m, ["balcony"] = 4m, ["building"] = 3m,
        ["heatingType"] = 2.5m, ["constructionAge"] = 2m, ["ceilingHeight"] = 1.5m, ["maxArea"] = 1.25m,
        ["maxRooms"] = 1m, ["minPrice"] = .75m, ["view"] = .5m,
        ["airConditioning"] = 3m, ["privateGarden"] = 3m, ["minEnergyRating"] = 3m
    };
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
    private static readonly HashSet<string> ValueHeating = ["Gázkazán / cirkó", "Távfűtés", "Házközponti fűtés"];

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
    private static bool KnownFloor(Property property) => PropertyAttributes.KnownFloor(property.Floor);
    private static bool KnownTopFloor(Property property) => PropertyAttributes.KnownTopFloor(property);
    private static bool BelowTopFloor(Property property) => PropertyAttributes.BelowTopFloor(property);
    private static bool AboveGroundFloor(Property property) => PropertyAttributes.AboveGroundFloor(property);

    public static CompiledSearch Prepare(SearchRequest search, bool sellerPerspective = false)
    {
        var cities = new HashSet<string>(StringComparer.Ordinal);
        var districts = new HashSet<string>(StringComparer.Ordinal);
        var neighborhoods = new HashSet<string>(StringComparer.Ordinal);
        var streets = new HashSet<string>(StringComparer.Ordinal);
        foreach (var location in LocationCatalog.ForSearch(search))
        {
            if (location.Kind == "street") streets.Add(location.Id);
            else if (location.Kind == "neighborhood") neighborhoods.Add(location.Id);
            else if (location.Kind == "area")
            {
                if (AreaMembers.Value.TryGetValue(location.Id, out var members)) cities.UnionWith(members);
            }
            else if (location.District is not null) districts.Add(location.Id);
            else cities.Add(location.City);
        }
        districts.RemoveWhere(id => cities.Contains(LocationCatalog.Get(id)!.City));
        var prepared = new CompiledSearch(search, cities, districts, neighborhoods, streets, sellerPerspective);
        prepared.Specificity = SpecificityOf(prepared);
        return prepared;
    }

    // Known municipalities and districts must agree. Identity-only legacy
    // backfills can keep an unspecified district; free text alone never
    // establishes membership in an exact street.
    internal static string? VerifiedStreetId(Property property, Location? location = null)
    {
        if (property.HideStreet) return null;
        location ??= LocationCatalog.ForProperty(property);
        var street = LocationCatalog.Get(property.StreetId);
        return location is not null && street?.Kind == "street" && street.City == location.City
            && (street.District is null || location.District is null || street.District == location.District) ? street.Id : null;
    }

    public static bool BaseEligible(Property property, CompiledSearch search)
    {
        if (property.Archived || search.Source.Archived || property.OwnerId == search.Source.OwnerId) return false;
        if (search.NormalizedType.Length > 0 && Rules.Normalize(property.Type) != search.NormalizedType) return false;
        if (!string.IsNullOrWhiteSpace(property.LocationId) && LocationCatalog.Get(property.LocationId) is null) return false;
        var location = LocationCatalog.ForProperty(property);
        return location is not null && (location.Kind is "city" or "district");
    }

    public static bool ExactLocation(Property property, CompiledSearch search)
    {
        var location = LocationCatalog.ForProperty(property);
        return location is not null && (location.Kind is "city" or "district")
            && (search.Cities.Contains(location.City) || search.DistrictIds.Contains(location.Id)
                || Dto.Strings(property.NeighborhoodIdsJson).Any(search.NeighborhoodIds.Contains)
                || search.StreetIds.Count > 0 && VerifiedStreetId(property, location) is { } streetId && search.StreetIds.Contains(streetId));
    }

    public static bool CanRecommend(Property property, SearchRequest search, double? locationDistanceKm = null)
    {
        var prepared = Prepare(search);
        return BaseEligible(property, prepared) && (ExactLocation(property, prepared)
            || prepared.HasNonStreetLocations && locationDistanceKm is { } km && double.IsFinite(km) && km >= 0);
    }

    public static MatchEvaluation Evaluate(Property property, CompiledSearch search, bool includeReasons = true,
        double? locationDistanceKm = null)
    {
        if (!BaseEligible(property, search)) return new(false, false, 0, []);
        var exactLocation = ExactLocation(property, search);
        // Street identity is deliberately not expanded to its town or inferred
        // from another street's coordinates. A supplied distance is server-owned.
        if (!exactLocation && (!search.HasNonStreetLocations || locationDistanceKm is not { } km || !double.IsFinite(km) || km < 0))
            return new(false, false, 0, []);
        var s = search.Source;
        double distanceSquared = 0d;
        var different = !exactLocation;
        List<string>? differences = includeReasons ? [] : null;
        void Add(decimal criterionWeight, bool active, decimal penalty, string label)
        {
            if (!active) return;
            var amount = (double)Math.Max(0m, penalty);
            distanceSquared += (double)criterionWeight * amount * amount;
            if (amount <= 0) return;
            different = true;
            differences?.Add(label + ": eltérés a kereséstől");
        }
        if (!exactLocation)
        {
            var distance = locationDistanceKm!.Value / LocationDistanceScaleKm;
            distanceSquared += (double)LocationWeight * distance * distance;
            differences?.Add("Helyszín: eltérés a kereséstől");
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
        var floorLoss = search.Floors.Length == 0 ? 0m : KnownFloor(property)
            ? search.Floors.Min(wanted => wanted == 9m && property.Floor!.Value >= 9m ? 0m : Math.Abs(wanted - property.Floor!.Value) / 5m) : 1m;
        if (s.ExcludeTopFloor && !BelowTopFloor(property)) floorLoss = Math.Max(floorLoss, 1m);
        if (s.ExcludeGroundFloorAndBelow && !AboveGroundFloor(property)) floorLoss = Math.Max(floorLoss, 1m);
        if (!PropertyAttributes.AtticSatisfied(property, s.AtticPreference)) floorLoss = Math.Max(floorLoss, 1m);
        Add(FloorWeight, !search.House && (search.Floors.Length > 0 || s.ExcludeTopFloor || s.ExcludeGroundFloorAndBelow || s.AtticPreference.Length > 0), floorLoss, "Emelet");
        Add(ElevatorWeight, !search.House && s.Elevator, property.Elevator ? 0 : 1, "Lift");
        Add(BalconyWeight, !search.House && s.Balcony, property.Balcony == true ? 0 : 1, "Erkély");
        Add(AirConditioningWeight, s.AirConditioning, property.AirConditioning == true ? 0 : 1, "Légkondi");
        Add(PrivateGardenWeight, search.Flat && s.PrivateGarden, property.PrivateGarden == true ? 0 : 1, "Saját kert");
        Add(BuildingWeight, search.Buildings.Count > 0, CategoryLoss(Canonical(property.Building, PropertyAttributes.Buildings), search.Buildings, PropertyAttributes.Buildings), "Falazat");
        Add(HeatingWeight, search.Heating.Count > 0, CategoryLoss(PropertyAttributes.NormalizeHeating(property.HeatingType), search.Heating, PropertyAttributes.HeatingTypes), "Fűtés típusa");
        Add(EnergyWeight, s.MinEnergyRating.Length > 0, EnergyCertificates.Loss(property, s.MinEnergyRating), "Energetikai tanúsítvány");
        var age = Array.IndexOf(PropertyAttributes.ConstructionAges, Canonical(property.ConstructionAge, PropertyAttributes.ConstructionAges));
        var ageLoss = age < 0 || search.Ages.Count == 0 ? 1m : search.Ages.Min(value => Math.Abs(Array.IndexOf(PropertyAttributes.ConstructionAges, value) - age) / 4m);
        Add(AgeWeight, search.Ages.Count > 0, ageLoss, "Építési kor");
        var ceiling = Canonical(property.CeilingHeight, PropertyAttributes.CeilingHeights);
        Add(CeilingWeight, !string.IsNullOrEmpty(s.CeilingHeight), PropertyAttributes.CeilingHeights.Contains(ceiling) && ceiling == s.CeilingHeight ? 0 : 1, "Belmagasság");
        Add(ViewWeight, search.Views.Count > 0, CategoryLoss(Canonical(property.View, PropertyAttributes.Views), search.Views, PropertyAttributes.Views), "Kilátás");
        var exact = !different;
        var score = exact ? 100 : ScoreFromDistanceSquared(distanceSquared);
        return new(true, exact, score, !includeReasons ? [] : exact
            ? ["Megfelelő elhelyezkedés", "A megadott árkereten belül", "Megfelelő alapterület és szobaszám"] : differences!.ToArray()) {
                DistanceSquared = distanceSquared,
                LocationDistanceKm = exactLocation ? 0d : locationDistanceKm,
                MatchDetails = includeReasons ? Explain(property, search, exactLocation, locationDistanceKm) : []
            };
    }

    public static int ScoreFromDistanceSquared(double distanceSquared) =>
        double.IsNaN(distanceSquared) || distanceSquared < 0 ? 0
            : Math.Clamp((int)Math.Round(100d * Math.Exp(-Math.Sqrt(distanceSquared)), MidpointRounding.AwayFromZero), 0, 99);

    private static readonly CultureInfo Hungarian = CultureInfo.GetCultureInfo("hu-HU");
    private static string Number(decimal value) => value.ToString("0.######", Hungarian);
    private static string Floor(decimal value, bool bucket = false) => value switch {
        -1m => "Szuterén", 0m => "Földszint", .5m => "Magasföldszint", 9m when bucket => "9. emelet vagy afölötti", _ => Number(value) + ". emelet"
    };
    private static string Known(string value, string[] options) => options.Contains(value) ? value : "Nincs megadva";

    // Built only for cards actually returned, never during the lean ranking scan.
    // The requested value remains separate from the listing's value so both
    // successful and unsuccessful criteria can be rendered without guessing.
    private static MatchCriterion[] Explain(Property p, CompiledSearch q, bool exactLocation, double? locationDistanceKm)
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
        var actualLocation = location.Label;
        if (!exactLocation && locationDistanceKm is { } distance)
            actualLocation += " (kb. " + distance.ToString("0.#", Hungarian) + " km-re a keresett területtől)";
        Add("location", "Helyszín", string.Join(" vagy ", LocationCatalog.ForSearch(s).Select(value => value.Label)), actualLocation, exactLocation);
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
                KnownFloor(p) ? Floor(p.Floor!.Value, p.FloorIsUpperRange) : "Nincs megadva",
                KnownFloor(p) && q.Floors.Any(value => value == p.Floor!.Value || value == 9m && p.Floor!.Value >= 9m));
        if (!q.House && s.Elevator) Add("elevator", "Lift", "Van lift", p.Elevator ? "Van lift" : "Nincs lift", p.Elevator);
        if (!q.House && s.Balcony) Add("balcony", "Erkély", "Van erkély", p.Balcony is null ? "Nincs megadva" : p.Balcony == true ? "Van erkély" : "Nincs erkély", p.Balcony == true);
        if (!q.House && s.ExcludeTopFloor) Add("excludeTopFloor", "Legfelső emelet", "Nem legfelső emelet",
            !KnownTopFloor(p) ? "Nincs megadva" : BelowTopFloor(p) ? "Nem legfelső emelet" : "Legfelső emelet", BelowTopFloor(p));
        if (!q.House && s.ExcludeGroundFloorAndBelow) Add("excludeGroundFloorAndBelow", "Földszint és szuterén", "Földszint felett",
            KnownFloor(p) ? Floor(p.Floor!.Value, p.FloorIsUpperRange) : "Nincs megadva", AboveGroundFloor(p));
        if (!q.House && s.AtticPreference.Length > 0) Add("atticPreference", "Tetőtér", s.AtticPreference == "only" ? "Tetőtéri ingatlan" : "Nem tetőtéri ingatlan",
            p.IsAttic is null ? "Nincs megadva" : p.IsAttic == true ? "Tetőtéri ingatlan" : "Nem tetőtéri ingatlan", PropertyAttributes.AtticSatisfied(p, s.AtticPreference));
        if (s.AirConditioning) Add("airConditioning", "Légkondi", "Van légkondi",
            p.AirConditioning is null ? "Nincs megadva" : p.AirConditioning == true ? "Van légkondi" : "Nincs légkondi", p.AirConditioning == true);
        if (q.Flat && s.PrivateGarden) Add("privateGarden", "Saját kert", "Van saját kert",
            p.PrivateGarden is null ? "Nincs megadva" : p.PrivateGarden == true ? "Van saját kert" : "Nincs saját kert", p.PrivateGarden == true);
        Category("building", "Falazat", Canonical(p.Building, PropertyAttributes.Buildings), q.Buildings, PropertyAttributes.Buildings);
        Category("heatingType", "Fűtés típusa", PropertyAttributes.NormalizeHeating(p.HeatingType), q.Heating, PropertyAttributes.HeatingTypes);
        if (s.MinEnergyRating.Length > 0) Add("minEnergyRating", "Energetikai tanúsítvány", s.MinEnergyRating + " vagy jobb",
            EnergyCertificates.IsCurrent(p) ? p.EnergyRating : "Nincs megadva", EnergyCertificates.MinimumSatisfied(p, s.MinEnergyRating));
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
        var heating = PropertyAttributes.NormalizeHeating(p.HeatingType);
        quality += heating == "Hőszivattyú" ? .025m : ValueHeating.Contains(heating) ? .015m : PropertyAttributes.HeatingTypes.Contains(heating) && heating != "Nincs fűtés" ? .005m : 0m;
        quality += p.Insulated == true ? .015m : 0m;
        var energy = Rules.Normalize(p.EnergyRating);
        quality += TopEnergy.IsMatch(energy) ? .02m : GoodEnergy.IsMatch(energy) ? .015m : AverageEnergy.IsMatch(energy) ? .005m : 0m;
        quality += p.AirConditioning == true ? .01m : 0m;
        var flat = Rules.Normalize(p.Type) == "LAKAS";
        quality += flat && p.PrivateGarden == true ? .015m : 0m;
        quality += p.SolarPanels == true ? .015m : 0m;
        var parking = PropertyAttributes.Parking(p);
        quality += parking.Any(value => value is "Garázs" or "Mélygarázs" or "Teremgarázs") ? .015m
            : parking.Any(value => value is "Fedett beálló" or "Udvari beálló") ? .01m : 0m;
        quality += Canonical(p.CeilingHeight, PropertyAttributes.CeilingHeights) == "3 m feletti" ? .005m : 0m;
        quality += !house && KnownFloor(p) && p.Floor is >= 0 and <= 3 ? .005m : 0m;
        quality += !house && p.Balcony == true ? .01m : 0m;
        quality += !house && p.Elevator ? .01m : 0m;
        quality += Math.Min(1m, Math.Max(0m, p.Rooms) / (p.Area / 25m)) * .005m;
        var land = house ? Math.Max(0m, p.LotArea ?? 0m) : 0m;
        var effectiveArea = p.Area + .04m * Math.Min(land, 5m * p.Area);
        return effectiveArea / (p.Price / 1_000_000m) * (1m + Math.Min(.25m, quality));
    }

    public static decimal SpecificityWeight(string criterion) => FocusWeights[criterion];

    public static int Specificity(SearchRequest search, bool sellerPerspective = false) => Prepare(search, sellerPerspective).Specificity;
    private static int SpecificityOf(CompiledSearch search)
    {
        var s = search.Source;
        var coverage = search.Cities.Count + search.DistrictIds.Count / 23d + search.NeighborhoodIds.Count / 100d
            + search.StreetIds.Count / 10000d;
        decimal selected = coverage > 0 ? (decimal)(8d / (1d + Math.Log2(1d + coverage))) : 0m, total = 8m;
        void Add(decimal weight, decimal strength) { total += weight; selected += weight * Unit(strength); }
        void Bounds(decimal? minimum, decimal? maximum, decimal minWeight, decimal maxWeight)
        {
            var min = minimum is > 0; var max = maximum.HasValue;
            var strength = min && max ? .5m + .5m * Unit(maximum is > 0 ? minimum!.Value / maximum.Value : 1m) : .5m;
            Add(minWeight, min ? strength : 0m); Add(maxWeight, max ? strength : 0m);
        }
        static decimal Category(int count, int options) => count == 0 ? 0m : (decimal)(1d / Math.Sqrt(Math.Min(count, options)));
        Bounds(s.MinPrice, s.MaxPrice, FocusWeights["minPrice"], FocusWeights["maxPrice"]);
        Bounds(s.MinArea, s.MaxArea, FocusWeights["minArea"], FocusWeights["maxArea"]);
        Bounds(s.MinRooms, s.MaxRooms, FocusWeights["minRooms"], FocusWeights["maxRooms"]);
        Add(FocusWeights["condition"], search.ConditionMinimum.HasValue ? (search.ConditionMinimum.Value + 1m) / 4m : 0m);
        Add(FocusWeights["building"], Category(search.Buildings.Count, PropertyAttributes.Buildings.Length));
        Add(FocusWeights["heatingType"], Category(search.Heating.Count, PropertyAttributes.HeatingTypes.Length));
        Add(FocusWeights["minEnergyRating"], EnergyCertificates.Rank(s.MinEnergyRating) >= 0 ? (EnergyCertificates.Rank(s.MinEnergyRating) + 1m) / 12m : 0m);
        Add(FocusWeights["constructionAge"], Category(search.Ages.Count, PropertyAttributes.ConstructionAges.Length));
        Add(FocusWeights["view"], Category(search.Views.Count, PropertyAttributes.Views.Length));
        Add(FocusWeights["ceilingHeight"], string.IsNullOrEmpty(s.CeilingHeight) ? 0m : 1m);
        Add(FocusWeights["airConditioning"], s.AirConditioning ? 1m : 0m);
        if (search.Flat)
        {
            Add(FocusWeights["privateGarden"], s.PrivateGarden ? 1m : 0m);
        }
        if (!search.House)
        {
            Add(FocusWeights["floor"], Math.Max(Category(search.Floors.Length, 12), s.ExcludeTopFloor || s.ExcludeGroundFloorAndBelow || s.AtticPreference.Length > 0 ? 1m : 0m));
            Add(FocusWeights["elevator"], s.Elevator ? 1m : 0m); Add(FocusWeights["balcony"], s.Balcony ? 1m : 0m);
        }
        return Math.Clamp((int)Math.Round(100m * selected / total, MidpointRounding.AwayFromZero), 0, 100);
    }
}
