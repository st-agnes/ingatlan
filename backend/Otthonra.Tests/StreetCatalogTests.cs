using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class StreetCatalogTests
{
    private static readonly string[] Romans = ["I.", "II.", "III.", "IV.", "V.", "VI.", "VII.", "VIII.", "IX.", "X.", "XI.", "XII.", "XIII.", "XIV.", "XV.", "XVI.", "XVII.", "XVIII.", "XIX.", "XX.", "XXI.", "XXII.", "XXIII."];

    private static Property PropertyAt(PostalStreet street) => new()
    {
        City = street.City,
        District = street.District ?? "",
        LocationId = street.District is null ? "city:" + street.City : "district:Budapest:" + (Array.IndexOf(Romans, street.District) + 1),
        Street = street.StreetName,
        HouseNumber = "12/A",
        PostalCode = street.PostalCodes.FirstOrDefault() ?? "",
        Address = street.StreetName + " 12/A",
        Latitude = 47.497913,
        Longitude = 19.040236,
        GeocodedAt = new DateTime(2026, 11, 18, 12, 0, 0, DateTimeKind.Utc),
        GeocodingProvider = "google",
        GeocodingPlaceId = "owner-specific-existing-place",
        GeocodingQuality = "ROOFTOP",
        GeocodingAddressKey = "existing-address-fingerprint",
        NeighborhoodIdsJson = "[\"existing-membership\"]"
    };

    private static PostalStreet UniqueTownStreet(string? type = null) => StreetCatalog.All
        .Where(street => street.City != "Budapest" && (type is null || Rules.Normalize(street.Type) == type))
        .GroupBy(street => (street.City, Name: Rules.Normalize(street.StreetName)))
        .First(group => group.Count() == 1).Single();

    [Fact]
    public void RuntimeContainsRealNationwideMetadataWithStableLookupIds()
    {
        Assert.True(StreetCatalog.All.Count > 100_000);
        Assert.Contains(StreetCatalog.All, street => street.City == "Szeged");
        Assert.Contains(StreetCatalog.All, street => street.City == "Debrecen");
        Assert.Contains(StreetCatalog.All, street => street.City == "Budapest" && street.District == "V.");
        Assert.Equal(StreetCatalog.All.Count, StreetCatalog.All.Select(street => street.Id).Distinct(StringComparer.Ordinal).Count());
        foreach (var street in StreetCatalog.All)
        {
            Assert.Matches("^street:[0-9a-f]{24}$", street.Id);
            Assert.Same(street, StreetCatalog.Get(street.Id));
            Assert.False(string.IsNullOrWhiteSpace(street.StreetName));
            Assert.False(string.IsNullOrWhiteSpace(street.Label));
            Assert.All(street.PostalCodes, postcode => Assert.Matches("^[0-9]{4}$", postcode));
        }
        Assert.Null(StreetCatalog.Get(null));
        Assert.Null(StreetCatalog.Get("street:not-a-real-id"));
    }

    [Fact]
    public void PickerRecognizesAccentlessStreetThenCityAndCityThenStreet()
    {
        var street = StreetCatalog.All.First(value => value.City == "Szeged" && value.Name.Length is > 8 and < 80
            && Rules.Normalize(value.Name) != value.Name.ToUpperInvariant());
        Assert.Contains(StreetCatalog.Search(Rules.Normalize(street.Name + " " + street.City), 25), value => value.Id == street.Id);
        Assert.Contains(StreetCatalog.Search(Rules.Normalize(street.City + " " + street.Name), 25), value => value.Id == street.Id);
        Assert.DoesNotContain(StreetCatalog.Search("NEVETEZNEMLETEZOKOZTERULET"), value => value.Id == street.Id);
    }

    [Fact]
    public void PickerScopesStreetSuggestionsToCanonicalCityAndDistrict()
    {
        var town = UniqueTownStreet();
        var townItems = StreetCatalog.Search(town.Name, 25, "city:" + town.City);
        Assert.Contains(townItems, value => value.Id == town.Id);
        Assert.All(townItems, value => Assert.Equal(town.City, value.City));

        var district = StreetCatalog.All.First(value => value.City == "Budapest" && value.District == "V." && value.Name.Length > 5);
        var districtItems = StreetCatalog.Search(district.Name, 25, "district:Budapest:5");
        Assert.Contains(districtItems, value => value.Id == district.Id);
        Assert.All(districtItems, value => { Assert.Equal("Budapest", value.City); Assert.Equal("V.", value.District); });
        Assert.Contains(StreetCatalog.Search("5 Budapest " + district.Name, 25), value => value.Id == district.Id);
        Assert.Contains(StreetCatalog.Search("V Budapest " + district.Name, 25), value => value.Id == district.Id);
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.Search("Kossuth", 12, "city:Debrceen")).Status);
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.Search("Kossuth", 12, "area:Budapest")).Status);
    }

    [Fact]
    public void PickerBoundsInputAndResults()
    {
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.Search(new string('a', 201))).Status);
        Assert.InRange(StreetCatalog.Search("Kossuth", int.MaxValue).Length, 1, 25);
        Assert.InRange(StreetCatalog.Search("Kossuth", 0).Length, 0, 1);
    }

    [Fact]
    public void ExplicitStreetResolvesWithoutChangingAddressOrGeocoding()
    {
        var street = UniqueTownStreet();
        var property = PropertyAt(street);
        var before = JsonSerializer.Serialize(property);
        Assert.Same(street, StreetCatalog.ResolveProperty(property, street.Id));
        Assert.Equal(before, JsonSerializer.Serialize(property));
    }

    [Fact]
    public void ExplicitUnknownOrConflictingStreetCannotBeSilentlyAssociated()
    {
        var street = UniqueTownStreet();
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(PropertyAt(street), "street:000000000000000000000000")).Status);

        var otherCity = PropertyAt(street);
        otherCity.City = street.City == "Szeged" ? "Debrecen" : "Szeged";
        otherCity.LocationId = "city:" + otherCity.City;
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(otherCity, street.Id)).Status);

        var otherName = PropertyAt(street);
        otherName.Street = "Biztosan nem azonos közterület utca";
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(otherName, street.Id)).Status);

        var otherPostcode = PropertyAt(street);
        otherPostcode.PostalCode = "0000";
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(otherPostcode, street.Id)).Status);
    }

    [Fact]
    public void ExplicitBudapestStreetRejectsAnotherDistrict()
    {
        var street = StreetCatalog.All.First(value => value.City == "Budapest" && value.District == "V.");
        var property = PropertyAt(street);
        property.District = "VI.";
        property.LocationId = "district:Budapest:6";
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(property, street.Id)).Status);
        property.District = "";
        property.PostalCode = "";
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(property, street.Id)).Status);
        Assert.Null(StreetCatalog.ResolveProperty(property));
    }

    [Fact]
    public void UniqueCanonicalNamesResolveWithAccentsAndCommonUtcaAbbreviations()
    {
        var street = UniqueTownStreet("UTCA");
        var property = PropertyAt(street);
        Assert.Same(street, StreetCatalog.ResolveProperty(property));
        property.Street = Rules.Normalize(street.Name) + " u.";
        Assert.Same(street, StreetCatalog.ResolveProperty(property));
        property.Street = Rules.Normalize(street.Name) + " u";
        Assert.Same(street, StreetCatalog.ResolveProperty(property));
    }

    [Fact]
    public void SourceAliasesAreAcceptedOnlyForTheirOwnScopedStreet()
    {
        // A source may legitimately provide no aliases. Check the first real
        // examples when supplied instead of inventing alternative street names.
        var examples = StreetCatalog.All.Where(value => value.Aliases.Any(alias => alias != value.StreetName)).Take(30);
        Assert.All(examples, street =>
        {
            var property = PropertyAt(street);
            property.Street = street.Aliases.First(alias => alias != street.StreetName);
            Assert.Same(street, StreetCatalog.ResolveProperty(property, street.Id));
            property.City = "Nincs ilyen település";
            Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(property, street.Id)).Status);
        });
    }

    [Fact]
    public void MultiplePostcodesRetainOneCanonicalStreetIdentity()
    {
        var street = StreetCatalog.All.First(value => value.PostalCodes.Length > 1);
        var property = PropertyAt(street);
        foreach (var postcode in street.PostalCodes)
        {
            property.PostalCode = postcode;
            Assert.Same(street, StreetCatalog.ResolveProperty(property, street.Id));
        }
    }

    [Fact]
    public void BudapestPostalRowsWithoutAKnownDistrictNeverBecomeSpecificDistrictStreets()
    {
        var street = StreetCatalog.All.First(value => value.City == "Budapest" && value.District is null);
        var property = PropertyAt(street);
        Assert.Same(street, StreetCatalog.ResolveProperty(property, street.Id));
        property.LocationId = "district:Budapest:5";
        Assert.Equal(400, Assert.Throws<ApiException>(() => StreetCatalog.ResolveProperty(property, street.Id)).Status);
        Assert.DoesNotContain(StreetCatalog.Search(street.Name, 25, "district:Budapest:5"), value => value.Id == street.Id);
    }

    [Fact]
    public void SameBudapestStreetNameAcrossDistrictsStaysUnassociatedWithoutAUniqueScope()
    {
        var shared = StreetCatalog.All.Where(street => street.City == "Budapest" && street.District is not null)
            .GroupBy(street => Rules.Normalize(street.StreetName))
            .First(group => group.Select(street => street.District).Distinct().Count() > 1);
        var property = PropertyAt(shared.First());
        property.LocationId = "city:Budapest";
        property.District = "";
        property.PostalCode = "";
        Assert.Null(StreetCatalog.ResolveProperty(property));
    }

    [Fact]
    public void UnknownStreetAndLegacyNullValuesStayUnassociated()
    {
        var property = new Property { City = "Szeged", LocationId = "city:Szeged", Street = "Még nem katalogizált tesztközterület utca", PostalCode = "6720" };
        Assert.Null(StreetCatalog.ResolveProperty(property));
        property.City = null!;
        property.LocationId = null!;
        property.District = null!;
        property.Street = null!;
        property.PostalCode = null!;
        Assert.Null(StreetCatalog.ResolveProperty(property));
    }
}
