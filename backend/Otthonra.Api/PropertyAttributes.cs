using System.Text.Json;

namespace Otthonra.Api;

/// <summary>Optional, canonical attributes shared by listing validation and matching.</summary>
public static class PropertyAttributes
{
    public static readonly string[] Conditions = ["Felújítandó", "Átlagos", "Jó", "Új/felújított"];
    public static readonly string[] Buildings = ["Tégla", "Panel", "Csúsztatott zsalu", "Vályog", "Szilikát", "Vegyes falazat", "Fa", "Könnyűszerkezet", "Kő és tégla", "Rönkház", "Passzívház", "Egyéb"];
    public static readonly string[] ConstructionAges = ["10 évnél fiatalabb", "10–30 év közötti", "31–40 év közötti", "41–50 év közötti", "Több mint 50 éves"];
    public static readonly string[] Views = ["Kertre néző", "Utcai", "Udvari", "Panorámás"];
    public static readonly string[] CeilingHeights = ["3 m alatti", "3 m feletti"];

    // Old rows retain their stored value. Only the representation used for
    // reading/filtering is canonicalized; no data-rewriting migration is needed.
    public static string NormalizeCondition(string? value)
    {
        var text = value?.Trim() ?? "";
        return Rules.Normalize(text) switch
        {
            "FELUJITOTT" or "UJSZERU" or "UJ EPITESU" => "Új/felújított",
            "JO ALLAPOTU" => "Jó",
            _ => Canonical(text, Conditions)
        };
    }
    public static string NormalizeBuilding(string? value) => Canonical(value?.Trim() ?? "", Buildings);
    private static string Canonical(string value, string[] options) =>
        options.FirstOrDefault(option => Rules.Normalize(option) == Rules.Normalize(value)) ?? value;

    public static string Choice(string? value, string[] options, string name, bool condition = false)
    {
        var text = Rules.PublicText(value, 100);
        if (text.Length == 0) return "";
        var result = condition ? NormalizeCondition(text) : Canonical(text, options);
        if (!options.Contains(result)) throw new ApiException(400, $"Érvénytelen {name}.");
        return result;
    }
    private static string ChoicePreservingLegacy(string? value, string previous, string[] options, string name, bool condition = false)
    {
        var text = Rules.PublicText(value, 100);
        var canonical = condition ? NormalizeCondition(text) : Canonical(text, options);
        // Older API versions permitted arbitrary metadata. An unrelated edit
        // may retain that exact value, but cannot introduce another unknown one.
        if (text.Length > 0 && text == previous.Trim() && !options.Contains(canonical)) return text;
        return Choice(text, options, name, condition);
    }
    public static string[] Selections(string[]? values, string[] options, string name, bool condition = false)
    {
        if (values is null) return [];
        if (values.Length > options.Length) throw new ApiException(400, $"Túl sok {name} került megadásra.");
        var result = values.Select(value => Choice(value, options, name, condition)).ToArray();
        if (result.Any(string.IsNullOrEmpty)) throw new ApiException(400, $"Érvénytelen {name}.");
        return result.Distinct().ToArray();
    }
    public static int[] FloorSelections(int[]? values)
    {
        if (values is null) return [];
        if (values.Length > 13 || values.Any(value => value < -1 || value > 11))
            throw new ApiException(400, "Érvénytelen emeletlista.");
        return values.Distinct().ToArray();
    }
    public static int[] Floors(string? json) => string.IsNullOrWhiteSpace(json) ? [] : JsonSerializer.Deserialize<int[]>(json) ?? [];

    private static bool Selected(string[] selected, string? propertyValue) => selected.Length == 0
        || (!string.IsNullOrEmpty(propertyValue) && selected.Contains(propertyValue));

    public static bool Compatible(Property property, SearchRequest search)
    {
        var conditions = Dto.Strings(search.ConditionsJson).Select(NormalizeCondition).ToArray();
        var buildings = Dto.Strings(search.BuildingsJson).Select(NormalizeBuilding).ToArray();
        var floors = Floors(search.FloorsJson);
        return Selected(conditions, NormalizeCondition(property.Condition))
            && Selected(buildings, NormalizeBuilding(property.Building))
            && Selected(Dto.Strings(search.ConstructionAgesJson), property.ConstructionAge)
            && Selected(Dto.Strings(search.ViewsJson), property.View)
            && (string.IsNullOrEmpty(search.CeilingHeight) || search.CeilingHeight == property.CeilingHeight)
            && (floors.Length == 0 || property.Floor.HasValue
                && floors.Any(floor => floor == 11 ? property.Floor.Value >= 11 : floor == property.Floor.Value));
    }

    public static void Apply(Property property, PropertyInput input)
    {
        property.Condition = ChoicePreservingLegacy(input.Condition, property.Condition, Conditions, "állapot", condition: true);
        property.Building = ChoicePreservingLegacy(input.Building, property.Building, Buildings, "falazat");
        property.ConstructionAge = Choice(input.ConstructionAge, ConstructionAges, "építési korcsoport");
        property.View = Choice(input.View, Views, "kilátás");
        property.CeilingHeight = Choice(input.CeilingHeight, CeilingHeights, "belmagasság");
        property.HeatingType = Rules.PublicText(input.HeatingType, 80);
        property.EnergyRating = Rules.PublicText(input.EnergyRating, 20);
        property.ParkingType = Rules.PublicText(input.ParkingType, 80);
        property.Insulated = input.Insulated;
        property.AirConditioning = input.AirConditioning;
        property.SolarPanels = input.SolarPanels;
    }
    public static void Apply(SearchRequest search, SearchInput input)
    {
        search.ConditionsJson = JsonSerializer.Serialize(Selections(input.Conditions, Conditions, "állapot", condition: true));
        search.BuildingsJson = JsonSerializer.Serialize(Selections(input.Buildings, Buildings, "falazat"));
        search.ConstructionAgesJson = JsonSerializer.Serialize(Selections(input.ConstructionAges, ConstructionAges, "építési korcsoport"));
        search.ViewsJson = JsonSerializer.Serialize(Selections(input.Views, Views, "kilátás"));
        search.CeilingHeight = Choice(input.CeilingHeight, CeilingHeights, "belmagasság");
        search.FloorsJson = JsonSerializer.Serialize(FloorSelections(input.Floors));
    }
}
