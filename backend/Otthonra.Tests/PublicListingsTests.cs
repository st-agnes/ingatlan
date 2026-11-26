using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicListingsTests
{
    private static JsonElement Json(object value) => JsonSerializer.SerializeToElement(value, new JsonSerializerOptions(JsonSerializerDefaults.Web) { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
    private static Property Property() => new() {
        Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Type = "Lakás", Title = "Világos otthon a park mellett",
        City = "Debrecen", LocationId = "city:Debrecen", Street = "Példa utca", HouseNumber = "12/A",
        Address = "Példa utca 12/A", Price = 48_000_000m, Area = 65m, Rooms = 2.5m, WholeRooms = 2, HalfRooms = 1,
        Description = "Világos szobák, tágas konyha és rendezett környék.", Latitude = 47.5123456789, Longitude = 21.6123456789,
        GeocodingProvider = "secret-provider", GeocodingPlaceId = "secret-place", GeocodingQuality = "secret-quality",
        CreationRequestId = Guid.NewGuid(), CreationRequestHash = "private-receipt-hash"
    };
    private static SearchRequest Search() => new() {
        Id = Guid.NewGuid(), OwnerId = Guid.NewGuid(), Title = "Csendes lakást keresünk", Type = "Lakás", City = "Debrecen",
        LocationIdsJson = "[\"city:Debrecen\"]", MaxPrice = 60_000_000m, MinArea = 55m, MinRooms = 2.5m,
        ConditionsJson = "[\"Jó\",\"Új/felújított\"]", BuildingsJson = "[\"Tégla\"]", HeatingTypesJson = "[\"Gázcirkó\"]",
        FloorsJson = "[0.5,9]", AtticPreference = "exclude", MinEnergyRating = "C", Balcony = true, AirConditioning = true,
        MoveIn = "3 hónapon belül", Financing = "Saját megtakarítás", Description = "Nagy konyhát szeretnénk.",
        CreationRequestId = Guid.NewGuid(), CreationRequestHash = "private-search-receipt"
    };

    [Theory]
    [InlineData("property")]
    [InlineData("search")]
    public void OpaquePublicKeysAreValidatedWithoutAcceptingSourceIdsOrAnotherKind(string kind)
    {
        var id = Guid.NewGuid(); var key = PublicLanding.SourceKey(kind, id);
        Assert.True(PublicListings.ValidKey(kind, key));
        Assert.False(PublicListings.ValidKey(kind == "search" ? "property" : "search", key));
        foreach (var invalid in new[] { "", id.ToString(), id.ToString("N"), key.ToUpperInvariant(), key + "x", key[..^1], key.Replace('a','z') + "z" })
            Assert.False(PublicListings.ValidKey(kind, invalid));
        Assert.False(PublicListings.ValidKey(kind, null));
        Assert.False(PublicListings.ValidKey("users", key));
    }

    [Theory]
    [InlineData(true, true, "", "")]
    [InlineData(true, false, "", "")]
    [InlineData(false, true, "Példa utca", "")]
    [InlineData(false, false, "Példa utca", "12/A")]
    public void PublicPropertyExposesExactlyTheAddressPartsTheOwnerAllows(bool hideStreet, bool hideHouseNumber, string street, string number)
    {
        var property = Property(); property.HideStreet = hideStreet; property.HideHouseNumber = hideHouseNumber;
        var detail = PublicListings.Property(property, AccountTypes.Agent, "Kovács Anna")!;
        var root = Json(detail); var listing = root.GetProperty("listing");
        Assert.Equal(street, listing.GetProperty("street").GetString());
        Assert.Equal(number, listing.GetProperty("houseNumber").GetString());
        Assert.Equal(string.Join(" ", new[] { street, number }.Where(value => value.Length > 0)), listing.GetProperty("address").GetString());
        Assert.Equal(hideStreet || hideHouseNumber, listing.GetProperty("hideHouseNumber").GetBoolean());
        Assert.Equal("Anna", root.GetProperty("ownerFirstName").GetString());
        Assert.Equal("agent", root.GetProperty("ownerAccountType").GetString());
        var json = root.GetRawText();
        foreach (var secret in new[] { property.OwnerId.ToString(), property.Id.ToString(), "Kovács Anna", "47.5123456789", "21.6123456789", "secret-provider", "secret-place", "secret-quality", "private-receipt-hash" })
            Assert.DoesNotContain(secret, json);
        foreach (var forbidden in new[] { "ownerId", "id", "addressDetails", "latitude", "longitude", "provider", "email", "phone", "creationRequestHash", "creationRequestId" })
            Assert.DoesNotContain(forbidden, listing.EnumerateObject().Select(value => value.Name));
        Assert.Equal("#listing/property/" + detail.SourceKey, detail.Href);
        Assert.Equal("#listing/property/" + detail.SourceKey, PublicLanding.PropertyTeaser(property, AccountTypes.Private)!.Value.Teaser.Href);
    }

    [Fact]
    public void PublicPropertyIncludesAllSafeImagesAndRetainsFalseVersusUnknownAmenities()
    {
        var property = Property();
        property.ImagesJson = "[\"https://images.example.test/one.jpg\",\"https://images.example.test/two.jpg\",\"https://images.example.test/one.jpg\",\"http://images.example.test/no.jpg\",\"https://user:password@images.example.test/private.jpg\"]";
        property.Balcony = null; property.AirConditioning = false; property.PrivateGarden = true;
        property.Insulated = false; property.SolarPanels = null; property.IsAttic = false;
        property.Floor = .5m; property.BuildingFloors = 4;
        property.EnergyRating = "A+"; property.EnergyRatingScheme = "2023";
        var detail = PublicListings.Property(property, AccountTypes.Private)!;
        var listing = Json(detail).GetProperty("listing");
        Assert.Equal(2, listing.GetProperty("images").GetArrayLength());
        Assert.Equal(JsonValueKind.Null, listing.GetProperty("balcony").ValueKind);
        Assert.False(listing.GetProperty("airConditioning").GetBoolean());
        Assert.True(listing.GetProperty("privateGarden").GetBoolean());
        Assert.False(listing.GetProperty("insulated").GetBoolean());
        Assert.Equal(JsonValueKind.Null, listing.GetProperty("solarPanels").ValueKind);
        Assert.False(listing.GetProperty("isAttic").GetBoolean());
        Assert.Equal(.5m, listing.GetProperty("floor").GetDecimal());
        Assert.Equal("A+", listing.GetProperty("energyRating").GetString());
        Assert.Equal("2023", listing.GetProperty("energyRatingScheme").GetString());
        Assert.Equal(property.Description, listing.GetProperty("description").GetString());
        Assert.DoesNotContain("secondaryHeatingType", listing.EnumerateObject().Select(value => value.Name));
        Assert.Equal("https://images.example.test/one.jpg", PublicLanding.PropertyTeaser(property, AccountTypes.Private)!.Value.Teaser.Image);
    }

    [Fact]
    public void SearchCloneContainsEveryCriterionWithoutPrivateIdentityOrForcedBounds()
    {
        var search = Search(); var detail = PublicListings.Search(search, AccountTypes.Private, "Nagy Péter")!;
        var root = Json(detail); var clone = root.GetProperty("clonePrefill");
        Assert.Equal(JsonValueKind.Null, clone.GetProperty("minPrice").ValueKind);
        Assert.Equal(60_000_000m, clone.GetProperty("maxPrice").GetDecimal());
        Assert.Equal(55m, clone.GetProperty("minArea").GetDecimal());
        Assert.Equal(JsonValueKind.Null, clone.GetProperty("maxArea").ValueKind);
        Assert.Equal(2.5m, clone.GetProperty("minRooms").GetDecimal());
        Assert.Equal(JsonValueKind.Null, clone.GetProperty("maxRooms").ValueKind);
        Assert.Equal(new[] { .5m, 8m }, clone.GetProperty("floors").EnumerateArray().Select(value => value.GetDecimal()));
        Assert.Equal(new[] { "Gázkazán / cirkó" }, clone.GetProperty("heatingTypes").EnumerateArray().Select(value => value.GetString()));
        Assert.Equal("exclude", clone.GetProperty("atticPreference").GetString());
        Assert.Equal("C", clone.GetProperty("minEnergyRating").GetString());
        Assert.Equal(search.MoveIn, clone.GetProperty("moveIn").GetString());
        Assert.Equal(search.Financing, clone.GetProperty("financing").GetString());
        Assert.Equal(search.Description, clone.GetProperty("description").GetString());
        Assert.Equal(search.Description, root.GetProperty("listing").GetProperty("description").GetString());
        Assert.DoesNotContain("title", clone.EnumerateObject().Select(value => value.Name));
        foreach (var secret in new[] { search.Id.ToString(), search.OwnerId.ToString(), "Nagy Péter", "private-search-receipt" })
            Assert.DoesNotContain(secret, root.GetRawText());
    }

    [Fact]
    public void ArchivedAndInvalidListingsHaveNoPublicDetail()
    {
        var property = Property(); property.Archived = true;
        Assert.Null(PublicListings.Property(property, AccountTypes.Private));
        property.Archived = false; property.LocationId = "city:unknown";
        Assert.Null(PublicListings.Property(property, AccountTypes.Private));
        Assert.Null(PublicLanding.PropertyTeaser(property, AccountTypes.Private));
        property.LocationId = "";
        Assert.NotNull(PublicListings.Property(property, AccountTypes.Private)); // A genuinely old blank identity may use its known city.
        var search = Search(); search.Archived = true;
        Assert.Null(PublicListings.Search(search, AccountTypes.Private));
        search.Archived = false; search.LocationIdsJson = "{broken";
        Assert.Null(PublicListings.Search(search, AccountTypes.Private));
    }

    [Theory]
    [InlineData("Írj ide: peter kukac pelda pont hu")]
    [InlineData("Hívj a nulla hat húsz egy kettő három négy öt hat hét számon")]
    [InlineData("Telefon: +36 20 123 4567")]
    public void LegacyContactDetailsCannotBecomeAnonymousDescriptionsOrCloneSeeds(string contact)
    {
        var property = Property(); property.Description = contact; property.Title = contact;
        var search = Search(); search.Description = contact; search.Title = contact;
        var publicProperty = Json(PublicListings.Property(property, AccountTypes.Private)!);
        var publicSearch = Json(PublicListings.Search(search, AccountTypes.Private)!);
        Assert.Equal("", publicProperty.GetProperty("listing").GetProperty("description").GetString());
        Assert.Equal("", publicSearch.GetProperty("listing").GetProperty("description").GetString());
        Assert.Equal("", publicSearch.GetProperty("clonePrefill").GetProperty("description").GetString());
        Assert.NotEqual(contact, publicProperty.GetProperty("title").GetString());
        Assert.NotEqual(contact, publicSearch.GetProperty("title").GetString());
    }

    [Fact]
    public void MalformedOptionalLegacyJsonAndUnknownEnergySchemesAreSafeToRead()
    {
        var property = Property(); property.NeighborhoodIdsJson = "{broken"; property.ParkingTypesJson = "{broken"; property.ImagesJson = "{broken";
        property.EnergyRating = "AA"; property.EnergyRatingScheme = "old";
        var root = Json(PublicListings.Property(property, AccountTypes.Private)!);
        Assert.Equal("AA", root.GetProperty("listing").GetProperty("energyRating").GetString());
        Assert.Equal("", root.GetProperty("listing").GetProperty("energyRatingScheme").GetString());
        Assert.Equal("", root.GetProperty("prefill").GetProperty("energyRating").GetString());
        Assert.Empty(root.GetProperty("listing").GetProperty("images").EnumerateArray());
        var search = Search(); search.MinEnergyRating = "secret@example.test"; search.AtticPreference = "secret@example.test";
        root = Json(PublicListings.Search(search, AccountTypes.Private)!);
        Assert.Equal("", root.GetProperty("prefill").GetProperty("minEnergyRating").GetString());
        Assert.Equal("", root.GetProperty("prefill").GetProperty("atticPreference").GetString());
    }
}
