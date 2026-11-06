using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class SellerFormTests
{
    private static PropertyInput Input() => new(
        "Világos otthon", "Debrecen", null, null, null, "Szerethető otthon.",
        "Lakás", 80_000_000m, 70m, 3m, 2, null, null, true, true, [],
        LocationId: "city:Debrecen");
    private static JsonElement Field(JsonElement item, string name) =>
        item.EnumerateObject().Single(value => value.Name.Equals(name, StringComparison.OrdinalIgnoreCase)).Value;

    [Fact]
    public void SeparateRoomCountsPreserveTheirCompositionAndUseWeightedTotalForMatching()
    {
        var property = new Property { OwnerId = Guid.NewGuid() };
        Rules.Apply(property, Input() with { Rooms = 3.5m, WholeRooms = 2, HalfRooms = 3 });
        Assert.Equal(2, property.WholeRooms);
        Assert.Equal(3, property.HalfRooms);
        Assert.Equal(3.5m, property.Rooms);
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(2, Field(dto.RootElement, "wholeRooms").GetInt32());
        Assert.Equal(3, Field(dto.RootElement, "halfRooms").GetInt32());
        Assert.Equal(3.5m, Field(dto.RootElement, "rooms").GetDecimal());
        var search = new SearchRequest {
            OwnerId = Guid.NewGuid(), City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]",
            MinRooms = 3.5m, MaxRooms = 3.5m
        };
        Assert.True(Rules.Compatible(property, search));
        search.MinRooms = 4m; search.MaxRooms = null;
        Assert.False(Rules.Compatible(property, search));
    }

    [Theory]
    [InlineData(2, null, 2)]
    [InlineData(null, 3, 1.5)]
    public void OneExplicitRoomCountDefaultsTheOtherToZero(int? whole, int? half, double total)
    {
        var property = new Property();
        Rules.Apply(property, Input() with { Rooms = 0m, WholeRooms = whole, HalfRooms = half });
        Assert.Equal(whole ?? 0, property.WholeRooms);
        Assert.Equal(half ?? 0, property.HalfRooms);
        Assert.Equal((decimal)total, property.Rooms);
    }

    [Theory]
    [InlineData(-1, 1)]
    [InlineData(1, -1)]
    [InlineData(0, 0)]
    [InlineData(1000, 1)]
    [InlineData(0, 1001)]
    [InlineData(0, 2001)]
    [InlineData(int.MaxValue, int.MaxValue)]
    public void InvalidRoomCountsCannotBeSaved(int whole, int half)
    {
        var error = Assert.Throws<ApiException>(() => Rules.Apply(new Property(), Input() with { WholeRooms = whole, HalfRooms = half }));
        Assert.Equal(400, error.Status);
    }

    [Theory]
    [InlineData(3, 3, 0)]
    [InlineData(3.5, 3, 1)]
    [InlineData(.5, 0, 1)]
    public void LegacyHalfStepTotalsHaveLosslessDisplayCountsWithoutChangingStoredColumns(double total, int whole, int half)
    {
        var property = new Property { Rooms = (decimal)total };
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(whole, Field(dto.RootElement, "wholeRooms").GetInt32());
        Assert.Equal(half, Field(dto.RootElement, "halfRooms").GetInt32());
        Assert.Null(property.WholeRooms); Assert.Null(property.HalfRooms);
        Assert.Equal((decimal)total, property.Rooms);
    }

    [Fact]
    public void ArbitraryLegacyRoomFractionsStayExactInsteadOfBeingRoundedToHalfRooms()
    {
        var property = new Property();
        Rules.Apply(property, Input() with { Rooms = 3.2m });
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(3.2m, Field(dto.RootElement, "rooms").GetDecimal());
        Assert.Equal(JsonValueKind.Null, Field(dto.RootElement, "wholeRooms").ValueKind);
        Assert.Equal(JsonValueKind.Null, Field(dto.RootElement, "halfRooms").ValueKind);
        Assert.Null(property.WholeRooms); Assert.Null(property.HalfRooms);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(0d)]
    [InlineData(-1d)]
    [InlineData(10000001d)]
    public void HousesRequireAValidLotAreaOnEverySave(double? lotArea)
    {
        var property = new Property { Type = "Ház", LotArea = null };
        var error = Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { Type = "Ház", LotArea = lotArea.HasValue ? (decimal)lotArea.Value : null }));
        Assert.Equal(400, error.Status);
    }

    [Fact]
    public void HouseSaveClearsApartmentOnlyFieldsAndApartmentSaveClearsPlotArea()
    {
        var property = new Property();
        Rules.Apply(property, Input() with { Type = "Ház", LotArea = 600m, Floor = -100, Balcony = true, Elevator = true });
        Assert.Equal(600m, property.LotArea);
        Assert.Null(property.Floor); Assert.False(property.Balcony); Assert.False(property.Elevator);
        Rules.Apply(property, Input() with { LotArea = 600m });
        Assert.Null(property.LotArea);
        Assert.Equal(2, property.Floor); Assert.True(property.Balcony); Assert.True(property.Elevator);
    }

    [Fact]
    public void ReadingAnOldHouseDoesNotRewriteItsMissingLotAreaOrApartmentOnlyValues()
    {
        var property = new Property { Type = "Ház", LotArea = null, Floor = 3, Balcony = true, Elevator = true };
        _ = Dto.Property(property);
        Assert.Null(property.LotArea);
        Assert.Equal(3, property.Floor); Assert.True(property.Balcony); Assert.True(property.Elevator);
    }

    [Theory]
    [InlineData("price")]
    [InlineData("area")]
    [InlineData("rooms")]
    public void NegativePropertyMeasurementsAreRejectedByTheApi(string field)
    {
        var input = field switch {
            "price" => Input() with { Price = -1m },
            "area" => Input() with { Area = -1m },
            _ => Input() with { Rooms = -1m }
        };
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(new Property(), input)).Status);
    }
    [Fact]
    public void ExplicitCountsRequireAConsistentNonnegativeCompatibilityTotal()
    {
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), Input() with { Rooms = 4m, WholeRooms = 2, HalfRooms = 3 }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), Input() with { Rooms = -1m, WholeRooms = 2, HalfRooms = 3 }));
        var property = new Property();
        Rules.Apply(property, Input() with { Rooms = 0m, WholeRooms = 2, HalfRooms = 3 });
        Assert.Equal(3.5m, property.Rooms);
        Rules.Apply(property, Input() with { Rooms = 3.5m });
        Assert.Equal(2, property.WholeRooms); Assert.Equal(3, property.HalfRooms);
        Rules.Apply(property, Input() with { Rooms = 4.5m });
        Assert.Equal(4, property.WholeRooms); Assert.Equal(1, property.HalfRooms);
    }

    [Fact]
    public void HeatingUsesTheCommonChoicesAndPreservesOnlyAnUnchangedLegacyPrimaryValue()
    {
        var property = new Property();
        Rules.Apply(property, Input() with { HeatingType = "gazkazan", SecondaryHeatingType = "Kandalló" });
        Assert.Equal("Gázkazán", property.HeatingType); Assert.Equal("Kandalló", property.SecondaryHeatingType);
        Rules.Apply(property, Input() with { HeatingType = "Nincs fűtés" });
        Assert.Equal("Nincs fűtés", property.HeatingType); Assert.Equal("", property.SecondaryHeatingType);
        property.HeatingType = "Hőszivattyú és padlófűtés";
        Rules.Apply(property, Input() with { HeatingType = property.HeatingType });
        Assert.Equal("Hőszivattyú és padlófűtés", property.HeatingType);
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), Input() with { HeatingType = property.HeatingType }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { HeatingType = "Másik régi fűtés" }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { SecondaryHeatingType = "Hőszivattyú és padlófűtés" }));
    }

    [Fact]
    public void MultipleParkingChoicesAreCanonicalDistinctAndAnExplicitEmptyListClearsThem()
    {
        var property = new Property();
        Rules.Apply(property, Input() with { ParkingTypes = ["garazs", "Garázs", "Udvari beálló"] });
        Assert.Equal(new[] { "Garázs", "Udvari beálló" }, PropertyAttributes.Parking(property));
        Assert.Equal("Garázs, Udvari beálló", property.ParkingType);
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(2, Field(dto.RootElement, "parkingTypes").GetArrayLength());
        Rules.Apply(property, Input() with { ParkingType = property.ParkingType });
        Assert.Equal(new[] { "Garázs", "Udvari beálló" }, PropertyAttributes.Parking(property));
        Rules.Apply(property, Input() with { ParkingType = "Garázs", ParkingTypes = [] });
        Assert.Empty(PropertyAttributes.Parking(property)); Assert.Equal("", property.ParkingType);
    }

    [Fact]
    public void LegacyParkingProseIsOneSelectionAndMayOnlyBeRetainedUnchanged()
    {
        var property = new Property { ParkingType = "Garázs és udvari beálló" };
        Assert.Equal(new[] { "Garázs és udvari beálló" }, PropertyAttributes.Parking(property));
        Assert.Null(property.ParkingTypesJson);
        Rules.Apply(property, Input() with { ParkingType = property.ParkingType });
        Assert.Equal(new[] { "Garázs és udvari beálló" }, PropertyAttributes.Parking(property));
        Rules.Apply(property, Input() with { ParkingTypes = ["Garázs és udvari beálló", "Garázs"] });
        Assert.Equal(2, PropertyAttributes.Parking(property).Length);
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), Input() with { ParkingTypes = ["Garázs és udvari beálló"] }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { ParkingTypes = ["Másik egyéni parkoló"] }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { ParkingTypes = [null!] }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { ParkingTypes = [""] }));
        Assert.Throws<ApiException>(() => Rules.Apply(property, Input() with { ParkingTypes = Enumerable.Repeat("Garázs", 21).ToArray() }));
    }

    [Fact]
    public void HeatingSearchUsesOrWithinThePrimaryFilterButNeverTheSupplementarySystem()
    {
        var property = new Property { OwnerId = Guid.NewGuid() };
        Rules.Apply(property, Input() with { HeatingType = "Gázkazán", SecondaryHeatingType = "Kandalló" });
        var search = new SearchRequest { OwnerId = Guid.NewGuid() };
        var input = new SearchInput("Otthont keresünk", "Debrecen", null, null, "Lakás", null, null, null, null, null, null, false, false, null, null,
            LocationIds: ["city:Debrecen"], HeatingTypes: ["Hőszivattyú", "gazkazan", "Gázkazán"]);
        Rules.Apply(search, input);
        Assert.Equal(new[] { "Hőszivattyú", "Gázkazán" }, Dto.Strings(search.HeatingTypesJson));
        Assert.True(Rules.Compatible(property, search));
        Rules.Apply(search, input with { HeatingTypes = ["Kandalló"] });
        Assert.False(Rules.Compatible(property, search));
        Rules.Apply(search, input with { HeatingTypes = ["Nincs fűtés"] });
        property.HeatingType = "";
        Assert.False(Rules.Compatible(property, search));
        property.HeatingType = "Nincs fűtés";
        Assert.True(Rules.Compatible(property, search));
        Rules.Apply(search, input with { HeatingTypes = [] });
        property.HeatingType = "";
        Assert.True(Rules.Compatible(property, search));
        Assert.Throws<ApiException>(() => Rules.Apply(search, input with { HeatingTypes = ["Ismeretlen"] }));
    }

    [Fact]
    public void HouseSearchSaveClearsApartmentOnlyRestrictionsAndLegacyHouseFiltersAreIgnoredOnRead()
    {
        var property = new Property { OwnerId = Guid.NewGuid(), Type = "Ház", City = "Debrecen", Rooms = 3m, Price = 80_000_000m, Area = 70m };
        var search = new SearchRequest {
            OwnerId = Guid.NewGuid(), Type = "Ház", City = "Debrecen", Balcony = true, Elevator = true, FloorsJson = "[9]"
        };
        Assert.True(Rules.Compatible(property, search));
        Assert.True(search.Balcony); Assert.True(search.Elevator); Assert.Equal("[9]", search.FloorsJson);
        Assert.DoesNotContain("Erkéllyel", Rules.Reasons(property, search));
        Assert.DoesNotContain("Liftes épület", Rules.Reasons(property, search));
        Rules.Apply(search, new SearchInput("Házat keresünk", "Debrecen", null, null, "Ház", null, null, null, null, null, null, true, true, null, null,
            LocationIds: ["city:Debrecen"], Floors: [9]));
        Assert.False(search.Balcony); Assert.False(search.Elevator); Assert.Empty(PropertyAttributes.Floors(search.FloorsJson));
    }

    [Fact]
    public void NewColumnsAreAdditiveAndNullableWhereLegacyRowsNeedAnUnknownValue()
    {
        var options = new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options;
        using var db = new AppDb(options);
        var property = db.Model.FindEntityType(typeof(Property))!;
        Assert.True(property.FindProperty(nameof(Property.WholeRooms))!.IsNullable);
        Assert.True(property.FindProperty(nameof(Property.HalfRooms))!.IsNullable);
        Assert.True(property.FindProperty(nameof(Property.ParkingTypesJson))!.IsNullable);
        Assert.Equal("longtext", property.FindProperty(nameof(Property.ParkingTypesJson))!.GetColumnType());
        Assert.False(property.FindProperty(nameof(Property.SecondaryHeatingType))!.IsNullable);
        var heating = db.Model.FindEntityType(typeof(SearchRequest))!.FindProperty(nameof(SearchRequest.HeatingTypesJson))!;
        Assert.True(heating.IsNullable); Assert.Equal("longtext", heating.GetColumnType());
        Assert.Equal("20261106-seller-form-details", SchemaUpgrade.SellerFormDetailsVersion);
    }

}
