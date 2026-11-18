using System.Data;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class NeighborhoodMatchingTests
{
    // Stable source identities from the shared catalog, rather than a city-name substitute.
    private const string Venkert = "neighborhood:e8c749e1fc0a306c717ad312";
    private const string Sestakert = "neighborhood:f22df415c7b5ea79925e8886";
    private const string Szentimrevaros = "neighborhood:103b9c3b79a152ff1507e51f";
    private const string Buda = "neighborhood:1f903296a1db8657f2fdb1f4";
    private const string BudapestEleven = "neighborhood:939730523f9c2a912fa19445";
    private static readonly Guid Seller = Guid.Parse("e177eb6f-fc4a-4b1e-a6c9-dcd79ed16779");
    private static readonly Guid Buyer = Guid.Parse("ac966c16-cd37-40df-ab85-e84301aa9214");

    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=neighborhood_query_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    private static Property Home(string locationId = "city:Debrecen", params string[] memberships) => new()
    {
        OwnerId = Seller, LocationId = locationId, City = LocationCatalog.Get(locationId)?.City ?? "Debrecen",
        Type = "Lakás", Price = 60_000_000m, Area = 60m, Rooms = 3m,
        NeighborhoodIdsJson = JsonSerializer.Serialize(memberships)
    };

    private static SearchRequest Wanted(params string[] locations) => new()
    {
        OwnerId = Buyer, City = "Debrecen", Type = "Lakás", LocationIdsJson = JsonSerializer.Serialize(locations)
    };

    private static MatchEvaluation Evaluate(Property property, SearchRequest search)
        => MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search));

    [Fact]
    public void ExactNeighborhoodMembershipMatchesWithoutExpandingTheChoiceToItsCity()
    {
        var search = Wanted(Venkert);
        var property = Home("city:Debrecen", Venkert);
        Assert.True(LocationCatalog.Matches(property, search));
        Assert.True(Rules.Compatible(property, search));
        Assert.True(MatchingRanking.CanRecommend(property, search));
        var result = Evaluate(property, search);
        Assert.True(result.Eligible);
        Assert.True(result.IsExact);
        Assert.Equal(100, result.Score);

        var prepared = MatchingRanking.Prepare(search);
        Assert.Empty(prepared.Cities);
        Assert.Empty(prepared.DistrictIds);
        Assert.Equal(Venkert, Assert.Single(prepared.NeighborhoodIds));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("[]")]
    [InlineData("[\"neighborhood:f22df415c7b5ea79925e8886\"]")]
    [InlineData("[\"neighborhood:unknown\"]")]
    public void SameCityAndDisplayNameCannotReplaceMissingOrWrongMembership(string? memberships)
    {
        var property = Home();
        property.Neighborhood = "Vénkert";
        property.NeighborhoodIdsJson = memberships;
        var search = Wanted(Venkert);
        Assert.False(LocationCatalog.Matches(property, search));
        Assert.False(Rules.Compatible(property, search));
        Assert.False(MatchingRanking.CanRecommend(property, search));
        var result = Evaluate(property, search);
        Assert.False(result.Eligible);
        Assert.False(result.IsExact);
        Assert.Equal(0, result.Score);
        Assert.Empty(result.Reasons);
        Assert.Empty(result.MatchDetails);
    }

    [Fact]
    public void LegacyNullMembershipRemainsReadableWithoutInventingCoordinatesOrNeighborhoods()
    {
        using var db = Context();
        var membership = db.Model.FindEntityType(typeof(Property))!.FindProperty(nameof(Property.NeighborhoodIdsJson))!;
        Assert.True(membership.IsNullable);
        Assert.Equal("longtext", membership.GetColumnType());

        var property = Home();
        property.NeighborhoodIdsJson = null;
        var dto = JsonSerializer.SerializeToElement(Dto.Property(property, own: true));
        Assert.Equal(0, dto.GetProperty("neighborhoodIds").GetArrayLength());
        Assert.Equal(0, dto.GetProperty("neighborhoods").GetArrayLength());
        Assert.Equal(JsonValueKind.Null, dto.GetProperty("addressDetails").GetProperty("latitude").ValueKind);
        Assert.Equal(JsonValueKind.Null, dto.GetProperty("addressDetails").GetProperty("longitude").ValueKind);
        Assert.Equal("missing", dto.GetProperty("addressDetails").GetProperty("geocodingStatus").GetString());
        Assert.Empty(PropertyNeighborhoodIndex.SelectedIds(property));
        Assert.True(Rules.Compatible(property, Wanted("city:Debrecen")));
        Assert.False(Rules.Compatible(property, Wanted(Venkert)));
    }

    [Fact]
    public void NeighborhoodGateRunsBeforePartialScoringAndStillAppliesOtherCriteria()
    {
        var property = Home("city:Debrecen", Venkert);
        var search = Wanted(Venkert);
        search.MaxPrice = 50_000_000m;
        var partial = Evaluate(property, search);
        Assert.True(partial.Eligible);
        Assert.False(partial.IsExact);
        Assert.InRange(partial.Score, 1, 99);
        Assert.False(Rules.Compatible(property, search));

        property.NeighborhoodIdsJson = JsonSerializer.Serialize(new[] { Sestakert });
        var excluded = Evaluate(property, search);
        Assert.False(excluded.Eligible);
        Assert.Equal(0, excluded.Score);
        Assert.Empty(excluded.Reasons);
        Assert.Empty(excluded.MatchDetails);
    }

    [Fact]
    public void TownAreaAndNeighborhoodChoicesAreAlternativesWithIndependentAttributeFilters()
    {
        var search = Wanted(Venkert, "city:Szeged", "area:Budapest");
        Assert.True(Rules.Compatible(Home("city:Debrecen", Venkert), search));
        Assert.True(Rules.Compatible(Home("city:Szeged"), search));
        Assert.True(Rules.Compatible(Home("city:Solymár"), search));
        Assert.False(Rules.Compatible(Home("city:Debrecen", Sestakert), search));
        Assert.False(Rules.Compatible(Home("city:Győr"), search));

        search.ViewsJson = "[\"Panorámás\"]";
        foreach (var property in new[] { Home("city:Debrecen", Venkert), Home("city:Szeged"), Home("city:Solymár") })
        {
            Assert.False(Rules.Compatible(property, search));
            property.View = "Panorámás";
            Assert.True(Rules.Compatible(property, search));
        }
        Assert.True(Rules.Compatible(Home("city:Debrecen", Sestakert), Wanted(Venkert, "city:Debrecen")));
    }

    [Fact]
    public void RecordedMembershipCanCrossTheSourceMunicipalityWithoutALabelGate()
    {
        // Membership comes from geometry classification; catalog City labels identify the source municipality.
        var property = Home("city:Szeged", Venkert);
        Assert.True(LocationCatalog.Matches(property, Wanted(Venkert)));
        Assert.True(Rules.Compatible(property, Wanted(Venkert)));
        Assert.Equal(100, Evaluate(property, Wanted(Venkert)).Score);
        Assert.False(LocationCatalog.Matches(Home("city:Szeged"), Wanted(Venkert)));
        Assert.False(Rules.Compatible(property, Wanted("city:Debrecen")));
    }

    [Fact]
    public void EveryRecordedOverlapAtTheKnownSyntheticSzentimrevarosPointMatchesIndependently()
    {
        // The browser/TEST fixture records these three overlapping boundaries at this explicit synthetic point.
        var property = Home("district:Budapest:11", Szentimrevaros, Buda, BudapestEleven);
        property.Latitude = 47.47957725;
        property.Longitude = 19.039750858788466;
        foreach (var id in new[] { Szentimrevaros, Buda, BudapestEleven })
        {
            var search = Wanted(id);
            Assert.True(LocationCatalog.Matches(property, search));
            Assert.True(Rules.Compatible(property, search));
            Assert.Equal(100, Evaluate(property, search).Score);
        }
        Assert.False(LocationCatalog.Matches(property, Wanted(Venkert)));
    }

    [Fact]
    public void SellerInverseMatchingAcceptsOnlySearchesContainingAPropertyMembershipOrAnotherMatchingChoice()
    {
        var property = Home("city:Debrecen", Venkert);
        var choices = new[] {
            (Search: Wanted(Venkert), Expected: true),
            (Search: Wanted(Sestakert), Expected: false),
            (Search: Wanted("city:Debrecen"), Expected: true),
            (Search: Wanted(Sestakert, "city:Debrecen"), Expected: true),
            (Search: Wanted("city:Szeged", Sestakert), Expected: false),
            (Search: Wanted("area:Debrecen"), Expected: true)
        };
        foreach (var (search, expected) in choices)
        {
            Assert.Equal(expected, MatchingRanking.CanRecommend(property, search));
            Assert.Equal(expected, Rules.Compatible(property, search));
        }
    }

    [Fact]
    public void NeighborhoodChoicesNeverServeAsPrecisePropertyLocationsOrLegacyCityNames()
    {
        Assert.Throws<ApiException>(() => LocationCatalog.ResolvePropertyInput(Venkert, "Debrecen", null));
        Assert.Null(LocationCatalog.ForProperty(Home(Venkert, Venkert)));
        Assert.False(Evaluate(Home(Venkert, Venkert), Wanted(Venkert)).Eligible);
        Assert.Empty(LocationCatalog.ResolveLegacy(NeighborhoodCatalog.Get(Venkert)!.Label));
        Assert.DoesNotContain(LocationCatalog.Search("Vénkert", 50, "property"), value => value.Kind == "neighborhood");
    }

    [Fact]
    public void InvalidOrOversizedSelectionsCannotBroadenAQuarterSearchThroughItsLegacyCity()
    {
        var property = Home("city:Debrecen", Venkert);
        Assert.Throws<ApiException>(() => LocationCatalog.ResolveSearchInput(new[] { Venkert, "neighborhood:unknown" }, "Debrecen", null));
        Assert.False(Evaluate(property, Wanted(Venkert, "neighborhood:unknown")).Eligible);
        var tooMany = NeighborhoodCatalog.All.Take(51).Select(value => value.Id).ToArray();
        Assert.Throws<ApiException>(() => LocationCatalog.ResolveSearchInput(tooMany, "Debrecen", null));
        Assert.Empty(LocationCatalog.ForSearch(Wanted(tooMany)));
        Assert.False(Evaluate(property, Wanted(tooMany)).Eligible);
    }

    [Fact]
    public void BuyerQueryUsesMembershipExistenceWithoutAnOriginCityRestrictionOrEarlyLimit()
    {
        using var db = Context();
        var user = new User { Id = Buyer, ActiveKind = "search" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, search: Wanted(Venkert));
        Assert.Contains("PropertyNeighborhoods", sql);
        Assert.Contains("EXISTS", sql);
        Assert.Contains(Venkert, sql);
        Assert.DoesNotContain("'Debrecen'", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        Assert.DoesNotContain("LIMIT 50", sql);
        foreach (var column in new[] { "Street", "HouseNumber", "PostalCode", "Address", "Latitude", "Longitude", "Description", "ImagesJson" })
            Assert.DoesNotContain("`" + column + "`", sql);
        Assert.Equal(ConnectionState.Closed, db.Database.GetDbConnection().State);
    }

    [Fact]
    public void SellerQueryFindsNeighborhoodSearchesAcrossMunicipalitiesAndDropsMembershipAfterAnAddressChange()
    {
        using var db = Context();
        var property = Home("city:Szeged", Venkert);
        var user = new User { Id = Seller, ActiveKind = "property" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, property: property);
        Assert.Contains("SearchLocations", sql);
        Assert.Contains("DISTINCT", sql);
        Assert.Contains(Venkert, sql);
        Assert.DoesNotContain(Sestakert, sql);
        Assert.DoesNotContain("city:Debrecen", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        Assert.DoesNotContain("LIMIT 50", sql);

        property.NeighborhoodIdsJson = "[]";
        Assert.DoesNotContain(Venkert, RecommendationFeed.CandidateQuerySql(db, user, property: property));
        Assert.Equal(ConnectionState.Closed, db.Database.GetDbConnection().State);
    }

    [Fact]
    public async Task NewMembershipLinksStayCompactAndSynchronizeAllOverlapsWithoutADatabaseRead()
    {
        using var db = Context();
        var property = Home("district:Budapest:11", Szentimrevaros, Buda, Szentimrevaros);
        db.Properties.Add(property);
        var saves = 0;
        Task<int> SaveWithoutDatabase() { saves++; return Task.FromResult(1); }
        await PropertyNeighborhoodIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        await PropertyNeighborhoodIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Equal(2, saves);
        Assert.Equal(new[] { Szentimrevaros, Buda }.Order(), db.PropertyNeighborhoods.Local.Select(value => value.NeighborhoodId).Order());
        Assert.All(db.PropertyNeighborhoods.Local, value => Assert.Equal(property.Id, value.PropertyId));

        property.NeighborhoodIdsJson = JsonSerializer.Serialize(new[] { Buda });
        await PropertyNeighborhoodIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Equal(Buda, Assert.Single(db.PropertyNeighborhoods.Local).NeighborhoodId);
        property.NeighborhoodIdsJson = "[]";
        await PropertyNeighborhoodIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Empty(db.PropertyNeighborhoods.Local);
        Assert.Equal(ConnectionState.Closed, db.Database.GetDbConnection().State);

        Assert.Equal(new[] { Venkert, "city:Szeged" }, SearchLocationIndex.SelectedIds(Wanted(Venkert, "city:Szeged", Venkert)));
    }

    [Fact]
    public void MembershipSchemaHasBothLookupDirectionsAndAPropertyForeignKey()
    {
        using var db = Context();
        var entity = db.Model.FindEntityType(typeof(PropertyNeighborhood))!;
        Assert.Equal(new[] { "PropertyId", "NeighborhoodId" }, entity.FindPrimaryKey()!.Properties.Select(value => value.Name));
        Assert.Contains(entity.GetIndexes(), index => index.Properties.Select(value => value.Name)
            .SequenceEqual(new[] { "NeighborhoodId", "PropertyId" }));
        Assert.Contains(entity.GetForeignKeys(), key => key.PrincipalEntityType.ClrType == typeof(Property)
            && key.Properties.Single().Name == "PropertyId" && key.DeleteBehavior == DeleteBehavior.Restrict);
        Assert.Contains("IX_PropertyNeighborhoods_NeighborhoodId_PropertyId", db.Database.GenerateCreateScript());
    }
}
