using System.Globalization;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Otthonra.Api;

public sealed record PropertyGeocodingRequest(Guid OwnerId, Guid PropertyId, string City, string Street,
    string HouseNumber, string? PostalCode, string? LocationId = null);

public sealed record PropertyGeocodeResult(double Latitude, double Longitude, string Provider, string PlaceId, string Quality);

public interface IPropertyGeocoder
{
    Task<PropertyGeocodeResult> GeocodeAsync(PropertyGeocodingRequest address, CancellationToken cancellationToken = default);
}

/// <summary>Coordinates belong to one owner's one property. This service never shares address results.</summary>
public sealed class PropertyGeocodingService(IPropertyGeocoder geocoder)
{
    public static string AddressKey(Property property) => PropertyGeocodingAddress.Key(Address(property));

    private static PropertyGeocodingRequest Address(Property property) => PropertyGeocodingAddress.Validate(new(
        property.OwnerId, property.Id, property.City, property.Street, property.HouseNumber, property.PostalCode, property.LocationId));

    public async Task UpdateAsync(Property property, CancellationToken cancellationToken = default)
    {
        var address = Address(property);
        var key = PropertyGeocodingAddress.Key(address);
        if (property.GeocodingAddressKey == key && property.GeocodedAt.HasValue
            && !string.IsNullOrEmpty(property.GeocodingProvider) && !string.IsNullOrEmpty(property.GeocodingPlaceId)
            && !string.IsNullOrEmpty(property.GeocodingQuality)
            && PropertyGeocodingAddress.ValidCoordinates(property.Latitude, property.Longitude)) return;

        // Once the address changes, old coordinates must never identify the new address.
        property.Latitude = property.Longitude = null;
        property.GeocodedAt = null;
        property.GeocodingProvider = property.GeocodingPlaceId = property.GeocodingQuality = property.GeocodingAddressKey = "";
        var result = await geocoder.GeocodeAsync(address, cancellationToken);
        if (!PropertyGeocodingAddress.ValidCoordinates(result.Latitude, result.Longitude)
            || string.IsNullOrWhiteSpace(result.Provider) || result.Provider.Length > 40
            || string.IsNullOrWhiteSpace(result.PlaceId) || result.PlaceId.Length > 255
            || string.IsNullOrWhiteSpace(result.Quality) || result.Quality.Length > 40)
            throw new ApiException(502, "A címkereső érvénytelen helyadatot adott vissza. Próbáld később.");
        property.Latitude = result.Latitude;
        property.Longitude = result.Longitude;
        property.GeocodedAt = DateTime.UtcNow;
        property.GeocodingProvider = result.Provider;
        property.GeocodingPlaceId = result.PlaceId;
        property.GeocodingQuality = result.Quality;
        property.GeocodingAddressKey = key;
    }
}

public static class PropertyGeocodingAddress
{
    public static PropertyGeocodingRequest Validate(PropertyGeocodingRequest address)
    {
        var city = Clean(address.City, 100);
        var street = Clean(address.Street, 180);
        var house = Clean(address.HouseNumber, 32);
        var postal = Clean(address.PostalCode, 4);
        var location = LocationCatalog.ResolvePropertyInput(address.LocationId, city, null);
        if (address.OwnerId == Guid.Empty || address.PropertyId == Guid.Empty
            || Canonical(location.City) != Canonical(city) || street.Length == 0
            || !Regex.IsMatch(house, @"^[0-9]{1,5}(?:(?:\s*[/\-]\s*[\p{L}0-9]{1,6})|(?:\s*\p{L}))?\.?$", RegexOptions.CultureInvariant)
            || postal.Length > 0 && !Regex.IsMatch(postal, @"^[1-9][0-9]{3}$", RegexOptions.CultureInvariant))
            throw InvalidAddress();
        return address with { City = location.City, Street = street, HouseNumber = house, PostalCode = postal, LocationId = location.Id };
    }

