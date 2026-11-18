using System.Data;
using System.Data.Common;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>Versioned native postal catalogue; deliberately outside disposable EF application data.</summary>
public static class StreetData
{
    private const int BatchRows = 300;
    private const int BatchBytes = 768 * 1024;

    public static async Task InitializeAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        // Validate packaging before consulting a previously completed import.
        var version = StreetCatalog.DatasetVersion;
        var count = StreetCatalog.All.Count;
        if (db.Database.CurrentTransaction is not null)
            throw new InvalidOperationException("Street initialization must run outside an application transaction.");
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        var lockName = "otthonra-streets-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
        var acquired = false;
        try
        {
            acquired = Convert.ToInt32(await ScalarAsync(connection, null, "SELECT GET_LOCK(@name,120)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the postal street dataset import lock.");
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `StreetCatalog` (
                    `Id` VARCHAR(31) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
                    `City` VARCHAR(128) NOT NULL,
                    `District` VARCHAR(8) NULL,
                    `Name` VARCHAR(255) NOT NULL,
                    `Type` VARCHAR(128) NOT NULL,
                    `StreetName` VARCHAR(384) NOT NULL,
                    `Label` VARCHAR(600) NOT NULL,
                    `PostalCodes` JSON NOT NULL,
                    `Aliases` JSON NOT NULL,
                    KEY `IX_StreetCatalog_CityDistrict` (`City`,`District`)
                ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_hungarian_ci
                """, cancellationToken);
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `__OtthonraStreetDataset` (
                    `Id` TINYINT NOT NULL PRIMARY KEY,
                    `DatasetVersion` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    `StreetCount` INT NOT NULL,
                    `ImportedAt` DATETIME(6) NOT NULL
                ) ENGINE=InnoDB
                """, cancellationToken);
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `__OtthonraStreetAssociation` (
                    `Id` TINYINT NOT NULL PRIMARY KEY,
                    `DatasetVersion` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    `ReclassifiedAt` DATETIME(6) NOT NULL
                ) ENGINE=InnoDB
                """, cancellationToken);
            var current = Convert.ToString(await ScalarAsync(connection, null,
                "SELECT `DatasetVersion` FROM `__OtthonraStreetDataset` WHERE `Id`=1 AND `StreetCount`=@count", cancellationToken, ("count", count)));
            if (current != version)
            {
                // Catalogue rows and the successful version marker commit
                // together. Readers never see a partly replaced source version.
                await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
                await ExecuteAsync(connection, transaction, "DELETE FROM `StreetCatalog`", cancellationToken);
                var seen = new HashSet<string>(StringComparer.Ordinal);
                var batch = new List<PostalStreet>(BatchRows);
                var bytes = 0;
                var headerSeen = false;
                using var stream = StreetCatalog.OpenRuntimeStream();
                await foreach (var element in JsonSerializer.DeserializeAsyncEnumerable<JsonElement>(stream, cancellationToken: cancellationToken))
                {
                    if (!headerSeen)
                    {
                        StreetCatalog.ValidateHeader(element);
                        if (element.GetProperty("datasetVersion").GetString() != version || element.GetProperty("count").GetInt32() != count)
                            throw new InvalidOperationException("The postal street import source differs from its catalogue.");
                        headerSeen = true;
                        continue;
                    }
                    var row = StreetCatalog.ParseRow(element);
                    if (StreetCatalog.Get(row.Id) is null || !seen.Add(row.Id))
                        throw new InvalidOperationException("The postal street import contains an unknown or duplicate identity.");
                    var size = Encoding.UTF8.GetByteCount(element.GetRawText()) + 512;
                    if (size > BatchBytes) throw new InvalidOperationException("A postal street exceeds the bounded import payload.");
                    if (batch.Count > 0 && (batch.Count >= BatchRows || bytes + size > BatchBytes))
                    {
                        await ImportBatchAsync(connection, transaction, batch, cancellationToken);
                        batch.Clear(); bytes = 0;
                    }
                    batch.Add(row); bytes += size;
                }
                if (batch.Count > 0) await ImportBatchAsync(connection, transaction, batch, cancellationToken);
                if (!headerSeen || seen.Count != count) throw new InvalidOperationException("The postal street import is incomplete.");
                await VerifyCountAsync(connection, transaction, count, cancellationToken);
                await ExecuteAsync(connection, transaction, """
                    INSERT INTO `__OtthonraStreetDataset` (`Id`,`DatasetVersion`,`StreetCount`,`ImportedAt`)
                    VALUES (1,@version,@count,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE `DatasetVersion`=VALUES(`DatasetVersion`),`StreetCount`=VALUES(`StreetCount`),`ImportedAt`=VALUES(`ImportedAt`)
                    """, cancellationToken, ("version", version), ("count", count));
                await transaction.CommitAsync(cancellationToken);
            }
            else await VerifyCountAsync(connection, null, count, cancellationToken);

            var associationVersion = Convert.ToString(await ScalarAsync(connection, null,
                "SELECT `DatasetVersion` FROM `__OtthonraStreetAssociation` WHERE `Id`=1", cancellationToken));
            if (associationVersion != version)
            {
                await ReclassifyAsync(connection, cancellationToken);
                // Interrupted passes can repeat their committed pages safely.
                await ExecuteAsync(connection, null, """
                    INSERT INTO `__OtthonraStreetAssociation` (`Id`,`DatasetVersion`,`ReclassifiedAt`)
                    VALUES (1,@version,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE `DatasetVersion`=VALUES(`DatasetVersion`),`ReclassifiedAt`=VALUES(`ReclassifiedAt`)
                    """, cancellationToken, ("version", version));
            }
        }
        finally
        {
            try
            {
                if (acquired) await ScalarAsync(connection, null, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName));
            }
            finally { if (openedHere) await db.Database.CloseConnectionAsync(); }
        }
    }

    private static async Task VerifyCountAsync(DbConnection connection, DbTransaction? transaction, int expectedCount, CancellationToken cancellationToken)
    {
        var count = Convert.ToInt32(await ScalarAsync(connection, transaction, "SELECT COUNT(*) FROM `StreetCatalog`", cancellationToken));
        if (count != expectedCount) throw new InvalidOperationException($"The postal street import has {count} rows; expected {expectedCount}.");
    }

    private static async Task ImportBatchAsync(DbConnection connection, DbTransaction transaction, List<PostalStreet> rows, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction; command.CommandTimeout = 120;
        var values = new List<string>(rows.Count);
        for (var index = 0; index < rows.Count; index++)
        {
            var row = rows[index];
            var suffix = index.ToString(CultureInfo.InvariantCulture);
            foreach (var (name, value) in new (string, object?)[] { ("id", row.Id), ("city", row.City), ("district", row.District),
                ("name", row.Name), ("type", row.Type), ("street", row.StreetName), ("label", row.Label),
                ("postal", JsonSerializer.Serialize(row.PostalCodes)), ("aliases", JsonSerializer.Serialize(row.Aliases)) })
                Parameter(command, name + suffix, value);
            values.Add($"(@id{suffix},@city{suffix},@district{suffix},@name{suffix},@type{suffix},@street{suffix},@label{suffix},CAST(@postal{suffix} AS JSON),CAST(@aliases{suffix} AS JSON))");
        }
        command.CommandText = "INSERT INTO `StreetCatalog` (`Id`,`City`,`District`,`Name`,`Type`,`StreetName`,`Label`,`PostalCodes`,`Aliases`) VALUES " + string.Join(',', values);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task ReclassifyAsync(DbConnection connection, CancellationToken cancellationToken)
    {
        string? after = null;
        while (true)
        {
            // Lock each current address before inferring its association. Raw
            // ADO snapshots also tolerate old NULL values in legacy text fields.
            await using var transaction = await connection.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            var rows = new List<(string Id, Property Property, string? PreviousStreetId)>(100);
            await using (var command = connection.CreateCommand())
            {
                command.Transaction = transaction; command.CommandTimeout = 30;
                command.CommandText = "SELECT `Id`,`City`,`District`,`Street`,`PostalCode`,`StreetId`,`LocationId` FROM `Properties` "
                    + (after is null ? "" : "WHERE `Id`>@after ") + "ORDER BY `Id` LIMIT 100 FOR UPDATE";
                if (after is not null) Parameter(command, "after", after);
                await using var reader = await command.ExecuteReaderAsync(cancellationToken);
                while (await reader.ReadAsync(cancellationToken))
                {
                    string ReadText(int ordinal) => reader.IsDBNull(ordinal) ? "" : reader.GetString(ordinal);
                    var id = Convert.ToString(reader.GetValue(0), CultureInfo.InvariantCulture)!;
                    rows.Add((id, new Property { City = ReadText(1), District = ReadText(2), Street = ReadText(3), PostalCode = ReadText(4), LocationId = ReadText(6) },
                        reader.IsDBNull(5) ? null : reader.GetString(5)));
                }
            }
            foreach (var row in rows)
            {
                PostalStreet? selected = null;
                if (row.PreviousStreetId is not null)
                {
                    try { selected = StreetCatalog.ResolveProperty(row.Property, row.PreviousStreetId); }
                    catch (ApiException exception) when (exception.Status == 400) { }
                }
                var resolved = (selected ?? StreetCatalog.ResolveProperty(row.Property))?.Id;
                if (resolved == row.PreviousStreetId) continue;
                // Do not rewrite street text, coordinates, geocoding hashes,
                // district/location selections or neighborhood memberships.
                await ExecuteAsync(connection, transaction, "UPDATE `Properties` SET `StreetId`=@street WHERE `Id`=@id", cancellationToken,
                    ("street", resolved), ("id", row.Id));
            }
            await transaction.CommitAsync(cancellationToken);
            if (rows.Count == 0) return;
            after = rows[^1].Id;
        }
    }

    private static void Parameter(DbCommand command, string name, object? value)
    {
        var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value ?? DBNull.Value;
        command.Parameters.Add(parameter);
    }

    private static async Task<object?> ScalarAsync(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object? Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 150; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        return await command.ExecuteScalarAsync(cancellationToken);
    }

    private static async Task ExecuteAsync(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object? Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
