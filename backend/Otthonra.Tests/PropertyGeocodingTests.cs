using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Hosting;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PropertyGeocodingTests
{
    private const string Secret = "private-google-key-never-in-errors";
    private static PropertyGeocodingRequest Address => new(Guid.Parse("c5e62bb0-dc55-4e63-bb2c-0918ec281096"),
        Guid.Parse("bb623a29-c8a4-4fef-b639-71993b3f7b88"), "Debrecen", "Piac utca", "20/A", "4024", "city:Debrecen");

    private static IConfiguration Configuration(string? apiKey = Secret, string? perMinute = null) => new ConfigurationBuilder()
        .AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Geocoding:Google:ApiKey"] = apiKey, ["Geocoding:Google:RequestsPerMinute"] = perMinute
        }).Build();

    private static JsonObject SuccessfulResult() => JsonNode.Parse("""
        {
          "address_components": [
            { "long_name": "20/A", "short_name": "20/A", "types": ["street_number"] },
            { "long_name": "Piac utca", "short_name": "Piac u.", "types": ["route"] },
            { "long_name": "Debrecen", "short_name": "Debrecen", "types": ["locality", "political"] },
            { "long_name": "Magyarország", "short_name": "HU", "types": ["country", "political"] },
            { "long_name": "4024", "short_name": "4024", "types": ["postal_code"] }
          ],
          "geometry": { "location": { "lat": 47.5284, "lng": 21.6251 }, "location_type": "ROOFTOP" },
          "place_id": "google-property-place", "types": ["street_address"]
        }
        """)!.AsObject();

    private static string Response(Action<JsonObject>? change = null, int resultCount = 1)
    {
        var result = SuccessfulResult();
        change?.Invoke(result);
        return new JsonObject { ["status"] = "OK", ["results"] = new JsonArray(
            Enumerable.Range(0, resultCount).Select(_ => (JsonNode?)result.DeepClone()).ToArray()) }.ToJsonString();
    }

    private static JsonObject Component(JsonObject result, string type) => result["address_components"]!.AsArray()
        .Select(node => node!.AsObject()).Single(node => node["types"]!.AsArray().Any(value => value!.GetValue<string>() == type));

    private static (GooglePropertyGeocoder Geocoder, FakeHandler Handler) Google(string body, HttpStatusCode status = HttpStatusCode.OK,
        IConfiguration? configuration = null)
    {
        var handler = new FakeHandler(_ => new HttpResponseMessage(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") });
        var config = configuration ?? Configuration();
        return (new GooglePropertyGeocoder(new ClientFactory(new HttpClient(handler)), config, new GoogleGeocodingBudget(config)), handler);
    }

    [Theory]
    [InlineData("ROOFTOP", "rooftop")]
    [InlineData("RANGE_INTERPOLATED", "range-interpolated")]
    public async Task AcceptsOneFullHungarianBuildingAddressWithExplicitQuality(string geometry, string quality)
    {
        var (google, handler) = Google(Response(result => result["geometry"]!["location_type"] = geometry));
        var result = await google.GeocodeAsync(Address);
        Assert.Equal("google", result.Provider);
        Assert.Equal("google-property-place", result.PlaceId);
        Assert.Equal(47.5284, result.Latitude);
        Assert.Equal(21.6251, result.Longitude);
        Assert.Equal(quality, result.Quality);
        Assert.Equal(1, handler.Calls);
        Assert.Equal(GooglePropertyGeocoder.HttpClientName, ClientFactory.LastName);
        var query = Uri.UnescapeDataString(handler.RequestUri!.Query);
        Assert.Contains("components=country:HU", query);
        Assert.Contains("language=hu", query);
        Assert.Contains("Piac utca 20/A", query);
    }

    [Theory]
    [InlineData("country", "Ausztria", "AT")]
    [InlineData("locality", "Szeged", "Szeged")]
    [InlineData("route", "Kossuth utca", "Kossuth u.")]
    [InlineData("street_number", "20", "20")]
    [InlineData("postal_code", "4025", "4025")]
    public async Task RejectsWrongCountryCityStreetHouseOrSuppliedPostalCode(string component, string longName, string shortName)
    {
        var (google, _) = Google(Response(result =>
        {
            Component(result, component)["long_name"] = longName;
            Component(result, component)["short_name"] = shortName;
        }));
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(400, error.Status);
    }

    [Theory]
    [InlineData("APPROXIMATE")]
    [InlineData("GEOMETRIC_CENTER")]
    public async Task RejectsImpreciseGeometry(string geometry)
    {
        var (google, _) = Google(Response(result => result["geometry"]!["location_type"] = geometry));
        Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address))).Status);
    }

    [Fact]
    public async Task RejectsPartialMatchesStreetCentroidsAndAmbiguousResults()
    {
        foreach (var body in new[]
        {
            Response(result => result["partial_match"] = true),
            Response(result => result["types"] = new JsonArray("route")),
            Response(result => result["geometry"]!["location"]!["lat"] = 0),
            Response(resultCount: 2), Response(resultCount: 0),
            "{\"status\":\"ZERO_RESULTS\",\"results\":[]}"
        })
        {
            var (google, _) = Google(body);
            Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address))).Status);
        }
    }

    [Fact]
    public async Task RequiresTheSelectedBudapestDistrictEvenWhenThePostalInputIsEmpty()
    {
        var address = Address with { City = "Budapest", LocationId = "district:Budapest:5", PostalCode = "" };
        string ForDistrict(string postal) => Response(result =>
        {
            Component(result, "locality")["long_name"] = "Budapest";
            Component(result, "postal_code")["long_name"] = postal;
            result["geometry"]!["location"]!["lat"] = 47.4981;
            result["geometry"]!["location"]!["lng"] = 19.0495;
        });
        var (wrong, _) = Google(ForDistrict("1061"));
        Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => wrong.GeocodeAsync(address))).Status);
        var (correct, _) = Google(ForDistrict("1051"));
        Assert.Equal("google", (await correct.GeocodeAsync(address)).Provider);
    }

    [Theory]
    [InlineData("OVER_QUERY_LIMIT", 503)]
    [InlineData("OVER_DAILY_LIMIT", 503)]
    [InlineData("REQUEST_DENIED", 503)]
    [InlineData("UNKNOWN_ERROR", 502)]
    [InlineData("INVALID_REQUEST", 502)]
    public async Task MapsProviderFailuresWithoutExposingProviderMessages(string status, int expected)
    {
        var body = JsonSerializer.Serialize(new { status, error_message = Secret + " Piac utca 20/A" });
        var (google, handler) = Google(body);
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(expected, error.Status);
        AssertSanitized(error);
        Assert.Equal(1, handler.Calls);
    }

    [Theory]
    [InlineData(HttpStatusCode.Forbidden, 503)]
    [InlineData(HttpStatusCode.Unauthorized, 503)]
    [InlineData(HttpStatusCode.TooManyRequests, 503)]
    [InlineData(HttpStatusCode.BadGateway, 502)]
    [InlineData(HttpStatusCode.BadRequest, 502)]
    [InlineData(HttpStatusCode.Redirect, 502)]
    public async Task DoesNotRetryHttpFailuresOrExposeResponseBodies(HttpStatusCode status, int expected)
    {
        var (google, handler) = Google(Secret + " Piac utca 20/A", status);
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(expected, error.Status);
        AssertSanitized(error);
        Assert.Equal(1, handler.Calls);
    }

    [Theory]
    [InlineData("{invalid-json")]
    [InlineData("{\"status\":\"OK\",\"results\":{}}")]
    [InlineData("{\"error_message\":\"private-google-key-never-in-errors\"}")]
    public async Task RejectsMalformedResponsesWithoutIncludingRawContent(string body)
    {
        var (google, _) = Google(body);
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(502, error.Status);
        AssertSanitized(error);
    }

    [Fact]
    public async Task TransportExceptionsCannotRetainPrivateUriOrApiKey()
    {
        var handler = new FakeHandler(_ => throw new HttpRequestException("https://maps.googleapis.com/?key=" + Secret + "&address=Piac utca 20/A"));
        var config = Configuration();
        var google = new GooglePropertyGeocoder(new ClientFactory(new HttpClient(handler)), config, new GoogleGeocodingBudget(config));
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(502, error.Status);
        AssertSanitized(error);
        Assert.Equal(1, handler.Calls);
    }

    [Fact]
    public async Task MissingKeyFailsClearlyBeforeAnyNetworkRequest()
    {
        var (google, handler) = Google(Response(), configuration: Configuration(""));
        var error = await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(Address));
        Assert.Equal(503, error.Status);
        Assert.Contains("nincs beállítva", error.Message);
        Assert.Equal(0, handler.Calls);
    }

    [Fact]
    public async Task RejectsInvalidStructuredAddressesBeforeAnyNetworkRequest()
    {
        var (google, handler) = Google(Response());
        foreach (var address in new[]
        {
            Address with { Street = "" }, Address with { HouseNumber = "" }, Address with { HouseNumber = "12 34" },
            Address with { PostalCode = "0000" }, Address with { PostalCode = "4024X" },
            Address with { City = "Szeged" }, Address with { LocationId = "area:Debrecen" },
            Address with { Street = "Piac\nutca" }, Address with { OwnerId = Guid.Empty }
        })
            Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => google.GeocodeAsync(address))).Status);
        Assert.Equal(0, handler.Calls);
    }

    [Fact]
    public async Task BoundsResponseSizeAndCallBudgetWithoutRetries()
    {
        var (large, _) = Google(new string('x', 256 * 1024 + 1));
        Assert.Equal(502, (await Assert.ThrowsAsync<ApiException>(() => large.GeocodeAsync(Address))).Status);
        var (limited, handler) = Google(Response(), configuration: Configuration(perMinute: "1"));
        await limited.GeocodeAsync(Address);
        Assert.Equal(503, (await Assert.ThrowsAsync<ApiException>(() => limited.GeocodeAsync(Address))).Status);
        Assert.Equal(1, handler.Calls);
    }

    [Fact]
    public void BoundsConcurrentCallsWithoutAWaitingQueue()
    {
        var budget = new GoogleGeocodingBudget(Configuration());
        using var first = budget.Enter();
        using var second = budget.Enter();
        using var third = budget.Enter();
        using var fourth = budget.Enter();
        Assert.Equal(503, Assert.Throws<ApiException>(() => budget.Enter()).Status);
    }

    [Fact]
    public async Task UnchangedAddressReusesOnlyTheSameOwnerPropertyRegardlessOfAge()
    {
        var geocoder = new CountingGeocoder();
        var service = new PropertyGeocodingService(geocoder);
        var property = Property();
        await service.UpdateAsync(property);
        property.GeocodedAt = DateTime.UtcNow.AddYears(-10);
        property.Street = "  PIAC   UTCA  "; property.HouseNumber = "20a";
        await service.UpdateAsync(property);
        Assert.Equal(1, geocoder.Calls);

        // Equal text is not a cache key shared by another listing or another owner.
        var other = Property(); other.Id = Guid.NewGuid();
        await service.UpdateAsync(other);
        Assert.Equal(2, geocoder.Calls);
        property.OwnerId = Guid.NewGuid();
        await service.UpdateAsync(property);
        Assert.Equal(3, geocoder.Calls);
        Assert.NotEqual(other.GeocodingAddressKey, property.GeocodingAddressKey);
    }

    [Fact]
    public async Task EveryChangedAddressAndMissingCoordinatesRequiresFreshLookup()
    {
        var geocoder = new CountingGeocoder();
        var service = new PropertyGeocodingService(geocoder);
        var property = Property();
        await service.UpdateAsync(property);
        var key = property.GeocodingAddressKey;
        property.HouseNumber = "22";
        await service.UpdateAsync(property);
        Assert.Equal(2, geocoder.Calls);
        Assert.NotEqual(key, property.GeocodingAddressKey);
        property.PostalCode = "4025";
        await service.UpdateAsync(property);
        Assert.Equal(3, geocoder.Calls);
        property.Latitude = null;
        await service.UpdateAsync(property);
        Assert.Equal(4, geocoder.Calls);
        property.City = "Szeged"; property.LocationId = "city:Szeged";
        await service.UpdateAsync(property);
        Assert.Equal(5, geocoder.Calls);
    }

    [Fact]
    public async Task FailedAddressChangeCannotKeepThePreviousCoordinatesForANewAddress()
    {
        var geocoder = new CountingGeocoder();
        var service = new PropertyGeocodingService(geocoder);
        var property = Property();
        await service.UpdateAsync(property);
        property.HouseNumber = "99";
        geocoder.Fail = true;
        await Assert.ThrowsAsync<ApiException>(() => service.UpdateAsync(property));
        Assert.Null(property.Latitude);
        Assert.Null(property.Longitude);
        Assert.Null(property.GeocodedAt);
        Assert.Empty(property.GeocodingAddressKey);
    }

    [Fact]
    public void CanonicalAddressKeysDoNotConfuseNumericHouseSuffixes()
    {
        Assert.NotEqual(PropertyGeocodingAddress.Key(Address with { HouseNumber = "12/34" }),
            PropertyGeocodingAddress.Key(Address with { HouseNumber = "1234" }));
        Assert.NotEqual(PropertyGeocodingAddress.Key(Address with { HouseNumber = "12-14" }),
            PropertyGeocodingAddress.Key(Address with { HouseNumber = "1214" }));
    }

    [Fact]
    public async Task TestGeocoderOnlyResolvesReservedSyntheticAddressesAtKnownNeighborhoodPoints()
    {
        var geocoder = new TestPropertyGeocoder();
        var first = await geocoder.GeocodeAsync(Address with { Street = TestPropertyGeocoder.ReservedStreet, HouseNumber = "1", PostalCode = "" });
        var second = await geocoder.GeocodeAsync(Address with { Street = TestPropertyGeocoder.ReservedStreet, HouseNumber = "2", PostalCode = "" });
        var venkert = NeighborhoodCatalog.RepresentativePoint("neighborhood:e8c749e1fc0a306c717ad312")!;
        var sestakert = NeighborhoodCatalog.RepresentativePoint("neighborhood:f22df415c7b5ea79925e8886")!;
        Assert.Equal((venkert.Latitude, venkert.Longitude), (first.Latitude, first.Longitude));
        Assert.Equal((sestakert.Latitude, sestakert.Longitude), (second.Latitude, second.Longitude));
        Assert.Equal("test-fixture", first.Provider);
        Assert.Equal("test-fixture", first.Quality);
        Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => geocoder.GeocodeAsync(Address))).Status);

        var citiesWithAreas = NeighborhoodCatalog.All.Select(area => area.City).ToHashSet(StringComparer.Ordinal);
        var noAreaCity = LocationCatalog.All.First(location => location.Kind == "city" && !citiesWithAreas.Contains(location.City));
        var municipal = Address with { Street = TestPropertyGeocoder.ReservedStreet, HouseNumber = "1", City = noAreaCity.City, LocationId = noAreaCity.Id };
        var municipalResult = await geocoder.GeocodeAsync(municipal);
        var municipalPoint = NeighborhoodCatalog.TestPointForCity(noAreaCity.City)!;
        Assert.Equal((municipalPoint.Latitude, municipalPoint.Longitude), (municipalResult.Latitude, municipalResult.Longitude));
        var unknown = municipal with { City = "Nemlétezőhely", LocationId = "city:Nemlétezőhely" };
        Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => geocoder.GeocodeAsync(unknown))).Status);
    }

    [Theory]
    [InlineData("Hajdúszoboszló")]
    [InlineData("Abádszalók")]
    [InlineData("Kaszaper")]
    public async Task ReservedTestAddressesCanUseTheirOwnCanonicalMunicipalityPointWithoutAQuarter(string city)
    {
        var geocoder = new TestPropertyGeocoder();
        var address = Address with { Street = TestPropertyGeocoder.ReservedStreet, HouseNumber = "1", PostalCode = "",
            City = city, LocationId = "city:" + city };
        var result = await geocoder.GeocodeAsync(address);
        var point = NeighborhoodCatalog.TestPointForCity(city)!;
        Assert.Equal((point.Latitude, point.Longitude), (result.Latitude, result.Longitude));
        Assert.Equal("test-fixture", result.Provider);
        Assert.Equal("test-fixture", result.Quality);
        Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => geocoder.GeocodeAsync(address with { Street = "Valódi utca" }))).Status);
    }

    [Theory]
    [InlineData("Böszörményi út", "4027", "neighborhood:e8c749e1fc0a306c717ad312")]
    [InlineData("Egyetem sugárút", "4032", "neighborhood:f22df415c7b5ea79925e8886")]
    public async Task TestSpecificFixtureCasesUseOnlyTheDesignatedPostalStreetsAndFictionalHouse(string street, string postal, string areaId)
    {
        var geocoder = new TestPropertyGeocoder();
        var address = Address with { Street = street, PostalCode = postal, HouseNumber = "99999" };
        var result = await geocoder.GeocodeAsync(address);
        var point = NeighborhoodCatalog.RepresentativePoint(areaId)!;
        Assert.Equal((point.Latitude, point.Longitude), (result.Latitude, result.Longitude));
        Assert.Equal("test-fixture", result.Provider); Assert.Equal("SYNTHETIC", result.Quality);
        foreach (var invalid in new[] { address with { HouseNumber = "12" }, address with { HouseNumber = "99998" },
            address with { PostalCode = "9999" }, address with { City = "Szeged", LocationId = "city:Szeged" },
            address with { Street = "Piac utca", PostalCode = "4024" }, address with { Street = "Nemlétező utca" } })
            Assert.Equal(400, (await Assert.ThrowsAsync<ApiException>(() => geocoder.GeocodeAsync(invalid))).Status);
    }

    [Theory]
    [InlineData(2, "neighborhood:ba157ae98860772474d9d016")]
    [InlineData(23, "neighborhood:6caf5ba44e563972619da861")]
    [InlineData(11, "neighborhood:9d5b9a27888a2969fbf6b60a")]
    [InlineData(13, "neighborhood:6a3137f318ad4733d5b82728")]
    [InlineData(5, "neighborhood:8a63932c228529e3252478b6")]
    [InlineData(9, "neighborhood:2a7704f06397ff7829181cd2")]
    public async Task TestGeocoderHonorsKnownBudapestDistricts(int district, string neighborhoodId)
    {
        var geocoder = new TestPropertyGeocoder();
        var address = Address with { City = "Budapest", LocationId = "district:Budapest:" + district,
            Street = TestPropertyGeocoder.ReservedStreet, HouseNumber = "1", PostalCode = "" };
        var result = await geocoder.GeocodeAsync(address);
        var point = NeighborhoodCatalog.RepresentativePoint(neighborhoodId)!;
        Assert.Equal((point.Latitude, point.Longitude), (result.Latitude, result.Longitude));
    }

    [Theory]
    [InlineData("Development", null, true)]
    [InlineData("Production", "test", true)]
    [InlineData("Production", null, false)]
    [InlineData("Production", "production", false)]
    public void TestGeocoderRequiresBothExplicitOptInAndAnAllowedEnvironment(string environment, string? deployment, bool allowed)
    {
        IConfiguration config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Geocoding:EnableTestGeocoder"] = "true", ["Deployment:Environment"] = deployment
        }).Build();
        var services = new ServiceCollection();
        services.AddSingleton(config);
        if (!allowed)
        {
            Assert.Throws<InvalidOperationException>(() => services.AddPropertyGeocoding(config, new HostEnvironment { EnvironmentName = environment }));
            return;
        }
        services.AddPropertyGeocoding(config, new HostEnvironment { EnvironmentName = environment });
        using var provider = services.BuildServiceProvider();
        Assert.IsType<TestPropertyGeocoder>(provider.GetRequiredService<IPropertyGeocoder>());
    }

    [Fact]
    public void TestEnvironmentAloneNeverEnablesSyntheticGeocoding()
    {
        var config = Configuration();
        var services = new ServiceCollection();
        services.AddSingleton(config);
        services.AddPropertyGeocoding(config, new HostEnvironment { EnvironmentName = "Development" });
        using var provider = services.BuildServiceProvider();
        Assert.IsType<GooglePropertyGeocoder>(provider.GetRequiredService<IPropertyGeocoder>());
    }

    [Fact]
    public void HiddenAddressAndInternalCoordinatesStayPrivateWhenPublicAddressPartsAreOptedIn()
    {
        var property = Property();
        property.Address = "Titkos magáncím 20/A";
        property.Street = "Titkos magáncím";
        property.Latitude = 47.5554321;
        property.Longitude = 21.6665432;
        property.GeocodedAt = new DateTime(2026, 11, 16, 12, 0, 0, DateTimeKind.Utc);
        property.GeocodingProvider = "google";
        property.GeocodingQuality = "rooftop";
        property.GeocodingPlaceId = "private-provider-place-id";
        property.GeocodingAddressKey = "private-scoped-address-key";
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        var foreign = JsonSerializer.Serialize(Dto.Property(property), options);
        using var publicDocument = JsonDocument.Parse(foreign);
        Assert.Equal(JsonValueKind.Null, publicDocument.RootElement.GetProperty("addressDetails").ValueKind);
        Assert.Equal("", publicDocument.RootElement.GetProperty("address").GetString());
        Assert.Equal("", publicDocument.RootElement.GetProperty("street").GetString());
        Assert.Equal("", publicDocument.RootElement.GetProperty("houseNumber").GetString());
        var internalFields = new[] { "postalCode", "latitude", "longitude", "geocodedAt", "geocodingProvider", "geocodingPlaceId", "geocodingAddressKey" };
        foreach (var field in internalFields)
            Assert.False(publicDocument.RootElement.TryGetProperty(field, out _));
        foreach (var value in new[] { "Titkos magáncím", "47.5554321", "21.6665432", "private-provider-place-id", "private-scoped-address-key", "rooftop" })
            Assert.DoesNotContain(value, foreign);

        using var owner = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property, own: true), options));
        var details = owner.RootElement.GetProperty("addressDetails");
        Assert.Equal(property.Street, details.GetProperty("street").GetString());
        Assert.Equal(property.HouseNumber, details.GetProperty("houseNumber").GetString());
        Assert.Equal(property.PostalCode, details.GetProperty("postalCode").GetString());
        Assert.Equal(property.Latitude.Value, details.GetProperty("latitude").GetDouble());
        Assert.Equal(property.Longitude.Value, details.GetProperty("longitude").GetDouble());
        Assert.Equal("google", details.GetProperty("provider").GetString());

        property.HideStreet = false;
        foreach (var hideHouseNumber in new[] { true, false })
        {
            property.HideHouseNumber = hideHouseNumber;
            using var visible = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property), options));
            Assert.Equal(property.Street, visible.RootElement.GetProperty("street").GetString());
            Assert.Equal(hideHouseNumber ? "" : property.HouseNumber, visible.RootElement.GetProperty("houseNumber").GetString());
            Assert.Equal(property.Street + (hideHouseNumber ? "" : " " + property.HouseNumber), visible.RootElement.GetProperty("address").GetString());
            Assert.Equal(JsonValueKind.Null, visible.RootElement.GetProperty("addressDetails").ValueKind);
            foreach (var field in internalFields) Assert.False(visible.RootElement.TryGetProperty(field, out _));
            foreach (var secret in new[] { "47.5554321", "21.6665432", "private-provider-place-id", "private-scoped-address-key", "rooftop" })
                Assert.DoesNotContain(secret, visible.RootElement.GetRawText());
        }
    }

    private static Property Property() => new()
    {
        Id = Address.PropertyId, OwnerId = Address.OwnerId, City = Address.City, LocationId = Address.LocationId!,
        Street = Address.Street, HouseNumber = Address.HouseNumber, PostalCode = Address.PostalCode!
    };

    private static void AssertSanitized(Exception error)
    {
        Assert.DoesNotContain(Secret, error.ToString());
        Assert.DoesNotContain("Piac", error.ToString());
        Assert.DoesNotContain("maps.googleapis.com", error.ToString());
        Assert.Null(error.InnerException);
    }

    private sealed class CountingGeocoder : IPropertyGeocoder
    {
        public int Calls { get; private set; }
        public bool Fail { get; set; }
        public Task<PropertyGeocodeResult> GeocodeAsync(PropertyGeocodingRequest address, CancellationToken cancellationToken = default)
        {
            Calls++;
            if (Fail) throw new ApiException(400, "Nem azonosítható cím.");
            return Task.FromResult(new PropertyGeocodeResult(47.5284, 21.6251, "google", "property-" + Calls, "rooftop"));
        }
    }

    private sealed class FakeHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        public int Calls { get; private set; }
        public Uri? RequestUri { get; private set; }
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            RequestUri = request.RequestUri;
            return Task.FromResult(respond(request));
        }
    }

    private sealed class ClientFactory(HttpClient client) : IHttpClientFactory
    {
        public static string? LastName { get; private set; }
        public HttpClient CreateClient(string name) { LastName = name; return client; }
    }

    private sealed class HostEnvironment : IHostEnvironment
    {
        public string EnvironmentName { get; set; } = "Production";
        public string ApplicationName { get; set; } = "Otthonra.Tests";
        public string ContentRootPath { get; set; } = "/";
        public IFileProvider ContentRootFileProvider { get; set; } = new NullFileProvider();
    }
}
