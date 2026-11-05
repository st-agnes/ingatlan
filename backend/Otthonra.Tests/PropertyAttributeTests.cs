using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PropertyAttributeTests
{
    private static PropertyInput PropertyInput() => new(
        "Világos otthon", "Budapest", "XIII.", "Újlipótváros", null, "Kellemes otthon.",
        "Lakás", 80_000_000m, 70m, 3m, null, null, null, false, false, [],
        LocationId: "district:Budapest:13");
    private static SearchInput SearchInput() => new(
        "Otthont keresünk", "Budapest", null, "Világos lakást keresünk.", "Lakás",
        null, 100_000_000m, null, null, null, null, false, false, null, null,
        LocationIds: ["city:Budapest"]);
    private static (Property Property, SearchRequest Search) Pair()
    {
        var property = new Property { OwnerId = Guid.NewGuid() };
        var search = new SearchRequest { OwnerId = Guid.NewGuid() };
        Rules.Apply(property, PropertyInput());
        Rules.Apply(search, SearchInput());
        return (property, search);
    }
    private static JsonElement Field(JsonElement item, string name) =>
        item.EnumerateObject().Single(value => value.Name.Equals(name, StringComparison.OrdinalIgnoreCase)).Value;

    [Fact]
    public void NoNewAttributeIsRequiredAndMissingSellerDetailsDoNotRestrictAnUnfilteredSearch()
    {
        var (property, search) = Pair();
        Assert.True(Rules.Compatible(property, search));
        Assert.Equal("", property.Condition); Assert.Equal("", property.Building);
        Assert.Equal("", property.ConstructionAge); Assert.Equal("", property.View);
        Assert.Equal("", property.CeilingHeight); Assert.Null(property.Floor);
        Assert.Null(property.Insulated); Assert.Null(property.AirConditioning); Assert.Null(property.SolarPanels);
        Assert.Empty(Dto.Strings(search.ConditionsJson));
        Assert.Empty(Dto.Strings(search.BuildingsJson));
        Assert.Empty(Dto.Strings(search.ConstructionAgesJson));
        Assert.Empty(Dto.Strings(search.ViewsJson)); Assert.Empty(PropertyAttributes.Floors(search.FloorsJson));
    }

    [Fact]
    public void AlternativeChoicesWithinAFieldAreOrButDifferentFieldsAreAnd()
    {
        var (property, search) = Pair();
        Rules.Apply(property, PropertyInput() with {
            Condition = "Felújított", Building = "Panel", ConstructionAge = "31–40 év közötti",
            View = "Kertre néző", CeilingHeight = "3 m alatti", Floor = 12
        });
        Rules.Apply(search, SearchInput() with {
            Conditions = ["Jó", "Új/felújított"], Buildings = ["Tégla", "Panel"],
            ConstructionAges = ["10 évnél fiatalabb", "31–40 év közötti"], Views = ["Kertre néző", "Panorámás"],
            CeilingHeight = "3 m alatti", Floors = [0, 11]
        });
        Assert.True(Rules.Compatible(property, search));
        property.Building = "Fa";
        Assert.False(Rules.Compatible(property, search));
        property.Building = "Panel"; property.View = "Utcai";
        Assert.False(Rules.Compatible(property, search));
    }

    [Theory]
    [InlineData("condition")]
    [InlineData("building")]
    [InlineData("constructionAge")]
    [InlineData("view")]
    [InlineData("ceilingHeight")]
    [InlineData("floor")]
    public void EverySelectedAttributeRequiresKnownMatchingSellerData(string attribute)
    {
        var (property, search) = Pair();
        var input = attribute switch
        {
            "condition" => SearchInput() with { Conditions = ["Jó"] },
            "building" => SearchInput() with { Buildings = ["Tégla"] },
            "constructionAge" => SearchInput() with { ConstructionAges = ["10 évnél fiatalabb"] },
            "view" => SearchInput() with { Views = ["Panorámás"] },
            "ceilingHeight" => SearchInput() with { CeilingHeight = "3 m feletti" },
            _ => SearchInput() with { Floors = [0] }
        };
        Rules.Apply(search, input);
        Assert.False(Rules.Compatible(property, search));
    }

    [Theory]
    [InlineData(-1, -1, true)]
    [InlineData(0, -1, false)]
    [InlineData(-1, 0, false)]
    [InlineData(0, 0, true)]
    [InlineData(10, 11, false)]
    [InlineData(11, 11, true)]
    [InlineData(12, 11, true)]
    [InlineData(200, 11, true)]
    [InlineData(-2, -1, false)]
    public void FloorBucketsDistinguishBasementGroundAndElevenOrAbove(int actual, int selected, bool expected)
    {
        var (property, search) = Pair();
        property.Floor = actual;
        Rules.Apply(search, SearchInput() with { Floors = [selected] });
        Assert.Equal(expected, Rules.Compatible(property, search));
    }

    [Fact]
    public void UnsupportedNewFloorsAreRejectedButAnExistingLegacyBasementLevelCanBeKept()
    {
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { Floor = -2 }));
        var property = new Property { Floor = -2 };
        Rules.Apply(property, PropertyInput() with { Floor = -2 });
        Assert.Equal(-2, property.Floor);
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Floors = [-2] }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Floors = [12] }));
    }

    [Theory]
    [InlineData("Felújított", "Új/felújított")]
    [InlineData("Újszerű", "Új/felújított")]
    [InlineData("Új építésű", "Új/felújított")]
    [InlineData("Jó állapotú", "Jó")]
    public void ExistingConditionLabelsRemainCompatibleWithoutRewritingTheStoredRow(string previous, string canonical)
    {
        var (property, search) = Pair();
        property.Condition = previous;
        Rules.Apply(search, SearchInput() with { Conditions = [canonical] });
        Assert.True(Rules.Compatible(property, search));
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(canonical, Field(dto.RootElement, "condition").GetString());
        Assert.Equal(previous, property.Condition);
    }

    [Fact]
    public void AnUnrecognizedLegacyValueCanBePreservedButCannotBeIntroducedOrMatchAnExplicitFilter()
    {
        var (property, search) = Pair();
        property.Condition = "Korábbi egyéni állapot";
        property.Building = "Korábbi egyéni szerkezet";
        Rules.Apply(property, PropertyInput() with { Condition = property.Condition, Building = property.Building });
        Assert.Equal("Korábbi egyéni állapot", property.Condition);
        Assert.Equal("Korábbi egyéni szerkezet", property.Building);
        Assert.True(Rules.Compatible(property, search));
        Rules.Apply(search, SearchInput() with { Conditions = ["Jó"] });
        Assert.False(Rules.Compatible(property, search));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { Condition = property.Condition }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, PropertyInput() with { Building = "Másik ismeretlen" }));
    }

    [Fact]
    public void ChoiceListsAreCanonicalDistinctBoundedAndRejectUnknownOrEmptyMembers()
    {
        var search = new SearchRequest();
        Rules.Apply(search, SearchInput() with { Conditions = ["jó", "Jó"], Buildings = ["tegla", "Tégla"], Floors = [0, 0, 11] });
        Assert.Equal(new[] { "Jó" }, Dto.Strings(search.ConditionsJson));
        Assert.Equal(new[] { "Tégla" }, Dto.Strings(search.BuildingsJson));
        Assert.Equal(new[] { 0, 11 }, PropertyAttributes.Floors(search.FloorsJson));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Views = ["Ismeretlen"] }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Conditions = [""] }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Buildings = [null!] }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { CeilingHeight = "5 méter" }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInput() with { Views = Enumerable.Repeat("Utcai", 100).ToArray() }));
    }

    [Fact]
    public void OptionalSellerAddonsPreserveExplicitFalseSeparatelyFromUnknownAndAreReturnedByTheDto()
    {
        var property = new Property();
        Rules.Apply(property, PropertyInput() with {
            HeatingType = "Hőszivattyú és padlófűtés", Insulated = false, EnergyRating = "AA++",
            AirConditioning = true, SolarPanels = null, ParkingType = "Garázs és udvari beálló"
        });
        Assert.False(property.Insulated); Assert.True(property.AirConditioning); Assert.Null(property.SolarPanels);
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.False(Field(dto.RootElement, "insulated").GetBoolean());
        Assert.True(Field(dto.RootElement, "airConditioning").GetBoolean());
        Assert.Equal(JsonValueKind.Null, Field(dto.RootElement, "solarPanels").ValueKind);
        Assert.Equal("AA++", Field(dto.RootElement, "energyRating").GetString());
        Rules.Apply(property, PropertyInput());
        Assert.Null(property.Insulated); Assert.Null(property.AirConditioning); Assert.Null(property.SolarPanels);
        Assert.Equal("", property.HeatingType); Assert.Equal("", property.EnergyRating); Assert.Equal("", property.ParkingType);
    }

    [Fact]
    public void SellerFreeTextAddonsHaveLimitsAndCannotLeakContactDetails()
    {
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { HeatingType = new string('x', 81) }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { EnergyRating = new string('x', 21) }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { ParkingType = new string('x', 81) }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { HeatingType = "contact@example.hu" }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { ParkingType = "+36 30 123 4567" }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInput() with { EnergyRating = "hello@example.hu" }));
    }

    [Fact]
    public void SearchDtoReturnsAllOptionalFiltersAsListsAndEmptyFiltersClearTheRestrictions()
    {
        var (property, search) = Pair();
        Rules.Apply(search, SearchInput() with {
            Conditions = ["Átlagos", "Jó"], Buildings = ["Panel"], ConstructionAges = ["41–50 év közötti"],
            Views = ["Udvari"], CeilingHeight = "3 m alatti", Floors = [-1, 0, 11]
        });
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Search(search)));
        Assert.Equal(2, Field(dto.RootElement, "conditions").GetArrayLength());
        Assert.Equal("Panel", Field(dto.RootElement, "buildings")[0].GetString());
        Assert.Equal("41–50 év közötti", Field(dto.RootElement, "constructionAges")[0].GetString());
        Assert.Equal("Udvari", Field(dto.RootElement, "views")[0].GetString());
        Assert.Equal("3 m alatti", Field(dto.RootElement, "ceilingHeight").GetString());
        Assert.Equal(11, Field(dto.RootElement, "floors")[2].GetInt32());
        Rules.Apply(search, SearchInput());
        Assert.True(Rules.Compatible(property, search));
    }

    [Fact]
    public void SchemaUsesNullableTriStateFlagsAndNullableLongtextFilterLists()
    {
        var options = new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options;
        using var db = new AppDb(options);
        var property = db.Model.FindEntityType(typeof(Property))!;
        foreach (var name in new[] { nameof(Property.Insulated), nameof(Property.AirConditioning), nameof(Property.SolarPanels) })
            Assert.True(property.FindProperty(name)!.IsNullable);
        var search = db.Model.FindEntityType(typeof(SearchRequest))!;
        foreach (var name in new[] { nameof(SearchRequest.ConditionsJson), nameof(SearchRequest.BuildingsJson), nameof(SearchRequest.ConstructionAgesJson), nameof(SearchRequest.ViewsJson), nameof(SearchRequest.FloorsJson) })
        {
            Assert.True(search.FindProperty(name)!.IsNullable);
            Assert.Equal("longtext", search.FindProperty(name)!.GetColumnType());
        }
        Assert.Equal("20261105-property-attributes", SchemaUpgrade.PropertyAttributesVersion);
    }
}
