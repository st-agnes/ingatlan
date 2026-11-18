using System.Data;
using System.Data.Common;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>Versioned, streamed native-MySQL geometry import and point membership.</summary>
public static class NeighborhoodData
{
    private const int BatchRows = 40;
    private const int BatchBytes = 768 * 1024;
    private sealed record ImportRow(NeighborhoodArea Area, string CanonicalNameKey, string Method, string Metadata, string Geometry);

    public static async Task InitializeAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        // Validate the embedded header even when this database already has the
        // expected version. A packaging error must stop startup/readiness.
        var version = NeighborhoodCatalog.DatasetVersion;
        if (db.Database.CurrentTransaction is not null)
            throw new InvalidOperationException("Neighborhood initialization must run outside an application transaction.");
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        var lockName = "otthonra-neighborhoods-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
        var acquired = false;
        try
        {
            acquired = Convert.ToInt32(await ScalarAsync(connection, null, "SELECT GET_LOCK(@name,120)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the neighborhood dataset import lock.");
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `NeighborhoodSearchAreas` (
                    `Id` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
                    `Municipality` VARCHAR(128) NOT NULL,
                    `Name` VARCHAR(255) NOT NULL,
                    `CanonicalNameKey` VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
                    `Method` VARCHAR(48) NOT NULL,
                    `Metadata` JSON NOT NULL,
                    `Boundary` GEOMETRY NOT NULL SRID 4326,
                    UNIQUE KEY `UX_NeighborhoodSearchAreas_Name` (`Municipality`,`CanonicalNameKey`),
                    KEY `IX_NeighborhoodSearchAreas_Municipality` (`Municipality`),
                    SPATIAL INDEX `SX_NeighborhoodSearchAreas_Boundary` (`Boundary`)
                ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_hungarian_ci
                """, cancellationToken);
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `__OtthonraNeighborhoodDataset` (
                    `Id` TINYINT NOT NULL PRIMARY KEY,
                    `SourceSha256` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    `FeatureCount` INT NOT NULL,
                    `ImportedAt` DATETIME(6) NOT NULL
                ) ENGINE=InnoDB
                """, cancellationToken);
            await ExecuteAsync(connection, null, """
                CREATE TABLE IF NOT EXISTS `__OtthonraNeighborhoodMembership` (
                    `Id` TINYINT NOT NULL PRIMARY KEY,
                    `SourceSha256` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    `ReclassifiedAt` DATETIME(6) NOT NULL
                ) ENGINE=InnoDB
                """, cancellationToken);
            var current = Convert.ToString(await ScalarAsync(connection, null,
                "SELECT `SourceSha256` FROM `__OtthonraNeighborhoodDataset` WHERE `Id`=1 AND `FeatureCount`=@count", cancellationToken,
                ("count", NeighborhoodCatalog.ExpectedCount)));
            if (current == version)
            {
                await VerifyCountAsync(connection, null, cancellationToken);
            }
            else
            {
                await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
                var seen = new HashSet<string>(StringComparer.Ordinal);
                var batch = new List<ImportRow>(BatchRows);
                var bytes = 0;
                var headerSeen = false;
                using var stream = NeighborhoodCatalog.OpenRuntimeStream();
                await foreach (var element in JsonSerializer.DeserializeAsyncEnumerable<JsonElement>(stream, cancellationToken: cancellationToken))
                {
                    if (!headerSeen)
                    {
                        NeighborhoodCatalog.ValidateHeader(element);
                        headerSeen = true;
                        continue;
                    }
                    var id = element.GetProperty("id").GetString();
                    var area = NeighborhoodCatalog.Get(id) ?? throw new InvalidOperationException("A boundary has no catalogue metadata.");
                    if (!seen.Add(area.Id)) throw new InvalidOperationException("A neighborhood boundary ID is duplicated.");
                    var geometry = element.GetProperty("geometry");
                    if (geometry.GetProperty("type").GetString() is not ("Polygon" or "MultiPolygon"))
                        throw new InvalidOperationException("A neighborhood boundary is not polygonal.");
                    var metadata = JsonSerializer.Serialize(new { area.Label, area.Aliases, area.Estimated, GeometrySha256 = element.GetProperty("geometrySha256").GetString() });
                    var row = new ImportRow(area, element.GetProperty("canonicalNameKey").GetString()!, element.GetProperty("method").GetString()!, metadata, geometry.GetRawText());
                    var size = Encoding.UTF8.GetByteCount(row.Geometry) + Encoding.UTF8.GetByteCount(metadata) + 1024;
                    if (size > BatchBytes) throw new InvalidOperationException("A neighborhood boundary exceeds the bounded import payload.");
                    if (batch.Count > 0 && (batch.Count >= BatchRows || bytes + size > BatchBytes))
                    {
                        await ImportBatchAsync(connection, transaction, batch, cancellationToken);
                        batch.Clear(); bytes = 0;
                    }
                    batch.Add(row); bytes += size;
                }
                if (batch.Count > 0) await ImportBatchAsync(connection, transaction, batch, cancellationToken);
                if (!headerSeen || seen.Count != NeighborhoodCatalog.ExpectedCount)
                    throw new InvalidOperationException("The embedded neighborhood boundaries are incomplete.");
                await VerifyCountAsync(connection, transaction, cancellationToken, validateIds: true);
                await ExecuteAsync(connection, transaction, """
                    INSERT INTO `__OtthonraNeighborhoodDataset` (`Id`,`SourceSha256`,`FeatureCount`,`ImportedAt`)
                    VALUES (1,@version,@count,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE `SourceSha256`=VALUES(`SourceSha256`),`FeatureCount`=VALUES(`FeatureCount`),`ImportedAt`=VALUES(`ImportedAt`)
                    """, cancellationToken, ("version", version), ("count", seen.Count));
                await transaction.CommitAsync(cancellationToken);
            }
            // Import's ADO transaction is disposed before EF starts its bounded
            // reclassification transactions. The shared dataset lock spans both.
            var membershipVersion = Convert.ToString(await ScalarAsync(connection, null,
                "SELECT `SourceSha256` FROM `__OtthonraNeighborhoodMembership` WHERE `Id`=1", cancellationToken));
            if (membershipVersion != version)
            {
                await PropertyNeighborhoodIndex.ReclassifyAsync(db, cancellationToken);
                // Partial page commits are safe to repeat after an interrupted
                // startup; only a fully completed pass receives this marker.
                await ExecuteAsync(connection, null, """
                    INSERT INTO `__OtthonraNeighborhoodMembership` (`Id`,`SourceSha256`,`ReclassifiedAt`)
                    VALUES (1,@version,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE `SourceSha256`=VALUES(`SourceSha256`),`ReclassifiedAt`=VALUES(`ReclassifiedAt`)
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

    private static async Task VerifyCountAsync(DbConnection connection, DbTransaction? transaction, CancellationToken cancellationToken, bool validateIds = false)
    {
        var count = Convert.ToInt32(await ScalarAsync(connection, transaction, "SELECT COUNT(*) FROM `NeighborhoodSearchAreas`", cancellationToken));
        if (count != NeighborhoodCatalog.ExpectedCount)
            throw new InvalidOperationException($"The neighborhood geometry import has {count} rows; expected {NeighborhoodCatalog.ExpectedCount}.");
        if (validateIds)
        {
            // A pre-existing different ID with the same unique municipality/
            // canonical key must not silently absorb an upsert and receive a
            // successful version marker. This reads only the small PK index.
            await using var command = connection.CreateCommand(); command.Transaction = transaction;
            command.CommandText = "SELECT `Id` FROM `NeighborhoodSearchAreas`";
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
                if (NeighborhoodCatalog.Get(reader.GetString(0)) is null)
                    throw new InvalidOperationException("The neighborhood geometry table contains an unexpected persistent ID.");
        }
    }

    private static async Task ImportBatchAsync(DbConnection connection, DbTransaction transaction, List<ImportRow> rows, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction; command.CommandTimeout = 120;
        var values = new List<string>(rows.Count);
        for (var index = 0; index < rows.Count; index++)
        {
            var row = rows[index];
            var suffix = index.ToString(CultureInfo.InvariantCulture);
            foreach (var (name, value) in new (string, object)[] { ("id", row.Area.Id), ("city", row.Area.City), ("name", row.Area.Name),
                ("key", row.CanonicalNameKey), ("method", row.Method), ("metadata", row.Metadata), ("geometry", row.Geometry) })
                Parameter(command, name + suffix, value);
            values.Add($"(@id{suffix},@city{suffix},@name{suffix},@key{suffix},@method{suffix},CAST(@metadata{suffix} AS JSON),ST_GeomFromGeoJSON(@geometry{suffix},1,4326))");
        }
        command.CommandText = "INSERT INTO `NeighborhoodSearchAreas` (`Id`,`Municipality`,`Name`,`CanonicalNameKey`,`Method`,`Metadata`,`Boundary`) VALUES "
            + string.Join(',', values) + " ON DUPLICATE KEY UPDATE `Municipality`=VALUES(`Municipality`),`Name`=VALUES(`Name`),`CanonicalNameKey`=VALUES(`CanonicalNameKey`),`Method`=VALUES(`Method`),`Metadata`=VALUES(`Metadata`),`Boundary`=VALUES(`Boundary`)";
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    /// <summary>Return all intersecting areas, including overlaps and boundary points, across municipality labels.</summary>
    public static async Task<string[]> ComputeMembershipAsync(AppDb db, double latitude, double longitude, CancellationToken cancellationToken = default)
    {
        if (!double.IsFinite(latitude) || !double.IsFinite(longitude) || latitude is < -90 or > 90 || longitude is <= -180 or > 180)
            throw new ArgumentOutOfRangeException(nameof(latitude), "Coordinates must be finite WGS84 latitude/longitude values.");
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        try
        {
            await using var command = connection.CreateCommand();
            command.Transaction = db.Database.CurrentTransaction?.GetDbTransaction();
            command.CommandTimeout = 30;
            // GeoJSON import uses longitude,latitude. Explicit WKT axis order
            // matches it even though EPSG:4326's default axes are latitude first.
            command.CommandText = """
                SELECT `Id` FROM `NeighborhoodSearchAreas`
                WHERE MBRIntersects(`Boundary`,ST_GeomFromText(@point,4326,'axis-order=long-lat'))
                  AND ST_Intersects(`Boundary`,ST_GeomFromText(@point,4326,'axis-order=long-lat'))
                ORDER BY `Id`
                """;
            Parameter(command, "point", FormattableString.Invariant($"POINT({longitude:R} {latitude:R})"));
            var result = new List<string>();
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken)) result.Add(reader.GetString(0));
            return result.ToArray();
        }
        finally { if (openedHere) await db.Database.CloseConnectionAsync(); }
    }

    private static void Parameter(DbCommand command, string name, object value)
    {
        var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value;
        command.Parameters.Add(parameter);
    }

    private static async Task<object?> ScalarAsync(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 150; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        return await command.ExecuteScalarAsync(cancellationToken);
    }

    private static async Task ExecuteAsync(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
