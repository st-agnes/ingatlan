using System.Data;
using System.Data.Common;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>
/// Authoritative pair evaluation for incoming interest and direct decisions.
/// Existing exact location identities need no geometry query. Outside pairs
/// share a bounded database query for minimum distance to any nonstreet choice.
/// The caller remains responsible for user/agent/action authorization.
/// </summary>
public static class MatchingPairEvaluation
{
    private const int BatchSize = 100;
    private sealed record Pending(Property Property, SearchRequest Search, CompiledSearch Prepared);

    public static async Task<MatchEvaluation> EvaluateAsync(AppDb db, Property property, SearchRequest search,
        bool sellerPerspective = false, bool includeReasons = true, CancellationToken cancellationToken = default)
    {
        var results = await EvaluateManyAsync(db, new[] { (Property: property, Search: search) }, sellerPerspective, includeReasons, cancellationToken);
        return results[(property.Id, search.Id)];
    }

    public static async Task<Dictionary<(Guid PropertyId, Guid SearchRequestId), MatchEvaluation>> EvaluateManyAsync(
        AppDb db, IEnumerable<(Property Property, SearchRequest Search)> pairs,
        bool sellerPerspective = false, bool includeReasons = true, CancellationToken cancellationToken = default)
    {
        var results = new Dictionary<(Guid PropertyId, Guid SearchRequestId), MatchEvaluation>();
        var pending = new Dictionary<(Guid PropertyId, Guid SearchRequestId), Pending>();
        var prepared = new Dictionary<SearchRequest, CompiledSearch>(ReferenceEqualityComparer.Instance);
        foreach (var (property, search) in pairs)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!prepared.TryGetValue(search, out var compiled))
                prepared.Add(search, compiled = MatchingRanking.Prepare(search, sellerPerspective));
            var key = (property.Id, search.Id);
            // Duplicate IDs describe a single persisted pair; the latest supplied
            // objects consistently replace both its immediate and deferred value.
            pending.Remove(key);
            results[key] = MatchingRanking.Evaluate(property, compiled, includeReasons);
            if (!MatchingRanking.BaseEligible(property, compiled) || MatchingRanking.ExactLocation(property, compiled)
                || !compiled.HasNonStreetLocations || !ValidCoordinates(property)) continue;
            pending[key] = new(property, search, compiled);
        }
        if (pending.Count == 0) return results;

        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        try
        {
            foreach (var batch in pending.Values.Chunk(BatchSize))
            {
                cancellationToken.ThrowIfCancellationRequested();
                await using var command = connection.CreateCommand();
                command.Transaction = db.Database.CurrentTransaction?.GetDbTransaction();
                command.CommandTimeout = 60;
                var requested = new List<string>(batch.Length);
                for (var index = 0; index < batch.Length; index++)
                {
                    Parameter(command, "property" + index, batch[index].Property.Id.ToString("D"));
                    Parameter(command, "search" + index, batch[index].Search.Id.ToString("D"));
                    requested.Add($"SELECT @property{index} AS PropertyId,@search{index} AS SearchRequestId");
                }
                // The same maintained point index is authoritative for feeds
                // and actions; a missing point never creates an action-only
                // nearby candidate. All geometry stays on the server.
                command.CommandText = """
                    WITH requested AS (
                    """ + string.Join(" UNION ALL ", requested) + """
                    )
                    SELECT requested.PropertyId,requested.SearchRequestId,
                        MIN(ST_Distance(pp.`Position`,area.`Boundary`))/1000.0 AS DistanceKm
                    FROM requested
                    JOIN `Properties` p ON p.`Id`=requested.PropertyId AND p.`Archived`=0
                    JOIN `SearchRequests` s ON s.`Id`=requested.SearchRequestId AND s.`Archived`=0
                    JOIN `MatchingPropertyPoints` pp ON pp.`PropertyId`=p.`Id`
                    JOIN `SearchLocations` location ON location.`SearchRequestId`=s.`Id`
                    JOIN `MatchingLocationMembers` lm ON lm.`SelectionId`=location.`LocationId`
                    JOIN `MatchingLocationAreas` area ON area.`Id`=lm.`AreaId`
                    GROUP BY requested.PropertyId,requested.SearchRequestId
                    """;
                var distances = new Dictionary<(Guid PropertyId, Guid SearchRequestId), double>(batch.Length);
                await using (var reader = await command.ExecuteReaderAsync(cancellationToken))
                    while (await reader.ReadAsync(cancellationToken))
                    {
                        if (reader.IsDBNull(2)) continue;
                        var distance = Convert.ToDouble(reader.GetValue(2));
                        if (double.IsFinite(distance) && distance >= 0)
                            distances[(reader.GetGuid(0), reader.GetGuid(1))] = distance;
                    }
                foreach (var item in batch)
                {
                    var key = (item.Property.Id, item.Search.Id);
                    if (distances.TryGetValue(key, out var distance))
                        results[key] = MatchingRanking.Evaluate(item.Property, item.Prepared, includeReasons, locationDistanceKm: distance);
                    // Missing point/target rows retain the scorer's ineligible
                    // result; a nearby result is never invented from a city name.
                }
            }
        }
        finally { if (openedHere) await db.Database.CloseConnectionAsync(); }
        return results;
    }

    private static bool ValidCoordinates(Property property) => property.Latitude is { } latitude && property.Longitude is { } longitude
        && double.IsFinite(latitude) && double.IsFinite(longitude) && latitude is >= -90 and <= 90 && longitude is > -180 and <= 180;

    private static void Parameter(DbCommand command, string name, object value)
    {
        var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value;
        command.Parameters.Add(parameter);
    }
}
