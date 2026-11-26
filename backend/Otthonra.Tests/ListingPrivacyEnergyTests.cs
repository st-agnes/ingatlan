using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class ListingPrivacyEnergyTests
{
    private static PropertyInput Input() => new("Városi otthon", "Debrecen", null, null, null,
        "Világos, nyugodt otthon.", "Lakás", 65_000_000m, 70m, 3m, 2m, null, null,
        false, false, [], LocationId: "city:Debrecen", Street: "Fiktív teszt utca", HouseNumber: "12");
    private static SearchInput Wanted() => new("Otthont keresek", "Debrecen", [], "Nyugodt otthont keresek.",
        "Lakás", null, null, null, null, null, null, false, false, null, null, LocationIds: ["city:Debrecen"]);
    private static (Property Property, SearchRequest Search) Pair()
    {
        var p = new Property { OwnerId = Guid.NewGuid() }; Rules.Apply(p, Input());
        var s = new SearchRequest { OwnerId = Guid.NewGuid() }; Rules.Apply(s, Wanted()); return (p, s);
    }
    private static JsonElement Json(object value) => JsonSerializer.SerializeToElement(value,
        new JsonSerializerOptions(JsonSerializerDefaults.Web));

    [Fact]
    public void AddressPrivacyDefaultsAndHouseNumberDependencyDoNotLoseTheOwnedAddress()
    {
        var (p, _) = Pair();
        Assert.True(p.HideStreet); Assert.True(p.HideHouseNumber);
        Assert.Equal("", Dto.PublicAddress(p));
        Rules.Apply(p, Input() with { HideStreet = false, HideHouseNumber = true });
        Assert.Equal("Fiktív teszt utca", Dto.PublicAddress(p));
        Rules.Apply(p, Input() with { HideStreet = false, HideHouseNumber = false });
        Assert.Equal("Fiktív teszt utca 12", Dto.PublicAddress(p));
        Rules.Apply(p, Input() with { HideStreet = true, HideHouseNumber = false });
        Assert.True(p.HideHouseNumber);
        var foreign = Json(Dto.Property(p)); var own = Json(Dto.Property(p, own: true));
        Assert.Equal("", foreign.GetProperty("address").GetString());
        Assert.Equal("", foreign.GetProperty("street").GetString());
        Assert.Equal("", foreign.GetProperty("houseNumber").GetString());
        Assert.Equal(JsonValueKind.Null, foreign.GetProperty("addressDetails").ValueKind);
        Assert.Equal("Fiktív teszt utca 12", own.GetProperty("address").GetString());
        Assert.Equal("12", own.GetProperty("addressDetails").GetProperty("houseNumber").GetString());
        // A reciprocal match must not turn its legacy own flag into raw coordinate access.
        var matchedForeign = Json(Dto.Property(p, own: true, includeOwnedLocationDetails: false));
        Assert.Equal("", matchedForeign.GetProperty("address").GetString());
        Assert.Equal(JsonValueKind.Null, matchedForeign.GetProperty("addressDetails").ValueKind);
    }

    [Fact]
    public void HiddenStreetCannotBeDiscoveredByStreetButCityAndNeighborhoodOrChoicesStillWork()
    {
        var street = StreetCatalog.All.First(row => row.City == "Debrecen");
        var (p, s) = Pair(); p.StreetId = street.Id;
        s.LocationIdsJson = JsonSerializer.Serialize(new[] { street.Id });
        Assert.False(LocationCatalog.Matches(p, s)); Assert.False(MatchingRanking.CanRecommend(p, s));
        p.HideStreet = false; Assert.True(Rules.Compatible(p, s));
        p.HideStreet = true;
        s.LocationIdsJson = JsonSerializer.Serialize(new[] { street.Id, "city:Debrecen" });
        Assert.True(Rules.Compatible(p, s));
        var area = NeighborhoodCatalog.All.First(row => row.City == "Debrecen");
        p.NeighborhoodIdsJson = JsonSerializer.Serialize(new[] { area.Id });
        s.LocationIdsJson = JsonSerializer.Serialize(new[] { street.Id, area.Id });
        Assert.True(Rules.Compatible(p, s));
    }

    [Theory]
    [InlineData("only", true, true)]
    [InlineData("only", false, false)]
    [InlineData("only", null, false)]
    [InlineData("exclude", false, true)]
    [InlineData("exclude", true, false)]
    [InlineData("exclude", null, false)]
    public void AtticFiltersRequireKnownCorrespondingInformation(string preference, bool? attic, bool exact)
    {
        var (p, s) = Pair(); p.IsAttic = attic; s.AtticPreference = preference;
        var match = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s));
        Assert.True(match.Eligible); Assert.Equal(exact, match.IsExact);
        Assert.Equal(exact, Assert.Single(match.MatchDetails, row => row.Key == "atticPreference").Matches);
        Assert.Equal(exact, PropertyAttributes.Compatible(p, s));
        Assert.Equal(exact, Rules.Compatible(p, s));
    }

    [Fact]
    public void AtticAndFloorConditionsShareOneFloorWeightAndHousesIgnoreThem()
    {
        var (p, s) = Pair(); p.IsAttic = false; s.AtticPreference = "only"; s.MaxPrice = p.Price;
        var first = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Score;
        Assert.Equal(61, first); // Full attic loss: exp(-sqrt(0.25)).
        s.FloorsJson = "[8]";
        // Floor2 versus8 is a6/5=1.2 deviation, but attic is an OR
        // alternative whose unmet loss is1, so the shared term takes min(1.2,1).
        var combined = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s));
        Assert.Equal(61, combined.Score); // exp(-sqrt(0.25)).
        Assert.InRange(Math.Abs(combined.DistanceSquared - .25d), 0d, 1e-12);
        p.Type = s.Type = "Ház"; p.LotArea = 500m;
        Assert.True(Rules.Compatible(p, s));
        Rules.Apply(s, Wanted() with { Type = "Ház", AtticPreference = "only" });
        Assert.Equal("", s.AtticPreference);
    }

    [Theory]
    [InlineData(3, false, true)]
    [InlineData(3, null, true)]
    [InlineData(7, true, true)]
    [InlineData(null, true, true)]
    [InlineData(2, false, false)]
    [InlineData(2, null, false)]
    [InlineData(null, null, false)]
    public void AtticIsAnAlternativeToSelectedFloorsInCompatibilityScoringAndExplanations(int? floor, bool? attic, bool exact)
    {
        var (p, s) = Pair(); p.Floor = floor; p.IsAttic = attic;
        s.FloorsJson = "[3]"; s.AtticPreference = "only";
        var match = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s));
        Assert.Equal(exact, match.IsExact); Assert.Equal(exact, Rules.Compatible(p, s));
        var detail = Assert.Single(match.MatchDetails, item => item.Key == "floor");
        Assert.Equal("3. emelet vagy Tetőtéri ingatlan", detail.Expected);
        Assert.Equal(exact, detail.Matches);
        Assert.DoesNotContain(match.MatchDetails, item => item.Key == "atticPreference");
    }

    [Fact]
    public void OtherFloorExclusionsAndElevatorStillApplyToAtticAlternatives()
    {
        var (p, s) = Pair(); p.IsAttic = true; p.Floor = 7; p.BuildingFloors = 7;
        s.FloorsJson = "[3]"; s.AtticPreference = "only";
        Assert.True(Rules.Compatible(p, s));
        s.ExcludeTopFloor = true;
        Assert.False(Rules.Compatible(p, s)); Assert.Equal(61, MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Score);
        s.ExcludeTopFloor = false; s.ExcludeGroundFloorAndBelow = true; p.Floor = 0;
        Assert.False(Rules.Compatible(p, s));
        s.ExcludeGroundFloorAndBelow = false; s.Elevator = true;
        Assert.False(Rules.Compatible(p, s)); Assert.False(MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).IsExact);
    }

    [Fact]
    public void OnlyTheCurrentEnergySchemeCanProveTheMinimumAndLossFollowsTheGradeDistance()
    {
        var (p, s) = Pair(); s.MinEnergyRating = "B"; p.EnergyRating = "A";
        Assert.False(Rules.Compatible(p, s));
        p.EnergyRatingScheme = "2023"; Assert.True(Rules.Compatible(p, s));
        p.EnergyRating = "C";
        var near = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Score;
        Assert.Equal(98, near); // One grade: round(100 * exp(-sqrt(0.04) / 11)).
        p.EnergyRating = "H";
        var far = MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Score;
        Assert.Equal(90, far); // Six grades: round(100 * exp(-sqrt(0.04) * 6 / 11)).
        Assert.True(far < near);
        p.EnergyRating = "I"; s.MinEnergyRating = "I"; Assert.True(Rules.Compatible(p, s));
        p.EnergyRating = "AA"; Assert.False(Rules.Compatible(p, s));
        // Unknown legacy certificates incur the full loss instead of proving the minimum.
        Assert.Equal(82, MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s)).Score);
        Assert.Equal(0, EnergyCertificates.Rank("I")); Assert.Equal(11, EnergyCertificates.Rank("A+++"));
    }

    [Fact]
    public void CurrentEnergyEditsAndLegacyEnergyReadsNeverGuessAConversion()
    {
        var p = new Property { OwnerId = Guid.NewGuid(), EnergyRating = "AA", EnergyRatingScheme = "" };
        Rules.Apply(p, Input() with { EnergyRating = "AA" });
        Assert.Equal("AA", p.EnergyRating); Assert.Equal("", p.EnergyRatingScheme);
        Rules.Apply(p, Input() with { EnergyRating = "A+", EnergyRatingScheme = "2023" });
        Assert.True(EnergyCertificates.IsCurrent(p));
        Rules.Apply(p, Input() with { EnergyRating = "A+" });
        Assert.Equal("2023", p.EnergyRatingScheme);
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(p, Input() with {
            EnergyRating = "AA", EnergyRatingScheme = "2023" })).Status);
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), Wanted() with {
            MinEnergyRating = "AA" })).Status);
    }

    [Theory]
    [InlineData("Gázkazán", "Gázkazán / cirkó")]
    [InlineData("Gázcirkó", "Gázkazán / cirkó")]
    [InlineData("Klíma", "Fűtő klíma")]
    [InlineData("Vegyes tüzelésű kazán", "Fa- / vegyes tüzelésű kazán")]
    [InlineData("Cserépkályha", "Kályha / cserépkályha")]
    public void HeatingAliasesRemainReadableWhilePrimaryChoicesUseTheApprovedList(string old, string current)
    {
        var (p, s) = Pair(); Rules.Apply(p, Input() with { HeatingType = old, SecondaryHeatingType = "Klíma" });
        Rules.Apply(s, Wanted() with { HeatingTypes = [old] });
        Assert.Equal(current, p.HeatingType); Assert.Equal(current, Assert.Single(Dto.Strings(s.HeatingTypesJson)));
        Assert.Equal("Klíma", p.SecondaryHeatingType); Assert.True(Rules.Compatible(p, s));
        var value = MatchingRanking.ValueForMoney(p); p.SecondaryHeatingType = "";
        Assert.Equal(value, MatchingRanking.ValueForMoney(p));
    }

    [Fact]
    public void NullableBalconyAndOtherAmenitiesRetainFalseVersusUnspecified()
    {
        var (p, s) = Pair();
        Rules.Apply(p, Input() with { Balcony = null, AirConditioning = null, PrivateGarden = null, Insulated = null, SolarPanels = null });
        Assert.Null(p.Balcony); Assert.Null(Json(Dto.Property(p)).GetProperty("balcony").Deserialize<bool?>());
        s.Balcony = true; Assert.False(Rules.Compatible(p, s));
        Rules.Apply(p, Input() with { Balcony = false }); Assert.False(p.Balcony);
        Rules.Apply(p, Input() with { Balcony = true }); Assert.True(Rules.Compatible(p, s));
        Rules.Apply(p, Input() with { Type = "Ház", LotArea = 500m, Balcony = true, IsAttic = true });
        Assert.Null(p.Balcony); Assert.Null(p.IsAttic);
    }

    [Fact]
    public void OnlyVersionOneReceiptsPermitTheOriginalMissingBalconyFalseFallback()
    {
        var previousInput = Input() with { Balcony = false };
        var missing = previousInput with { Balcony = null };
        var old = new Property { CreationRequestHashVersion = 1, CreationRequestHash = EntityCreation.RequestHash(previousInput) };
        EntityCreation.VerifyPropertyReplay(old, missing, EntityCreation.RequestHash(missing));
        old.CreationRequestHashVersion = 2;
        Assert.Equal(409, Assert.Throws<ApiException>(() => EntityCreation.VerifyPropertyReplay(old, missing, EntityCreation.RequestHash(missing))).Status);
        old.CreationRequestHash = EntityCreation.RequestHash(missing);
        EntityCreation.VerifyPropertyReplay(old, missing, EntityCreation.RequestHash(missing));
        Assert.Equal(409, Assert.Throws<ApiException>(() => EntityCreation.VerifyPropertyReplay(old, previousInput, EntityCreation.RequestHash(previousInput))).Status);
        old.CreationRequestHashVersion = 1;
        Assert.Equal(409, Assert.Throws<ApiException>(() => EntityCreation.VerifyPropertyReplay(old, missing with { HideStreet = false }, EntityCreation.RequestHash(missing with { HideStreet = false }))).Status);
    }

    [Fact]
    public void NewPublicAndPrivacyFieldsAreMappedWithoutExposingPrivateCreationMetadata()
    {
        using var db = new AppDb(new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options);
        var property = db.Model.FindEntityType(typeof(Property))!;
        Assert.True(property.FindProperty(nameof(Property.Balcony))!.IsNullable);
        Assert.Equal(true, property.FindProperty(nameof(Property.HideStreet))!.GetDefaultValue());
        Assert.Equal(true, property.FindProperty(nameof(Property.HideStreet))!.Sentinel);
        Assert.Equal(true, property.FindProperty(nameof(Property.HideHouseNumber))!.Sentinel);
        Assert.Equal(1, property.FindProperty(nameof(Property.CreationRequestHashVersion))!.GetDefaultValue());
        Assert.Equal("", property.FindProperty(nameof(Property.EnergyRatingScheme))!.GetDefaultValue());
        var search = db.Model.FindEntityType(typeof(SearchRequest))!;
        Assert.Equal("", search.FindProperty(nameof(SearchRequest.AtticPreference))!.GetDefaultValue());
        Assert.Equal("", search.FindProperty(nameof(SearchRequest.MinEnergyRating))!.GetDefaultValue());
        foreach (var type in new[] { typeof(Property), typeof(SearchRequest) })
        {
            var entity = db.Model.FindEntityType(type)!;
            Assert.Equal(80, entity.FindProperty("PublicListingKey")!.GetMaxLength());
            Assert.Contains(entity.GetIndexes(), index => index.IsUnique && index.Properties.Select(row => row.Name).SequenceEqual(new[] { "PublicListingKey" }));
        }
        Assert.DoesNotContain("creationRequestHashVersion", Json(Dto.Property(new Property(), true)).GetRawText());
    }
}
