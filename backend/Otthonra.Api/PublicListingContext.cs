using System.Data;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

public sealed record ListingActiveSummary(string Kind, Guid Id, string Title, string Type, Location[] Locations,
    string[] LocationIds, decimal? Price = null, decimal? MinPrice = null, decimal? MaxPrice = null,
    decimal? MinArea = null, decimal? MaxArea = null, decimal? MinRooms = null, decimal? MaxRooms = null);
public sealed record ListingInteractionContext(bool Available, ListingActiveSummary? Active = null, FeedItem? Item = null,
    string? MyDecision = null, Guid? MatchId = null, bool Compatible = false, bool IsExact = false,
    int CompatibilityScore = 0, int LikeCost = 0, int Credits = 0, bool CanDecide = false,
    bool RequiresApproximateConsent = false, bool HasUnseenExact = false, string? UnavailableReason = null);
public sealed record PublicListingMap(string Kind, bool Available, string[] LocationIds, string? ExternalUrl = null);

/// <summary>Shared public pages use ordinary active-profile authorization and decision endpoints.</summary>
public static class PublicListingContext
{
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);
    public static IEndpointRouteBuilder MapListingContextEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapListingConnectionEndpoints();
        endpoints.MapGet("/api/listings/{kind}/{key}/context", async Task<IResult>
            (string kind, string key, AppDb db, ClaimsPrincipal principal, HttpContext context, CancellationToken cancellationToken) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (!PublicListings.ValidKey(kind, key)) return Results.NotFound();
            // User activation, pair state and ranking are read from one snapshot.
            // The POST /decisions transaction remains authoritative for actions.
            await using var snapshot = await db.Database.BeginTransactionAsync(IsolationLevel.RepeatableRead, cancellationToken);
            var user = await db.Users.AsNoTracking().SingleAsync(row => row.Id == principal.UserId(), cancellationToken);
            Property? property = null; SearchRequest? search = null; User? targetOwner;
            if (kind == "property")
            {
                property = await db.Properties.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
                targetOwner = property is null ? null : await db.Users.AsNoTracking().SingleOrDefaultAsync(row => row.Id == property.OwnerId, cancellationToken);
                if (property is null || targetOwner is null || PublicListings.Property(property, targetOwner.AccountType, targetOwner.Name) is null) return Results.NotFound();
            }
            else
            {
                search = await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
                targetOwner = search is null ? null : await db.Users.AsNoTracking().SingleOrDefaultAsync(row => row.Id == search.OwnerId, cancellationToken);
                if (search is null || targetOwner is null || PublicListings.Search(search, targetOwner.AccountType, targetOwner.Name) is null) return Results.NotFound();
            }

            Property? activeProperty = null; SearchRequest? activeSearch = null;
            if (user.ActiveKind == "property") activeProperty = await db.Properties.AsNoTracking().SingleOrDefaultAsync(row => row.Id == user.ActiveEntityId && row.OwnerId == user.Id && !row.Archived, cancellationToken);
            if (user.ActiveKind == "search") activeSearch = await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(row => row.Id == user.ActiveEntityId && row.OwnerId == user.Id && !row.Archived, cancellationToken);
            var active = ActiveSummary(activeProperty, activeSearch);
            var cost = AccountTypes.LikeCost(user.AccountType, user.ActiveKind);
            ListingInteractionContext Unavailable(string reason) => new(false, active, LikeCost: cost, Credits: user.Credits, UnavailableReason: reason);
            if (active is null) return Results.Ok(Unavailable("no_active_profile"));
            if (kind == active.Kind) return Results.Ok(Unavailable("opposite_profile_required"));
            if (targetOwner.Id == user.Id) return Results.Ok(Unavailable("own_listing"));
            if (!AccountTypes.CanInteract(user.AccountType, targetOwner.AccountType)) return Results.Ok(Unavailable("agent_pair_forbidden"));
            property ??= activeProperty!; search ??= activeSearch!;
            var buyer = activeSearch is not null;
            var evaluation = await MatchingPairEvaluation.EvaluateAsync(db, property, search, sellerPerspective: !buyer, cancellationToken: cancellationToken);
            var prior = await db.Decisions.AsNoTracking().SingleOrDefaultAsync(row => row.PropertyId == property.Id && row.SearchRequestId == search.Id && row.ActorKind == active.Kind && row.ActorUserId == user.Id, cancellationToken);
            var matchId = await db.Matches.AsNoTracking().Where(row => row.PropertyId == property.Id && row.SearchRequestId == search.Id).Select(row => (Guid?)row.Id).SingleOrDefaultAsync(cancellationToken);
            var oppositeKind = buyer ? "property" : "search";
            var likedYou = await db.Decisions.AsNoTracking().AnyAsync(row => row.PropertyId == property.Id && row.SearchRequestId == search.Id && row.ActorKind == oppositeKind && row.ActorUserId == targetOwner.Id && row.Liked, cancellationToken);
            var awaitingDecision = prior is null && matchId is null && evaluation.Eligible;
            var seller = buyer ? targetOwner : user; var seeker = buyer ? user : targetOwner;
            // Even the owned property is deliberately stripped of coordinates on
            // this compact page context. Its full editor DTO stays owner-only.
            var item = new FeedItem(SafeCard(Dto.Property(property, false, seller.AccountType, seller.Name), property.Title, property.Description, "Eladó ingatlan"),
                SafeCard(Dto.Search(search, seeker.AccountType, seeker.Name, own: buyer), search.Title, search.Description, "Keresési igény"), property.Id, search.Id,
                evaluation.Score, evaluation.Reasons, likedYou, evaluation.IsExact,
                MatchingRanking.ValueForMoney(property), MatchingRanking.Prepare(search, sellerPerspective: !buyer).Specificity, evaluation.MatchDetails);
            var myDecision = prior is null ? null : prior.Liked ? "liked" : "passed";
            var reason = prior is not null ? "already_" + myDecision : matchId.HasValue ? "already_matched"
                : !evaluation.Eligible ? "incompatible" : null;
            var result = new ListingInteractionContext(true, active, item, myDecision, matchId, evaluation.Eligible,
                evaluation.IsExact, evaluation.Score, cost, user.Credits, awaitingDecision,
                false, false, reason);
            await snapshot.CommitAsync(cancellationToken);
            return Results.Ok(result);
        }).RequireAuthorization();

        endpoints.MapGet("/api/public/listings/{kind}/{key}/map", async Task<IResult>
            (string kind, string key, AppDb db, HttpContext context, CancellationToken cancellationToken) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (!PublicListings.ValidKey(kind, key)) return Results.NotFound();
            if (kind == "search")
            {
                var search = await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
                if (search is null || PublicListings.Search(search, AccountTypes.Private) is null) return Results.NotFound();
                return Results.Ok(SearchMap(search));
            }
            // Keep the visibility flags and chosen outline in a coherent read.
            await using var snapshot = await db.Database.BeginTransactionAsync(IsolationLevel.RepeatableRead, cancellationToken);
            var property = await db.Properties.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
            if (property is null || PublicListings.Property(property, AccountTypes.Private) is null) return Results.NotFound();
            var external = PublicAddressUrl(property);
            if (external is not null) return Results.Ok(new PublicListingMap(kind, true, [], external));
            var neighborhoodId = await SmallestNeighborhoodAsync(db, property.Id, cancellationToken);
            var fallback = LocationCatalog.Get("city:" + LocationCatalog.ForProperty(property)?.City);
            var id = neighborhoodId ?? fallback?.Id;
            await snapshot.CommitAsync(cancellationToken);
            return Results.Ok(new PublicListingMap(kind, id is not null, id is null ? [] : [id]));
        }).AllowAnonymous();
        return endpoints;
    }

    /// <summary>Direct detail actions name the opposite listing; feed actions keep their existing consent gate.</summary>
    public static bool IsDirectDecision(string? listingKey, string? activeKind, Property property, SearchRequest search)
    {
        if (listingKey is null) return false;
        var kind = activeKind == "property" ? "search" : activeKind == "search" ? "property" : null;
        var expected = kind == "property" ? property.PublicListingKey ?? PublicLanding.SourceKey("property", property.Id)
            : kind == "search" ? search.PublicListingKey ?? PublicLanding.SourceKey("search", search.Id) : null;
        if (kind is null || !PublicListings.ValidKey(kind, listingKey)
            || !string.Equals(listingKey, expected, StringComparison.Ordinal))
            throw new ApiException(400, "A döntéshez a megtekintett hirdetés azonosítóját add meg.");
        return true;
    }

    public static ListingActiveSummary? ActiveSummary(Property? property, SearchRequest? search)
    {
        if (property is not null)
        {
            var place = LocationCatalog.ForProperty(property);
            Location[] locations = place is null ? [] : [place];
            return new("property", property.Id, property.Title, property.Type, locations, locations.Select(row => row.Id).ToArray(), Price: property.Price);
        }
        if (search is null) return null;
        var selected = LocationCatalog.ForSearch(search);
        return new("search", search.Id, search.Title, search.Type, selected, selected.Select(row => row.Id).ToArray(),
            MinPrice: search.MinPrice, MaxPrice: search.MaxPrice, MinArea: search.MinArea, MaxArea: search.MaxArea,
            MinRooms: search.MinRooms, MaxRooms: search.MaxRooms);
    }

    public static PublicListingMap SearchMap(SearchRequest search)
    {
        var ids = LocationCatalog.ForSearch(search).Where(row => row.Kind != "street").Select(row => row.Id).Distinct(StringComparer.Ordinal).ToArray();
        return new("search", ids.Length > 0, ids);
    }

    private static object SafeCard(object dto, string title, string description, string fallback)
    {
        // Legacy text predates contact validation. A new detail context must
        // not reveal contacts that its anonymous listing already suppresses.
        var fields = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(JsonSerializer.Serialize(dto, WebJson), WebJson)!;
        fields["title"] = JsonSerializer.SerializeToElement(PublicListings.Title(title, fallback));
        fields["description"] = JsonSerializer.SerializeToElement(PublicListings.Description(description));
        return fields;
    }

    public static string? PublicAddressUrl(Property property)
    {
        if (property.HideStreet || property.HideHouseNumber || string.IsNullOrWhiteSpace(property.Street) || string.IsNullOrWhiteSpace(property.HouseNumber)) return null;
        var place = LocationCatalog.ForProperty(property);
        if (place is null) return null;
        // Human-entered public address only. Google-derived coordinates/place
        // identifiers are never sent to another map provider or returned here.
        var query = $"{place.Label}, {property.Street.Trim()} {property.HouseNumber.Trim()}, Magyarország";
        return "https://www.google.com/maps/search/?api=1&query=" + Uri.EscapeDataString(query);
    }

    private static async Task<string?> SmallestNeighborhoodAsync(AppDb db, Guid propertyId, CancellationToken cancellationToken)
    {
        var connection = db.Database.GetDbConnection();
        if (connection.State != ConnectionState.Open) await db.Database.OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.Transaction = db.Database.CurrentTransaction?.GetDbTransaction();
        command.CommandTimeout = 30;
        command.CommandText = """
            SELECT area.`Id` FROM `PropertyNeighborhoods` membership
            JOIN `MatchingLocationAreas` area ON area.`Id`=CONVERT(membership.`NeighborhoodId` USING utf8mb4) COLLATE utf8mb4_bin
            WHERE membership.`PropertyId`=@property AND area.`Kind`='neighborhood'
            ORDER BY CASE WHEN ST_IsValid(area.`Boundary`) THEN
                COALESCE(NULLIF(ABS(ST_Area(area.`Boundary`)),0),ABS((area.`East`-area.`West`)*(area.`North`-area.`South`))*12364000000)
                ELSE ABS((area.`East`-area.`West`)*(area.`North`-area.`South`))*12364000000 END,area.`Id`
            LIMIT 1
            """;
        var parameter = command.CreateParameter(); parameter.ParameterName = "@property"; parameter.Value = propertyId.ToString("D"); command.Parameters.Add(parameter);
        var id = await command.ExecuteScalarAsync(cancellationToken) as string;
        return LocationCatalog.Get(id)?.Kind == "neighborhood" ? id : null;
    }
}
