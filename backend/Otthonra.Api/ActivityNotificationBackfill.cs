using System.Data;
using System.Data.Common;
using System.Security.Cryptography;
using System.Text;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>Bounded, restart-safe historical receipts; never runs from a request or account refresh.</summary>
public static class ActivityNotificationBackfill
{
    public static async Task RunAsync(AppDb db, string scope, CancellationToken ct = default)
    {
        var connection = db.Database.GetDbConnection(); var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(ct);
        var lockName = "otthonra-notices-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
        // Hash the deployment identity so arbitrarily long platform names cannot truncate the marker.
        var version = ActivityNotifications.Version + ":" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(scope)));
        var acquired = false;
        try
        {
            acquired = Convert.ToInt32(await Command(connection, "SELECT GET_LOCK(@name, 120)", ct, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the activity notification backfill lock.");
            await Command(connection, "CREATE TABLE IF NOT EXISTS `__OtthonraNotificationBackfills` (`Version` varchar(200) NOT NULL PRIMARY KEY, `AppliedAt` datetime(6) NOT NULL)", ct);
            if (Convert.ToInt32(await Command(connection, "SELECT COUNT(*) FROM `__OtthonraNotificationBackfills` WHERE `Version`=@version", ct, ("version", version))) != 0) return;

            async Task Pairs<T>(string table, string filter, Func<T, Guid> propertyId, Func<T, Guid> searchId,
                Func<T, Property, SearchRequest, IReadOnlyDictionary<Guid, User>, IEnumerable<UserNotification>> make) where T : class
            {
                await Pages<T>(db, table, filter, async rows => {
                    var pids = rows.Select(propertyId).Distinct().ToArray(); var sids = rows.Select(searchId).Distinct().ToArray();
                    var properties = await db.Properties.AsNoTracking().Where(p => pids.Contains(p.Id)).ToDictionaryAsync(p => p.Id, ct);
                    var searches = await db.SearchRequests.AsNoTracking().Where(s => sids.Contains(s.Id)).ToDictionaryAsync(s => s.Id, ct);
                    var uids = properties.Values.Select(p => p.OwnerId).Concat(searches.Values.Select(s => s.OwnerId)).Distinct().ToArray();
                    var users = await db.Users.AsNoTracking().Where(u => uids.Contains(u.Id)).ToDictionaryAsync(u => u.Id, ct);
                    return rows.Where(row => properties.ContainsKey(propertyId(row)) && searches.ContainsKey(searchId(row)))
                        .SelectMany(row => make(row, properties[propertyId(row)], searches[searchId(row)], users)).ToArray();
                }, ct);
            }
            await Pairs<Decision>("Decisions", "`Liked`=TRUE", d => d.PropertyId, d => d.SearchRequestId, (d, p, s, users) =>
                p.OwnerId != s.OwnerId && (d.ActorKind == "property" && d.ActorUserId == p.OwnerId || d.ActorKind == "search" && d.ActorUserId == s.OwnerId)
                    ? new[] { ActivityNotifications.IncomingLike(d, p, s, users.GetValueOrDefault(d.ActorUserId)?.Name ?? "") } : []);
            await Pairs<Match>("Matches", "TRUE", m => m.PropertyId, m => m.SearchRequestId,
                (m, p, s, _) => ActivityNotifications.MatchCreated(m, p, s));
            await Pages<Message>(db, "Messages", "TRUE", async rows => {
                var ids = rows.Select(row => row.MatchId).Distinct().ToArray();
                var pairs = await (from m in db.Matches.AsNoTracking() join p in db.Properties.AsNoTracking() on m.PropertyId equals p.Id
                    join s in db.SearchRequests.AsNoTracking() on m.SearchRequestId equals s.Id where ids.Contains(m.Id)
                    select new { Match = m, Property = p, Search = s }).ToDictionaryAsync(row => row.Match.Id, ct);
                return rows.Where(row => pairs.TryGetValue(row.MatchId, out var pair) && pair.Property.OwnerId != pair.Search.OwnerId
                    && (row.SenderId == pair.Property.OwnerId || row.SenderId == pair.Search.OwnerId))
                    .Select(row => { var pair = pairs[row.MatchId]; return ActivityNotifications.MessageReceived(row, pair.Match, pair.Property, pair.Search); }).ToArray();
            }, ct);
            await Pages<FeedbackInvitation>(db, "FeedbackInvitations", "`AnsweredAt` IS NOT NULL AND `Reason` IS NOT NULL AND `Reason` <> 'decline'", async rows => {
                var ids = rows.Select(row => row.PackageId).Distinct().ToArray();
                var packages = await (from package in db.FeedbackPackages.AsNoTracking() join p in db.Properties.AsNoTracking() on package.PropertyId equals p.Id
                    where ids.Contains(package.Id) select new { Package = package, Property = p }).ToDictionaryAsync(row => row.Package.Id, ct);
                return rows.Where(row => packages.ContainsKey(row.PackageId)).Select(row => {
                    var pair = packages[row.PackageId]; return ActivityNotifications.FeedbackReceived(row, pair.Package, pair.Property);
                }).ToArray();
            }, ct);
            await Pages<FeedbackPackage>(db, "FeedbackPackages", "`ReceivedCount` >= `Size` OR `RefundedAt` IS NOT NULL", async rows => {
                var ids = rows.Select(row => row.PropertyId).Distinct().ToArray();
                var properties = await db.Properties.AsNoTracking().Where(p => ids.Contains(p.Id)).ToDictionaryAsync(p => p.Id, ct);
                var packageIds = rows.Select(row => row.Id).ToArray();
                var completed = await db.FeedbackInvitations.AsNoTracking().Where(i => packageIds.Contains(i.PackageId) && i.AnsweredAt != null && i.Reason != SellerFeedbackPolicy.Decline)
                    .GroupBy(i => i.PackageId).Select(g => new { Id = g.Key, At = g.Max(i => i.AnsweredAt) }).ToDictionaryAsync(x => x.Id, x => x.At, ct);
                return rows.Where(row => properties.ContainsKey(row.PropertyId)).SelectMany(row => {
                    var receipts = new List<UserNotification>(); var p = properties[row.PropertyId];
                    if (row.ReceivedCount >= row.Size) receipts.Add(ActivityNotifications.FeedbackCompleted(row, p, completed.GetValueOrDefault(row.Id) ?? row.CreatedAt));
                    if (row.RefundedAt is { } at) receipts.Add(ActivityNotifications.FeedbackExpired(row, p, at));
                    return receipts;
                }).ToArray();
            }, ct);
            await Pages<CreditEntry>(db, "CreditEntries", "`Amount` > 0 AND `RefundedDecisionId` IS NULL AND `RefundedFeedbackPackageId` IS NULL",
                rows => Task.FromResult<IEnumerable<UserNotification>>(rows.Select(ActivityNotifications.CreditAdded).ToArray()), ct);

            // Preserve old receipt IDs, text and first-read timestamps while attaching safe destinations.
            string cursor = "";
            while (true)
            {
                var rows = await db.UserNotifications.FromSqlInterpolated($"SELECT * FROM `UserNotifications` WHERE `Id` > {cursor} AND `EventKey` IS NULL ORDER BY `Id` LIMIT 100").AsNoTracking().ToListAsync(ct);
                if (rows.Count == 0) break;
                foreach (var row in rows)
                {
                    if (row.Kind == "like_refund" && row.DecisionId is { } did)
                    {
                        var d = await db.Decisions.AsNoTracking().SingleOrDefaultAsync(x => x.Id == did && x.ActorUserId == row.UserId, ct);
                        if (d is null) continue;
                        row.EventKey = "like_refund:" + did; row.EntityKind = d.ActorKind;
                        row.EntityId = d.ActorKind == "property" ? d.PropertyId : d.SearchRequestId; row.PropertyId = d.PropertyId; row.SearchRequestId = d.SearchRequestId;
                    }
                    else if (row.Kind == "feedback_refund" && row.FeedbackPackageId is { } pid)
                    {
                        var p = await db.FeedbackPackages.AsNoTracking().SingleOrDefaultAsync(x => x.Id == pid && x.OwnerId == row.UserId, ct);
                        if (p is null) continue;
                        row.EventKey = "feedback_refund:" + pid; row.EntityKind = "property"; row.EntityId = row.PropertyId = p.PropertyId;
                    }
                    else continue;
                    await db.Database.ExecuteSqlInterpolatedAsync($"UPDATE `UserNotifications` SET `EventKey`={row.EventKey},`EntityKind`={row.EntityKind},`EntityId`={row.EntityId},`PropertyId`={row.PropertyId},`SearchRequestId`={row.SearchRequestId} WHERE `Id`={row.Id} AND `EventKey` IS NULL", ct);
                }
                cursor = rows[^1].Id.ToString("D");
            }
            await Command(connection, "INSERT IGNORE INTO `__OtthonraNotificationBackfills` (`Version`,`AppliedAt`) VALUES (@version,UTC_TIMESTAMP(6))", ct, ("version", version));
        }
        finally
        {
            if (acquired) await Command(connection, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName));
            if (openedHere) await db.Database.CloseConnectionAsync();
        }
    }

    private static async Task Pages<T>(AppDb db, string table, string filter,
        Func<List<T>, Task<IEnumerable<UserNotification>>> make, CancellationToken ct) where T : class
    {
        string cursor = "";
        while (true)
        {
            // Table/filter are fixed internal literals; the cursor is always a bound parameter.
            var rows = await db.Set<T>().FromSqlRaw($"SELECT * FROM `{table}` WHERE `Id` > {{0}} AND ({filter}) ORDER BY `Id` LIMIT 100", cursor).AsNoTracking().ToListAsync(ct);
            if (rows.Count == 0) return;
            await InsertAsync(db.Database.GetDbConnection(), await make(rows), ct);
            cursor = ((Guid)typeof(T).GetProperty("Id")!.GetValue(rows[^1])!).ToString("D");
        }
    }
    // A multi-value insert obtains shared User FK locks in VALUES order. Match the
    // live event handlers' ordered account locks even when source IDs arrive in
    // another order, so a historical batch cannot invert those account locks.
    public static IEnumerable<UserNotification> OrderByRecipient(IEnumerable<UserNotification> receipts) => receipts
        .OrderBy(row => row.UserId.ToString("D"), StringComparer.Ordinal)
        .ThenBy(row => row.EventKey, StringComparer.Ordinal)
        .ThenBy(row => row.Id.ToString("D"), StringComparer.Ordinal);

    private static async Task InsertAsync(DbConnection connection, IEnumerable<UserNotification> receipts, CancellationToken ct)
    {
        var rows = OrderByRecipient(receipts).ToArray(); if (rows.Length == 0) return;
        await using var command = connection.CreateCommand();
        var values = new List<string>();
        foreach (var row in rows)
        {
            var data = new object?[] { row.Id.ToString("D"), row.UserId.ToString("D"), row.EventKey, row.Kind, row.Amount, row.Text, row.CreatedAt,
                row.EntityKind, row.EntityId?.ToString("D"), row.PropertyId?.ToString("D"), row.SearchRequestId?.ToString("D"), row.MatchId?.ToString("D") };
            var names = new List<string>();
            foreach (var value in data)
            {
                var parameter = command.CreateParameter(); parameter.ParameterName = "@p" + command.Parameters.Count; parameter.Value = value ?? DBNull.Value;
                command.Parameters.Add(parameter); names.Add(parameter.ParameterName);
            }
            values.Add("(" + string.Join(',', names) + ")");
        }
        // Concurrent cold starts/source transactions may already have written the same unique event.
        // IGNORE preserves that receipt and its read state instead of replacing it.
        command.CommandText = "INSERT IGNORE INTO `UserNotifications` (`Id`,`UserId`,`EventKey`,`Kind`,`Amount`,`Text`,`CreatedAt`,`EntityKind`,`EntityId`,`PropertyId`,`SearchRequestId`,`MatchId`) VALUES " + string.Join(',', values);
        await command.ExecuteNonQueryAsync(ct);
    }
    private static async Task<object?> Command(DbConnection connection, string sql, CancellationToken ct, params (string Name, object Value)[] args)
    {
        await using var command = connection.CreateCommand(); command.CommandText = sql;
        foreach (var (name, value) in args) { var p = command.CreateParameter(); p.ParameterName = "@" + name; p.Value = value; command.Parameters.Add(p); }
        return await command.ExecuteScalarAsync(ct);
    }
}