    private static string Clean(string? value, int maximum)
    {
        if ((value?.Length ?? 0) > maximum || value?.Any(char.IsControl) == true) throw InvalidAddress();
        return Regex.Replace(value?.Trim() ?? "", @"\s+", " ");
    }

    internal static string Canonical(string? value) => Regex.Replace(Rules.Normalize(value ?? ""), @"\s+", " ").Trim().TrimEnd('.');
    internal static string HouseKey(string? value) => Regex.Replace(Canonical(value).Replace(" ", ""), @"/(?=\p{L})", "");

    public static string Key(PropertyGeocodingRequest address)
    {
        var scoped = new[] { address.OwnerId.ToString("D"), address.PropertyId.ToString("D"), Canonical(address.City),
            address.LocationId ?? "", Canonical(address.Street), HouseKey(address.HouseNumber), address.PostalCode ?? "" };
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(scoped))));
    }

    // A country component alone is insufficient if the response geometry is corrupt.
    public static bool ValidCoordinates(double? latitude, double? longitude) => latitude.HasValue && longitude.HasValue
        && double.IsFinite(latitude.Value) && double.IsFinite(longitude.Value)
        && latitude.Value is >= 45.7 and <= 48.65 && longitude.Value is >= 16.0 and <= 23.0;

    internal static ApiException InvalidAddress() => new(400,
        "A pontos cím nem azonosítható egyértelműen. Ellenőrizd a települést, az utcát, a házszámot és az irányítószámot.");
}

/// <summary>Process-local cost cap, supplementary to the authenticated owner endpoint limiter and Google quotas.</summary>
public sealed class GoogleGeocodingBudget(IConfiguration configuration)
{
    private readonly object gate = new();
    private readonly Queue<DateTimeOffset> recent = new();
    private readonly int perMinute = Math.Clamp(configuration.GetValue<int?>("Geocoding:Google:RequestsPerMinute") ?? 60, 1, 120);
    private int running;

    public IDisposable Enter()
    {
        lock (gate)
        {
            var now = DateTimeOffset.UtcNow;
            while (recent.TryPeek(out var first) && first <= now.AddMinutes(-1)) recent.Dequeue();
            if (running >= 4 || recent.Count >= perMinute)
                throw new ApiException(503, "A címkereső most foglalt. Kérjük, próbáld egy perc múlva.");
            recent.Enqueue(now);
            running++;
        }
        return new Lease(this);
    }

    private sealed class Lease(GoogleGeocodingBudget owner) : IDisposable
    {
        private int disposed;
        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0) return;
            lock (owner.gate) owner.running--;
        }
    }
}

public sealed class GooglePropertyGeocoder(IHttpClientFactory clients, IConfiguration configuration, GoogleGeocodingBudget budget) : IPropertyGeocoder
{
    public const string HttpClientName = "property-google-geocoding";
    private const int MaximumResponseBytes = 256 * 1024;

