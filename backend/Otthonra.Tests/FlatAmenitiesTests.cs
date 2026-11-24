using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class FlatAmenitiesTests
{
    private static PropertyInput PropertyInput() => new(
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
    private static MatchEvaluation Match(Property p, SearchRequest s) => MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s));
    private static JsonElement Field(object value, string name) => JsonSerializer.SerializeToElement(value)
        .EnumerateObject().Single(field => field.Name.Equals(name, StringComparison.OrdinalIgnoreCase)).Value;

    [Theory]
    [InlineData(null, null)]
    [InlineData(0, 0)]
    [InlineData(-1, 0)]
    [InlineData(2, 2)]
    [InlineData(2, 5)]
    [InlineData(200, 200)]
    public void BuildingFloorsIsOptionalAndMeansTheHighestAboveGroundFloor(int? floor, int? buildingFloors)
    {
        var p = new Property();
        Rules.Apply(p, PropertyInput() with { Floor = floor, BuildingFloors = buildingFloors });
        Assert.Equal((decimal?)floor, p.Floor); Assert.Equal(buildingFloors, p.BuildingFloors);
    }

    [Theory]
    [InlineData(null, -1)]
    [InlineData(null, 201)]
    [InlineData(3, 2)]
    [InlineData(1, 0)]
    public void InvalidBuildingHeightOrAFloorAboveTheBuildingIsRejected(int? floor, int buildingFloors)
    {
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(new Property(),
            PropertyInput() with { Floor = floor, BuildingFloors = buildingFloors })).Status);
    }

    [Fact]
    public void SellerPrivateGardenRoundTripsWhileRetiredSharedGardenInputIsNeutralized()
    {
        var p = new Property();
        foreach (bool? value in new bool?[] { null, false, true })
        {
            Rules.Apply(p, PropertyInput() with { BuildingFloors = 5, PrivateGarden = value, SharedGarden = value });
            Assert.Equal(value, p.PrivateGarden); Assert.Null(p.SharedGarden);
            Assert.Equal(5, Field(Dto.Property(p), "buildingFloors").GetInt32());
            foreach (var name in new[] { "privateGarden" })
            {
                var field = Field(Dto.Property(p), name);
                if (value.HasValue) Assert.Equal(value.Value, field.GetBoolean());
                else Assert.Equal(JsonValueKind.Null, field.ValueKind);
            }
            Assert.Equal(JsonValueKind.Null, Field(Dto.Property(p), "sharedGarden").ValueKind);
        }
    }

    [Theory]
    [InlineData("Ház")]
    [InlineData("Telek")]
    [InlineData("Iroda")]
    public void NonFlatSavesClearGardenFieldsAndHousesAlsoClearFloorRestrictions(string type)
    {
        var p = new Property { PrivateGarden = true, SharedGarden = true, BuildingFloors = 5 };
        var house = type == "Ház";
        Rules.Apply(p, PropertyInput() with { Type = type, LotArea = 600, Floor = house ? -100 : 2,
            BuildingFloors = house ? 999 : 5, PrivateGarden = true, SharedGarden = true, AirConditioning = true });
        Assert.Null(p.PrivateGarden); Assert.Null(p.SharedGarden); Assert.True(p.AirConditioning);
        if (house) { Assert.Null(p.Floor); Assert.Null(p.BuildingFloors); }
        else Assert.Equal(5, p.BuildingFloors);
        var q = new SearchRequest();
        Rules.Apply(q, SearchInput() with { Type = type, PrivateGarden = true, SharedGarden = true,
            ExcludeTopFloor = true, ExcludeGroundFloorAndBelow = true, AirConditioning = true });
        Assert.False(q.PrivateGarden); Assert.False(q.SharedGarden); Assert.True(q.AirConditioning);
        Assert.Equal(!house, q.ExcludeTopFloor); Assert.Equal(!house, q.ExcludeGroundFloorAndBelow);
    }

    [Theory]
    [InlineData(1, 5, true)]
    [InlineData(5, 5, false)]
    [InlineData(0, 0, false)]
    [InlineData(null, 5, false)]
    [InlineData(1, null, false)]
    [InlineData(null, null, false)]
    public void TopFloorExclusionRequiresKnownProofThatTheApartmentIsBelowTheHighestFloor(int? floor, int? height, bool exact)
    {
        var p = Home(); p.Floor = floor; p.BuildingFloors = height;
        var q = Wanted(); q.ExcludeTopFloor = true;
        var result = Match(p, q);
        Assert.True(result.Eligible); Assert.Equal(exact, result.IsExact); Assert.Equal(exact ? 100 : 0, result.Score);
        Assert.Equal(exact, Assert.Single(result.MatchDetails.Where(d => d.Key == "excludeTopFloor")).Matches);
    }

    [Theory]
    [InlineData(-1, false)]
    [InlineData(0, false)]
    [InlineData(1, true)]
    [InlineData(200, true)]
    [InlineData(null, false)]
    public void GroundAndBasementExclusionNeedsAPositiveKnownFloorButNotBuildingHeight(int? floor, bool exact)
    {
        var p = Home(); p.Floor = floor;
        var q = Wanted(); q.ExcludeGroundFloorAndBelow = true;
        var result = Match(p, q);
        Assert.True(result.Eligible); Assert.Equal(exact, result.IsExact);
        Assert.Equal(exact, Assert.Single(result.MatchDetails.Where(d => d.Key == "excludeGroundFloorAndBelow")).Matches);
    }

    [Fact]
    public void CombinedFloorRestrictionsUseTheWorstFloorLossOnceRatherThanTripleCountingIt()
    {
        var p = Home(); p.Floor = 0; p.BuildingFloors = 0;
        var q = Wanted(); q.MaxPrice = 100_000_000m;
        q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = true; q.FloorsJson = "[5]";
        var result = Match(p, q);
        Assert.Equal(82, result.Score); // One failed floor weight7 against a satisfied price weight32.
        Assert.Equal(3, result.MatchDetails.Count(d => d.Key is "floor" or "excludeTopFloor" or "excludeGroundFloorAndBelow"));
        Assert.Equal(result.Score, MatchingRanking.Evaluate(p, MatchingRanking.Prepare(q), includeReasons: false).Score);
        q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = false;
        Assert.Equal(result.Score, Match(p, q).Score);
    }

    [Theory]
    [InlineData("airConditioning", null)]
    [InlineData("airConditioning", false)]
    [InlineData("airConditioning", true)]
    [InlineData("privateGarden", null)]
    [InlineData("privateGarden", false)]
    [InlineData("privateGarden", true)]
    public void RequiredAmenitiesNeedTrueAndMissingOrExplicitlyAbsentDetailsRemainPartial(string key, bool? available)
    {
        var p = Home(); var q = Wanted();
        if (key == "airConditioning") { p.AirConditioning = available; q.AirConditioning = true; }
        else { p.PrivateGarden = available; q.PrivateGarden = true; }
        var result = Match(p, q);
        Assert.True(result.Eligible); Assert.Equal(available == true, result.IsExact);
        Assert.Equal(available == true ? 100 : 0, result.Score);
        var detail = Assert.Single(result.MatchDetails.Where(d => d.Key == key));
        Assert.Equal(available == true, detail.Matches);
        if (available is null) Assert.Equal("Nincs megadva", detail.Actual);
        Assert.Empty(MatchingRanking.Evaluate(p, MatchingRanking.Prepare(q), includeReasons: false).MatchDetails);
    }

    [Fact]
    public void ActiveAmenityWeightsRemainSmallAndRetiredSharedGardenAddsNoRequirement()
    {
        var p = Home(); var q = Wanted(); q.MaxPrice = 100_000_000m;
        q.AirConditioning = true; Assert.Equal(91, Match(p, q).Score); // 32/(32+3).
        q.AirConditioning = false; q.PrivateGarden = true; Assert.Equal(91, Match(p, q).Score);
        q.PrivateGarden = false; q.SharedGarden = true; Assert.Equal(100, Match(p, q).Score);
        q.AirConditioning = q.PrivateGarden = true;
        p.AirConditioning = p.PrivateGarden = true;
        Assert.True(Match(p, q).IsExact);
        p.SharedGarden = true; Assert.True(Match(p, q).IsExact);
    }

    [Fact]
    public void LegacyHouseFloorAndGardenFlagsAreIgnoredWhileAirConditioningStillApplies()
    {
        var p = Home(); var q = Wanted(); p.Type = q.Type = "Ház";
        q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = q.PrivateGarden = q.SharedGarden = true;
        Assert.True(Match(p, q).IsExact);
        var clean = Wanted(); clean.Type = "Ház";
        Assert.Equal(MatchingRanking.Specificity(clean), MatchingRanking.Specificity(q));
        q.AirConditioning = true; Assert.False(Match(p, q).IsExact);
        p.AirConditioning = true; Assert.True(Match(p, q).IsExact);
        Assert.DoesNotContain(Match(p, q).MatchDetails, d => d.Key is "excludeTopFloor" or "excludeGroundFloorAndBelow" or "privateGarden" or "sharedGarden");
        p.Type = q.Type = "Iroda"; q.AirConditioning = false;
        q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = false;
        Assert.True(Match(p, q).IsExact);
        Assert.DoesNotContain(Match(p, q).MatchDetails, d => d.Key is "privateGarden" or "sharedGarden");
    }

    [Fact]
    public void CompiledSearchSnapshotsTheNewFlagsAndSpecificityIncreasesForSelectedRequirements()
    {
        var p = Home(); var q = Wanted(); var broad = MatchingRanking.Specificity(q);
        q.AirConditioning = q.PrivateGarden = q.SharedGarden = q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = true;
        var compiled = MatchingRanking.Prepare(q);
        Assert.True(compiled.Specificity > broad);
        q.AirConditioning = q.PrivateGarden = q.SharedGarden = q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = false;
        Assert.True(Match(p, q).IsExact);
        Assert.False(MatchingRanking.Evaluate(p, compiled).IsExact);
    }


    [Theory]
    [InlineData(null)]
    [InlineData(false)]
    [InlineData(true)]
    public void LegacySharedGardenMetadataCannotAffectCompatibilityRankingSpecificityOrPublicDtos(bool? available)
    {
        var p = Home(); p.SharedGarden = available;
        var q = Wanted(); q.SharedGarden = true;
        var clean = Wanted();
        Assert.True(PropertyAttributes.Compatible(p, q));
        Assert.True(Match(p, q).IsExact); Assert.Equal(100, Match(p, q).Score);
        Assert.Equal(MatchingRanking.Specificity(clean), MatchingRanking.Specificity(q));
        Assert.False(MatchingRanking.Prepare(q).Source.SharedGarden);
        Assert.DoesNotContain(Match(p, q).MatchDetails, detail => detail.Key == "sharedGarden");
        Assert.DoesNotContain(Match(p, q).Reasons, reason => reason.Contains("Közös kert", StringComparison.Ordinal));
        var value = MatchingRanking.ValueForMoney(p);
        p.SharedGarden = available == true ? false : true;
        Assert.Equal(value, MatchingRanking.ValueForMoney(p));
        Assert.Equal(JsonValueKind.Null, Field(Dto.Property(p), "sharedGarden").ValueKind);
        Assert.Equal(JsonValueKind.Null, Field(Dto.Property(p, own: true), "sharedGarden").ValueKind);
        Assert.False(Field(Dto.Search(q), "sharedGarden").GetBoolean());
        Assert.True(q.SharedGarden); // Reading old rows never performs a destructive data rewrite.
        Rules.Apply(q, SearchInput() with { SharedGarden = true });
        Assert.False(q.SharedGarden);
    }

    [Fact]
    public void RequestFingerprintsPreserveOldDefaultPayloadsButBindEveryNewNondefaultChoice()
    {
        var p = PropertyInput(); var q = SearchInput();
        // These are the canonical fingerprints of these exact pre-feature record payloads.
        Assert.Equal("4110FFF3F97EA4DB0432948C1C583B930FA64785A3DC056FA93F07124B887FDC", EntityCreation.RequestHash(p));
        Assert.Equal("A4CF6F2AA6CBB19D047E765004ECF81600893C9B8381508B10F6C7A1B8FACA27", EntityCreation.RequestHash(q));
        foreach (var changed in new[] { p with { BuildingFloors = 0 }, p with { PrivateGarden = false },
            p with { PrivateGarden = true }, p with { SharedGarden = false }, p with { SharedGarden = true } })
            Assert.NotEqual(EntityCreation.RequestHash(p), EntityCreation.RequestHash(changed));
        foreach (var changed in new[] { q with { ExcludeTopFloor = true }, q with { ExcludeGroundFloorAndBelow = true },
            q with { AirConditioning = true }, q with { PrivateGarden = true }, q with { SharedGarden = true } })
            Assert.NotEqual(EntityCreation.RequestHash(q), EntityCreation.RequestHash(changed));
        Assert.NotEqual(EntityCreation.RequestHash(p with { PrivateGarden = false }), EntityCreation.RequestHash(p with { PrivateGarden = true }));
    }

    [Fact]
    public void FrozenSharedGardenCreationReceiptsKeepTheirOriginalHashWhileTheSavedOptionIsRetired()
    {
        // Canonical fingerprints of the same pre-retirement input record payloads.
        // Keep the raw legacy field until creation replay has been authenticated.
        var p = PropertyInput() with { SharedGarden = true, CreationRequestId = Guid.NewGuid() };
        var q = SearchInput() with { SharedGarden = true, CreationRequestId = Guid.NewGuid() };
        const string propertyHash = "60ABEBA3EA46EF43B97D09874FBB099016FA6806232A09C3682BE1933928F72F";
        const string searchHash = "C01F6A17B6A1C1E65FC83052C16A39116A5E703F531499D3EEA70EF4B8D1C39D";
        Assert.Equal(propertyHash, EntityCreation.RequestHash(p));
        Assert.Equal(searchHash, EntityCreation.RequestHash(q));
        Assert.Equal("53CCF6905B225D8C090B4CDDC2EC96A8B697FFDF515A4D978EAB251B7BAF0654",
            EntityCreation.RequestHash(p with { SharedGarden = false }));
        var home = new Property(); var wanted = new SearchRequest();
        Rules.Apply(home, p); Rules.Apply(wanted, q);
        Assert.Null(home.SharedGarden); Assert.False(wanted.SharedGarden);
        Assert.True(p.SharedGarden); Assert.True(q.SharedGarden);
        EntityCreation.VerifyReplay(propertyHash, EntityCreation.RequestHash(p));
        EntityCreation.VerifyReplay(searchHash, EntityCreation.RequestHash(q));
    }

    [Fact]
    public void OptionalSellerColumnsAndNonnullableSearchFlagsHaveSafeLegacyDefaultsAndDtoRoundTrips()
    {
        using var db = new AppDb(new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options);
        var property = db.Model.FindEntityType(typeof(Property))!; var search = db.Model.FindEntityType(typeof(SearchRequest))!;
        foreach (var name in new[] { "BuildingFloors", "PrivateGarden", "SharedGarden" }) Assert.True(property.FindProperty(name)!.IsNullable);
        foreach (var name in new[] { "ExcludeTopFloor", "ExcludeGroundFloorAndBelow", "AirConditioning", "PrivateGarden", "SharedGarden" })
        {
            Assert.False(search.FindProperty(name)!.IsNullable);
            Assert.Equal(false, search.FindProperty(name)!.GetDefaultValue());
        }
        var p = new Property(); Assert.Null(p.BuildingFloors); Assert.Null(p.PrivateGarden); Assert.Null(p.SharedGarden);
        var q = new SearchRequest(); Assert.False(q.ExcludeTopFloor); Assert.False(q.ExcludeGroundFloorAndBelow);
        Assert.False(q.AirConditioning); Assert.False(q.PrivateGarden); Assert.False(q.SharedGarden);
        Rules.Apply(q, SearchInput() with { ExcludeTopFloor = true, ExcludeGroundFloorAndBelow = true,
            AirConditioning = true, PrivateGarden = true, SharedGarden = true });
        foreach (var name in new[] { "excludeTopFloor", "excludeGroundFloorAndBelow", "airConditioning", "privateGarden" })
            Assert.True(Field(Dto.Search(q), name).GetBoolean());
        Assert.False(q.SharedGarden); Assert.False(Field(Dto.Search(q), "sharedGarden").GetBoolean());
    }

    [Fact]
    public void PublicLandingPrefillsCarryOnlyApplicableNewAmenitiesAndFloorFacts()
    {
        var p = Home(); p.Floor = 2; p.BuildingFloors = 5; p.AirConditioning = true;
        p.PrivateGarden = false; p.SharedGarden = true;
        var propertySeed = PublicLanding.PropertyTeaser(p, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.Equal(5, propertySeed.BuildingFloors); Assert.True(propertySeed.AirConditioning);
        Assert.False(propertySeed.PrivateGarden); Assert.Null(propertySeed.SharedGarden);
        var q = Wanted(); q.ExcludeTopFloor = q.ExcludeGroundFloorAndBelow = true;
        q.AirConditioning = q.PrivateGarden = q.SharedGarden = true;
        var searchSeed = PublicLanding.SearchTeaser(q, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.True(searchSeed.ExcludeTopFloor); Assert.True(searchSeed.ExcludeGroundFloorAndBelow);
        Assert.True(searchSeed.AirConditioning); Assert.True(searchSeed.PrivateGarden); Assert.False(searchSeed.SharedGarden);
        p.Type = q.Type = "Ház";
        propertySeed = PublicLanding.PropertyTeaser(p, AccountTypes.Private)!.Value.Teaser.Prefill!;
        searchSeed = PublicLanding.SearchTeaser(q, AccountTypes.Private)!.Value.Teaser.Prefill!;
        Assert.Null(propertySeed.BuildingFloors); Assert.Null(propertySeed.PrivateGarden); Assert.Null(propertySeed.SharedGarden);
        Assert.False(searchSeed.ExcludeTopFloor); Assert.False(searchSeed.ExcludeGroundFloorAndBelow);
        Assert.False(searchSeed.PrivateGarden); Assert.False(searchSeed.SharedGarden); Assert.True(searchSeed.AirConditioning);
    }
}
