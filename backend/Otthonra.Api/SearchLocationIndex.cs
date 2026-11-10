using System.Data;
using System.Data.Common;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>One indexed row per canonical selected location, including compact area IDs.</summary>
public sealed class SearchLocation
{
    public Guid SearchRequestId { get; set; }
    public string LocationId { get; set; } = "";
}

public static class SearchLocationIndex
{
    public const string InvalidLocation = "@invalid";

    public static string[] SelectedIds(SearchRequest search)
    {
        try
        {
            var ids = LocationCatalog.ForSearch(search).Select(location => location.Id).Distinct(StringComparer.Ordinal).ToArray();
            return ids.Length is > 0 and <= 50 ? ids : [InvalidLocation];
        }
        catch (JsonException) { return [InvalidLocation]; }
    }

    private static EntityEntry<SearchRequest>[] Pending(AppDb db)
    {
        db.ChangeTracker.DetectChanges();
        return db.ChangeTracker.Entries<SearchRequest>().Where(entry => entry.State is EntityState.Added or EntityState.Deleted
            || entry.State == EntityState.Modified && new[] { nameof(SearchRequest.LocationIdsJson), nameof(SearchRequest.City), nameof(SearchRequest.DistrictsJson) }
                .Any(name => entry.Property(name).IsModified)).ToArray();
    }

    /// <summary>
    /// Existing-search edits lock their parent rows before the single old-links
    /// query. The principal update and key diffs commit together. New searches
    /// need no read and use SaveChanges' ordinary implicit transaction.
    /// </summary>
    public static async Task<int> SaveAsync(AppDb db, Func<Task<int>> save, CancellationToken cancellationToken)
    {
        var pending = Pending(db);
        if (pending.Length == 0) return await save().ConfigureAwait(false);
        var existingIds = pending.Where(entry => entry.State != EntityState.Added).Select(entry => entry.Entity.Id).Distinct().Order().ToArray();
        IDbContextTransaction? owned = null;
        try
        {
            if (existingIds.Length > 0)
            {
                if (db.Database.CurrentTransaction is null)
                    owned = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken).ConfigureAwait(false);
                await LockParentsAsync(db, existingIds, cancellationToken).ConfigureAwait(false);
                // Locking current read also stays correct inside a caller's
                // RepeatableRead transaction that has an earlier snapshot.
                var slots = string.Join(",", existingIds.Select((_, index) => "{" + index + "}"));
                var query = System.Runtime.CompilerServices.FormattableStringFactory.Create(
                    "SELECT * FROM `SearchLocations` WHERE `SearchRequestId` IN (" + slots + ") FOR UPDATE",
                    existingIds.Select(id => (object)id).ToArray());
                _ = await db.SearchLocations.FromSqlInterpolated(query).ToListAsync(cancellationToken).ConfigureAwait(false);
            }
            Apply(db, pending);
            var count = await save().ConfigureAwait(false);
            if (owned is not null) await owned.CommitAsync(cancellationToken).ConfigureAwait(false);
            return count;
        }
        finally
        {
            if (owned is not null) await owned.DisposeAsync().ConfigureAwait(false);
        }
    }

    private static async Task LockParentsAsync(AppDb db, Guid[] ids, CancellationToken cancellationToken)
    {
        var connection = db.Database.GetDbConnection();
        await using var command = connection.CreateCommand();
        command.Transaction = db.Database.CurrentTransaction!.GetDbTransaction();
        command.CommandTimeout = 30;
        var names = new List<string>();
        for (var index = 0; index < ids.Length; index++)
        {
            var parameter = command.CreateParameter(); parameter.ParameterName = "@search" + index;
            parameter.Value = ids[index].ToString("D"); command.Parameters.Add(parameter); names.Add(parameter.ParameterName);
        }
        command.CommandText = "SELECT `Id` FROM `SearchRequests` WHERE `Id` IN (" + string.Join(",", names) + ") ORDER BY `Id` FOR UPDATE";
        await using var reader = await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false)) { }
    }

    private static void Apply(AppDb db, EntityEntry<SearchRequest>[] pending)
    {
        var ids = pending.Select(entry => entry.Entity.Id).ToHashSet();
        var tracked = db.ChangeTracker.Entries<SearchLocation>().Where(entry => ids.Contains(entry.Entity.SearchRequestId))
            .GroupBy(entry => entry.Entity.SearchRequestId).ToDictionary(group => group.Key, group => group.ToArray());
        foreach (var search in pending)
        {
            var expected = search.State == EntityState.Deleted ? new HashSet<string>(StringComparer.Ordinal)
                : SelectedIds(search.Entity).ToHashSet(StringComparer.Ordinal);
            var retained = new HashSet<string>(StringComparer.Ordinal);
            foreach (var entry in tracked.GetValueOrDefault(search.Entity.Id) ?? [])
            {
                if (expected.Contains(entry.Entity.LocationId))
                {
                    if (entry.State == EntityState.Deleted) entry.State = EntityState.Unchanged;
                    retained.Add(entry.Entity.LocationId);
                }
                else if (entry.State == EntityState.Added) entry.State = EntityState.Detached;
                else entry.State = EntityState.Deleted;
            }
            foreach (var id in expected.Except(retained))
                db.SearchLocations.Add(new SearchLocation { SearchRequestId = search.Entity.Id, LocationId = id });
        }
    }

    /// <summary>Idempotent, bounded backfill under SchemaUpgrade's database lock.</summary>
    public static async Task BackfillAsync(AppDb db, CancellationToken cancellationToken)
    {
        while (true)
        {
            var missing = await db.SearchRequests.AsNoTracking()
                .Where(search => !db.SearchLocations.Any(location => location.SearchRequestId == search.Id))
                .OrderBy(search => search.Id).Take(500)
                .Select(search => new SearchRequest { Id = search.Id, City = search.City,
                    DistrictsJson = search.DistrictsJson, LocationIdsJson = search.LocationIdsJson })
                .ToListAsync(cancellationToken);
            if (missing.Count == 0) return;
            var rows = missing.SelectMany(search => SelectedIds(search).Select(id =>
                new SearchLocation { SearchRequestId = search.Id, LocationId = id })).ToArray();
            db.SearchLocations.AddRange(rows);
            await db.SaveChangesAsync(cancellationToken);
            foreach (var row in rows) db.Entry(row).State = EntityState.Detached;
        }
    }
}
