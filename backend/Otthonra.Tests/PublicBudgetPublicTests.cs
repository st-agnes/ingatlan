using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicBudgetPublicTests
{
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);
    private static JsonElement Json(object value) => JsonSerializer.SerializeToElement(value, WebJson);
    private static SearchRequest Wanted(decimal actual = 80_000_000m, decimal? published = 70_000_000m) => new() {
        Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Title = "Világos otthont keresünk", City = "Debrecen",
        LocationIdsJson = "[\"city:Debrecen\"]", Type = "Lakás", MinPrice = 10_000_000m,
        MaxPrice = actual, PublicMaxPrice = published, MinArea = 20m, MinRooms = 1m
    };

    private static int AssertOnlyPublicBudget(JsonElement node, decimal expected)
    {
        var count = 0;
        if (node.ValueKind == JsonValueKind.Object)
            foreach (var property in node.EnumerateObject())
            {
                Assert.False(property.Name.Equals("publicMaxPrice", StringComparison.OrdinalIgnoreCase),
                    "Foreign output must not reveal separate private/public budget fields.");
                if (property.Name.Equals("maxPrice", StringComparison.OrdinalIgnoreCase))
                {
                    Assert.Equal(expected, property.Value.GetDecimal());
                    count++;
                }
                count += AssertOnlyPublicBudget(property.Value, expected);
            }
        else if (node.ValueKind == JsonValueKind.Array)
            foreach (var value in node.EnumerateArray()) count += AssertOnlyPublicBudget(value, expected);
        return count;
    }

    [Fact]
    public void OnlyAnOwnedSearchDtoIncludesTheActualAndSeparatelyPublishedMaximum()
    {
        var search = Wanted();
        var foreign = Json(Dto.Search(search));
        Assert.Equal(1, AssertOnlyPublicBudget(foreign, 70_000_000m));
        Assert.Equal(10_000_000m, foreign.GetProperty("minPrice").GetDecimal());
        Assert.Equal(MatchingRanking.Prepare(search, sellerPerspective: true).Specificity,
            foreign.GetProperty("searchSpecificity").GetInt32());
        var owner = Json(Dto.Search(search, own: true));
        Assert.Equal(80_000_000m, owner.GetProperty("maxPrice").GetDecimal());
        Assert.Equal(70_000_000m, owner.GetProperty("publicMaxPrice").GetDecimal());
        Assert.Equal(MatchingRanking.Prepare(search).Specificity, owner.GetProperty("searchSpecificity").GetInt32());
        Assert.Equal(80_000_000m, search.MaxPrice); // DTO creation must not mutate the stored owner criteria.
        Assert.Equal(70_000_000m, search.PublicMaxPrice);
    }

    [Fact]
    public void AnonymousTeasersAndEveryPublicDetailAndCloneSeedUseThePublishedMaximum()
    {
        var search = Wanted();
        var teaser = PublicLanding.SearchTeaser(search, AccountTypes.Private, "Nagy Péter")!.Value.Teaser;
        Assert.Equal(2, AssertOnlyPublicBudget(Json(teaser), 70_000_000m));
        var detail = PublicListings.Search(search, AccountTypes.Private, "Nagy Péter")!;
        Assert.Equal(3, AssertOnlyPublicBudget(Json(detail), 70_000_000m));
        Assert.Equal(search.MinPrice, Json(detail).GetProperty("clonePrefill").GetProperty("minPrice").GetDecimal());
        Assert.Equal(search.MinArea, Json(detail).GetProperty("clonePrefill").GetProperty("minArea").GetDecimal());
        Assert.Equal(80_000_000m, search.MaxPrice);
    }

    [Fact]
    public void PublicSnapshotCopiesContainOnlyThePublishedBudgetAndRemainIsolated()
    {
        var search = Wanted();
        var snapshot = new PublicLandingSnapshot(new Random(13));
        snapshot.Add(search, AccountTypes.Private, "Nagy Péter");
        var county = RegionCatalog.Get(Assert.Single(RegionCatalog.ForLocations(LocationCatalog.ForSearch(search))));
        Assert.NotNull(county);
        var item = Assert.Single(snapshot.Response(county).Searches);
        Assert.Equal(2, AssertOnlyPublicBudget(Json(item), 70_000_000m));
        var copied = item.Prefill! with { MaxPrice = 1m };
        Assert.Equal(1m, copied.MaxPrice);
        Assert.Equal(70_000_000m, Assert.Single(snapshot.Response(null).Searches).Prefill!.MaxPrice);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(70_000_000)]
    public void LegacyFallbackAndExplicitPublicBudgetHaveIdenticalForeignShape(int? published)
    {
        var search = Wanted(70_000_000m, published);
        var foreign = Json(Dto.Search(search));
        Assert.Equal(1, AssertOnlyPublicBudget(foreign, 70_000_000m));
        Assert.Equal(3, AssertOnlyPublicBudget(Json(PublicListings.Search(search, AccountTypes.Private)!), 70_000_000m));
        var owner = Json(Dto.Search(search, own: true));
        if (published is null) Assert.Equal(JsonValueKind.Null, owner.GetProperty("publicMaxPrice").ValueKind);
        else Assert.Equal((decimal)published.Value, owner.GetProperty("publicMaxPrice").GetDecimal());
    }

    [Fact]
    public void ForeignSpecificityDoesNotDiscloseChangesToThePrivateMaximum()
    {
        var search = Wanted();
        var before = Json(Dto.Search(search));
        search.MaxPrice = 800_000_000m;
        var after = Json(Dto.Search(search));
        Assert.Equal(before.GetProperty("maxPrice").GetDecimal(), after.GetProperty("maxPrice").GetDecimal());
        Assert.Equal(before.GetProperty("searchSpecificity").GetInt32(), after.GetProperty("searchSpecificity").GetInt32());
        Assert.Equal(3, AssertOnlyPublicBudget(Json(PublicListings.Search(search, AccountTypes.Private)!), 70_000_000m));
    }
}
