using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicListingContextTests
{
    private static JsonElement Json(object value) => JsonSerializer.SerializeToElement(value, new JsonSerializerOptions(JsonSerializerDefaults.Web));
    private static Property Home() => new() {
        Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Title = "Világos otthon", City = "Budapest", District = "V.",
        LocationId = "district:Budapest:5", Street = "Nádor utca", HouseNumber = "12/A", Address = "PRIVATE LEGACY ADDRESS",
        Latitude = 47.123456789, Longitude = 19.987654321, GeocodingPlaceId = "PRIVATE PLACE ID", GeocodingProvider = "PRIVATE PROVIDER",
        Type = "Lakás", Price = 75_000_000m, Area = 50m, Rooms = 2m
    };

    [Theory]
    [InlineData(true, true)]
    [InlineData(true, false)]
    [InlineData(false, true)]
    public void HiddenAddressNeverProvidesExactMapLink(bool street, bool house)
    {
        var property = Home(); property.HideStreet = street; property.HideHouseNumber = house;
        Assert.Null(PublicListingContext.PublicAddressUrl(property));
    }

    [Fact]
    public void ExactMapUsesOnlyThePublicHumanAddressWithAnEncodedGoogleSearch()
    {
        var property = Home(); property.HideStreet = false; property.HideHouseNumber = false;
        var url = PublicListingContext.PublicAddressUrl(property)!;
        Assert.StartsWith("https://www.google.com/maps/search/?api=1&query=", url);
        var query = Uri.UnescapeDataString(url[(url.IndexOf("query=", StringComparison.Ordinal) + 6)..]);
        Assert.Equal("Budapest V. kerület, Nádor utca 12/A, Magyarország", query);
        foreach (var secret in new[] { property.Id.ToString(), property.OwnerId.ToString(), property.Address, "47.123456789", "19.987654321", property.GeocodingPlaceId, property.GeocodingProvider }) Assert.DoesNotContain(secret, url);
        property.HouseNumber = ""; Assert.Null(PublicListingContext.PublicAddressUrl(property));
    }

    [Fact]
    public void SearchMapKeepsAllNonStreetChoicesWithoutPublishingSearchOrUserIdentity()
    {
        var search = new SearchRequest { City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\",\"area:Budapest\",\"district:Budapest:5\"]", MaxPrice = 98_765_432m, PublicMaxPrice = 60_000_000m };
        var map = PublicListingContext.SearchMap(search);
        Assert.True(map.Available);
        Assert.Equal(new[] { "city:Debrecen", "area:Budapest", "district:Budapest:5" }, map.LocationIds);
        var json = Json(map).GetRawText();
        foreach (var secret in new[] { search.Id.ToString(), search.OwnerId.ToString(), "98765432", "60000000", "latitude", "longitude", "provider", "street:" }) Assert.DoesNotContain(secret, json);
        search.LocationIdsJson = "[\"unknown:location\"]";
        Assert.False(PublicListingContext.SearchMap(search).Available);
    }

    [Fact]
    public void CompactActiveSummaryIncludesOnlyTheOwnersBudgetAndNoGeocodingOrContacts()
    {
        var search = new SearchRequest { Title = "Otthont keresek", City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]", MaxPrice = 80_000_000m, PublicMaxPrice = 70_000_000m, MinArea = 50m };
        var summary = PublicListingContext.ActiveSummary(null, search)!;
        Assert.Equal(search.MaxPrice, summary.MaxPrice);
        Assert.Equal(search.Id, summary.Id); Assert.Equal("search", summary.Kind);
        Assert.DoesNotContain("publicMaxPrice", Json(summary).GetRawText());
        var propertySummary = Json(PublicListingContext.ActiveSummary(Home(), null)!);
        foreach (var field in new[] { "latitude", "longitude", "street", "houseNumber", "address", "ownerId", "email", "phone", "addressDetails", "provider" }) Assert.False(propertySummary.TryGetProperty(field, out _));
        Assert.Null(PublicListingContext.ActiveSummary(null, null));
    }

    [Fact]
    public void AuthenticatedEntityDtosCarryStablePublicKeysForOwnersAndCounterparties()
    {
        var property = Home(); var search = new SearchRequest { City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]" };
        foreach (var own in new[] { false, true })
        {
            Assert.Equal(PublicLanding.SourceKey("property", property.Id), Json(Dto.Property(property, own)).GetProperty("publicListingKey").GetString());
            Assert.Equal(PublicLanding.SourceKey("search", search.Id), Json(Dto.Search(search, own: own)).GetProperty("publicListingKey").GetString());
        }
    }
}
