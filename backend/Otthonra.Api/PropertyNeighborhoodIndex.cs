using System.Data;
using System.Data.Common;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>One indexed row per property/polygon membership, written with its parent row.</summary>
public sealed class PropertyNeighborhood
{
    public Guid PropertyId { get; set; }
    public string NeighborhoodId { get; set; } = "";
}

public static class PropertyNeighborhoodIndex
{
    public static string[] SelectedIds(Property property)
    {
        try { return Dto.Strings(property.NeighborhoodIdsJson).Where(id => NeighborhoodCatalog.Get(id) is not null)
            .Distinct(StringComparer.Ordinal).ToArray(); }
        catch (JsonException) { return []; }
    }

    private static EntityEntry<Property>[] Pending(AppDb db)
    {
        db.ChangeTracker.DetectChanges();
        return db.ChangeTracker.Entries<Property>().Where(entry => entry.State is EntityState.Added or EntityState.Deleted
            || entry.State == EntityState.Modified && new[] { nameof(Property.NeighborhoodIdsJson) }
                .Any(name => entry.Property(name).IsModified)).ToArray();
    }

    /// <summary>
    /// Existing-property edits lock their parent rows before the single old-links
    /// query. The principal update and key diffs commit together. New properties
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
                    "SELECT * FROM `PropertyNeighborhoods` WHERE `PropertyId` IN (" + slots + ") FOR UPDATE",
                    existingIds.Select(id => (object)id).ToArray());
                _ = await db.PropertyNeighborhoods.FromSqlInterpolated(query).ToListAsync(cancellationToken).ConfigureAwait(false);
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
            var parameter = command.CreateParameter(); parameter.ParameterName = "@property" + index;
            parameter.Value = ids[index].ToString("D"); command.Parameters.Add(parameter); names.Add(parameter.ParameterName);
        }
        command.CommandText = "SELECT `Id` FROM `Properties` WHERE `Id` IN (" + string.Join(",", names) + ") ORDER BY `Id` FOR UPDATE";
        await using var reader = await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false)) { }
    }

    private static void Apply(AppDb db, EntityEntry<Property>[] pending)
    {
        var ids = pending.Select(entry => entry.Entity.Id).ToHashSet();
        var tracked = db.ChangeTracker.Entries<PropertyNeighborhood>().Where(entry => ids.Contains(entry.Entity.PropertyId))
            .GroupBy(entry => entry.Entity.PropertyId).ToDictionary(group => group.Key, group => group.ToArray());
        foreach (var property in pending)
        {
            var expected = property.State == EntityState.Deleted ? new HashSet<string>(StringComparer.Ordinal)
                : SelectedIds(property.Entity).ToHashSet(StringComparer.Ordinal);
            var retained = new HashSet<string>(StringComparer.Ordinal);
            foreach (var entry in tracked.GetValueOrDefault(property.Entity.Id) ?? [])
            {
                if (expected.Contains(entry.Entity.NeighborhoodId))
                {
                    if (entry.State == EntityState.Deleted) entry.State = EntityState.Unchanged;
                    retained.Add(entry.Entity.NeighborhoodId);
                }
                else if (entry.State == EntityState.Added) entry.State = EntityState.Detached;
                else entry.State = EntityState.Deleted;
            }
            foreach (var id in expected.Except(retained))
                db.PropertyNeighborhoods.Add(new PropertyNeighborhood { PropertyId = property.Entity.Id, NeighborhoodId = id });
        }
    }

    /// <summary>Recompute only previously geocoded rows after a catalogue version changes.</summary>
    public static async Task ReclassifyAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        Guid? after = null;
        while (true)
        {
            // Lock coordinates and memberships together for each small page.
            // An address edit then either commits before this read or writes its
            // complete new address/point/membership value after this page.
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            var rows = after.HasValue
                ? await db.Properties.FromSqlInterpolated($"SELECT * FROM `Properties` WHERE `Latitude` IS NOT NULL AND `Longitude` IS NOT NULL AND `Id` > {after.Value} ORDER BY `Id` LIMIT 100 FOR UPDATE").ToListAsync(cancellationToken)
                : await db.Properties.FromSqlRaw("SELECT * FROM `Properties` WHERE `Latitude` IS NOT NULL AND `Longitude` IS NOT NULL ORDER BY `Id` LIMIT 100 FOR UPDATE").ToListAsync(cancellationToken);
            if (rows.Count == 0)
            {
                await transaction.CommitAsync(cancellationToken);
                return;
            }
            foreach (var property in rows)
            {
                var ids = await NeighborhoodData.ComputeMembershipAsync(db, property.Latitude!.Value, property.Longitude!.Value, cancellationToken);
                property.NeighborhoodIdsJson = JsonSerializer.Serialize(ids);
                property.Neighborhood = ids.Select(NeighborhoodCatalog.Get).FirstOrDefault(x => x is not null)?.Name ?? "";
                // A pre-existing JSON value can already be correct while the
                // newly added indexed link table is still empty.
                db.Entry(property).Property(p => p.NeighborhoodIdsJson).IsModified = true;
            }
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            after = rows[^1].Id;
            foreach (var property in rows) db.Entry(property).State = EntityState.Detached;
            foreach (var entry in db.ChangeTracker.Entries<PropertyNeighborhood>().ToArray()) entry.State = EntityState.Detached;
        }
    }
}
