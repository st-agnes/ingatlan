using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record RecommendationActive(string Kind, Guid Id);
public sealed record RecommendationResponse(RecommendationActive? Active, FeedItem[] Items, bool HasApproximate,
    bool RequiresApproximateConsent, string Stage, int SellerLikeCost, int LikeCost);

/// <summary>
/// MySQL filters, scores and orders the complete eligible candidate set. Only
/// the selected top fifty IDs/ranking values are read; full cards and detailed
/// explanations are fetched for those IDs in the same consistent snapshot.
/// </summary>
public static class RecommendationFeed
{
    public const int PageSize = 50;

    public static async Task<RecommendationResponse> GetAsync(AppDb db, User user, bool includeApproximate = false,
        CancellationToken cancellationToken = default)
    {
        if (db.Database.CurrentTransaction is not null)
            return await BuildAsync(db,user,includeApproximate,cancellationToken);
        await using var snapshot = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead,cancellationToken);
        var result = await BuildAsync(db,user,includeApproximate,cancellationToken);
        await snapshot.CommitAsync(cancellationToken);
        return result;
    }

    private static async Task<RecommendationResponse> BuildAsync(AppDb db, User user, bool includeApproximate,
        CancellationToken cancellationToken)
    {
        var active=await ActiveAsync(db,user,cancellationToken);
        if(active.Property is null && active.Search is null)
            return new(null,[],false,false,"empty",Rules.SellerLikeCost,0);
        var buyer=active.Search is not null;
        var selected=await RecommendationSql.SelectAsync(db,user,active.Property,active.Search,exact:true,cancellationToken);
        var stage=selected.Length>0?"exact":"empty";
        // Preserve the availability flag even while exact cards remain. The
        // existence query does not calculate spatial distance or rank partial
        // candidates; actual partial ranking still waits for exact exhaustion.
        var hasApproximate=false;
        if(selected.Length>0)
            hasApproximate=await RecommendationSql.ExistsAsync(db,user,active.Property,active.Search,exact:false,cancellationToken);
        else
        {
            if(includeApproximate)
            {
                selected=await RecommendationSql.SelectAsync(db,user,active.Property,active.Search,exact:false,cancellationToken);
                hasApproximate=selected.Length>0;
                if(hasApproximate)stage="approximate";
            }
            else hasApproximate=await RecommendationSql.ExistsAsync(db,user,active.Property,active.Search,exact:false,cancellationToken);
        }
        var items=await CardsAsync(db,selected,buyer,cancellationToken);
        return new(new(buyer?"search":"property",buyer?active.Search!.Id:active.Property!.Id),items,
            hasApproximate,stage=="empty"&&hasApproximate&&!includeApproximate,stage,Rules.SellerLikeCost,
            AccountTypes.LikeCost(user.AccountType,user.ActiveKind));
    }

    public static async Task<bool> HasExactUnseenAsync(AppDb db, User user, CancellationToken cancellationToken=default)
    {
        var active=await ActiveAsync(db,user,cancellationToken);
        return (active.Property is not null || active.Search is not null)
            && await RecommendationSql.ExistsAsync(db,user,active.Property,active.Search,exact:true,cancellationToken);
    }

    /// <summary>Parameterized final-ranking SQL for diagnostics/tests, without reading the database.</summary>
    public static string CandidateQuerySql(AppDb db, User user, Property? property=null, SearchRequest? search=null) =>
        RecommendationSql.Build(user,property,search).Text;

    private static async Task<(Property? Property,SearchRequest? Search)> ActiveAsync(AppDb db,User user,CancellationToken cancellationToken)
    {
        if(user.ActiveKind=="search")return(null,await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(search=>
            search.Id==user.ActiveEntityId&&search.OwnerId==user.Id&&!search.Archived,cancellationToken));
        if(user.ActiveKind=="property")return(await db.Properties.AsNoTracking().SingleOrDefaultAsync(property=>
            property.Id==user.ActiveEntityId&&property.OwnerId==user.Id&&!property.Archived,cancellationToken),null);
        return(null,null);
    }

    private static async Task<FeedItem[]> CardsAsync(AppDb db,RecommendationSql.RankedPair[] candidates,bool buyer,CancellationToken cancellationToken)
    {
        if(candidates.Length==0)return [];
        var propertyIds=candidates.Select(candidate=>candidate.PropertyId).Distinct().ToArray();
        var searchIds=candidates.Select(candidate=>candidate.SearchRequestId).Distinct().ToArray();
        var properties=await db.Properties.AsNoTracking().Where(property=>propertyIds.Contains(property.Id)).ToDictionaryAsync(property=>property.Id,cancellationToken);
        var searches=await db.SearchRequests.AsNoTracking().Where(search=>searchIds.Contains(search.Id)).ToDictionaryAsync(search=>search.Id,cancellationToken);
        var ownerIds=properties.Values.Select(property=>property.OwnerId).Concat(searches.Values.Select(search=>search.OwnerId)).Distinct().ToArray();
        var owners=await db.Users.AsNoTracking().Where(owner=>ownerIds.Contains(owner.Id))
            .Select(owner=>new{owner.Id,owner.Name,owner.AccountType}).ToDictionaryAsync(owner=>owner.Id,cancellationToken);
        var prepared=searches.Values.ToDictionary(search=>search.Id,search=>MatchingRanking.Prepare(search,sellerPerspective:!buyer));
        return candidates.Select(candidate=>{
            var property=properties[candidate.PropertyId];var search=searches[candidate.SearchRequestId];
            var seller=owners[property.OwnerId];var seeker=owners[search.OwnerId];
            var evaluation=MatchingRanking.Evaluate(property,prepared[search.Id],locationDistanceKm:candidate.LocationDistanceKm);
            return new FeedItem(Dto.Property(property,!buyer,seller.AccountType,seller.Name),
                Dto.Search(search,seeker.AccountType,seeker.Name,own:buyer),property.Id,search.Id,
                candidate.Score,evaluation.Reasons,candidate.LikedYou,candidate.IsExact,candidate.ValueForMoney,candidate.Specificity,evaluation.MatchDetails);
        }).ToArray();
    }
}
