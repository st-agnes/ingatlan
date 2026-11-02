using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class LocationTests
{
    private static readonly Guid Seller = Guid.Parse("44c4b3d1-1dde-48e4-ac41-f54fa08a1901");
    private static readonly Guid Buyer = Guid.Parse("54d6b5e2-66d1-4546-b0b5-c9195a232502");

    private static Property PropertyAt(string locationId, string city, string district = "") => new()
    {
        OwnerId = Seller, LocationId = locationId, City = city, District = district,
        Type = "Lakás", Price = 75_000_000m, Area = 62m, Rooms = 3m
    };

    private static SearchRequest SearchAt(params string[] locationIds) => new()
    {
        OwnerId = Buyer, LocationIdsJson = JsonSerializer.Serialize(locationIds),
        Type = "Lakás", MinPrice = null, MaxPrice = 90_000_000m,
        MinArea = 40m, MaxArea = null, MinRooms = 2m, MaxRooms = null
    };

    private static PropertyInput PropertyInputAt(string id, string type = "Lakás", decimal? lotArea = null) => new(
        "Világos otthon", "Debrecen", null, null, null, "Egy szerethető otthon.",
        type, 75_000_000m, 62m, 3m, 1, "Jó állapotú", "Tégla", false, false, [],
        LocationId: id, LotArea: lotArea);

    private static SearchInput SearchInputAt(string[] ids) => new(
        "Közös otthonunk", "Debrecen", null, "Otthont keresünk.", "Lakás",
        null, 90_000_000m, 40m, null, 2m, null, false, false, "Rugalmas", null,
        LocationIds: ids);

    [Fact]
    public void MultipleTownsAreAlternativesAndDoNotBroadenToOtherTowns()
    {
        var search = SearchAt("city:Debrecen", "city:Hajdúszoboszló", "city:Hajdúsámson");
        Assert.True(Rules.Compatible(PropertyAt("city:Debrecen", "Debrecen"), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Hajdúszoboszló", "Hajdúszoboszló"), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Hajdúsámson", "Hajdúsámson"), search));
        Assert.False(Rules.Compatible(PropertyAt("city:Szeged", "Szeged"), search));
    }

    [Fact]
    public void MixedBudapestDistrictsAndTownsMatchOnlyTheirOwnLocations()
    {
        var search = SearchAt("district:Budapest:5", "district:Budapest:9", "city:Solymár", "city:Pilisvörösvár");
        Assert.True(Rules.Compatible(PropertyAt("district:Budapest:5", "Budapest", "V."), search));
        Assert.True(Rules.Compatible(PropertyAt("district:Budapest:9", "Budapest", "IX."), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Solymár", "Solymár"), search));
        Assert.True(Rules.Compatible(PropertyAt("city:Pilisvörösvár", "Pilisvörösvár"), search));
        Assert.False(Rules.Compatible(PropertyAt("district:Budapest:13", "Budapest", "XIII."), search));
        Assert.False(Rules.Compatible(PropertyAt("city:Debrecen", "Debrecen"), search));
        Assert.False(Rules.Compatible(PropertyAt("city:Budapest", "Budapest"), search));
    }

    [Fact]
    public void WholeBudapestIncludesDistrictsButASelectedDistrictDoesNotIncludeTheWholeCity()
    {
        var district = PropertyAt("district:Budapest:23", "Budapest", "XXIII.");
        Assert.True(Rules.Compatible(district, SearchAt("city:Budapest")));
        Assert.False(Rules.Compatible(district, SearchAt("district:Budapest:5")));
        Assert.False(Rules.Compatible(PropertyAt("city:Budapest", "Budapest"), SearchAt("district:Budapest:5")));
    }

    [Fact]
    public void MissingOptionalBoundsRemainUnboundedRatherThanBecomingZeroOrArtificialLimits()
    {
        var property = PropertyAt("city:Debrecen", "Debrecen");
        property.Price = 1_000_000m;
        property.Area = 750m;
        property.Rooms = 25m;
        var search = SearchAt("city:Debrecen");
        Assert.True(Rules.Compatible(property, search));
        var input = SearchInputAt(["city:Debrecen"]);
        Rules.Apply(search, input);
        Assert.Null(search.MinPrice); Assert.Null(search.MaxArea); Assert.Null(search.MaxRooms);
        Assert.True(Rules.Compatible(property, search));
    }

    [Fact]
    public void UnknownAndEmptyCanonicalSelectionsAreRejectedRatherThanSavedAsTypos()
    {
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInputAt("city:Debrceen")));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInputAt(["city:Debrceen"])));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), SearchInputAt([])));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInputAt("city:Debrecen") with { LocationId = null, City = "Debrceen" }));
    }

    [Fact]
    public void HousePlotAreaIsPreservedAndValidatedButClearedForApartments()
    {
        var property = new Property();
        Rules.Apply(property, PropertyInputAt("city:Debrecen", "Ház", 1240m));
        Assert.Equal(1240m, property.LotArea);
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property)));
        Assert.Equal(1240m, dto.RootElement.EnumerateObject().Single(value => value.Name.Equals("lotArea", StringComparison.OrdinalIgnoreCase)).Value.GetDecimal());
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInputAt("city:Debrecen", "Ház", -1m)));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), PropertyInputAt("city:Debrecen", "Ház", 0m)));
        Rules.Apply(property, PropertyInputAt("city:Debrecen", "Lakás", 1240m));
        Assert.Null(property.LotArea);
        Rules.Apply(property, PropertyInputAt("city:Debrecen", "Ház", null));
        Assert.Null(property.LotArea);
    }

    [Fact]
    public void LegacyBudapestDistrictDataKeepsItsMeaningWithoutCanonicalIds()
    {
        var property = PropertyAt("", "Budapest", "IX.");
        var search = new SearchRequest { OwnerId = Buyer, City = "budapest", DistrictsJson = "[\"V.\",\"IX.\"]", Type = "Lakás" };
        Assert.True(Rules.Compatible(property, search));
        property.District = "XIII.";
        Assert.False(Rules.Compatible(property, search));
    }

    [Fact]
    public void AutocompleteReturnsCanonicalAccentInsensitiveSuggestions()
    {
        Assert.Contains(LocationCatalog.Search("hajduszoboszlo"), value => value.Id == "city:Hajdúszoboszló");
        Assert.Contains(LocationCatalog.Search("Budapest 5"), value => value.Id == "district:Budapest:5");
    }
}
