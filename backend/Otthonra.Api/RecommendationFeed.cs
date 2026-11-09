using System.Linq.Expressions;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record RecommendationActive(string Kind, Guid Id);
public sealed record RecommendationResponse(RecommendationActive? Active, FeedItem[] Items, bool HasApproximate,
    bool RequiresApproximateConsent, string Stage, int SellerLikeCost, int LikeCost);

/// <summary>
/// SQL first removes foreign locations/types, archived/self/agent pairs and
/// previous decisions. Only ranking columns are streamed; the best 50 complete
/// cards are then fetched. No country-wide listing text/images are buffered.
/// </summary>
public static class RecommendationFeed
{
    public const int PageSize = 50;
    private sealed record Candidate(Property Property, SearchRequest Search, string PropertyOwnerType,
        string SearchOwnerType, bool LikedYou, MatchEvaluation Evaluation, CompiledSearch Prepared,
        decimal ValueForMoney, int Specificity);

    private sealed class CandidateRow
    {
        public Property? Property { get; init; }
        public SearchRequest? Search { get; init; }
        public string OwnerType { get; init; } = AccountTypes.Private;
        public bool LikedYou { get; init; }
    }

    // Returning a newly projected entity rather than the tracked table avoids
    // selecting free text, exact address or image JSON merely for ranking.
    private static readonly Expression<Func<Property, Property>> PropertyColumns = property => new Property {
        Id = property.Id, OwnerId = property.OwnerId, LocationId = property.LocationId,
        City = property.City, District = property.District, Type = property.Type,
        Price = property.Price, Area = property.Area, LotArea = property.LotArea, Rooms = property.Rooms,
        WholeRooms = property.WholeRooms, HalfRooms = property.HalfRooms, Floor = property.Floor,
        Condition = property.Condition, Building = property.Building, ConstructionAge = property.ConstructionAge,
        View = property.View, CeilingHeight = property.CeilingHeight, HeatingType = property.HeatingType,
        SecondaryHeatingType = property.SecondaryHeatingType, Insulated = property.Insulated,
        EnergyRating = property.EnergyRating, AirConditioning = property.AirConditioning,
        SolarPanels = property.SolarPanels, ParkingType = property.ParkingType, ParkingTypesJson = property.ParkingTypesJson,
        Balcony = property.Balcony, Elevator = property.Elevator, Archived = property.Archived
    };
    private static readonly Expression<Func<SearchRequest, SearchRequest>> SearchColumns = search => new SearchRequest {
        Id = search.Id, OwnerId = search.OwnerId, City = search.City, DistrictsJson = search.DistrictsJson,
        LocationIdsJson = search.LocationIdsJson, Type = search.Type,
        MinPrice = search.MinPrice, MaxPrice = search.MaxPrice, MinArea = search.MinArea, MaxArea = search.MaxArea,
        MinRooms = search.MinRooms, MaxRooms = search.MaxRooms, ConditionsJson = search.ConditionsJson,
        BuildingsJson = search.BuildingsJson, ConstructionAgesJson = search.ConstructionAgesJson,
        ViewsJson = search.ViewsJson, CeilingHeight = search.CeilingHeight, FloorsJson = search.FloorsJson,
        HeatingTypesJson = search.HeatingTypesJson, Balcony = search.Balcony, Elevator = search.Elevator,
        Archived = search.Archived
    };

    private sealed class BestCandidates(bool buyer)
    {
        private readonly List<Candidate> rows = [];
        private readonly IComparer<Candidate> order = Comparer<Candidate>.Create((left, right) => Compare(left, right, buyer));
        public void Add(Candidate candidate)
        {
            var index = rows.BinarySearch(candidate, order);
            if (index < 0) index = ~index;
            if (index >= PageSize) return;
            rows.Insert(index, candidate);
            if (rows.Count > PageSize) rows.RemoveAt(PageSize);
        }
        public Candidate[] Items => rows.ToArray();
    }

    private static int Compare(Candidate left, Candidate right, bool buyer)
    {
        // Buyers first compare match percentages, then incoming interest and
        // value. Sellers first compare incoming interest within the stage.
        var result = buyer ? right.Evaluation.Score.CompareTo(left.Evaluation.Score)
            : right.LikedYou.CompareTo(left.LikedYou);
        if (result != 0) return result;
        result = buyer ? right.LikedYou.CompareTo(left.LikedYou)
            : right.Evaluation.Score.CompareTo(left.Evaluation.Score);
        if (result != 0) return result;
        result = buyer ? right.ValueForMoney.CompareTo(left.ValueForMoney) : right.Specificity.CompareTo(left.Specificity);
        if (result != 0) return result;
        result = left.Property.Id.CompareTo(right.Property.Id);
        return result != 0 ? result : left.Search.Id.CompareTo(right.Search.Id);
    }