    public async Task<PropertyGeocodeResult> GeocodeAsync(PropertyGeocodingRequest address, CancellationToken cancellationToken = default)
    {
        address = PropertyGeocodingAddress.Validate(address);
        var apiKey = configuration["Geocoding:Google:ApiKey"]?.Trim();
        if (string.IsNullOrEmpty(apiKey))
            throw new ApiException(503, "A pontos címkeresés még nincs beállítva. Kérjük, próbáld később.");
        if (apiKey.Length > 512 || apiKey.Any(char.IsControl))
            throw new ApiException(503, "A pontos címkeresés beállítása hibás. Kérjük, próbáld később.");

        // No result cache, no automatic retry, and no provider response or request URI in application logs.
        using var lease = budget.Enter();
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(12));
        var queryCity = LocationCatalog.Get(address.LocationId)?.Label ?? address.City;
        var queryAddress = $"{address.Street} {address.HouseNumber}, {address.PostalCode} {queryCity}, Magyarország";
        var uri = "https://maps.googleapis.com/maps/api/geocode/json?address=" + Uri.EscapeDataString(queryAddress)
            + "&components=" + Uri.EscapeDataString("country:HU") + "&language=hu&region=hu&key=" + Uri.EscapeDataString(apiKey);
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, uri);
            using var response = await clients.CreateClient(HttpClientName).SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeout.Token);
            if (response.StatusCode is HttpStatusCode.TooManyRequests or HttpStatusCode.Forbidden or HttpStatusCode.Unauthorized)
                throw Unavailable();
            if (!response.IsSuccessStatusCode) throw ProviderFailure();
            if (response.Content.Headers.ContentLength > MaximumResponseBytes) throw ProviderFailure();
            await using var stream = await response.Content.ReadAsStreamAsync(timeout.Token);
            using var payload = new MemoryStream();
            var buffer = new byte[8192];
            while (true)
            {
                var read = await stream.ReadAsync(buffer.AsMemory(), timeout.Token);
                if (read == 0) break;
                if (payload.Length + read > MaximumResponseBytes) throw ProviderFailure();
                payload.Write(buffer, 0, read);
            }
            using var document = JsonDocument.Parse(payload.ToArray());
            return Parse(document.RootElement, address);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested) { throw ProviderFailure(); }
        catch (OperationCanceledException) { throw new OperationCanceledException(cancellationToken); }
        catch (Exception error) when (error is HttpRequestException or IOException or JsonException or InvalidOperationException or FormatException)
        {
            // Do not retain an inner transport exception: it may contain the API key or the private address.
            throw ProviderFailure();
        }
    }

    private static PropertyGeocodeResult Parse(JsonElement root, PropertyGeocodingRequest address)
    {
        if (!String(root, "status", out var status)) throw ProviderFailure();
        if (status == "ZERO_RESULTS") throw PropertyGeocodingAddress.InvalidAddress();
        if (status is "OVER_QUERY_LIMIT" or "OVER_DAILY_LIMIT" or "REQUEST_DENIED") throw Unavailable();
        if (status != "OK") throw ProviderFailure();
        if (!root.TryGetProperty("results", out var results) || results.ValueKind != JsonValueKind.Array) throw ProviderFailure();
        if (results.GetArrayLength() != 1) throw PropertyGeocodingAddress.InvalidAddress();
        var result = results[0];
        if (result.TryGetProperty("partial_match", out var partial) && partial.ValueKind != JsonValueKind.False
            || !HasType(result, "street_address", "premise", "subpremise")) throw PropertyGeocodingAddress.InvalidAddress();
        if (!result.TryGetProperty("address_components", out var components) || components.ValueKind != JsonValueKind.Array)
            throw PropertyGeocodingAddress.InvalidAddress();
        var all = components.EnumerateArray().ToArray();
        var country = all.Where(component => HasType(component, "country")).ToArray();
        if (country.Length != 1 || !String(country[0], "short_name", out var countryCode) || countryCode != "HU")
            throw PropertyGeocodingAddress.InvalidAddress();
        if (!Matches(all, "locality", address.City, PropertyGeocodingAddress.Canonical)
            || !Matches(all, "route", address.Street, PropertyGeocodingAddress.Canonical)
            || !Matches(all, "street_number", address.HouseNumber, PropertyGeocodingAddress.HouseKey)
            || !string.IsNullOrEmpty(address.PostalCode) && !Matches(all, "postal_code", address.PostalCode, PropertyGeocodingAddress.Canonical))
            throw PropertyGeocodingAddress.InvalidAddress();
        if (address.LocationId?.StartsWith("district:Budapest:", StringComparison.Ordinal) == true)
        {
            var district = int.Parse(address.LocationId["district:Budapest:".Length..], CultureInfo.InvariantCulture);
            // Budapest postcodes encode the district in positions two and three, including district XXIII (123x).
            var postcodes = all.Where(component => HasType(component, "postal_code"))
                .Select(component => String(component, "long_name", out var code) ? code : "").ToArray();
            if (postcodes.Length != 1 || !Regex.IsMatch(postcodes[0], @"^1[0-9]{3}$")
                || !int.TryParse(postcodes[0].Substring(1, 2), out var postalDistrict) || postalDistrict != district)
                throw PropertyGeocodingAddress.InvalidAddress();
        }
        if (!result.TryGetProperty("geometry", out var geometry) || !String(geometry, "location_type", out var quality)
            || quality is not ("ROOFTOP" or "RANGE_INTERPOLATED")) throw PropertyGeocodingAddress.InvalidAddress();
        if (!geometry.TryGetProperty("location", out var position) || !position.TryGetProperty("lat", out var latitudeElement)
            || !position.TryGetProperty("lng", out var longitudeElement) || !latitudeElement.TryGetDouble(out var latitude)
            || !longitudeElement.TryGetDouble(out var longitude) || !PropertyGeocodingAddress.ValidCoordinates(latitude, longitude))
            throw PropertyGeocodingAddress.InvalidAddress();
        if (!String(result, "place_id", out var placeId) || string.IsNullOrWhiteSpace(placeId) || placeId.Length > 255) throw ProviderFailure();
        return new(latitude, longitude, "google", placeId, quality == "ROOFTOP" ? "rooftop" : "range-interpolated");
    }

    private static bool Matches(IEnumerable<JsonElement> components, string type, string expected, Func<string?, string> normalize)
    {
        var found = components.Where(component => HasType(component, type)).ToArray();
        return found.Length == 1 && String(found[0], "long_name", out var value) && normalize(value) == normalize(expected);
    }

    private static bool HasType(JsonElement value, params string[] desired) => value.ValueKind == JsonValueKind.Object
        && value.TryGetProperty("types", out var types) && types.ValueKind == JsonValueKind.Array
        && types.EnumerateArray().Any(type => type.ValueKind == JsonValueKind.String && desired.Contains(type.GetString(), StringComparer.Ordinal));

    private static bool String(JsonElement value, string name, out string result)
    {
        result = "";
        if (value.ValueKind != JsonValueKind.Object || !value.TryGetProperty(name, out var field) || field.ValueKind != JsonValueKind.String) return false;
        result = field.GetString() ?? "";
        return true;
    }

    private static ApiException ProviderFailure() => new(502, "A címkereső szolgáltató jelenleg nem érhető el vagy nem adott értékelhető választ. Próbáld később.");
    private static ApiException Unavailable() => new(503, "A címkereső szolgáltató jelenleg nem tudja feldolgozni a kérést. Próbáld később.");
}

