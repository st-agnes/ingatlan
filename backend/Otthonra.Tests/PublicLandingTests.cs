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
    public void AnonymousTeasersOnlySerializeApprovedPublicFieldsAndNeverContactsOrSourceIdentifiers()
    {
        const string secret = "secret-canary person@example.test +36 30 123 4567";
        var search = SearchAt("city:Debrecen");
        search.Title = secret; search.Description = secret; search.City = secret; search.Type = secret;
        search.MinPrice = -123m;
        var property = PropertyAt("district:Budapest:5");
        property.Title = secret; property.Description = secret; property.Neighborhood = secret; property.Address = secret;
        property.City = secret; property.District = secret; property.ImagesJson = JsonSerializer.Serialize(new[] { "https://tracker.example.test/" + secret });
        property.WholeRooms = 2; property.HalfRooms = 1; property.Type = secret;
        var snapshot = new PublicLandingSnapshot(); snapshot.Add(search, secret, secret); snapshot.Add(property, AccountTypes.Agent, secret);
        var response = snapshot.Response(null);
        var json = JsonSerializer.Serialize(response, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.DoesNotContain(secret, json);
        foreach (var id in new[] { search.Id, search.OwnerId, property.Id, property.OwnerId })
            Assert.DoesNotContain(id.ToString(), json);
        using var document = JsonDocument.Parse(json);
        var s = document.RootElement.GetProperty("searches")[0];
        var p = document.RootElement.GetProperty("properties")[0];
        Assert.Equal(new[] { "key", "locations", "maxArea", "maxPrice", "maxRooms", "minArea", "minPrice", "minRooms", "ownerAccountType", "ownerFirstName", "title", "type" },
            s.EnumerateObject().Select(value => value.Name).Order(StringComparer.Ordinal).ToArray());
        Assert.Equal(new[] { "area", "halfRooms", "key", "location", "lotArea", "ownerAccountType", "ownerFirstName", "price", "rooms", "title", "type", "wholeRooms" },
            p.EnumerateObject().Select(value => value.Name).Order(StringComparer.Ordinal).ToArray());
        Assert.Equal("Ingatlant keres", response.Searches[0].Title);
        Assert.Equal("Ingatlan", response.Properties[0].Type);
        Assert.Null(response.Searches[0].MinPrice);
        Assert.Equal("Debrecen", response.Searches[0].Locations[0]);
        Assert.Equal("Budapest V. kerület", response.Properties[0].Location);
        Assert.Equal("private", response.Searches[0].OwnerAccountType);
        Assert.Equal("agent", response.Properties[0].OwnerAccountType);
    }

    [Fact]
    public void TeasersDisplayTheRealAdTitleAndOnlyTheOwnersGivenName()
    {
        var search = SearchAt("city:Debrecen"); search.Title = "Kertes családi otthont keresünk";
        var property = PropertyAt("city:Debrecen"); property.Title = "Napfényes otthon az egyetem mellett";
        property.Address = "Személyes utca 42";
        var snapshot = new PublicLandingSnapshot();
        snapshot.Add(search, AccountTypes.Private, "Kovács Anna");
        snapshot.Add(property, AccountTypes.Agent, "Dr. Nagy Péter");
        var response = snapshot.Response(null);
        var publicSearch = Assert.Single(response.Searches);
        var publicProperty = Assert.Single(response.Properties);
        Assert.Equal(search.Title, publicSearch.Title); Assert.Equal("Anna", publicSearch.OwnerFirstName);
        Assert.Equal(property.Title, publicProperty.Title); Assert.Equal("Péter", publicProperty.OwnerFirstName);
        var json = JsonSerializer.Serialize(response);
        Assert.DoesNotContain("Nagy", json); Assert.DoesNotContain("Kovács", json);
        Assert.DoesNotContain(property.Address, json);
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
    [Fact]
    public void DiverseSamplesKeepRareTypesAndPriceBandsBehindThousandsOfSimilarRows()
    {
        var snapshot = new PublicLandingSnapshot(new Random(2718));
        for (var index = 0; index < 3000; index++)
        {
            var search = SearchAt("district:Budapest:13"); search.MaxPrice = 55_000_000m;
            var property = PropertyAt("district:Budapest:13"); property.Price = 55_000_000m;
            snapshot.Add(search, AccountTypes.Private); snapshot.Add(property, AccountTypes.Private);
        }
        var types = new[] { "Ház", "Nyaraló", "Iroda" };
        var prices = new[] { 20_000_000m, 105_000_000m, 220_000_000m };
        var districts = new[] { 2, 5, 11 };
        for (var index = 0; index < types.Length; index++)
        {
            var search = SearchAt($"district:Budapest:{districts[index]}");
            search.Type = types[index]; search.MaxPrice = prices[index]; search.MaxArea = 50m + index * 70m;
            var property = PropertyAt($"district:Budapest:{districts[index]}");
            property.Type = types[index]; property.Price = prices[index]; property.Area = 50m + index * 70m;
            property.LotArea = types[index] == "Ház" ? 500m : null;
            snapshot.Add(search, AccountTypes.Agent); snapshot.Add(property, AccountTypes.Private);
        }
        for (var refresh = 0; refresh < 20; refresh++)
        {
            var response = snapshot.Response(RegionCatalog.Get("HU110"));
            Assert.Equal(8, response.Searches.Length); Assert.Equal(4, response.Properties.Length);
            Assert.Equal(new[] { "Ház", "Iroda", "Lakás", "Nyaraló" }, response.Searches.Select(item => item.Type).Distinct().Order(StringComparer.Ordinal).ToArray());
            Assert.Equal(4, response.Properties.Select(item => item.Type).Distinct().Count());
            Assert.Equal(4, response.Searches.Select(item => item.MaxPrice).Distinct().Count());
            Assert.Equal(4, response.Properties.Select(item => item.Price).Distinct().Count());
            Assert.Equal(4, response.Properties.Select(item => item.Location).Distinct().Count());
        }
    }

    private static readonly Lazy<TestDataPlan> HostedFixtures = new(() =>
        TestDataSeed.BuildPlan(TestDataSeed.LoadCatalog()));

    private static PublicLandingSnapshot HostedFixtureSnapshot(int seed)
    {
        var snapshot = new PublicLandingSnapshot(new Random(seed));
        var owners = HostedFixtures.Value.Users.ToDictionary(user => user.Id, user => user.AccountType);
        foreach (var search in HostedFixtures.Value.Searches) snapshot.Add(search, owners[search.OwnerId]);
        foreach (var property in HostedFixtures.Value.Properties) snapshot.Add(property, owners[property.OwnerId]);
        return snapshot;
    }

    // Ignore positional UI keys: membership must change in fields the visitor
    // can actually see, rather than merely swapping internal source IDs/order.
    private static string VisibleSearch(LandingSearchTeaser item) => JsonSerializer.Serialize(item with { Key = "" });
    private static string VisibleProperty(LandingPropertyTeaser item) => JsonSerializer.Serialize(item with { Key = "" });
    private static string Membership(IEnumerable<string> signatures) => string.Join("\n", signatures.Order(StringComparer.Ordinal));

    [Fact]
    public void ActualHostedFixturesProduceDiverseSafeCountySamplesRatherThanOnlySyntheticTestRows()
    {
        var snapshot = HostedFixtureSnapshot(20261109);
        var owners = HostedFixtures.Value.Users.ToDictionary(user => user.Id, user => user.AccountType);
        foreach (var region in RegionCatalog.All)
        {
            var allowedSearches = HostedFixtures.Value.Searches
                .Select(item => PublicLanding.SearchTeaser(item, owners[item.OwnerId])!.Value)
                .Where(item => item.Regions.Contains(region.Id)).Select(item => VisibleSearch(item.Teaser)).ToHashSet();
            var allowedProperties = HostedFixtures.Value.Properties
                .Select(item => PublicLanding.PropertyTeaser(item, owners[item.OwnerId])!.Value)
                .Where(item => item.Regions.Contains(region.Id)).Select(item => VisibleProperty(item.Teaser)).ToHashSet();
            for (var refresh = 0; refresh < 8; refresh++)
            {
                var response = snapshot.Response(region);
                Assert.Equal(region.Id, response.Region!.Id);
                Assert.Equal(8, response.Searches.Length); Assert.Equal(4, response.Properties.Length);
                Assert.Equal(2, response.Searches.Select(item => item.Type).Distinct().Count());
                Assert.Equal(2, response.Properties.Select(item => item.Type).Distinct().Count());
                Assert.True(response.Searches.Select(item => (item.MinPrice, item.MaxPrice)).Distinct().Count() >= 3, region.Label);
                Assert.True(response.Searches.Select(item => (item.MinArea, item.MaxArea)).Distinct().Count() >= 3, region.Label);
                Assert.True(response.Searches.Select(item => (item.MinRooms, item.MaxRooms)).Distinct().Count() >= 3, region.Label);
                Assert.True(response.Properties.Select(item => item.Price).Distinct().Count() >= 3, region.Label);
                Assert.True(response.Properties.Select(item => item.Area).Distinct().Count() >= 3, region.Label);
                Assert.True(response.Properties.Select(item => item.Rooms).Distinct().Count() >= 2, region.Label);
                Assert.All(response.Searches, item => Assert.Contains(VisibleSearch(item), allowedSearches));
                Assert.All(response.Properties, item => Assert.Contains(VisibleProperty(item), allowedProperties));
            }
        }
    }

    [Fact]
    public void HajduBiharHostedSamplesSpanWideCriteriaAndRefreshTheirVisibleMembership()
    {
        var snapshot = HostedFixtureSnapshot(321);
        var seenSearches = new List<LandingSearchTeaser>();
        var seenProperties = new List<LandingPropertyTeaser>();
        var searchMemberships = new HashSet<string>(StringComparer.Ordinal);
        var propertyMemberships = new HashSet<string>(StringComparer.Ordinal);
        for (var refresh = 0; refresh < 30; refresh++)
        {
            var response = snapshot.Response(RegionCatalog.Get("HU321"));
            seenSearches.AddRange(response.Searches); seenProperties.AddRange(response.Properties);
            searchMemberships.Add(Membership(response.Searches.Select(VisibleSearch)));
            propertyMemberships.Add(Membership(response.Properties.Select(VisibleProperty)));
        }
        Assert.True(searchMemberships.Count >= 10, "Refreshes should show different search criteria, not only reorder the same cards.");
        Assert.True(propertyMemberships.Count >= 10, "Refreshes should show different properties, not only reorder the same cards.");
        Assert.Contains(seenSearches, item => item.MaxPrice <= 40_000_000m);
        Assert.Contains(seenSearches, item => item.MaxPrice >= 200_000_000m);
        Assert.Contains(seenSearches, item => item.MaxArea <= 55m);
        Assert.Contains(seenSearches, item => (item.MaxArea ?? item.MinArea) >= 160m);
        Assert.Contains(seenSearches, item => item.MinRooms <= 1.5m);
        Assert.Contains(seenSearches, item => item.MinRooms >= 5m);
        Assert.Contains(seenProperties, item => item.Price <= 35_000_000m);
        Assert.Contains(seenProperties, item => item.Price >= 200_000_000m);
        Assert.Contains(seenProperties, item => item.Area <= 45m);
        Assert.Contains(seenProperties, item => item.Area >= 160m);
        Assert.Contains(seenProperties, item => item.Rooms <= 2m);
        Assert.Contains(seenProperties, item => item.Rooms >= 5m);
    }

    private static PublicLandingSnapshot VariedSnapshot(int seed)
    {
        var snapshot = new PublicLandingSnapshot(new Random(seed));
        for (var index = 0; index < 32; index++)
        {
            var search = SearchAt("city:Debrecen"); search.MaxPrice = 10_000_000m + index * 5_000_000m;
            search.MaxArea = 30m + index * 6m; search.MaxRooms = 1m + index % 7;
            var property = PropertyAt("city:Debrecen"); property.Price = search.MaxPrice.Value;
            property.Area = search.MaxArea.Value; property.Rooms = search.MaxRooms.Value;
            snapshot.Add(search, index % 2 == 0 ? AccountTypes.Private : AccountTypes.Agent);
            snapshot.Add(property, AccountTypes.Private);
        }
        return snapshot;
    }

    [Fact]
    public void EveryRefreshChangesMembershipWithinTheSameCachedCandidateSnapshot()
    {
        var snapshot = VariedSnapshot(42);
        string? previousSearches = null, previousProperties = null;
        for (var refresh = 0; refresh < 30; refresh++)
        {
            var response = snapshot.Response(RegionCatalog.Get("HU321"));
            var searches = string.Join("|", response.Searches.Select(item => item.MaxPrice).Order());
            var properties = string.Join("|", response.Properties.Select(item => item.Price).Order());
            Assert.NotEqual(previousSearches, searches); Assert.NotEqual(previousProperties, properties);
            Assert.Equal(8, response.Searches.Select(item => item.MaxPrice).Distinct().Count());
            Assert.Equal(4, response.Properties.Select(item => item.Price).Distinct().Count());
            Assert.Equal(Enumerable.Range(1, 8).Select(index => "search-" + index), response.Searches.Select(item => item.Key));
            Assert.Equal(Enumerable.Range(1, 4).Select(index => "property-" + index), response.Properties.Select(item => item.Key));
            previousSearches = searches; previousProperties = properties;
        }
    }

    [Fact]
    public void SeededSelectionAndConcurrentResponsesRemainValidWithoutMutatingCachedLocations()
    {
        var first = VariedSnapshot(99); var second = VariedSnapshot(99);
        for (var refresh = 0; refresh < 5; refresh++)
        {
            var a = first.Response(RegionCatalog.Get("HU321")); var b = second.Response(RegionCatalog.Get("HU321"));
            Assert.Equal(a.Searches.Select(item => item.MaxPrice), b.Searches.Select(item => item.MaxPrice));
            Assert.Equal(a.Properties.Select(item => item.Price), b.Properties.Select(item => item.Price));
        }
        var original = first.Response(RegionCatalog.Get("HU321"));
        foreach (var item in original.Searches) item.Locations[0] = "Corrupted client array";
        var responses = new System.Collections.Concurrent.ConcurrentBag<PublicLandingResponse>();
        Parallel.For(0, 32, _ => responses.Add(first.Response(RegionCatalog.Get("HU321"))));
        Assert.Equal(32, responses.Count);
        foreach (var response in responses)
        {
            Assert.Equal(8, response.Searches.Length); Assert.Equal(4, response.Properties.Length);
            Assert.All(response.Searches, item => Assert.Equal("Debrecen", Assert.Single(item.Locations)));
            Assert.All(response.Properties, item => Assert.Equal("Debrecen", item.Location));
            Assert.Equal(8, response.Searches.Select(item => item.MaxPrice).Distinct().Count());
            Assert.Equal(4, response.Properties.Select(item => item.Price).Distinct().Count());
        }
    }

}
