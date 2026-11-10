using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class SearchLocationIndexTests
{
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    [Fact]
    public void SelectedLocationsRemainCanonicalCompactAndDeduplicated()
    {
        var search = new SearchRequest { LocationIdsJson = "[\"area:Budapest\",\"district:Budapest:13\",\"city:Solymár\",\"area:Budapest\"]" };
        Assert.Equal(new[] { "area:Budapest", "district:Budapest:13", "city:Solymár" }, SearchLocationIndex.SelectedIds(search));
        Assert.Equal(new[] { "district:Budapest:13" }, SearchLocationIndex.SelectedIds(new SearchRequest {
            City = "Budapest", DistrictsJson = "[\"XIII.\"]", LocationIdsJson = null
        }));
        Assert.Equal(new[] { "city:Debrecen" }, SearchLocationIndex.SelectedIds(new SearchRequest {
            City = "Debrecen", LocationIdsJson = "null"
        }));
    }

    [Theory]
    [InlineData("{broken")]
    [InlineData("[\"city:missing\"]")]
    [InlineData("[]")]
    public void InvalidOldLocationsReceiveOneNonmatchingMarker(string json)
        => Assert.Equal(new[] { SearchLocationIndex.InvalidLocation },
            SearchLocationIndex.SelectedIds(new SearchRequest { LocationIdsJson = json }));

    [Fact]
    public async Task NewSearchKeysAreSynchronizedWithoutAReadAndRepeatedAttemptsKeepTheSameKeys()
    {
        using var db = Context();
        var search = new SearchRequest { LocationIdsJson = "[\"city:Debrecen\"]" };
        db.SearchRequests.Add(search);
        var saves = 0;
        Task<int> SaveWithoutDatabase() { saves++; return Task.FromResult(1); }
        await SearchLocationIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        await SearchLocationIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Equal(2, saves);
        Assert.Equal("city:Debrecen", Assert.Single(db.SearchLocations.Local).LocationId);
        search.LocationIdsJson = "[\"city:Debrecen\",\"area:Debrecen\"]";
        await SearchLocationIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Equal(2, db.SearchLocations.Local.Count);
        search.LocationIdsJson = "[\"area:Debrecen\"]";
        await SearchLocationIndex.SaveAsync(db, SaveWithoutDatabase, CancellationToken.None);
        Assert.Equal("area:Debrecen", Assert.Single(db.SearchLocations.Local).LocationId);
    }

    [Fact]
    public async Task EditingAnUnrelatedSearchFieldDoesNotQueryOrRebuildTheLocationIndex()
    {
        using var db = Context();
        var search = new SearchRequest { LocationIdsJson = "[\"city:Debrecen\"]", Title = "Before" };
        db.SearchRequests.Attach(search);
        search.Title = "After";
        var saved = await SearchLocationIndex.SaveAsync(db, () => Task.FromResult(1), CancellationToken.None);
        Assert.Equal(1, saved);
        Assert.Empty(db.ChangeTracker.Entries<SearchLocation>());
    }

    [Fact]
    public void IndexLinksParticipateInForeignKeySafeFixtureResetOrder()
    {
        using var db = Context();
        var order = TestDataSeed.DeletionOrder(db.Model).ToList();
        Assert.True(order.IndexOf("SearchLocations") < order.IndexOf("SearchRequests"));
        var entity = db.Model.FindEntityType(typeof(SearchLocation))!;
        Assert.Equal(new[] { "SearchRequestId", "LocationId" }, entity.FindPrimaryKey()!.Properties.Select(property => property.Name));
        Assert.Contains(entity.GetIndexes(), index => index.Properties.Select(property => property.Name)
            .SequenceEqual(new[] { "LocationId", "SearchRequestId" }));
    }
}
