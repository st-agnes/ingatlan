using System.Globalization;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class FloorRefinementTests
{
    private static PropertyInput Input() => new(
        "Világos otthon", "Debrecen", null, null, null, "Otthon a városban.",
        "Lakás", 75_000_000m, 65m, 2.5m, 2, null, null, false, false, [],
        LocationId: "city:Debrecen", WholeRooms: 2, HalfRooms: 1,
        Street: "Fiktív teszt utca", HouseNumber: "12");
    private static SearchInput SearchInput() => new(
        "Városi otthont keresek", "Debrecen", [], "Világos otthont keresek.",
        "Lakás", null, 90_000_000m, 50m, null, 2m, null, false, false, "Rugalmas", "",
        LocationIds: ["city:Debrecen"]);
    private static Property Home() => new() {
        OwnerId = Guid.NewGuid(), LocationId = "city:Debrecen", City = "Debrecen", Type = "Lakás",
        Price = 75_000_000m, Area = 65m, Rooms = 2.5m
    };
    private static SearchRequest Wanted() => new() {
        OwnerId = Guid.NewGuid(), LocationIdsJson = "[\"city:Debrecen\"]", City = "Debrecen", Type = "Lakás"
    };
    private static MatchEvaluation Match(Property home, SearchRequest search) =>
        MatchingRanking.Evaluate(home, MatchingRanking.Prepare(search));
    private static JsonElement Field(object value, string name) => JsonSerializer.SerializeToElement(value,
        new JsonSerializerOptions(JsonSerializerDefaults.Web)).GetProperty(name);

    [Fact]
    public void RaisedGroundFloorPersistsAsAHalfLevelAndHasItsOwnSearchSelection()
    {
        var home = Home();
        Rules.Apply(home, Input() with { Floor = .5m, BuildingFloors = 1 });
        Assert.Equal(.5m, home.Floor); Assert.False(home.FloorIsUpperRange);
        Assert.Equal(.5m, Field(Dto.Property(home), "floor").GetDecimal());
        var search = Wanted();
        Rules.Apply(search, SearchInput() with { Floors = [.5m] });
        Assert.Equal(new[] { .5m }, PropertyAttributes.Floors(search.FloorsJson));
        Assert.True(Match(home, search).IsExact);
        var detail = Assert.Single(Match(home, search).MatchDetails.Where(value => value.Key == "floor"));
        Assert.Equal("Magasföldszint", detail.Expected); Assert.Equal("Magasföldszint", detail.Actual);
        home.Floor = 0; Assert.False(Match(home, search).IsExact);
        home.Floor = 1; Assert.False(Match(home, search).IsExact);
    }

    [Fact]
    public void RaisedGroundIsAboveGroundButIsTheTopOfAGroundOnlyBuilding()
    {
        var home = Home();
        Rules.Apply(home, Input() with { Floor = .5m, BuildingFloors = 0 });
        var search = Wanted(); search.ExcludeGroundFloorAndBelow = true;
        Assert.True(Match(home, search).IsExact);
        search.ExcludeTopFloor = true;
        Assert.False(Match(home, search).IsExact);
        home.BuildingFloors = 1;
        Assert.True(Match(home, search).IsExact);
    }

    [Theory]
    [InlineData("-0.5")]
    [InlineData("1.5")]
    [InlineData("9.5")]
    [InlineData("199.5")]
    [InlineData("201")]
    public void OnlyRaisedGroundIsAnAcceptedNonIntegerFloor(string raw)
    {
        var floor = decimal.Parse(raw, CultureInfo.InvariantCulture);
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(Home(), Input() with { Floor = floor })).Status);
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(Wanted(), SearchInput() with { Floors = [floor] })).Status);
    }

    [Fact]
    public void OldNineTenAndElevenSelectionsBecomeOneEightOrHigherBucketWithoutMutatingInput()
    {
        var input = SearchInput() with { Floors = [9m, 10m, 11m, .5m] };
        var search = Wanted(); Rules.Apply(search, input);
        Assert.Equal(new[] { 8m, .5m }, PropertyAttributes.Floors(search.FloorsJson));
        Assert.Equal(new[] { 9m, 10m, 11m, .5m }, input.Floors!);
        foreach (var actual in new[] { 8m, 9m, 10m, 11m, 12m, 200m })
        {
            var home = Home(); home.Floor = actual;
            Assert.True(Match(home, search).IsExact);
        }
        search.FloorsJson = "[11]";
        var upper = Home(); upper.Floor = 9m;
        Assert.True(Match(upper, search).IsExact);
        Assert.Equal("8. emelet vagy afölötti", Assert.Single(Match(upper, search).MatchDetails.Where(d => d.Key == "floor")).Expected);
    }

    [Fact]
    public void AGroupedUpperFloorDoesNotPretendToKnowWhetherItIsTheTopFloor()
    {
        var home = Home(); Rules.Apply(home, Input() with { Floor = 9m, FloorIsUpperRange = true, BuildingFloors = 12 });
        Assert.True(home.FloorIsUpperRange);
        Assert.True(Field(Dto.Property(home), "floorIsUpperRange").GetBoolean());
        var search = Wanted(); search.FloorsJson = "[9]";
        Assert.True(Match(home, search).IsExact);
        Assert.Equal("9. emelet vagy afölötti", Assert.Single(Match(home, search).MatchDetails.Where(d => d.Key == "floor")).Actual);
        search.ExcludeGroundFloorAndBelow = true; Assert.True(Match(home, search).IsExact);
        search.ExcludeTopFloor = true; Assert.False(Match(home, search).IsExact);
        Assert.Equal("Nincs megadva", Assert.Single(Match(home, search).MatchDetails.Where(d => d.Key == "excludeTopFloor")).Actual);
        Rules.Apply(home, Input() with { Floor = 12m, BuildingFloors = 13 });
        Assert.Equal(12m, home.Floor); Assert.False(home.FloorIsUpperRange);
        Assert.True(Match(home, search).IsExact);
    }

    [Fact]
    public void AnUpperRangeFlagRequiresTheBucketAndHousesClearIt()
    {
        foreach (var floor in new decimal?[] { null, .5m, 8m, 12m })
            Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(Home(),
                Input() with { Floor = floor, FloorIsUpperRange = true })).Status);
        var house = Home();
        Rules.Apply(house, Input() with { Type = "Ház", LotArea = 500, Floor = 9, FloorIsUpperRange = true });
        Assert.Null(house.Floor); Assert.False(house.FloorIsUpperRange);
    }

    [Fact]
    public void FloorPrecisionAndUpperRangeDefaultsMatchFreshAndUpgradedDatabaseContracts()
    {
        using var db = new AppDb(new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=127.0.0.1;Database=not-connected;User=test;Password=test", new MySqlServerVersion(new Version(8, 4, 0))).Options);
        var property = db.Model.FindEntityType(typeof(Property))!;
        Assert.Equal(4, property.FindProperty(nameof(Property.Floor))!.GetPrecision());
        Assert.Equal(1, property.FindProperty(nameof(Property.Floor))!.GetScale());
        var grouped = property.FindProperty(nameof(Property.FloorIsUpperRange))!;
        Assert.False(grouped.IsNullable); Assert.Equal(false, grouped.GetDefaultValue());
        Assert.Equal("20261124-raised-and-upper-floor-range", SchemaUpgrade.RaisedAndUpperFloorVersion);
    }

    [Fact]
    public void FrozenIntegerFloorAndOldSearchBucketCreationFingerprintsRemainCompatible()
    {
        // Canonical pre-feature fingerprints, independently verified against
        // the existing baseline property/search hashes before changing floors.
        var property = Input() with { Floor = 12m, CreationRequestId = Guid.NewGuid() };
        var search = SearchInput() with { Floors = [11m], CreationRequestId = Guid.NewGuid() };
        const string oldPropertyHash = "955F4857385B7D81C53AA57170EB2E009FE00CF84A96A6BB22769207632B9ED3";
        const string oldSearchHash = "A32AA8638A315F280F234BBBA8F724D05B03CD59F893A8662130A2B73B555522";
        Assert.Equal(oldPropertyHash, EntityCreation.RequestHash(property));
        Assert.Equal(oldSearchHash, EntityCreation.RequestHash(search));
        Rules.Apply(Home(), property); Rules.Apply(Wanted(), search);
        EntityCreation.VerifyReplay(oldPropertyHash, EntityCreation.RequestHash(property));
        EntityCreation.VerifyReplay(oldSearchHash, EntityCreation.RequestHash(search));
        Assert.NotEqual(EntityCreation.RequestHash(property), EntityCreation.RequestHash(property with { Floor = 9, FloorIsUpperRange = true }));
    }

    [Fact]
    public void PublicPrefillsKeepRaisedAndUpperRangeFactsWithoutExposingAddressData()
    {
        var home = Home(); home.Floor = .5m;
        var seed = PublicLanding.PropertyTeaser(home, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.Equal(.5m, seed.Floor); Assert.False(seed.FloorIsUpperRange);
        home.Floor = 9m; home.FloorIsUpperRange = true;
        seed = PublicLanding.PropertyTeaser(home, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.True(seed.FloorIsUpperRange);
        home.Type = "Ház";
        seed = PublicLanding.PropertyTeaser(home, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.Null(seed.Floor); Assert.False(seed.FloorIsUpperRange);
    }
}
