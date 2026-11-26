using System.Data;
using System.Security.Claims;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record ListingProfileOption(ListingActiveSummary Profile, int Score, bool IsExact,
    bool Compatible, bool IsActive);
public sealed record ListingProfileOptionsPage(string Kind, ListingProfileOption[] Items, int Total,
    int Offset, int Limit, bool HasMore, string? UnavailableReason = null);

/// <summary>Read-only, owner-scoped profile choices for one public counterpart.</summary>
public static class ListingProfileOptions
{
    public static (int Offset, int Limit) Page(int? offset, int? limit)
    {
        var start = offset ?? 0; var count = limit ?? 50;
        if (start is < 0 or > 1_000_000 || count is < 1 or > 50)
            throw new ApiException(400, "Érvénytelen lapozási beállítás.");
        return (start, count);
    }

    public static IEndpointRouteBuilder MapListingProfileOptionsEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/listings/{kind}/{key}/profiles", async Task<IResult>
            (string kind, string key, int? offset, int? limit, AppDb db, ClaimsPrincipal principal,
                HttpContext context, CancellationToken cancellationToken) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (!PublicListings.ValidKey(kind, key)) return Results.NotFound();
            var page = Page(offset, limit);
            var opposite = kind == "property" ? "search" : "property";
            await using var snapshot = await db.Database.BeginTransactionAsync(IsolationLevel.RepeatableRead, cancellationToken);
            var user = await db.Users.AsNoTracking().SingleAsync(row => row.Id == principal.UserId(), cancellationToken);
            Property? targetProperty = null; SearchRequest? targetSearch = null; User? targetOwner;
            if (kind == "property")
            {
                targetProperty = await db.Properties.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
                targetOwner = targetProperty is null ? null : await db.Users.AsNoTracking().SingleOrDefaultAsync(row => row.Id == targetProperty.OwnerId, cancellationToken);
                if (targetProperty is null || targetOwner is null || PublicListings.Property(targetProperty, targetOwner.AccountType, targetOwner.Name) is null) return Results.NotFound();
            }
            else
            {
                targetSearch = await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(row => row.PublicListingKey == key && !row.Archived, cancellationToken);
                targetOwner = targetSearch is null ? null : await db.Users.AsNoTracking().SingleOrDefaultAsync(row => row.Id == targetSearch.OwnerId, cancellationToken);
                if (targetSearch is null || targetOwner is null || PublicListings.Search(targetSearch, targetOwner.AccountType, targetOwner.Name) is null) return Results.NotFound();
            }
            ListingProfileOptionsPage Empty(string reason) => new(opposite, [], 0, page.Offset, page.Limit, false, reason);
            if (targetOwner.Id == user.Id) return Results.Ok(Empty("own_listing"));
            if (!AccountTypes.CanInteract(user.AccountType, targetOwner.AccountType)) return Results.Ok(Empty("agent_pair_forbidden"));

            int total; ListingProfileOption[] items;
            if (kind == "property")
            {
                var owned = db.SearchRequests.AsNoTracking().Where(row => row.OwnerId == user.Id && !row.Archived);
                total = await owned.CountAsync(cancellationToken);
                var rows = await owned.OrderByDescending(row => user.ActiveKind == "search" && row.Id == user.ActiveEntityId)
                    .ThenBy(row => row.Title).ThenBy(row => row.Id).Skip(page.Offset).Take(page.Limit).ToArrayAsync(cancellationToken);
                var evaluated = await MatchingPairEvaluation.EvaluateManyAsync(db,
                    rows.Select(row => (Property: targetProperty!, Search: row)), includeReasons: false,
                    cancellationToken: cancellationToken);
                items = rows.Select(row => Option(PublicListingContext.ActiveSummary(null, row)!,
                    evaluated[(targetProperty!.Id, row.Id)], user.ActiveKind, user.ActiveEntityId)).ToArray();
            }
            else
            {
                var owned = db.Properties.AsNoTracking().Where(row => row.OwnerId == user.Id && !row.Archived);
                total = await owned.CountAsync(cancellationToken);
                var rows = await owned.OrderByDescending(row => user.ActiveKind == "property" && row.Id == user.ActiveEntityId)
                    .ThenBy(row => row.Title).ThenBy(row => row.Id).Skip(page.Offset).Take(page.Limit).ToArrayAsync(cancellationToken);
                var evaluated = await MatchingPairEvaluation.EvaluateManyAsync(db,
                    rows.Select(row => (Property: row, Search: targetSearch!)), sellerPerspective: true,
                    includeReasons: false, cancellationToken: cancellationToken);
                items = rows.Select(row => Option(PublicListingContext.ActiveSummary(row, null)!,
                    evaluated[(row.Id, targetSearch!.Id)], user.ActiveKind, user.ActiveEntityId)).ToArray();
            }
            await snapshot.CommitAsync(cancellationToken);
            return Results.Ok(new ListingProfileOptionsPage(opposite, items, total, page.Offset, page.Limit,
                page.Offset + items.Length < total));
        }).RequireAuthorization();
        return endpoints;
    }

    public static ListingProfileOption Option(ListingActiveSummary profile, MatchEvaluation evaluation,
        string? activeKind, Guid? activeId) => new(profile, evaluation.Eligible ? evaluation.Score : 0,
            evaluation.Eligible && evaluation.IsExact, evaluation.Eligible,
            profile.Kind == activeKind && profile.Id == activeId);
}