    public static async Task<RecommendationResponse> GetAsync(AppDb db, User user, bool includeApproximate = false,
        CancellationToken cancellationToken = default)
    {
        if (db.Database.CurrentTransaction is not null)
            return await BuildAsync(db, user, includeApproximate, cancellationToken);
        // The lean ranking scan and full-card fetch see the same row versions,
        // so a concurrent edit cannot combine an old 100% score with new data.
        await using var snapshot = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, cancellationToken);
        var result = await BuildAsync(db, user, includeApproximate, cancellationToken);
        await snapshot.CommitAsync(cancellationToken);
        return result;
    }

    private static async Task<RecommendationResponse> BuildAsync(AppDb db, User user, bool includeApproximate,
        CancellationToken cancellationToken)
    {
        var active = await ActiveAsync(db, user, cancellationToken);
        if (active.Property is null && active.Search is null)
            return new(null, [], false, false, "empty", Rules.SellerLikeCost, 0);
        var buyer = active.Search is not null;
        var exact = new BestCandidates(buyer); var approximate = new BestCandidates(buyer);
        await foreach (var candidate in CandidatesAsync(db, user, active.Property, active.Search, cancellationToken))
            if (candidate.Evaluation.IsExact) exact.Add(candidate); else approximate.Add(candidate);
        var exactItems = exact.Items;
        var approximateItems = approximate.Items;
        var selected = exactItems.Length > 0 ? exactItems : includeApproximate ? approximateItems : [];
        var stage = selected.Length == 0 ? "empty" : exactItems.Length > 0 ? "exact" : "approximate";
        var items = await CardsAsync(db, selected, buyer, cancellationToken);
        return new(new(buyer ? "search" : "property", buyer ? active.Search!.Id : active.Property!.Id), items,
            approximateItems.Length > 0, exactItems.Length == 0 && approximateItems.Length > 0 && !includeApproximate,
            stage, Rules.SellerLikeCost, AccountTypes.LikeCost(user.AccountType, user.ActiveKind));
    }

    public static async Task<bool> HasExactUnseenAsync(AppDb db, User user, CancellationToken cancellationToken = default)
    {
        var active = await ActiveAsync(db, user, cancellationToken);
        if (active.Property is null && active.Search is null) return false;
        await foreach (var candidate in CandidatesAsync(db, user, active.Property, active.Search, cancellationToken))
            if (candidate.Evaluation.IsExact) return true;
        return false;
    }

    /// <summary>Provider SQL for diagnostics/tests, without executing a database read.</summary>
    public static string CandidateQuerySql(AppDb db, User user, Property? property = null, SearchRequest? search = null)
    {
        if (search is not null) return BuyerCandidates(db, user, search, MatchingRanking.Prepare(search)).ToQueryString();
        if (property is not null) return SellerCandidates(db, user, property).ToQueryString();
        throw new ArgumentException("Supply an active property or search.");
    }

    private static async Task<(Property? Property, SearchRequest? Search)> ActiveAsync(AppDb db, User user, CancellationToken cancellationToken)
    {
        if (user.ActiveKind == "search")
            return (null, await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(search =>
                search.Id == user.ActiveEntityId && search.OwnerId == user.Id && !search.Archived, cancellationToken));
        if (user.ActiveKind == "property")
            return (await db.Properties.AsNoTracking().SingleOrDefaultAsync(property =>
                property.Id == user.ActiveEntityId && property.OwnerId == user.Id && !property.Archived, cancellationToken), null);
        return (null, null);
    }

    private static async IAsyncEnumerable<Candidate> CandidatesAsync(AppDb db, User user, Property? activeProperty,
        SearchRequest? activeSearch, [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        if (activeSearch is not null)
        {
            var prepared = MatchingRanking.Prepare(activeSearch);
            var specificity = prepared.Specificity;
            await foreach (var row in BuyerCandidates(db, user, activeSearch, prepared).AsAsyncEnumerable().WithCancellation(cancellationToken))
            {
                var property = row.Property!;
                var evaluation = MatchingRanking.Evaluate(property, prepared, includeReasons: false);
                if (evaluation.Eligible)
                    yield return new(property, activeSearch, row.OwnerType, user.AccountType, row.LikedYou, evaluation, prepared,
                        MatchingRanking.ValueForMoney(property), specificity);
            }
        }
        else if (activeProperty is not null)
        {
            var value = MatchingRanking.ValueForMoney(activeProperty);
            await foreach (var row in SellerCandidates(db, user, activeProperty).AsAsyncEnumerable().WithCancellation(cancellationToken))
            {
                var search = row.Search!;
                var prepared = MatchingRanking.Prepare(search);
                var evaluation = MatchingRanking.Evaluate(activeProperty, prepared, includeReasons: false);
                if (evaluation.Eligible)
                    yield return new(activeProperty, search, user.AccountType, row.OwnerType, row.LikedYou, evaluation, prepared, value, prepared.Specificity);
            }
        }
    }

    private static IQueryable<CandidateRow> BuyerCandidates(AppDb db, User user, SearchRequest search, CompiledSearch prepared)
    {
        var cities = prepared.Cities.Concat(prepared.DistrictIds.Select(id => LocationCatalog.Get(id)!.City)).Distinct().ToArray();
        var ids = LocationCatalog.All.Where(location => location.Kind != "area"
            && (prepared.Cities.Contains(location.City) || prepared.DistrictIds.Contains(location.Id))).Select(location => location.Id).ToArray();
        var budapest = cities.Contains("Budapest");
        var anyType = prepared.NormalizedType.Length == 0;
        var properties = db.Properties.AsNoTracking().Where(property => !property.Archived && property.OwnerId != user.Id
            && (anyType || property.Type == search.Type) && (ids.Contains(property.LocationId)
                || (property.LocationId == null || property.LocationId.Trim() == "")
                    && (cities.Contains(property.City) || budapest && property.City.StartsWith("Budapest ")))
            && !db.Decisions.Any(decision => decision.SearchRequestId == search.Id && decision.PropertyId == property.Id && decision.ActorKind == "search"));
        return from property in properties.Select(PropertyColumns)
            join owner in db.Users.AsNoTracking() on property.OwnerId equals owner.Id
            where user.AccountType != AccountTypes.Agent || owner.AccountType != AccountTypes.Agent
            select new CandidateRow { Property = property, OwnerType = owner.AccountType,
                LikedYou = db.Decisions.Any(decision => decision.PropertyId == property.Id && decision.SearchRequestId == search.Id
                    && decision.ActorKind == "property" && decision.Liked && decision.ActorUserId == property.OwnerId) };
    }

    private static readonly Lazy<Dictionary<string, string[]>> AreasByCity = new(() => {
        var rows = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        foreach (var area in LocationCatalog.All.Where(location => location.Kind == "area"))
            foreach (var city in MatchingRanking.Prepare(new SearchRequest { LocationIdsJson = JsonSerializer.Serialize(new[] { area.Id }) }).Cities)
            {
                if (!rows.TryGetValue(city, out var list)) rows[city] = list = [];
                list.Add(area.Id);
            }
        return rows.ToDictionary(row => row.Key, row => row.Value.ToArray(), StringComparer.Ordinal);
    });

    private static IQueryable<CandidateRow> SellerCandidates(AppDb db, User user, Property property)
    {
        var place = LocationCatalog.ForProperty(property);
        if (place is null) return db.SearchRequests.Where(search => false).Select(search => new CandidateRow { Search = search });
        var accepted = new List<string> { "city:" + place.City };
        if (place.Kind == "district") accepted.Add(place.Id);
        if (AreasByCity.Value.TryGetValue(place.City, out var areas)) accepted.AddRange(areas);
        var acceptedIds = accepted.Distinct(StringComparer.Ordinal).ToArray();
        // The location-first covering index selects local search IDs before
        // reading ranking columns; overlapping city/district/area choices must
        // still produce each search only once.
        var localIds = db.SearchLocations.AsNoTracking().Where(location => acceptedIds.Contains(location.LocationId))
            .Select(location => location.SearchRequestId).Distinct();
        var searches = db.SearchRequests.AsNoTracking().Where(search => !search.Archived
            && (search.Type == property.Type || search.Type == "") && search.OwnerId != user.Id
            && !db.Decisions.Any(decision => decision.PropertyId == property.Id
                && decision.SearchRequestId == search.Id && decision.ActorKind == "property"))
            .Join(localIds, search => search.Id, id => id, (search, id) => search);
        return from search in searches.Select(SearchColumns)
            join owner in db.Users.AsNoTracking() on search.OwnerId equals owner.Id
            where user.AccountType != AccountTypes.Agent || owner.AccountType != AccountTypes.Agent
            select new CandidateRow { Search = search, OwnerType = owner.AccountType,
                LikedYou = db.Decisions.Any(decision => decision.PropertyId == property.Id && decision.SearchRequestId == search.Id
                    && decision.ActorKind == "search" && decision.Liked && decision.ActorUserId == search.OwnerId) };
    }

    private static async Task<FeedItem[]> CardsAsync(AppDb db, Candidate[] candidates, bool buyer, CancellationToken cancellationToken)
    {
        if (candidates.Length == 0) return [];
        var propertyIds = candidates.Select(candidate => candidate.Property.Id).Distinct().ToArray();
        var searchIds = candidates.Select(candidate => candidate.Search.Id).Distinct().ToArray();
        var properties = await db.Properties.AsNoTracking().Where(property => propertyIds.Contains(property.Id)).ToDictionaryAsync(property => property.Id, cancellationToken);
        var searches = await db.SearchRequests.AsNoTracking().Where(search => searchIds.Contains(search.Id)).ToDictionaryAsync(search => search.Id, cancellationToken);
        return candidates.Select(candidate => new FeedItem(
            Dto.Property(properties[candidate.Property.Id], !buyer, candidate.PropertyOwnerType),
            Dto.Search(searches[candidate.Search.Id], candidate.SearchOwnerType), candidate.Property.Id, candidate.Search.Id,
            candidate.Evaluation.Score, MatchingRanking.Evaluate(properties[candidate.Property.Id], candidate.Prepared).Reasons,
            candidate.LikedYou, candidate.Evaluation.IsExact,
            candidate.ValueForMoney, candidate.Specificity)).ToArray();
    }
}
