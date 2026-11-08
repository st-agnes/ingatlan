using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record LandingSearchTeaser(string Key, string Title, string Type, string[] Locations,
    decimal? MinPrice, decimal? MaxPrice, decimal? MinArea, decimal? MaxArea, decimal? MinRooms,
    decimal? MaxRooms, string OwnerAccountType);
public sealed record LandingPropertyTeaser(string Key, string Title, string Type, string Location,
    decimal Price, decimal Area, int? WholeRooms, int? HalfRooms, decimal Rooms, decimal? LotArea,
    string OwnerAccountType);
public sealed record PublicLandingResponse(IReadOnlyList<LandingRegion> Regions, LandingRegion? Region,
    string Scope, LandingSearchTeaser[] Searches, LandingPropertyTeaser[] Properties);

public static class PublicLanding
{
    public static IServiceCollection AddPublicLanding(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddSingleton<PublicLandingCache>();
        return services;
    }

    public static IEndpointRouteBuilder MapPublicLanding(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/public/landing", async (string? region, AppDb db, PublicLandingCache cache, CancellationToken cancellationToken) =>
        {
            var selected = ParseRegion(region);
            var snapshot = await cache.GetAsync(db, cancellationToken);
            return Results.Ok(snapshot.Response(selected));
        }).AllowAnonymous();
        return endpoints;
    }

    public static LandingRegion? ParseRegion(string? region)
    {
        if (string.IsNullOrWhiteSpace(region)) return null;
        return RegionCatalog.Get(region.Trim()) ?? throw new ApiException(400, "Ismeretlen régió. Válassz a régiók listájából.");
    }

    // Free-form text, owner/source IDs, photographs and addresses never enter a teaser.
    public static string SafeType(string? type) => Rules.Normalize(type ?? "") switch
    {
        "LAKAS" => "Lakás", "HAZ" => "Ház", "TELEK" => "Telek", "NYARALO" => "Nyaraló",
        "IRODA" => "Iroda", "UZLETHELYISEG" => "Üzlethelyiség", "GARAZS" => "Garázs",
        "EGYEB" => "Egyéb", _ => "Ingatlan"
    };
    private static string SearchTitle(string type) => type switch
    {
        "Lakás" => "Lakást keres", "Ház" => "Házat keres", "Telek" => "Telket keres",
        "Nyaraló" => "Nyaralót keres", "Iroda" => "Irodát keres", "Üzlethelyiség" => "Üzlethelyiséget keres",
        "Garázs" => "Garázst keres", _ => "Ingatlant keres"
    };
    private static decimal? SafeBound(decimal? value) => value >= 0 ? value : null;

    public static (LandingSearchTeaser Teaser, string[] Regions)? SearchTeaser(SearchRequest search, string? accountType)
    {
        if (search.Archived) return null;
        Location[] locations;
        try { locations = LocationCatalog.ForSearch(search); }
        catch (JsonException) { return null; }
        if (locations.Length == 0) return null;
        var type = SafeType(search.Type);
        return (new LandingSearchTeaser("", SearchTitle(type), type,
            locations.Select(location => location.Label).ToArray(), SafeBound(search.MinPrice), SafeBound(search.MaxPrice),
            SafeBound(search.MinArea), SafeBound(search.MaxArea), SafeBound(search.MinRooms), SafeBound(search.MaxRooms),
            AccountTypes.PublicType(accountType)), RegionCatalog.ForLocations(locations));
    }

    public static (LandingPropertyTeaser Teaser, string[] Regions)? PropertyTeaser(Property property, string? accountType)
    {
        if (property.Archived || property.Price <= 0 || property.Area <= 0 || property.Rooms < 0) return null;
        var location = LocationCatalog.ForProperty(property);
        if (location is null) return null;
        var type = SafeType(property.Type);
        var rooms = Rules.RoomCounts(property);
        return (new LandingPropertyTeaser("", "Eladó " + type.ToLowerInvariant(), type, location.Label,
            property.Price, property.Area, rooms.WholeRooms >= 0 ? rooms.WholeRooms : null,
            rooms.HalfRooms >= 0 ? rooms.HalfRooms : null, property.Rooms,
            type == "Ház" ? SafeBound(property.LotArea) : null, AccountTypes.PublicType(accountType)),
            RegionCatalog.ForLocation(location));
    }
}

/// <summary>Stores bounded candidate pools; every response independently selects a diverse sample.</summary>
public sealed class PublicLandingSnapshot
{
    private sealed class Content(Random random)
    {
        public object Gate { get; } = new();
        public LandingCandidatePool<LandingSearchTeaser> Searches { get; } = new(random);
        public LandingCandidatePool<LandingPropertyTeaser> Properties { get; } = new(random);
    }
    private readonly Dictionary<string, Content> contents;

