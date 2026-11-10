using System.Text.Json;
using System.Text.Json.Nodes;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class MatchingRankingTests
{
    private static readonly Guid Seller = Guid.Parse("00000000-0000-4000-8000-000000000001");
    private static readonly Guid Buyer = Guid.Parse("00000000-0000-4000-8000-000000000002");
    private static Property Home() => new() {
        OwnerId = Seller, LocationId = "city:Debrecen", City = "Debrecen", Type = "Lakás",
        Price = 80_000_000m, Area = 60m, Rooms = 3m
    };
    private static SearchRequest Wanted() => new() {
        OwnerId = Buyer, LocationIdsJson = "[\"city:Debrecen\"]", City = "Debrecen", Type = "Lakás"
    };
    private static MatchEvaluation Match(Property p, SearchRequest s) => MatchingRanking.Evaluate(p, MatchingRanking.Prepare(s));

    [Fact]
    public void ExactPairsHaveOneHundredWithoutABaseOrAmenityBonus()
    {
        var q = Wanted(); q.MaxPrice = 100_000_000m;
        foreach (var price in new[] { 60_000_000m, 80_000_000m, 100_000_000m })
        {
            var p = Home(); p.Price = price;
            Assert.True(Match(p, q).IsExact); Assert.Equal(100, Match(p, q).Score);
            p.Balcony = p.Elevator = true; Assert.Equal(100, Match(p, q).Score);
        }
        var house = Home(); house.Type = q.Type = "Ház";
        Assert.Equal(100, Match(house, q).Score);
    }

    [Fact]
    public void TypeLocationSelfAndArchiveAreHardGatesEvenWhenEverythingElseMatches()
    {
        var q = Wanted(); var p = Home();
        p.Type = "Ház"; Assert.False(Match(p, q).Eligible);
        p.Type = "Lakás"; p.LocationId = "city:Szeged"; Assert.False(Match(p, q).Eligible);
        p.LocationId = "city:missing"; Assert.False(Match(p, q).Eligible);
        p.LocationId = "area:Debrecen"; Assert.False(Match(p, q).Eligible);
        p.LocationId = "city:Debrecen"; p.OwnerId = Buyer; Assert.False(Match(p, q).Eligible);
        p.OwnerId = Seller; p.Archived = true; Assert.False(Match(p, q).Eligible);
        p.Archived = false; q.Archived = true; Assert.False(Match(p, q).Eligible);
        q.Archived = false; q.Type = "Bármilyen"; Assert.False(Match(p, q).Eligible);
    }

    [Fact]
    public void CanonicalAreasAndBudapestDistrictsKeepTheirLocationMeaning()
    {
        var p = Home(); var q = Wanted(); q.LocationIdsJson = "[\"area:Debrecen\"]";
        p.LocationId = "city:Hajdúsámson"; Assert.Equal(100, Match(p, q).Score);
        p.LocationId = "district:Budapest:2"; p.City = "Budapest"; p.District = "II.";
        q.LocationIdsJson = "[\"city:Budapest\"]"; Assert.Equal(100, Match(p, q).Score);
        q.LocationIdsJson = "[\"district:Budapest:13\"]"; Assert.False(Match(p, q).Eligible);
        q.LocationIdsJson = "[\"area:Budapest\"]";
        var prepared = MatchingRanking.Prepare(q);
        Assert.Contains("Budapest", prepared.Cities); Assert.Contains("Solymár", prepared.Cities);
        Assert.True(MatchingRanking.Evaluate(p, prepared).Eligible);
    }

    [Theory]
    [InlineData(100_000_000, 100)] [InlineData(110_000_000, 90)]
    [InlineData(120_000_000, 80)] [InlineData(150_000_000, 50)] [InlineData(200_000_000, 0)]
    public void PriceDeviationIsProportionalAndInclusive(int price, int expected)
    {
        var p = Home(); p.Price = price; var q = Wanted(); q.MaxPrice = 100_000_000;
        Assert.Equal(expected, Match(p, q).Score);
        Assert.Equal(expected == 100, Match(p, q).IsExact);
    }

    [Fact]
    public void TinyFailuresNeverRoundToOneHundredAndSmallPriceUnitsRemainProportional()
    {
        var p = Home(); var q = Wanted(); q.MaxPrice = 100_000_000m; p.Price = 100_000_001m;
        Assert.Equal(99, Match(p, q).Score);
        q.MaxPrice = 500_000m; p.Price = 600_000m; Assert.Equal(80, Match(p, q).Score);
        q.MaxPrice = 0; Assert.Equal(0, Match(p, q).Score);
        q.MaxPrice = null; q.MinPrice = 500_000m; p.Price = 400_000m;
        Assert.Equal(80, Match(p, q).Score); // A sole weight below 1 must still normalize to 100%.
    }

    [Fact]
    public void MaximumPriceThenMinimumRoomsThenMinimumAreaHaveDecreasingImportance()
    {
        var q = Wanted(); q.MaxPrice = 100_000_000m; q.MinRooms = 4; q.MinArea = 80;
        var p = Home(); p.Price = 150_000_000m; p.Rooms = 4; p.Area = 80;
        var price = Match(p, q).Score;
        p.Price = 100_000_000m; p.Rooms = 2; var rooms = Match(p, q).Score;
        p.Rooms = 4; p.Area = 40; var area = Match(p, q).Score;
        Assert.True(price < rooms && rooms < area);
    }

    [Fact]
    public void MinimumRoomAndAreaShortfallsUseTheirOwnRelativeDeviation()
    {
        var p = Home(); p.Rooms = 2; var q = Wanted(); q.MinRooms = 3;
        Assert.Equal(67, Match(p, q).Score);
        p.Rooms = 2.5m; q.MinRooms = 4; Assert.Equal(63, Match(p, q).Score);
        q.MinRooms = null; q.MinArea = 50; p.Area = 40; Assert.Equal(80, Match(p, q).Score);
    }

    [Fact]
    public void ConditionUsesTheWorstAllowedThresholdAndUnknownDataIsNotExact()
    {
        var q = Wanted(); q.ConditionsJson = "[\"Jó\",\"Új/felújított\"]";
        var p = Home(); var scores = new[] { 33, 67, 100, 100 };
        for (var i = 0; i < PropertyAttributes.Conditions.Length; i++)
        { p.Condition = PropertyAttributes.Conditions[i]; Assert.Equal(scores[i], Match(p, q).Score); }
        p.Condition = "Felújított"; Assert.Equal(100, Match(p, q).Score);
        p.Condition = ""; Assert.Equal(0, Match(p, q).Score);
        q.ConditionsJson = "[\"Átlagos\"]"; p.Condition = "Jó";
        Assert.True(Rules.Compatible(p, q)); Assert.Equal(100, Rules.Score(p, q));
    }

    [Fact]
    public void FloorUsesNearestSelectedLevelAndKeepsTheElevenPlusBucket()
    {
        var q = Wanted(); q.FloorsJson = "[1,5]"; var p = Home();
        p.Floor = 4; Assert.Equal(80, Match(p, q).Score);
        p.Floor = 3; Assert.Equal(60, Match(p, q).Score);
        p.Floor = null; Assert.Equal(0, Match(p, q).Score);
        q.FloorsJson = "[11]"; p.Floor = 27; Assert.Equal(100, Match(p, q).Score);
        q.FloorsJson = "[0]"; p.Floor = -1; Assert.Equal(80, Match(p, q).Score);
    }

    [Fact]
    public void UnknownSelectedCategoriesArePartialAndLegacyCanonicalLabelsRemainUsable()
    {
        var p = Home(); var q = Wanted();
        q.BuildingsJson = "[\"Tégla\",\"Panel\"]"; q.HeatingTypesJson = "[\"Gázkazán\"]";
        q.ConstructionAgesJson = "[\"10 évnél fiatalabb\"]"; q.ViewsJson = "[\"Kertre néző\"]"; q.CeilingHeight = "3 m alatti";
        Assert.False(Match(p, q).IsExact);
        p.Building = "panel"; p.HeatingType = "gázkazán"; p.ConstructionAge = "10 évnél fiatalabb";
        p.View = "kertre néző"; p.CeilingHeight = "3 m alatti"; Assert.Equal(100, Match(p, q).Score);
        q = Wanted(); q.ConstructionAgesJson = "[\"10 évnél fiatalabb\"]"; p.ConstructionAge = "10–30 év közötti";
        Assert.Equal(75, Match(p, q).Score);
    }

    [Fact]
    public void HousesIgnoreIrrelevantOldApartmentPreferences()
    {
        var p = Home(); p.Type = "Ház"; var q = Wanted(); q.Type = "Ház";
        q.FloorsJson = "[11]"; q.Balcony = q.Elevator = true;
        Assert.Equal(100, Match(p, q).Score);
        Assert.Equal(MatchingRanking.Specificity(WantedHouse()), MatchingRanking.Specificity(q));
    }
    private static SearchRequest WantedHouse() { var q = Wanted(); q.Type = "Ház"; return q; }

    [Fact]
    public void OtherExistingSearchBoundsAndViewsStillAffectThePercentage()
    {
        var p = Home(); var q = Wanted(); p.Price = 40_000_000m; q.MinPrice = 50_000_000m;
        Assert.Equal(80, Match(p, q).Score);
        q = Wanted(); p.Area = 90; q.MaxArea = 60; Assert.Equal(50, Match(p, q).Score);
        q = Wanted(); p.Rooms = 6; q.MaxRooms = 3; Assert.Equal(0, Match(p, q).Score);
        q = Wanted(); q.ViewsJson = "[\"Kertre néző\"]"; p.View = "Utcai"; Assert.Equal(0, Match(p, q).Score);
    }

    [Fact]
    public void ValueForMoneyKeepsPriceLivingAreaAndBoundedPlotAboveSmallQualityBonuses()
    {
        var p = Home(); p.Area = 100; p.Price = 100_000_000m; p.Rooms = 4;
        var baseline = MatchingRanking.ValueForMoney(p);
        p.Price = 80_000_000m; Assert.True(MatchingRanking.ValueForMoney(p) > baseline);
        p.Price = 100_000_000m; p.Condition = "Új/felújított"; p.Insulated = true;
        Assert.True(MatchingRanking.ValueForMoney(p) > baseline);
        p.Type = "Ház"; p.LotArea = 500; var capped = MatchingRanking.ValueForMoney(p);
        p.LotArea = 50000; Assert.Equal(capped, MatchingRanking.ValueForMoney(p));
        p.Area = 200; p.Rooms = 8; Assert.True(MatchingRanking.ValueForMoney(p) > capped);
        p.Price = 0; Assert.Equal(0m, MatchingRanking.ValueForMoney(p));
    }

    [Fact]
    public void SpecificityIncreasesWithRestrictionsNarrowBoundsAndFewerAlternatives()
    {
        var broad = Wanted(); var q = Wanted(); q.MinPrice = 70_000_000m; q.MaxPrice = 90_000_000m;
        q.MinRooms = 2; q.MaxRooms = 3; q.MinArea = 50; q.MaxArea = 70;
        q.ConditionsJson = "[\"Jó\"]"; q.BuildingsJson = "[\"Tégla\"]"; q.FloorsJson = "[1]"; q.Balcony = q.Elevator = true;
        Assert.True(MatchingRanking.Specificity(q) > MatchingRanking.Specificity(broad));
        q = Wanted(); q.MinPrice = 90_000_000m; q.MaxPrice = 100_000_000m; var narrow = MatchingRanking.Specificity(q);
        q.MinPrice = 10_000_000m; Assert.True(narrow > MatchingRanking.Specificity(q));
        q = Wanted(); q.BuildingsJson = "[\"Tégla\"]"; var one = MatchingRanking.Specificity(q);
        q.BuildingsJson = "[\"Tégla\",\"Panel\"]"; Assert.True(one > MatchingRanking.Specificity(q));
        q = Wanted(); var local = MatchingRanking.Specificity(q); q.LocationIdsJson = "[\"city:Debrecen\",\"city:Szeged\",\"city:Pécs\"]";
        Assert.True(local > MatchingRanking.Specificity(q));
    }

    [Fact]
    public void CompiledSearchSnapshotsFiltersForRepeatedLeanEvaluationsWithoutReasons()
    {
        var q = Wanted(); q.MaxPrice = 100_000_000m; q.BuildingsJson = "[\"Tégla\"]";
        var compiled = MatchingRanking.Prepare(q); var p = Home(); p.Building = "Tégla";
        q.MaxPrice = 1; q.BuildingsJson = "[\"Panel\"]"; q.LocationIdsJson = "[\"city:Szeged\"]";
        for (var i = 0; i < 10000; i++)
        {
            var result = MatchingRanking.Evaluate(p, compiled, includeReasons: false);
            Assert.Equal(100, result.Score); Assert.Empty(result.Reasons);
        }
        Assert.NotEmpty(MatchingRanking.Evaluate(p, compiled).Reasons);
        Assert.Equal(80_000_000m, p.Price); Assert.Equal("Tégla", p.Building);
    }

    [Fact]
    public void BrowserAndBackendConsumeTheSameFixedCrossLanguageFixtures()
    {
        using var stream = typeof(MatchingRankingTests).Assembly.GetManifestResourceStream("Otthonra.Tests.MatchingRankingCases.json");
        using var fixtures = JsonDocument.Parse(stream!);
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        foreach (var item in fixtures.RootElement.EnumerateArray())
        {
            var p = Home(); p.Price /= 1_000_000m;
            var property = Merge(p, item.GetProperty("property"), options);
            var search = Merge(Wanted(), item.GetProperty("search"), options);
            property.Price *= 1_000_000m;
            search.MinPrice *= 1_000_000m; search.MaxPrice *= 1_000_000m;
            var rawSearch = item.GetProperty("search");
            if (rawSearch.TryGetProperty("locationIds", out var ids)) search.LocationIdsJson = ids.GetRawText();
            if (rawSearch.TryGetProperty("conditions", out var conditions)) search.ConditionsJson = conditions.GetRawText();
            if (rawSearch.TryGetProperty("buildings", out var buildings)) search.BuildingsJson = buildings.GetRawText();
            if (rawSearch.TryGetProperty("heatingTypes", out var heating)) search.HeatingTypesJson = heating.GetRawText();
            if (rawSearch.TryGetProperty("constructionAges", out var ages)) search.ConstructionAgesJson = ages.GetRawText();
            if (rawSearch.TryGetProperty("views", out var views)) search.ViewsJson = views.GetRawText();
            if (rawSearch.TryGetProperty("floors", out var floors)) search.FloorsJson = floors.GetRawText();
            var result = Match(property, search);
            if (item.TryGetProperty("eligible", out var eligible)) Assert.Equal(eligible.GetBoolean(), result.Eligible);
            if (item.TryGetProperty("score", out var score))
            {
                Assert.Equal(score.GetInt32(), result.Score);
                Assert.Equal(score.GetInt32() == 100, result.IsExact);
            }
            if (item.TryGetProperty("specificity", out var specificity)) Assert.Equal(specificity.GetInt32(), MatchingRanking.Specificity(search));
            if (item.TryGetProperty("valueForMoney", out var value))
                Assert.InRange(Math.Abs((double)MatchingRanking.ValueForMoney(property) - value.GetDouble()), 0d, 1e-8);
        }
    }

    private static T Merge<T>(T original, JsonElement patch, JsonSerializerOptions options)
    {
        var node = JsonSerializer.SerializeToNode(original, options)!.AsObject();
        foreach (var field in patch.EnumerateObject()) node[field.Name] = JsonNode.Parse(field.Value.GetRawText());
        return node.Deserialize<T>(options)!;
    }
}