/// <summary>Explicit synthetic address capability. Never resolves an ordinary address or invents a city centre.</summary>
public sealed class TestPropertyGeocoder : IPropertyGeocoder
{
    public const string ReservedStreet = "OTTHONRA TEST";

    public Task<PropertyGeocodeResult> GeocodeAsync(PropertyGeocodingRequest address, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        address = PropertyGeocodingAddress.Validate(address);
        var ordinal = 0;
        var postalFixture = false;
        if (address.HouseNumber == "99999")
        {
            // Only the two designated, visibly fictional source-street cases
            // can use their synthetic quarter points. This provider is itself
            // gated to explicitly enabled Development/TEST; Google is separate.
            var street = StreetCatalog.ResolveProperty(new Property { City = address.City, Street = address.Street,
                PostalCode = address.PostalCode ?? "", LocationId = address.LocationId ?? "" });
            ordinal = street?.Id switch {
                "street:aae22ff8e2d0fa698c0291dc" => 1,
                "street:6cd1dbc01d7aec3be234b7ba" => 2,
                _ => 0
            };
            postalFixture = ordinal > 0;
        }
        if (!postalFixture && (PropertyGeocodingAddress.Canonical(address.Street) != ReservedStreet
            || !int.TryParse(address.HouseNumber, NumberStyles.None, CultureInfo.InvariantCulture, out ordinal)
            || ordinal is < 1 or > 9999))
            throw new ApiException(400, "A tesztcímkereső csak a fenntartott tesztcímeket és a két kijelölt, 99999 házszámú kitalált postai példát fogadja el.");

        var choices = NeighborhoodCatalog.All.Where(area => area.City == address.City).OrderBy(area => area.Id, StringComparer.Ordinal).ToArray();
        NeighborhoodArea? area = null;
        if (address.City == "Debrecen" && ordinal is 1 or 2)
        {
            var name = ordinal == 1 ? "Vénkert" : "Sestakert";
            area = choices.SingleOrDefault(choice => choice.Name == name);
        }
        else if (address.City == "Budapest" && address.LocationId?.StartsWith("district:Budapest:", StringComparison.Ordinal) == true)
        {
            var name = address.LocationId switch
            {
                "district:Budapest:2" => "Rózsadomb", "district:Budapest:23" => "Soroksár-Újtelep",
                "district:Budapest:11" => "Lágymányos",
                "district:Budapest:13" => "Újlipótváros", "district:Budapest:5" => "Belváros",
                "district:Budapest:9" => "Belső-Ferencváros", _ => null
            };
            area = name is null ? null : choices.SingleOrDefault(choice => choice.Name == name);
        }
        else if (choices.Length > 0) area = choices[(ordinal - 1) % choices.Length];

        var point = NeighborhoodCatalog.RepresentativePoint(area?.Id);
        // Canonical municipality interior points are only an explicit synthetic TEST capability.
        // A Budapest district still requires its own mapped point, never a different district's point.
        if (point is null && !(address.City == "Budapest" && address.LocationId?.StartsWith("district:Budapest:", StringComparison.Ordinal) == true))
            point = NeighborhoodCatalog.TestPointForCity(address.City);
        if (point is null || !PropertyGeocodingAddress.ValidCoordinates(point.Latitude, point.Longitude))
            throw new ApiException(400, "Ehhez a településhez vagy kerülethez nincs előre meghatározott tesztcím.");
        return Task.FromResult(new PropertyGeocodeResult(point.Latitude, point.Longitude, "test-fixture",
            "test-fixture:" + address.PropertyId.ToString("N") + ":" + (area?.Id[13..] ?? "city"), postalFixture ? "SYNTHETIC" : "test-fixture"));
    }
}

public static class PropertyGeocodingRegistration
{
    public static IServiceCollection AddPropertyGeocoding(this IServiceCollection services, IConfiguration configuration, IHostEnvironment environment)
    {
        services.AddHttpClient(GooglePropertyGeocoder.HttpClientName, client =>
        {
            client.Timeout = TimeSpan.FromSeconds(12);
            client.MaxResponseContentBufferSize = 256 * 1024;
        }).ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
        {
            AllowAutoRedirect = false, MaxConnectionsPerServer = 4, ConnectTimeout = TimeSpan.FromSeconds(5)
        }).RemoveAllLoggers();
        services.AddSingleton<GoogleGeocodingBudget>();
        var testGeocoder = configuration.GetValue<bool>("Geocoding:EnableTestGeocoder");
        if (testGeocoder && !environment.IsDevelopment()
            && !string.Equals(configuration["Deployment:Environment"], "test", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("A tesztcímkereső csak fejlesztői vagy TEST környezetben engedélyezhető.");
        if (testGeocoder) services.AddScoped<IPropertyGeocoder, TestPropertyGeocoder>();
        else services.AddScoped<IPropertyGeocoder, GooglePropertyGeocoder>();
        services.AddScoped<PropertyGeocodingService>();
        return services;
    }
}
