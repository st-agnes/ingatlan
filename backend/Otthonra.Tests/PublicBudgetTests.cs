using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class PublicBudgetTests
{
    private static SearchInput Input() => new("Otthont keresek", "Debrecen", [], "Világos lakásra vágyom.",
        "Lakás", null, 80_000_000m, 20m, null, 1m, null, false, false, null, null,
        LocationIds: ["city:Debrecen"], PublicMaxPrice: 70_000_000m);
    private static SearchRequest Search()
    {
        var search = new SearchRequest { OwnerId = Guid.NewGuid() }; Rules.Apply(search, Input()); return search;
    }
    private static Property Home(decimal price = 75_000_000m) => new() {
        OwnerId = Guid.NewGuid(), LocationId = "city:Debrecen", City = "Debrecen", Type = "Lakás",
        Price = price, Area = 30m, Rooms = 2m
    };
    private static MatchEvaluation Match(Property property, SearchRequest search, bool seller = false)
        => MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search, sellerPerspective: seller));

    [Fact]
    public void BuyerUsesTheRealCeilingButSellerUsesOnlyThePublicCeiling()
    {
        var search = Search(); var property = Home();
        var buyer = Match(property, search); var seller = Match(property, search, true);
        Assert.True(buyer.IsExact); Assert.Equal(100, buyer.Score);
        Assert.False(seller.IsExact); Assert.InRange(seller.Score, 1, 99);
        Assert.Equal("legfeljebb 80 M Ft", Assert.Single(buyer.MatchDetails, row => row.Key == "price").Expected);
        Assert.Equal("legfeljebb 70 M Ft", Assert.Single(seller.MatchDetails, row => row.Key == "price").Expected);
        Assert.True(Match(Home(70_000_000m), search, true).IsExact);
        Assert.False(Match(Home(85_000_000m), search).IsExact);
        Assert.Equal(80_000_000m, search.MaxPrice); Assert.Equal(70_000_000m, search.PublicMaxPrice);
    }

    [Fact]
    public void ChangingOnlyThePrivateCeilingCannotChangeSellerRankReasonsOrSpecificity()
    {
        var search = Search(); search.MinPrice = 20_000_000m; var property = Home();
        var before = Match(property, search, true); var specificity = MatchingRanking.Specificity(search, true);
        search.MaxPrice = 800_000_000m;
        var after = Match(property, search, true);
        Assert.Equal(before.Score, after.Score); Assert.Equal(before.IsExact, after.IsExact);
        Assert.Equal(before.Reasons, after.Reasons); Assert.Equal(before.MatchDetails, after.MatchDetails);
        Assert.Equal(specificity, MatchingRanking.Specificity(search, true));
    }

    [Fact]
    public void PublicCeilingDoesNotReduceBuyerEligibilityAndPreparedCriteriaRemainIndependent()
    {
        var search = Search(); var buyer = MatchingRanking.Prepare(search); var seller = MatchingRanking.Prepare(search, true);
        search.MaxPrice = 50_000_000m; search.PublicMaxPrice = 40_000_000m;
        Assert.True(MatchingRanking.Evaluate(Home(), buyer).IsExact);
        Assert.False(MatchingRanking.Evaluate(Home(), seller).IsExact);
        Assert.Equal(80_000_000m, buyer.Source.MaxPrice); Assert.Equal(70_000_000m, seller.Source.MaxPrice);
        Assert.Null(seller.Source.PublicMaxPrice); // No hidden cap remains in a prepared seller record.
    }

    [Fact]
    public void OldSearchesWithoutSeparatePublicAmountRetainTheirOldMatchingInBothDirections()
    {
        var search = Search(); search.PublicMaxPrice = null;
        Assert.Equal(search.MaxPrice, SearchBudgets.PublicMaximum(search));
        foreach (var price in new[] { 70_000_000m, 75_000_000m, 80_000_000m, 90_000_000m })
        {
            var buyer = Match(Home(price), search); var seller = Match(Home(price), search, true);
            Assert.Equal(buyer.Score, seller.Score); Assert.Equal(buyer.IsExact, seller.IsExact);
            Assert.Equal(buyer.MatchDetails, seller.MatchDetails);
        }
        search.MaxPrice = null;
        Assert.Null(SearchBudgets.PublicMaximum(search)); Assert.True(Match(Home(), search, true).IsExact);
    }

    [Theory]
    [InlineData(-1, null)] [InlineData(0, null)] [InlineData(80_000_001, null)]
    [InlineData(70_000_000, 75_000_000)]
    public void PublicCapMustBePositiveAndInsideTheVisiblePriceRange(int amount, int? minimum)
    {
        var search = new SearchRequest();
        var error = Assert.Throws<ApiException>(() => Rules.Apply(search, Input() with { PublicMaxPrice = amount, MinPrice = minimum }));
        Assert.Equal(400, error.Status);
    }

    [Fact]
    public void PublicCapCanEqualEitherBoundAndCanBeCleared()
    {
        var search = Search();
        Rules.Apply(search, Input() with { PublicMaxPrice = 80_000_000m }); Assert.Equal(search.MaxPrice, search.PublicMaxPrice);
        Rules.Apply(search, Input() with { MinPrice = 70_000_000m }); Assert.Equal(search.MinPrice, search.PublicMaxPrice);
        Rules.Apply(search, Input() with { PublicMaxPrice = null }); Assert.Null(search.PublicMaxPrice);
    }

    [Fact]
    public void CreationReceiptsKeepOldPayloadsCompatibleAndDistinguishDifferentNewPublicBudgets()
    {
        var input = Input() with { PublicMaxPrice = null };
        var json = JsonSerializer.SerializeToElement(input);
        Assert.False(json.TryGetProperty("PublicMaxPrice", out _));
        Assert.Equal(EntityCreation.RequestHash(input), EntityCreation.RequestHash(input with { CreationRequestId = Guid.NewGuid() }));
        Assert.NotEqual(EntityCreation.RequestHash(input), EntityCreation.RequestHash(input with { PublicMaxPrice = 70_000_000m }));
        Assert.NotEqual(EntityCreation.RequestHash(input with { PublicMaxPrice = 70_000_000m }), EntityCreation.RequestHash(input with { PublicMaxPrice = 75_000_000m }));
    }

    [Fact]
    public void SellerCandidateSqlResolvesPublicBudgetInsideTheLeanExistingProjection()
    {
        using var db = new AppDb(new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=query_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options);
        var sql = RecommendationFeed.CandidateQuerySql(db, new User { Id = Guid.NewGuid(), ActiveKind = "property" }, property: Home());
        Assert.Contains("COALESCE", sql); Assert.Contains("`PublicMaxPrice`", sql);
        Assert.Contains("SearchLocations", sql); Assert.DoesNotContain("`Description`", sql);
        Assert.DoesNotContain("`ImagesJson`", sql); Assert.DoesNotContain("LIMIT 50", sql);
        var column = db.Model.FindEntityType(typeof(SearchRequest))!.FindProperty(nameof(SearchRequest.PublicMaxPrice))!;
        Assert.True(column.IsNullable); Assert.Equal(18, column.GetPrecision()); Assert.Equal(2, column.GetScale());
        Assert.Equal("20261124-search-public-budget", SchemaUpgrade.PublicBudgetVersion);
    }
}
