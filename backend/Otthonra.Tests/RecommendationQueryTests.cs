using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class RecommendationQueryTests
{
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=query_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    [Fact]
    public void BuyerRankingQueryFiltersBeforeStreamingAndOmitsListingBodies()
    {
        using var db = Context();
        var user = new User { Id = Guid.NewGuid(), AccountType = AccountTypes.Agent, ActiveKind = "search" };
        var search = new SearchRequest { OwnerId = user.Id, LocationIdsJson = "[\"area:Debrecen\"]", Type = "Lakás" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, search: search);
        Assert.Contains("JOIN", sql);
        Assert.Contains("NOT EXISTS", sql);
        Assert.Contains("LocationId", sql);
        Assert.Contains("ActorKind", sql);
        Assert.Contains("AccountType", sql);
        Assert.DoesNotContain("`Description`", sql);
        Assert.DoesNotContain("`ImagesJson`", sql);
        Assert.DoesNotContain("`Address`", sql);
        Assert.DoesNotContain("LIMIT 50", sql); // No truncation before the complete candidate ranking.
    }

    [Fact]
    public void SellerRankingUsesIndexedCanonicalLocationsAndOmitsListingBodies()
    {
        using var db = Context();
        var user = new User { Id = Guid.NewGuid(), AccountType = AccountTypes.Agent, ActiveKind = "property" };
        var property = new Property { OwnerId = user.Id, LocationId = "district:Budapest:13", City = "Budapest", Type = "Lakás" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, property: property);
        Assert.Contains("SearchLocations", sql);
        Assert.Contains("DISTINCT", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        Assert.Contains("NOT EXISTS", sql);
        Assert.Contains("JOIN", sql);
        Assert.DoesNotContain("`Description`", sql);
        Assert.DoesNotContain("`Financing`", sql);
        Assert.DoesNotContain("LIMIT 50", sql);
    }

    [Fact]
    public void CandidateIndexesExistInNewSchemasAndHaveAnAdditiveUpgradeVersion()
    {
        using var db = Context();
        var sql = db.Database.GenerateCreateScript();
        Assert.Contains("IX_Properties_Archived_Type_LocationId", sql);
        Assert.Contains("IX_Properties_Archived_Type_City", sql);
        Assert.Contains("IX_SearchRequests_Archived_Type_City", sql);
        Assert.Contains("IX_SearchLocations_LocationId_SearchRequestId", sql);
        Assert.Contains("PK_SearchLocations", sql);
        Assert.Contains("IX_Decisions_SearchRequestId_ActorKind_PropertyId", sql);
        Assert.Equal("20261110-ranked-recommendation-indexes", SchemaUpgrade.RecommendationIndexesVersion);
    }
}
