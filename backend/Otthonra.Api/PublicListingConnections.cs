using System.Security.Claims;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record ListingConnectionContact(Guid Id, string Name, string Email, string Phone, string AccountType);
public sealed record ListingConnectionProfile(Guid Id, string Title, string PublicListingKey);
public sealed record ListingConnection(bool Connected, Guid? MatchId = null, ListingConnectionContact? Contact = null,
    ListingConnectionProfile? Property = null, ListingConnectionProfile? SearchRequest = null);
public sealed record ListingConnectionRow(Guid MatchId, DateTime CreatedAt,
    Guid PropertyId, string PropertyTitle, string? PropertyKey,
    Guid SearchRequestId, string SearchTitle, string? SearchKey,
    Guid ContactId, string ContactName, string Email, string Phone, string AccountType);

/// <summary>Existing contact access belongs to the viewed matched pair, independently of the active profile.</summary>
public static class PublicListingConnections
{
    public static IEndpointRouteBuilder MapListingConnectionEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/listings/{kind}/{key}/connection", async Task<IResult>
            (string kind, string key, AppDb db, ClaimsPrincipal principal, HttpContext context, CancellationToken cancellationToken) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (!PublicListings.ValidKey(kind, key)) return Results.NotFound();
            Guid? listingId = kind == "property"
                ? await db.Properties.AsNoTracking().Where(row => row.PublicListingKey == key && !row.Archived)
                    .Select(row => (Guid?)row.Id).SingleOrDefaultAsync(cancellationToken)
                : await db.SearchRequests.AsNoTracking().Where(row => row.PublicListingKey == key && !row.Archived)
                    .Select(row => (Guid?)row.Id).SingleOrDefaultAsync(cancellationToken);
            if (listingId is null) return Results.NotFound();
            // No recommendations, geometry, message history or mutable active
            // state is needed. Read at most one authorized existing match.
            var row = await ForListing(db.Matches.AsNoTracking(), db.Properties.AsNoTracking(), db.SearchRequests.AsNoTracking(),
                db.Users.AsNoTracking(), principal.UserId(), kind, listingId.Value).FirstOrDefaultAsync(cancellationToken);
            return Results.Ok(From(row));
        }).RequireAuthorization();
        return endpoints;
    }

    public static IQueryable<ListingConnectionRow> ForListing(IQueryable<Match> matches, IQueryable<Property> properties,
        IQueryable<SearchRequest> searches, IQueryable<User> users, Guid viewerId, string kind, Guid listingId)
    {
        // The entity on the viewer's side may be archived: a deletion must not
        // erase an already established conversation. The viewed foreign entity
        // must still be live. Never grant access based on owner identity alone.
        return from match in matches
            join property in properties on match.PropertyId equals property.Id
            join search in searches on match.SearchRequestId equals search.Id
            join contact in users on (kind == "property" ? property.OwnerId : search.OwnerId) equals contact.Id
            where property.OwnerId != search.OwnerId && contact.Id != viewerId
                && (kind == "property" && property.Id == listingId && !property.Archived && search.OwnerId == viewerId
                    || kind == "search" && search.Id == listingId && !search.Archived && property.OwnerId == viewerId)
            orderby match.CreatedAt descending, match.Id descending
            select new ListingConnectionRow(match.Id, match.CreatedAt,
                property.Id, property.Title, property.PublicListingKey, search.Id, search.Title, search.PublicListingKey,
                contact.Id, contact.Name, contact.Email, contact.Phone, contact.AccountType);
    }

    public static ListingConnection From(ListingConnectionRow? row) => row is null ? new(false) : new(true, row.MatchId,
        new(row.ContactId, row.ContactName, row.Email, row.Phone, row.AccountType),
        new(row.PropertyId, PublicListings.Title(row.PropertyTitle, "Eladó ingatlan"), row.PropertyKey ?? PublicLanding.SourceKey("property", row.PropertyId)),
        new(row.SearchRequestId, PublicListings.Title(row.SearchTitle, "Keresési igény"), row.SearchKey ?? PublicLanding.SourceKey("search", row.SearchRequestId)));
}