    public PublicLandingSnapshot(Random? random = null)
    {
        random ??= Random.Shared;
        contents = RegionCatalog.All.Select(region => region.Id).Prepend("")
            .ToDictionary(id => id, _ => new Content(new Random(random.Next())), StringComparer.Ordinal);
    }

    public void Add(SearchRequest search, string? accountType)
    {
        if (PublicLanding.SearchTeaser(search, accountType) is not { } item) return;
        var candidate = new LandingCandidate<LandingSearchTeaser>(search.Id, item.Teaser, LandingTraits.From(item.Teaser));
        foreach (var id in item.Regions.Prepend(""))
        {
            var content = contents[id];
            lock (content.Gate) content.Searches.Add(candidate);
        }
    }
    public void Add(Property property, string? accountType)
    {
        if (PublicLanding.PropertyTeaser(property, accountType) is not { } item) return;
        var candidate = new LandingCandidate<LandingPropertyTeaser>(property.Id, item.Teaser, LandingTraits.From(item.Teaser));
        foreach (var id in item.Regions.Prepend(""))
        {
            var content = contents[id];
            lock (content.Gate) content.Properties.Add(candidate);
        }
    }
    public PublicLandingResponse Response(LandingRegion? region)
    {
        var content = contents[region?.Id ?? ""];
        lock (content.Gate)
        {
            var searches = content.Searches.Select(8).Select((candidate, index) => candidate.Value with {
                Key = "search-" + (index + 1), Locations = candidate.Value.Locations.ToArray()
            }).ToArray();
            var properties = content.Properties.Select(4).Select((candidate, index) => candidate.Value with {
                Key = "property-" + (index + 1)
            }).ToArray();
            return new(RegionCatalog.All, region, region is null ? "national" : "region", searches, properties);
        }
    }
}

public sealed class PublicLandingCache
{
    private sealed record Cached(DateTime ExpiresAt, PublicLandingSnapshot Snapshot);
    private readonly SemaphoreSlim gate = new(1, 1);
    private Cached? cached;

    public async Task<PublicLandingSnapshot> GetAsync(AppDb db, CancellationToken cancellationToken)
    {
        var previous = Volatile.Read(ref cached);
        if (previous is not null && previous.ExpiresAt > DateTime.UtcNow) return previous.Snapshot;
        await gate.WaitAsync(cancellationToken);
        try
        {
            previous = cached;
            if (previous is not null && previous.ExpiresAt > DateTime.UtcNow) return previous.Snapshot;
            var snapshot = new PublicLandingSnapshot();
            // Stream all minimal projections so older counties/categories stay eligible.
            // The snapshot retains bounded stratified reservoirs, not cached final results;
            // each public request therefore receives a fresh diversified selection.
            var searches = from search in db.SearchRequests.AsNoTracking()
                join owner in db.Users.AsNoTracking() on search.OwnerId equals owner.Id
                where !search.Archived
                orderby search.CreatedAt descending, search.Id descending
                select new { search.Id, search.City, search.DistrictsJson, search.LocationIdsJson, search.Type,
                    search.MinPrice, search.MaxPrice, search.MinArea, search.MaxArea, search.MinRooms, search.MaxRooms,
                    owner.AccountType };
            await foreach (var row in searches.AsAsyncEnumerable().WithCancellation(cancellationToken))
                snapshot.Add(new SearchRequest { Id = row.Id, City = row.City, DistrictsJson = row.DistrictsJson,
                    LocationIdsJson = row.LocationIdsJson, Type = row.Type, MinPrice = row.MinPrice, MaxPrice = row.MaxPrice,
                    MinArea = row.MinArea, MaxArea = row.MaxArea, MinRooms = row.MinRooms, MaxRooms = row.MaxRooms }, row.AccountType);
            var properties = from property in db.Properties.AsNoTracking()
                join owner in db.Users.AsNoTracking() on property.OwnerId equals owner.Id
                where !property.Archived
                orderby property.CreatedAt descending, property.Id descending
                select new { property.Id, property.City, property.District, property.LocationId, property.Type, property.Price,
                    property.Area, property.Rooms, property.WholeRooms, property.HalfRooms, property.LotArea, owner.AccountType };
            await foreach (var row in properties.AsAsyncEnumerable().WithCancellation(cancellationToken))
                snapshot.Add(new Property { Id = row.Id, City = row.City, District = row.District, LocationId = row.LocationId,
                    Type = row.Type, Price = row.Price, Area = row.Area, Rooms = row.Rooms, WholeRooms = row.WholeRooms,
                    HalfRooms = row.HalfRooms, LotArea = row.LotArea }, row.AccountType);
            Volatile.Write(ref cached, new Cached(DateTime.UtcNow.AddSeconds(60), snapshot));
            return snapshot;
        }
        finally { gate.Release(); }
    }
}
