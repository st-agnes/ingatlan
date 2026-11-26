using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class ListingProfileOptionsTests
{
    [Theory]
    [InlineData(null, null, 0, 50)]
    [InlineData(0, 1, 0, 1)]
    [InlineData(1_000_000, 50, 1_000_000, 50)]
    public void PagesAreBoundedWithoutClampingOrSkippingChoices(int? offset, int? limit, int expectedOffset, int expectedLimit)
    {
        Assert.Equal((expectedOffset, expectedLimit), ListingProfileOptions.Page(offset, limit));
    }

    [Theory]
    [InlineData(-1, 50)]
    [InlineData(1_000_001, 50)]
    [InlineData(0, 0)]
    [InlineData(0, 51)]
    public void InvalidPagesAreRejected(int offset, int limit)
    {
        Assert.Equal(400, Assert.Throws<ApiException>(() => ListingProfileOptions.Page(offset, limit)).Status);
    }

    [Fact]
    public void OptionsUseTheAppropriateBudgetPerspectiveAndExposeOnlyOwnedSummaryFields()
    {
        var property = new Property { Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Title = "Tágas lakás",
            Type = "Lakás", LocationId = "city:Debrecen", City = "Debrecen", Price = 75_000_000m,
            Area = 60m, Rooms = 2m, Street = "PRIVATE STREET", HouseNumber = "42",
            Latitude = 47.53, Longitude = 21.62, GeocodingPlaceId = "PRIVATE PLACE" };
        var search = new SearchRequest { Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Title = "Saját keresés",
            Type = "Lakás", City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]",
            MaxPrice = 80_000_000m, PublicMaxPrice = 70_000_000m };
        var buyer = ListingProfileOptions.Option(PublicListingContext.ActiveSummary(null, search)!,
            MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search)), "search", search.Id);
        var seller = ListingProfileOptions.Option(PublicListingContext.ActiveSummary(property, null)!,
            MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search, sellerPerspective: true)), "property", null);
        Assert.Equal(100, buyer.Score); Assert.True(buyer.IsExact); Assert.True(buyer.IsActive);
        Assert.True(seller.Compatible); Assert.False(seller.IsExact); Assert.InRange(seller.Score, 1, 99); Assert.False(seller.IsActive);
        Assert.Equal(search.MaxPrice, buyer.Profile.MaxPrice);
        var json = JsonSerializer.Serialize(seller, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        foreach (var field in new[] { "street", "houseNumber", "latitude", "longitude", "addressDetails", "ownerId", "email", "phone", "provider" }) Assert.DoesNotContain("\"" + field + "\"", json);
        Assert.DoesNotContain("PRIVATE", json); Assert.DoesNotContain("80000000", json);
    }

    [Fact]
    public void DifferentPropertyTypesRemainVisibleAsZeroPercentWithoutEnablingAnExactPair()
    {
        var property = new Property { Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Type = "Ház", LocationId = "city:Debrecen", City = "Debrecen", Price = 75_000_000m, Area = 60m, Rooms = 2m };
        var search = new SearchRequest { Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Type = "Lakás", City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]" };
        var option = ListingProfileOptions.Option(PublicListingContext.ActiveSummary(null, search)!,
            MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search)), "property", property.Id);
        Assert.Equal(0, option.Score); Assert.False(option.IsExact); Assert.False(option.Compatible); Assert.False(option.IsActive);
    }
}
