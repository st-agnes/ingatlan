using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class AreaLocationTests
{
    private static readonly Guid Seller = Guid.Parse("842ce6b9-878a-4cc4-829c-fd214006a806");
    private static readonly Guid Buyer = Guid.Parse("099698d3-bd61-4518-acb2-8b7d57fc7dba");
    private static Property PropertyAt(string id) => new()
    {
        OwnerId = Seller, LocationId = id, City = LocationCatalog.Get(id)?.City ?? "",
        Type = "Lakás", Price = 75_000_000m, Area = 60m, Rooms = 3m
    };
    private static SearchRequest SearchAt(params string[] ids) => new()
    {
        OwnerId = Buyer, LocationIdsJson = JsonSerializer.Serialize(ids), Type = "Lakás", MaxPrice = 90_000_000m
    };
    private static SearchInput InputAt(params string[] ids) => new(
        "Környékbeli otthont keresünk", "Debrecen", null, "Világos lakást keresünk.", "Lakás",
        null, 90_000_000m, null, null, null, null, false, false, null, null, LocationIds: ids);
    private static JsonDocument Data()
    {
        using var stream = typeof(LocationCatalog).Assembly.GetManifestResourceStream("Otthonra.Api.Agglomerations.json");
        Assert.NotNull(stream);
        return JsonDocument.Parse(stream!);
    }

    [Theory]
    [InlineData("Budapest", 81)]
    [InlineData("Debrecen", 13)]
    public void CityAreasExposeTheirCountAndIncludeTheCenterExactlyOnce(string city, int count)
    {
        var location = LocationCatalog.Get("area:" + city);
        Assert.NotNull(location);
        Assert.Equal("area", location.Kind);
        Assert.Null(location.District);
        Assert.Equal(count, location.SettlementCount);
        Assert.Equal($"{city} és környéke ({count} település)", location.Label);
        Assert.True(Rules.Compatible(PropertyAt("city:" + city), SearchAt(location.Id)));
        using var data = Data();
        var members = data.RootElement.GetProperty("areas").EnumerateArray()
            .Single(area => area.GetProperty("id").GetString() == location.Id).GetProperty("settlements").EnumerateArray()
            .Select(value => value.GetString()).ToArray();
        Assert.Equal(count, members.Length);
        Assert.Single(members.Where(name => name == city));
    }

    [Fact]
    public void EveryOfficialMemberMatchesItsAreaWithoutBroadeningToAnUnrelatedCity()
    {
        using var data = Data();
        var areas = data.RootElement.GetProperty("areas").EnumerateArray().ToArray();
        Assert.Equal(24, areas.Length);
        foreach (var area in areas)
        {
            var id = area.GetProperty("id").GetString()!;
            var center = area.GetProperty("city").GetString()!;
            var members = area.GetProperty("settlements").EnumerateArray().Select(value => value.GetString()!).ToArray();
            Assert.Equal(members.Length, LocationCatalog.Get(id)!.SettlementCount);
            var search = SearchAt(id);
            foreach (var member in members)
            {
                Assert.NotNull(LocationCatalog.Get("city:" + member));
                Assert.True(Rules.Compatible(PropertyAt("city:" + member), search), $"{member} must be included in {id}.");
            }
            var outsider = LocationCatalog.All.First(place => place.Kind == "city" && !members.Contains(place.City));
            Assert.False(Rules.Compatible(PropertyAt(outsider.Id), search), $"{outsider.City} must remain outside {center}.");
        }
    }

    [Fact]
    public void BudapestAreaCoversAllDistrictsAndItsSurroundingsButCountsTheCapitalAsOneSettlement()
    {
        var search = SearchAt("area:Budapest");
        for (var number = 1; number <= 23; number++)
            Assert.True(Rules.Compatible(PropertyAt("district:Budapest:" + number), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Solymár"), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Pilisvörösvár"), search));
        Assert.False(Rules.Compatible(PropertyAt("city:Debrecen"), search));
        Assert.Equal(81, LocationCatalog.Get("area:Budapest")!.SettlementCount);
        Assert.Null(LocationCatalog.Get("city:Budapest")!.SettlementCount);
    }

    [Fact]
    public void AnAreaRemainsOneStoredSelectionEvenWhenItContainsMoreThanFiftySettlements()
    {
        var search = new SearchRequest { OwnerId = Buyer };
        Rules.Apply(search, InputAt("area:Budapest"));
        Assert.Equal(new[] { "area:Budapest" }, Dto.Strings(search.LocationIdsJson));
        Assert.Single(LocationCatalog.ForSearch(search));
        var accepted = LocationCatalog.ResolveSearchInput(
            new[] { "area:Budapest" }.Concat(LocationCatalog.All.Where(place => place.Kind == "city").Take(49).Select(place => place.Id)).ToArray(), null, null);
        Assert.Equal(50, accepted.Length);
        Assert.Throws<ApiException>(() => LocationCatalog.ResolveSearchInput(Enumerable.Repeat("area:Budapest", 51).ToArray(), null, null));
    }

    [Fact]
    public void GroupsAndExactTownsAreAlternativesWhileOtherSearchFiltersStillApply()
    {
        var search = SearchAt("area:Budapest", "city:Debrecen");
        Assert.True(Rules.Compatible(PropertyAt("city:Solymár"), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Debrecen"), search));
        Assert.False(Rules.Compatible(PropertyAt("city:Szeged"), search));
        var property = PropertyAt("city:Solymár");
        search.MaxPrice = 70_000_000m;
        Assert.False(Rules.Compatible(property, search));
        search.MaxPrice = 90_000_000m; search.ViewsJson = "[\"Panorámás\"]";
        Assert.False(Rules.Compatible(property, search));
        property.View = "Panorámás";
        Assert.True(Rules.Compatible(property, search));
    }

    [Fact]
    public void AreaIdsAreRejectedForPropertiesIncludingPersistedValuesWithAValidCenterFallback()
    {
        var error = Assert.Throws<ApiException>(() => LocationCatalog.ResolvePropertyInput("area:Debrecen", "Debrecen", null));
        Assert.Equal(400, error.Status);
        Assert.Throws<ApiException>(() => LocationCatalog.ResolvePropertyInput("area:Missing", "Debrecen", null));
        Assert.Null(LocationCatalog.ForProperty(new Property { LocationId = "area:Debrecen", City = "Debrecen" }));
        Assert.Null(LocationCatalog.ForProperty(new Property { LocationId = "area:Missing", City = "Debrecen" }));
        Assert.False(Rules.Compatible(PropertyAt("area:Debrecen"), SearchAt("city:Debrecen")));
        Assert.False(Rules.Compatible(PropertyAt("area:Debrecen"), SearchAt("area:Debrecen")));
    }

    [Fact]
    public void SearchSuggestionsShowTheAreaNearItsCenterButPropertySuggestionsExcludeIt()
    {
        var search = LocationCatalog.Search("Budapest", 8);
        Assert.Equal("city:Budapest", search[0].Id);
        Assert.Equal("area:Budapest", search[1].Id);
        Assert.Contains(LocationCatalog.Search("debrecen kornyeke"), place => place.Id == "area:Debrecen");
        Assert.Contains(LocationCatalog.Search("debrecen agglomeracio"), place => place.Id == "area:Debrecen");
        Assert.Equal("area:Debrecen", Assert.Single(LocationCatalog.Search("Debrecen és környéke (13 település)")).Id);
        Assert.DoesNotContain(LocationCatalog.Search("Budapest", 25, "property"), place => place.Kind == "area");
        Assert.DoesNotContain(LocationCatalog.Search("Debrecen", 25, "property"), place => place.Kind == "area");
        Assert.Equal("district:Budapest:5", LocationCatalog.Search("Budapest 5")[0].Id);
        Assert.DoesNotContain(LocationCatalog.Search("81"), place => place.Kind == "area");
        Assert.DoesNotContain(LocationCatalog.Search("Budapest 8"), place => place.Kind == "area");
        Assert.Throws<ApiException>(() => LocationCatalog.Search("Debrecen", 8, "other"));
    }

    [Fact]
    public void LegacyCityLookupsNeverResolveAreaLabelsAndExactSelectionsDoNotBroaden()
    {
        Assert.Equal("city:Debrecen", Assert.Single(LocationCatalog.ResolveLegacy("Debrecen")).Id);
        Assert.Empty(LocationCatalog.ResolveLegacy("Debrecen és környéke (13 település)"));
        Assert.False(Rules.Compatible(PropertyAt("city:Solymár"), SearchAt("city:Budapest")));
        Assert.True(Rules.Compatible(new Property { OwnerId = Seller, City = "Budapest", District = "XIII.", Type = "Lakás", Price = 50_000_000m, Area = 50m, Rooms = 2m }, SearchAt("area:Budapest")));
        Assert.Empty(LocationCatalog.ForSearch(new SearchRequest { City = "Debrecen", LocationIdsJson = "[\"area:Debrecen\",\"area:Missing\"]" }));
    }

    [Fact]
    public void SearchDtoPreservesAreaSelectionMetadataRatherThanExpandingMembers()
    {
        var search = new SearchRequest();
        Rules.Apply(search, InputAt("area:Debrecen", "city:Solymár"));
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Search(search)));
        var root = dto.RootElement;
        Assert.Equal(new[] { "area:Debrecen", "city:Solymár" }, root.GetProperty("locationIds").EnumerateArray().Select(x => x.GetString()).ToArray());
        var area = root.GetProperty("locations")[0];
        Assert.Equal("area:Debrecen", area.GetProperty("Id").GetString());
        Assert.Equal("area", area.GetProperty("Kind").GetString());
        Assert.Equal(13, area.GetProperty("SettlementCount").GetInt32());
        Assert.Equal("Debrecen és környéke (13 település)", area.GetProperty("Label").GetString());
    }
}
