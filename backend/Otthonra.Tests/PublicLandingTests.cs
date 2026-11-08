using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicLandingTests
{
    private static SearchRequest SearchAt(params string[] ids) => new()
    {
        LocationIdsJson = JsonSerializer.Serialize(ids), Type = "Lakás", MaxPrice = 90_000_000m,
        MinArea = 45m, MinRooms = 2m
    };
    private static Property PropertyAt(string id) => new()
    {
        LocationId = id, City = LocationCatalog.Get(id)?.City ?? "", Type = "Lakás",
        Price = 70_000_000m, Area = 60m, Rooms = 2.5m
    };

    [Fact]
    public void RegionCatalogCoversEveryCanonicalTownExactlyOnceAndAllBudapestDistricts()
    {
        Assert.Equal(20, RegionCatalog.All.Count);
        Assert.Equal(20, RegionCatalog.All.Select(region => region.Id).Distinct().Count());
        Assert.Equal("Budapest", RegionCatalog.Get("HU110")!.Label);
        Assert.Equal("Hajdú-Bihar vármegye", RegionCatalog.Get("HU321")!.Label);
        foreach (var town in LocationCatalog.All.Where(location => location.Kind == "city"))
            Assert.NotNull(RegionCatalog.Get(Assert.Single(RegionCatalog.ForLocation(town))));
        for (var district = 1; district <= 23; district++)
            Assert.Equal("HU110", Assert.Single(RegionCatalog.ForLocation(LocationCatalog.Get($"district:Budapest:{district}")!)));
        Assert.Equal("HU120", Assert.Single(RegionCatalog.ForLocation(LocationCatalog.Get("city:Solymár")!)));
        Assert.Equal("HU321", Assert.Single(RegionCatalog.ForLocation(LocationCatalog.Get("city:Debrecen")!)));
    }

    [Fact]
    public void AreasAreMappedByEveryMemberRatherThanOnlyTheirCentralCity()
    {
        using var stream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Agglomerations.json");
        using var data = JsonDocument.Parse(stream!);
        foreach (var area in data.RootElement.GetProperty("areas").EnumerateArray())
        {
            var expected = area.GetProperty("settlements").EnumerateArray()
                .SelectMany(town => RegionCatalog.ForLocation(LocationCatalog.Get("city:" + town.GetString())!))
                .Distinct().Order().ToArray();
            Assert.Equal(expected, RegionCatalog.ForLocation(LocationCatalog.Get(area.GetProperty("id").GetString())!).Order().ToArray());
        }
        Assert.Equal(new[] { "HU110", "HU120" }, RegionCatalog.ForLocation(LocationCatalog.Get("area:Budapest")!).Order().ToArray());
    }

    [Fact]
    public void RegionFilterKeepsAnOlderRegionalRowAfterThousandsOfOtherRows()
    {
        var snapshot = new PublicLandingSnapshot();
        for (var i = 0; i < 3000; i++)
        {
            snapshot.Add(SearchAt("city:Budapest"), AccountTypes.Private);
            snapshot.Add(PropertyAt("city:Budapest"), AccountTypes.Private);
        }
        snapshot.Add(SearchAt("city:Debrecen"), AccountTypes.Agent);
        snapshot.Add(PropertyAt("city:Debrecen"), AccountTypes.Private);
        var national = snapshot.Response(null);
        Assert.Equal("national", national.Scope);
        Assert.Null(national.Region);
        Assert.Equal(8, national.Searches.Length);
        Assert.Equal(4, national.Properties.Length);
        var regional = snapshot.Response(RegionCatalog.Get("HU321"));
        Assert.Equal("region", regional.Scope);
        Assert.Equal("HU321", regional.Region!.Id);
        Assert.Equal("Debrecen", Assert.Single(Assert.Single(regional.Searches).Locations));
        Assert.Equal(AccountTypes.Agent, Assert.Single(regional.Searches).OwnerAccountType);
        Assert.Equal("Debrecen", Assert.Single(regional.Properties).Location);
        var empty = snapshot.Response(RegionCatalog.Get("HU231"));
        Assert.Empty(empty.Searches); Assert.Empty(empty.Properties);
        Assert.Equal("region", empty.Scope);
    }

    [Fact]
    public void SearchWithMultiplePlacesAndACrossCountyAreaIsOnlyAddedOncePerRegion()
    {
        var snapshot = new PublicLandingSnapshot();
        snapshot.Add(SearchAt("area:Budapest", "city:Solymár", "district:Budapest:5", "city:Debrecen"), AccountTypes.Private);
        Assert.Single(snapshot.Response(null).Searches);
        Assert.Single(snapshot.Response(RegionCatalog.Get("HU110")).Searches);
        Assert.Single(snapshot.Response(RegionCatalog.Get("HU120")).Searches);
        Assert.Single(snapshot.Response(RegionCatalog.Get("HU321")).Searches);
        Assert.Empty(snapshot.Response(RegionCatalog.Get("HU231")).Searches);
    }

    [Fact]
    public void ArchivedAndMalformedLocationsCannotAppearInPublicSnapshots()
    {
        var snapshot = new PublicLandingSnapshot();
        var archivedSearch = SearchAt("city:Debrecen"); archivedSearch.Archived = true;
        var archivedProperty = PropertyAt("city:Debrecen"); archivedProperty.Archived = true;
        snapshot.Add(archivedSearch, AccountTypes.Private); snapshot.Add(archivedProperty, AccountTypes.Private);
        snapshot.Add(new SearchRequest { LocationIdsJson = "{broken", City = "Debrecen" }, AccountTypes.Private);
        snapshot.Add(new SearchRequest { LocationIdsJson = "[\"city:missing\"]", City = "Debrecen" }, AccountTypes.Private);
        snapshot.Add(PropertyAt("area:Debrecen"), AccountTypes.Private);
        snapshot.Add(PropertyAt("city:missing"), AccountTypes.Private);
        Assert.Empty(snapshot.Response(null).Searches); Assert.Empty(snapshot.Response(null).Properties);
    }

    [Fact]
    public void AnonymousTeasersOnlySerializeSafeFieldsAndNeverSourceIdentifiersOrFreeText()
    {
        const string secret = "secret-canary person@example.test +36 30 123 4567";
        var search = SearchAt("city:Debrecen");
        search.Title = secret; search.Description = secret; search.City = secret; search.Type = secret;
        search.MinPrice = -123m;
        var property = PropertyAt("district:Budapest:5");
        property.Title = secret; property.Description = secret; property.Neighborhood = secret; property.Address = secret;
        property.City = secret; property.District = secret; property.ImagesJson = JsonSerializer.Serialize(new[] { "https://tracker.example.test/" + secret });
        property.WholeRooms = 2; property.HalfRooms = 1; property.Type = secret;
        var snapshot = new PublicLandingSnapshot(); snapshot.Add(search, secret); snapshot.Add(property, AccountTypes.Agent);
        var response = snapshot.Response(null);
        var json = JsonSerializer.Serialize(response, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.DoesNotContain(secret, json);
        foreach (var id in new[] { search.Id, search.OwnerId, property.Id, property.OwnerId })
            Assert.DoesNotContain(id.ToString(), json);
        using var document = JsonDocument.Parse(json);
        var s = document.RootElement.GetProperty("searches")[0];
        var p = document.RootElement.GetProperty("properties")[0];
        Assert.Equal(new[] { "key", "locations", "maxArea", "maxPrice", "maxRooms", "minArea", "minPrice", "minRooms", "ownerAccountType", "title", "type" },
            s.EnumerateObject().Select(value => value.Name).Order(StringComparer.Ordinal).ToArray());
        Assert.Equal(new[] { "area", "halfRooms", "key", "location", "lotArea", "ownerAccountType", "price", "rooms", "title", "type", "wholeRooms" },
            p.EnumerateObject().Select(value => value.Name).Order(StringComparer.Ordinal).ToArray());
        Assert.Equal("Ingatlant keres", response.Searches[0].Title);
        Assert.Equal("Ingatlan", response.Properties[0].Type);
        Assert.Null(response.Searches[0].MinPrice);
        Assert.Equal("Debrecen", response.Searches[0].Locations[0]);
        Assert.Equal("Budapest V. kerület", response.Properties[0].Location);
        Assert.Equal("private", response.Searches[0].OwnerAccountType);
        Assert.Equal("agent", response.Properties[0].OwnerAccountType);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public void MissingRegionMeansNationwide(string? region) => Assert.Null(PublicLanding.ParseRegion(region));

    [Theory]
    [InlineData("HU999")]
    [InlineData("Debrecen")]
    [InlineData("../HU110")]
    public void UnknownRegionIsRejectedInsteadOfInventingLocalContent(string region)
    {
        var error = Assert.Throws<ApiException>(() => PublicLanding.ParseRegion(region));
        Assert.Equal(400, error.Status);
    }
}
