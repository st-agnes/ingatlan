using System.Data;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class StreetMatchingTests
{
    private static readonly Guid Seller = Guid.Parse("2591dd12-8f0e-4215-a4d1-35c74880913a");
    private static readonly Guid Buyer = Guid.Parse("4762e806-6386-4d80-8568-6326dc4ab35f");
    private const string UnknownStreet = "street:000000000000000000000000";
    private const string Venkert = "neighborhood:e8c749e1fc0a306c717ad312";
    private static IEnumerable<Location> Streets => StreetCatalog.All.Select(street => LocationCatalog.Get(street.Id)!);
    private static Location Street => Streets.First(street => street.City != "Budapest");

    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=street_query_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    private static Property Home(Location street) => new()
    {
        HideStreet = false, OwnerId = Seller, LocationId = LocationCatalog.ResolveLegacy(street.City,
            street.District is null ? [] : [street.District]).Single().Id,
        City = street.City, District = street.District ?? "", StreetId = street.Id, Street = street.StreetName ?? "",
        Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m
    };

    private static SearchRequest Wanted(params string[] locations) => new()
    {
        OwnerId = Buyer, City = Street.City, Type = "Lakás", LocationIdsJson = JsonSerializer.Serialize(locations)
    };

    private static MatchEvaluation Evaluate(Property property, SearchRequest search)
        => MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search));

    [Fact]
    public void ExactStreetIdentityIsACompactHardGateWithoutExpandingToItsMunicipality()
    {
        var street = Street;
        var search = Wanted(street.Id);
        var property = Home(street);
        var prepared = MatchingRanking.Prepare(search);
        Assert.Equal(street.Id, Assert.Single(prepared.StreetIds));
        Assert.Empty(prepared.Cities);
        Assert.Empty(prepared.DistrictIds);
        Assert.Empty(prepared.NeighborhoodIds);
        Assert.Equal(street.Id, Assert.Single(SearchLocationIndex.SelectedIds(search)));
        Assert.True(LocationCatalog.Matches(property, search));
        Assert.True(Rules.Compatible(property, search));
        Assert.True(MatchingRanking.CanRecommend(property, search));
        Assert.True(Evaluate(property, search).IsExact);
        Assert.Equal(100, Evaluate(property, search).Score);

        property.StreetId = Streets.First(value => value.City == street.City && value.Id != street.Id).Id;
        Assert.False(LocationCatalog.Matches(property, search));
        Assert.False(Rules.Compatible(property, search));
        Assert.False(Evaluate(property, search).Eligible);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(UnknownStreet)]
    public void LegacyFreeTextAndUnknownStreetIdsCannotInventAStreetMatch(string? streetId)
    {
        var street = Street;
        var property = Home(street);
        property.StreetId = streetId;
        // The visible street name and municipality are still identical.
        var search = Wanted(street.Id);
        Assert.False(LocationCatalog.Matches(property, search));
        Assert.False(Rules.Compatible(property, search));
        var evaluation = Evaluate(property, search);
        Assert.False(evaluation.Eligible);
        Assert.Equal(0, evaluation.Score);
        Assert.Empty(evaluation.Reasons);
        Assert.Empty(evaluation.MatchDetails);
        Assert.True(Rules.Compatible(property, Wanted("city:" + street.City)));
    }

    [Fact]
    public void SameStreetNameInAnotherMunicipalityAndAnOutOfScopeIdRemainExcluded()
    {
        var pair = StreetCatalog.All.Where(street => !string.IsNullOrWhiteSpace(street.StreetName))
            .GroupBy(street => street.StreetName, StringComparer.Ordinal)
            .Select(group => group.DistinctBy(street => street.City).Take(2).ToArray())
            .First(group => group.Length == 2).Select(street => LocationCatalog.Get(street.Id)!).ToArray();
        var search = Wanted(pair[0].Id);
        var otherTown = Home(pair[1]);
        Assert.False(LocationCatalog.Matches(otherTown, search));
        Assert.False(Evaluate(otherTown, search).Eligible);
        otherTown.StreetId = pair[0].Id;
        Assert.False(LocationCatalog.Matches(otherTown, search));
        Assert.False(Evaluate(otherTown, search).Eligible);
    }

    [Fact]
    public void KnownBudapestDistrictsMustAgreeWhileAnUnspecifiedLegacyDistrictDoesNotEraseAStoredIdentity()
    {
        var street = Streets.First(value => value.City == "Budapest" && value.District is not null);
        var search = Wanted(street.Id);
        var property = Home(street);
        Assert.True(Evaluate(property, search).Eligible);
        property.LocationId = "city:Budapest";
        property.District = "";
        Assert.True(Evaluate(property, search).Eligible);
        Assert.True(LocationCatalog.Matches(property, search));
        var wrongDistrict = LocationCatalog.All.First(value => value.Kind == "district" && value.District != street.District);
        property.LocationId = wrongDistrict.Id;
        property.District = wrongDistrict.District!;
        Assert.False(Evaluate(property, search).Eligible);
        Assert.False(LocationCatalog.Matches(property, search));
    }

    [Fact]
    public void StreetTownDistrictAreaAndNeighborhoodSelectionsUseOrSemanticsWithIndependentCriteria()
    {
        var street = Street;
        var search = Wanted(street.Id, "city:Szeged", "district:Budapest:13", "area:Debrecen", Venkert);
        var homes = new[] {
            Home(street),
            new Property { OwnerId = Seller, LocationId = "city:Szeged", Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m },
            new Property { OwnerId = Seller, LocationId = "district:Budapest:13", Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m },
            new Property { OwnerId = Seller, LocationId = "city:Hajdúsámson", Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m },
            new Property { OwnerId = Seller, LocationId = "city:Győr", Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m,
                NeighborhoodIdsJson = JsonSerializer.Serialize(new[] { Venkert }) }
        };
        foreach (var property in homes) Assert.True(Evaluate(property, search).IsExact);
        search.ViewsJson = "[\"Panorámás\"]";
        foreach (var property in homes)
        {
            Assert.True(Evaluate(property, search).Eligible);
            Assert.False(Rules.Compatible(property, search));
            property.View = "Panorámás";
            Assert.True(Rules.Compatible(property, search));
        }
        Assert.False(Evaluate(new Property { OwnerId = Seller, LocationId = "city:Győr", Type = "Lakás" }, search).Eligible);
    }

    [Fact]
    public void StreetAndTypeRemainHardGatesBeforePartialScoringAndOwnershipChecks()
    {
        var street = Street;
        var property = Home(street);
        var search = Wanted(street.Id);
        search.MaxPrice = 50_000_000m;
        var approximate = Evaluate(property, search);
        Assert.True(approximate.Eligible);
        Assert.False(approximate.IsExact);
        Assert.InRange(approximate.Score, 1, 99);
        property.Type = "Ház";
        Assert.False(Evaluate(property, search).Eligible);
        property.Type = search.Type;
        property.OwnerId = Buyer;
        Assert.False(Evaluate(property, search).Eligible);
        property.OwnerId = Seller;
        property.Archived = true;
        Assert.False(Evaluate(property, search).Eligible);
    }

    [Fact]
    public void InvalidExplicitChoicesNeverBroadenThroughTheLegacyCityAndTheFiftyChoiceCapStillApplies()
    {
        var street = Street;
        var property = Home(street);
        var invalid = Wanted(street.Id, UnknownStreet);
        invalid.City = street.City;
        Assert.Throws<ApiException>(() => LocationCatalog.ResolveSearchInput(new[] { street.Id, UnknownStreet }, street.City, null));
        Assert.False(Evaluate(property, invalid).Eligible);
        var fiftyOne = Streets.Take(51).Select(value => value.Id).ToArray();
        Assert.Throws<ApiException>(() => LocationCatalog.ResolveSearchInput(fiftyOne, street.City, null));
        Assert.Empty(LocationCatalog.ForSearch(Wanted(fiftyOne)));
        Assert.False(Evaluate(property, Wanted(fiftyOne)).Eligible);
        var fifty = fiftyOne.Take(50).ToArray();
        Assert.Equal(50, LocationCatalog.ResolveSearchInput(fifty, street.City, null).Length);
        Assert.Equal(fifty, SearchLocationIndex.SelectedIds(Wanted(fifty)));
    }

    [Fact]
    public void SearchDtosPreserveInvalidExplicitIdsSoAClientRoundTripCannotReviveTheLegacyCity()
    {
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        var street = Street;
        foreach (var ids in new[] { new[] { UnknownStreet }, new[] { street.Id, UnknownStreet }, Streets.Take(51).Select(value => value.Id).ToArray(), Enumerable.Repeat(street.Id, 51).ToArray() })
        {
            var search = Wanted(ids);
            var dto = JsonSerializer.SerializeToElement(Dto.Search(search), options);
            Assert.Equal(ids, dto.GetProperty("locationIds").EnumerateArray().Select(value => value.GetString()!).ToArray());
            Assert.Empty(dto.GetProperty("locations").EnumerateArray());
            var roundTrip = Wanted();
            roundTrip.City = dto.GetProperty("city").GetString()!;
            roundTrip.LocationIdsJson = dto.GetProperty("locationIds").GetRawText();
            Assert.False(Evaluate(Home(street), roundTrip).Eligible);
        }

        var valid = JsonSerializer.SerializeToElement(Dto.Search(Wanted(street.Id, street.Id)), options);
        Assert.Equal(street.Id, Assert.Single(valid.GetProperty("locationIds").EnumerateArray()).GetString());
        Assert.Equal(street.Id, Assert.Single(valid.GetProperty("locations").EnumerateArray()).GetProperty("id").GetString());
        var legacy = JsonSerializer.SerializeToElement(Dto.Search(Wanted()), options);
        Assert.Equal("city:" + street.City, Assert.Single(legacy.GetProperty("locationIds").EnumerateArray()).GetString());
    }

    [Fact]
    public void BuyerSqlFiltersTheStreetIndexColumnBeforeRankingWithoutSelectingPrivateAddressText()
    {
        using var db = Context();
        var street = Street;
        var user = new User { Id = Buyer, AccountType = AccountTypes.Agent, ActiveKind = "search" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, search: Wanted(street.Id));
        Assert.Contains(street.Id, sql);
        Assert.Contains("`StreetId`", sql[sql.IndexOf("WHERE", StringComparison.Ordinal)..]);
        Assert.DoesNotContain("'" + street.City + "'", sql);
        Assert.Contains("NOT EXISTS", sql);
        Assert.Contains("AccountType", sql);
        Assert.DoesNotContain("LIMIT 50", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        foreach (var column in new[] { "Street", "HouseNumber", "PostalCode", "Address", "Latitude", "Longitude", "Description", "ImagesJson" })
            Assert.DoesNotContain("`" + column + "`", sql);
        Assert.Contains("IX_Properties_Archived_Type_StreetId", db.Database.GenerateCreateScript());
        Assert.Equal(ConnectionState.Closed, db.Database.GetDbConnection().State);
    }

    [Fact]
    public void BuyerSqlCombinesStreetAndOtherLocationChoicesBeforeRanking()
    {
        using var db = Context();
        var sql = RecommendationFeed.CandidateQuerySql(db, new User { Id = Buyer, ActiveKind = "search" },
            search: Wanted(Street.Id, "city:Szeged", "district:Budapest:13", Venkert));
        Assert.Contains("`StreetId`", sql);
        Assert.Contains("PropertyNeighborhoods", sql);
        Assert.Contains("city:Szeged", sql);
        Assert.Contains("district:Budapest:13", sql);
        Assert.Contains(" OR ", sql);
        Assert.DoesNotContain("LIMIT 50", sql);
    }

    [Fact]
    public void SellerSqlReusesTheLocationIndexForExactStreetSearchesAndDropsOutOfScopeIdentities()
    {
        using var db = Context();
        var street = Street;
        var property = Home(street);
        var user = new User { Id = Seller, AccountType = AccountTypes.Agent, ActiveKind = "property" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, property: property);
        Assert.Contains("SearchLocations", sql);
        Assert.Contains("DISTINCT", sql);
        Assert.Contains(street.Id, sql);
        Assert.Contains("city:" + street.City, sql);
        Assert.Contains("NOT EXISTS", sql);
        Assert.Contains("AccountType", sql);
        Assert.DoesNotContain("LIMIT 50", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        property.StreetId = null;
        Assert.DoesNotContain(street.Id, RecommendationFeed.CandidateQuerySql(db, user, property: property));
        property.StreetId = street.Id;
        property.LocationId = LocationCatalog.All.First(value => value.Kind == "city" && value.City != street.City).Id;
        Assert.DoesNotContain(street.Id, RecommendationFeed.CandidateQuerySql(db, user, property: property));
        property.StreetId = UnknownStreet;
        Assert.DoesNotContain(UnknownStreet, RecommendationFeed.CandidateQuerySql(db, user, property: property));
        Assert.Equal(ConnectionState.Closed, db.Database.GetDbConnection().State);
    }

    [Fact]
    public void SellerInverseEvaluationAcceptsOnlyTheStreetOrAnotherMatchingChoice()
    {
        var street = Street;
        var property = Home(street);
        var another = Streets.First(value => value.City == street.City && value.Id != street.Id);
        foreach (var (search, expected) in new[] {
            (Wanted(street.Id), true), (Wanted(another.Id), false),
            (Wanted("city:" + street.City), true), (Wanted(another.Id, "city:" + street.City), true),
            (Wanted(UnknownStreet), false) })
        {
            Assert.Equal(expected, MatchingRanking.CanRecommend(property, search));
            Assert.Equal(expected, Rules.Compatible(property, search));
        }
    }

    [Fact]
    public void LocationDetailsShowThePublicMunicipalityWhileSpecificityAccountsForNarrowStreetCoverage()
    {
        var street = Street;
        var property = Home(street);
        var search = Wanted(street.Id);
        var details = Evaluate(property, search).MatchDetails.Single(detail => detail.Key == "location");
        Assert.Equal(street.Label, details.Expected);
        Assert.Equal(LocationCatalog.ForProperty(property)!.Label, details.Actual);
        Assert.DoesNotContain(street.Id, JsonSerializer.Serialize(Evaluate(property, search)));
        Assert.True(MatchingRanking.Specificity(search) > MatchingRanking.Specificity(Wanted("city:" + street.City)));
        Assert.True(MatchingRanking.Specificity(Wanted(Streets.Take(50).Select(value => value.Id).ToArray()))
            > MatchingRanking.Specificity(Wanted(NeighborhoodCatalog.All.Take(50).Select(value => value.Id).ToArray())));
    }
}
