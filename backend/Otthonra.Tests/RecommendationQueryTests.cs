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
    public void BuyerRankingQueryScoresAndLimitsInMySqlWithoutSelectingListingBodies()
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
        Assert.Contains("DistanceSquared", sql);
        Assert.Contains("ORDER BY", sql);
        Assert.Contains("LIMIT 50", sql);
        Assert.True(sql.LastIndexOf("LIMIT 50", StringComparison.Ordinal) > sql.LastIndexOf("FROM ranked", StringComparison.Ordinal));
    }

    [Fact]
    public void SellerRankingUsesIndexedCanonicalLocationsAndOmitsListingBodies()
    {
        using var db = Context();
        var user = new User { Id = Guid.NewGuid(), AccountType = AccountTypes.Agent, ActiveKind = "property" };
        var property = new Property { OwnerId = user.Id, LocationId = "district:Budapest:13", City = "Budapest", Type = "Lakás" };
        var sql = RecommendationFeed.CandidateQuerySql(db, user, property: property);
        Assert.Contains("SearchLocations", sql);
        // The exact stage has only this one candidate branch, so a UNION in
        // partial discovery cannot rescue duplicate city/area memberships.
        Assert.Matches(@"candidate_searches\s+AS\s*\(\s*SELECT\s+DISTINCT\s+sl\.`SearchRequestId`\s+AS\s+`Id`", sql);
        Assert.Contains("j.`Value` COLLATE utf8mb4_bin", sql);
        Assert.DoesNotContain("JSON_OVERLAPS", sql);
        Assert.Contains("NOT EXISTS", sql);
        Assert.Contains("JOIN", sql);
        Assert.DoesNotContain("`Description`", sql);
        Assert.DoesNotContain("`Financing`", sql);
        Assert.Contains("DistanceSquared", sql);
        Assert.Contains("ORDER BY", sql);
        Assert.Contains("LIMIT 50", sql);
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

    [Fact]
    public void ExactDiscoveryAvoidsSpatialDistanceWhilePartialDiscoveryScoresOnlyInMySql()
    {
        var user = new User { Id = Guid.NewGuid(), ActiveKind = "search" };
        var search = new SearchRequest { OwnerId = user.Id, Type = "Lakás", LocationIdsJson = "[\"city:Debrecen\"]" };
        var exact = RecommendationSql.Build(user, search: search);
        var partial = RecommendationSql.Build(user, search: search, exact: false);
        Assert.DoesNotContain("ST_Distance(", exact.Text);
        Assert.Contains("ST_Distance(", partial.Text);
        Assert.Contains("MatchingPropertyPoints", partial.Text);
        Assert.Contains("MatchingLocationAreas", partial.Text);
        Assert.Contains("DistanceSquared", partial.Text);
        Assert.Contains("POW(", partial.Text);
        Assert.Contains("EXP(-SQRT(", partial.Text);
        Assert.Contains("LIMIT 50", partial.Text);
        Assert.Contains("city:Debrecen", Assert.IsType<string>(partial.Parameters["targetAreas"]));
        foreach (var column in new[] { "Description", "ImagesJson", "Street", "HouseNumber", "Address" })
            Assert.DoesNotContain("`" + column + "`", partial.Text);
    }

    [Fact]
    public void FinalSqlOrderingPreservesRoundedScoreTiesAndIncomingInterestForEachRole()
    {
        var buyer = new User { Id = Guid.NewGuid(), ActiveKind = "search" };
        var search = new SearchRequest { OwnerId = buyer.Id, Type = "Lakás", LocationIdsJson = "[\"city:Debrecen\"]" };
        var buyerSql = RecommendationSql.Build(buyer, search: search, exact: false).Text;
        Assert.Matches(@"ORDER BY\s+Score DESC\s*,\s*LikedYou DESC\s*,\s*ValueForMoney DESC", buyerSql);
        var seller = new User { Id = Guid.NewGuid(), ActiveKind = "property" };
        var property = new Property { OwnerId = seller.Id, Type = "Lakás", LocationId = "city:Debrecen", City = "Debrecen" };
        var sellerSql = RecommendationSql.Build(seller, property: property, exact: false).Text;
        Assert.Matches(@"ORDER BY\s+LikedYou DESC\s*,\s*Score DESC\s*,\s*Specificity DESC", sellerSql);
        Assert.Contains("COALESCE(s.`PublicMaxPrice`,s.`MaxPrice`)", sellerSql);
    }
}
