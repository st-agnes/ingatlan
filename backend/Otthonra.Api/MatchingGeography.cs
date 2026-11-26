using System.Data;
using System.Data.Common;
using System.Globalization;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>
/// Original search boundaries and indexed property positions for distance ranking.
/// These native tables are intentionally outside the disposable application data
/// model. Property points are removed by their parent's cascading foreign key.
/// No provider lookup, display approximation or fixture point is used here.
/// </summary>
public static class MatchingGeography
{
    public const string MunicipalityResource = "Otthonra.Api.MunicipalityBoundaries.json.gz";
    public const int ExpectedAreaCount = 3155 + NeighborhoodCatalog.ExpectedCount + 23;
    private const string Policy = "20261126-matching-geography-v1";
    private const string PointPolicy = "20261126-matching-property-points-v1";
    private const int BatchRows = 40;
    private const int BatchBytes = 768 * 1024;
    private sealed record AreaRow(Location Location, double West, double South, double East, double North, string? Geometry, string? NeighborhoodId);
    private sealed record PointChange(Guid Id, double? Latitude, double? Longitude, bool Deleted);

    /// <summary>Create before any application SaveChanges/backfill can run.</summary>
    public static async Task EnsureSchemaAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        if (db.Database.CurrentTransaction is not null) throw new InvalidOperationException("Matching geography schema setup requires no application transaction.");
        var connection = db.Database.GetDbConnection();
        var opened = connection.State != ConnectionState.Open;
        if (opened) await db.Database.OpenConnectionAsync(cancellationToken);
        var acquired = false;
        var lockName = LockName(connection);
        try
        {
            acquired = Convert.ToInt32(await Scalar(connection, null, "SELECT GET_LOCK(@name,120)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the matching geography schema lock.");
            // Match the existing location-link key's collation for indexed joins
            // on both fresh and upgraded installations. Only server metadata is
            // interpolated; a strict identifier whitelist precedes SQL creation.
            var collation = Convert.ToString(await Scalar(connection, null,
                "SELECT COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='SearchLocations' AND COLUMN_NAME='LocationId'", cancellationToken));
            if (string.IsNullOrEmpty(collation)) collation = "utf8mb4_0900_ai_ci";
            if (!collation.StartsWith("utf8mb4_", StringComparison.Ordinal) || collation.Any(character => !char.IsAsciiLetterOrDigit(character) && character != '_'))
                throw new InvalidOperationException("The location key collation is not supported.");
            await Execute(connection, null, $"""
                CREATE TABLE IF NOT EXISTS `MatchingLocationAreas` (
                    `Id` VARCHAR(255) NOT NULL PRIMARY KEY,
                    `City` VARCHAR(128) NOT NULL,
                    `District` VARCHAR(8) NULL,
                    `Kind` VARCHAR(16) NOT NULL,
                    `West` DOUBLE NOT NULL, `South` DOUBLE NOT NULL,
                    `East` DOUBLE NOT NULL, `North` DOUBLE NOT NULL,
                    `Boundary` GEOMETRY NOT NULL SRID 4326,
                    KEY `IX_MatchingLocationAreas_City` (`City`,`Kind`),
                    SPATIAL INDEX `SX_MatchingLocationAreas_Boundary` (`Boundary`)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE {collation}
                """, cancellationToken);
            await Execute(connection, null, $"""
                CREATE TABLE IF NOT EXISTS `MatchingLocationMembers` (
                    `SelectionId` VARCHAR(255) NOT NULL,
                    `AreaId` VARCHAR(255) NOT NULL,
                    PRIMARY KEY (`SelectionId`,`AreaId`),
                    KEY `IX_MatchingLocationMembers_AreaId_SelectionId` (`AreaId`,`SelectionId`),
                    CONSTRAINT `FK_MatchingLocationMembers_Area` FOREIGN KEY (`AreaId`)
                        REFERENCES `MatchingLocationAreas` (`Id`) ON DELETE CASCADE
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE {collation}
                """, cancellationToken);
            await Execute(connection, null, """
                CREATE TABLE IF NOT EXISTS `MatchingPropertyPoints` (
                    `PropertyId` CHAR(36) COLLATE ascii_general_ci NOT NULL PRIMARY KEY,
                    `Position` POINT NOT NULL SRID 4326,
                    SPATIAL INDEX `SX_MatchingPropertyPoints_Position` (`Position`),
                    CONSTRAINT `FK_MatchingPropertyPoints_Property` FOREIGN KEY (`PropertyId`)
                        REFERENCES `Properties` (`Id`) ON DELETE CASCADE
                ) ENGINE=InnoDB CHARACTER SET ascii
                """, cancellationToken);
            await Execute(connection, null, """
                CREATE TABLE IF NOT EXISTS `__OtthonraMatchingGeography` (
                    `Id` TINYINT NOT NULL PRIMARY KEY,
                    `Version` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    `AreaCount` INT NOT NULL,
                    `MemberCount` INT NOT NULL,
                    `ImportedAt` DATETIME(6) NOT NULL,
                    `PointsVersion` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL
                ) ENGINE=InnoDB
                """, cancellationToken);
        }
        finally
        {
            try { if (acquired) await Scalar(connection, null, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName)); }
            finally { if (opened) await db.Database.CloseConnectionAsync(); }
        }
    }

    /// <summary>Run after the original neighborhood dataset has been imported.</summary>
    public static async Task InitializeAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        if (db.Database.CurrentTransaction is not null) throw new InvalidOperationException("Matching geography initialization requires no application transaction.");
        ValidateMunicipalityResource();
        var members = BuildMembers();
        var version = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Policy + "|" + NeighborhoodCatalog.DatasetVersion + "|"
            + NeighborhoodCatalog.ExpectedMunicipalitiesSha256 + "|" + JsonSerializer.Serialize(members.Select(row => new { row.Selection, row.Area }))))).ToLowerInvariant();
        var connection = db.Database.GetDbConnection();
        var opened = connection.State != ConnectionState.Open;
        if (opened) await db.Database.OpenConnectionAsync(cancellationToken);
        var acquired = false;
        var lockName = LockName(connection);
        try
        {
            acquired = Convert.ToInt32(await Scalar(connection, null, "SELECT GET_LOCK(@name,120)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the matching geography import lock.");
            var current = Convert.ToString(await Scalar(connection, null, "SELECT `Version` FROM `__OtthonraMatchingGeography` WHERE `Id`=1", cancellationToken));
            if (current != version)
            {
                await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
                await Execute(connection, transaction, "DELETE FROM `MatchingLocationMembers`", cancellationToken);
                await Execute(connection, transaction, "DELETE FROM `MatchingLocationAreas`", cancellationToken);
                await ImportMunicipalities(connection, transaction, cancellationToken);
                await ImportNeighborhoods(connection, transaction, cancellationToken);
                foreach (var district in LocationCatalog.All.Where(location => location.Kind == "district").OrderBy(location => location.Id, StringComparer.Ordinal))
                {
                    var neighborhood = NeighborhoodCatalog.All.Single(area => area.City == "Budapest" && area.Name == district.District + " kerület");
                    await Execute(connection, transaction, """
                        INSERT INTO `MatchingLocationAreas` (`Id`,`City`,`District`,`Kind`,`West`,`South`,`East`,`North`,`Boundary`)
                        SELECT @id,@city,@district,'district',`West`,`South`,`East`,`North`,`Boundary`
                        FROM `MatchingLocationAreas` WHERE `Id`=@source
                        """, cancellationToken, ("id", district.Id), ("city", district.City), ("district", district.District!), ("source", neighborhood.Id));
                }
                await ImportMembers(connection, transaction, members, cancellationToken);
                await VerifyCounts(connection, transaction, members.Count, cancellationToken);
                await Execute(connection, transaction, """
                    INSERT INTO `__OtthonraMatchingGeography` (`Id`,`Version`,`AreaCount`,`MemberCount`,`ImportedAt`)
                    VALUES (1,@version,@count,@members,UTC_TIMESTAMP(6))
                    ON DUPLICATE KEY UPDATE `Version`=VALUES(`Version`),`AreaCount`=VALUES(`AreaCount`),
                        `MemberCount`=VALUES(`MemberCount`),`ImportedAt`=VALUES(`ImportedAt`)
                    """, cancellationToken, ("version", version), ("count", ExpectedAreaCount), ("members", members.Count));
                await transaction.CommitAsync(cancellationToken);
            }
            else await VerifyCounts(connection, null, members.Count, cancellationToken);

            var pointVersion = Convert.ToString(await Scalar(connection, null, "SELECT `PointsVersion` FROM `__OtthonraMatchingGeography` WHERE `Id`=1", cancellationToken));
            if (pointVersion != PointPolicy)
            {
                await BackfillPoints(db, cancellationToken);
                await Execute(connection, null, "UPDATE `__OtthonraMatchingGeography` SET `PointsVersion`=@version WHERE `Id`=1", cancellationToken, ("version", PointPolicy));
            }
        }
        finally
        {
            try { if (acquired) await Scalar(connection, null, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName)); }
            finally { if (opened) await db.Database.CloseConnectionAsync(); }
        }
    }

    /// <summary>Canonical polygon IDs; streets deliberately do not get a proximity anchor.</summary>
    public static string[] SelectedAreaIds(SearchRequest search)
    {
        var locations = LocationCatalog.ForSearch(search);
        return locations.SelectMany(location => location.Kind == "street" ? Array.Empty<string>()
            : location.Kind == "area" ? MatchingRanking.Prepare(new SearchRequest { LocationIdsJson = JsonSerializer.Serialize(new[] { location.Id }) })
                .Cities.Select(city => "city:" + city)
            : new[] { location.Id }).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
    }

    /// <summary>Wrap the actual EF save, inside the other relationship writers.</summary>
    public static async Task<int> SaveAsync(AppDb db, Func<Task<int>> save, CancellationToken cancellationToken)
    {
        if (db.Database.ProviderName != "Pomelo.EntityFrameworkCore.MySql") return await save().ConfigureAwait(false);
        db.ChangeTracker.DetectChanges();
        var changes = db.ChangeTracker.Entries<Property>()
            .Where(entry => entry.State is EntityState.Added or EntityState.Deleted
                || entry.State == EntityState.Modified && (entry.Property(nameof(Property.Latitude)).IsModified || entry.Property(nameof(Property.Longitude)).IsModified))
            .Select(entry => new PointChange(entry.Entity.Id, entry.Entity.Latitude, entry.Entity.Longitude, entry.State == EntityState.Deleted)).ToArray();
        if (changes.Length == 0) return await save().ConfigureAwait(false);
        IDbContextTransaction? owned = null;
        try
        {
            if (db.Database.CurrentTransaction is null)
                owned = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken).ConfigureAwait(false);
            var result = await save().ConfigureAwait(false);
            await WritePoints(db.Database.GetDbConnection(), db.Database.CurrentTransaction!.GetDbTransaction(), changes, cancellationToken).ConfigureAwait(false);
            if (owned is not null) await owned.CommitAsync(cancellationToken).ConfigureAwait(false);
            return result;
        }
        finally { if (owned is not null) await owned.DisposeAsync().ConfigureAwait(false); }
    }

    private static bool ValidPoint(double? latitude, double? longitude) => latitude is { } lat && longitude is { } lon
        && double.IsFinite(lat) && double.IsFinite(lon) && lat is >= -90 and <= 90 && lon is > -180 and <= 180;

    private static async Task WritePoints(DbConnection connection, DbTransaction transaction, IEnumerable<PointChange> changes, CancellationToken cancellationToken)
    {
        foreach (var batch in changes.Chunk(100))
        {
            var positions = batch.Where(change => !change.Deleted && ValidPoint(change.Latitude, change.Longitude)).ToArray();
            var deleted = batch.Where(change => change.Deleted || !ValidPoint(change.Latitude, change.Longitude)).ToArray();
            if (deleted.Length > 0)
            {
                await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120;
                for (var index = 0; index < deleted.Length; index++) Parameter(command, "id" + index, deleted[index].Id.ToString("D"));
                command.CommandText = "DELETE FROM `MatchingPropertyPoints` WHERE `PropertyId` IN (" + string.Join(',', deleted.Select((_, index) => "@id" + index)) + ")";
                await command.ExecuteNonQueryAsync(cancellationToken);
            }
            if (positions.Length > 0)
            {
                await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120;
                var values = new List<string>();
                for (var index = 0; index < positions.Length; index++)
                {
                    var position = positions[index];
                    Parameter(command, "id" + index, position.Id.ToString("D"));
                    Parameter(command, "point" + index, FormattableString.Invariant($"POINT({position.Longitude!.Value:R} {position.Latitude!.Value:R})"));
                    values.Add($"(@id{index},ST_GeomFromText(@point{index},4326,'axis-order=long-lat'))");
                }
                command.CommandText = "INSERT INTO `MatchingPropertyPoints` (`PropertyId`,`Position`) VALUES " + string.Join(',', values)
                    + " ON DUPLICATE KEY UPDATE `Position`=VALUES(`Position`)";
                await command.ExecuteNonQueryAsync(cancellationToken);
            }
        }
    }

    private static async Task BackfillPoints(AppDb db, CancellationToken cancellationToken)
    {
        string? after = null;
        while (true)
        {
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            var connection = db.Database.GetDbConnection();
            var changes = new List<PointChange>(100);
            await using (var command = connection.CreateCommand())
            {
                command.Transaction = transaction.GetDbTransaction(); command.CommandTimeout = 120;
                command.CommandText = "SELECT `Id`,`Latitude`,`Longitude` FROM `Properties` "
                    + (after is null ? "" : "WHERE `Id`>@after ") + "ORDER BY `Id` LIMIT 100 FOR UPDATE";
                if (after is not null) Parameter(command, "after", after);
                await using var reader = await command.ExecuteReaderAsync(cancellationToken);
                while (await reader.ReadAsync(cancellationToken)) changes.Add(new(reader.GetGuid(0), reader.IsDBNull(1) ? null : reader.GetDouble(1), reader.IsDBNull(2) ? null : reader.GetDouble(2), false));
            }
            await WritePoints(connection, transaction.GetDbTransaction(), changes, cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            if (changes.Count == 0) return;
            after = changes[^1].Id.ToString("D");
        }
    }

    private static List<(string Selection, string Area)> BuildMembers()
    {
        var members = new HashSet<(string Selection, string Area)>();
        foreach (var location in LocationCatalog.All)
            if (location.Kind is "city" or "district" or "neighborhood") members.Add((location.Id, location.Id));
            else if (location.Kind == "area")
                foreach (var city in MatchingRanking.Prepare(new SearchRequest { LocationIdsJson = JsonSerializer.Serialize(new[] { location.Id }) }).Cities)
                    members.Add((location.Id, "city:" + city));
        return members.OrderBy(row => row.Selection, StringComparer.Ordinal).ThenBy(row => row.Area, StringComparer.Ordinal).ToList();
    }

    private static void ValidateMunicipalityResource()
    {
        using var stream = typeof(MatchingGeography).Assembly.GetManifestResourceStream(MunicipalityResource)
            ?? throw new InvalidOperationException("The original municipality boundary resource is missing.");
        var hash = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
        if (hash != NeighborhoodCatalog.ExpectedMunicipalitiesSha256)
            throw new InvalidOperationException("The original municipality boundary resource has the wrong source fingerprint.");
    }

    private static async Task ImportMunicipalities(DbConnection connection, DbTransaction transaction, CancellationToken cancellationToken)
    {
        using var resource = typeof(MatchingGeography).Assembly.GetManifestResourceStream(MunicipalityResource)!;
        using var stream = new GZipStream(resource, CompressionMode.Decompress);
        using var document = await JsonDocument.ParseAsync(stream, new JsonDocumentOptions { MaxDepth = 32 }, cancellationToken);
        var selected = new Dictionary<string, (double Footprint, JsonElement Geometry)>(StringComparer.Ordinal);
        foreach (var feature in document.RootElement.GetProperty("features").EnumerateArray())
        {
            var id = feature.GetProperty("properties").GetProperty("municipalityId").GetString()!;
            if (LocationCatalog.Get(id) is not { Kind: "city" }) throw new InvalidOperationException("An original municipality has no canonical search identity.");
            var geometry = feature.GetProperty("geometry");
            var footprint = Footprint(geometry);
            // Same deterministic duplicate policy as the existing municipality
            // map catalogue; retain one unmodified source geometry, never merge
            // a land-use alternative into a synthetic municipal boundary.
            if (!selected.TryGetValue(id, out var previous) || footprint > previous.Footprint)
                selected[id] = (footprint, geometry);
        }
        if (selected.Count != 3155) throw new InvalidOperationException("The original municipality boundary resource is incomplete.");
        var batch = new List<AreaRow>(); var bytes = 0;
        foreach (var (id, value) in selected.OrderBy(row => row.Key, StringComparer.Ordinal))
        {
            var row = Row(LocationCatalog.Get(id)!, value.Geometry, neighborhoodId: null);
            var size = Encoding.UTF8.GetByteCount(row.Geometry!);
            if (size > BatchBytes) throw new InvalidOperationException("A municipality boundary exceeds the bounded import payload.");
            if (batch.Count > 0 && (batch.Count >= BatchRows || bytes + size > BatchBytes))
            { await ImportBatch(connection, transaction, batch, cancellationToken); batch.Clear(); bytes = 0; }
            batch.Add(row); bytes += size;
        }
        if (batch.Count > 0) await ImportBatch(connection, transaction, batch, cancellationToken);
    }

    private static async Task ImportNeighborhoods(DbConnection connection, DbTransaction transaction, CancellationToken cancellationToken)
    {
        using var stream = NeighborhoodCatalog.OpenRuntimeStream();
        var header = false; var seen = new HashSet<string>(StringComparer.Ordinal); var batch = new List<AreaRow>();
        await foreach (var element in JsonSerializer.DeserializeAsyncEnumerable<JsonElement>(stream, cancellationToken: cancellationToken))
        {
            if (!header) { NeighborhoodCatalog.ValidateHeader(element); header = true; continue; }
            var id = element.GetProperty("id").GetString()!;
            var location = LocationCatalog.Get(id);
            if (location is not { Kind: "neighborhood" } || !seen.Add(id)) throw new InvalidOperationException("A neighborhood matching identity is invalid or repeated.");
            batch.Add(Row(location, element.GetProperty("geometry"), id));
            if (batch.Count >= BatchRows) { await ImportBatch(connection, transaction, batch, cancellationToken); batch.Clear(); }
        }
        if (batch.Count > 0) await ImportBatch(connection, transaction, batch, cancellationToken);
        if (!header || seen.Count != NeighborhoodCatalog.ExpectedCount) throw new InvalidOperationException("The matching neighborhood dataset is incomplete.");
    }

    private static AreaRow Row(Location location, JsonElement geometry, string? neighborhoodId)
    {
        var west = double.PositiveInfinity; var south = double.PositiveInfinity;
        var east = double.NegativeInfinity; var north = double.NegativeInfinity;
        var longestEdgeUpperKm = 0d;
        foreach (var polygon in Polygons(geometry))
        foreach (var ring in polygon.EnumerateArray())
        {
            double? previousLongitude = null; double previousLatitude = 0;
            foreach (var coordinate in ring.EnumerateArray())
            {
                var longitude = coordinate[0].GetDouble(); var latitude = coordinate[1].GetDouble();
                if (!ValidPoint(latitude, longitude)) throw new InvalidOperationException("A matching boundary contains an invalid coordinate.");
                west = Math.Min(west, longitude); south = Math.Min(south, latitude);
                east = Math.Max(east, longitude); north = Math.Max(north, latitude);
                if (previousLongitude.HasValue)
                    longestEdgeUpperKm = Math.Max(longestEdgeUpperKm, 111.7 * (Math.Abs(latitude - previousLatitude) + Math.Abs(longitude - previousLongitude.Value)));
                previousLongitude = longitude; previousLatitude = latitude;
            }
        }
        if (!double.IsFinite(west) || east <= west || north <= south) throw new InvalidOperationException("A matching boundary is empty or degenerate.");
        // Geographic polygon edges are geodesics, whose latitude extrema can
        // lie between vertices. A vertex-only envelope is not a safe pruning
        // bound. The shortest edge is no longer than a meridian+parallel route
        // (111.7 km per degree upper bound on WGS84). Every point on it is at
        // most half that edge length from an endpoint. Conservative latitude
        // and longitude margins cover that whole edge without changing it.
        var latitudeMargin = longestEdgeUpperKm / 220d + 1e-9;
        var maximumLatitude = Math.Max(Math.Abs(south), Math.Abs(north)) + latitudeMargin;
        var longitudeMargin = maximumLatitude >= 89d ? 180d : latitudeMargin / Math.Cos(maximumLatitude * Math.PI / 180d);
        west = Math.Max(-180d, west - longitudeMargin); east = Math.Min(180d, east + longitudeMargin);
        south = Math.Max(-90d, south - latitudeMargin); north = Math.Min(90d, north + latitudeMargin);
        return new(location, west, south, east, north, neighborhoodId is null ? geometry.GetRawText() : null, neighborhoodId);
    }

    private static IEnumerable<JsonElement> Polygons(JsonElement geometry) => geometry.GetProperty("type").GetString() switch
    {
        "Polygon" => new[] { geometry.GetProperty("coordinates") },
        "MultiPolygon" => geometry.GetProperty("coordinates").EnumerateArray().ToArray(),
        _ => throw new InvalidOperationException("A matching boundary must be polygonal.")
    };

    private static double Footprint(JsonElement geometry)
    {
        var total = 0d;
        foreach (var polygon in Polygons(geometry))
        {
            var outer = true;
            foreach (var ring in polygon.EnumerateArray())
            {
                var points = ring.EnumerateArray().ToArray(); var sum = 0d;
                for (var index = 1; index < points.Length; index++)
                    sum += points[index - 1][0].GetDouble() * points[index][1].GetDouble() - points[index][0].GetDouble() * points[index - 1][1].GetDouble();
                total += (outer ? 1 : -1) * Math.Abs(sum); outer = false;
            }
        }
        if (total <= 0) throw new InvalidOperationException("A municipality boundary has no positive footprint.");
        return total;
    }

    private static async Task ImportBatch(DbConnection connection, DbTransaction transaction, List<AreaRow> batch, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120;
        var rows = new List<string>();
        for (var index = 0; index < batch.Count; index++)
        {
            var row = batch[index]; var suffix = index.ToString(CultureInfo.InvariantCulture);
            foreach (var (name, value) in new (string, object)[] { ("id", row.Location.Id), ("city", row.Location.City),
                ("district", (object?)row.Location.District ?? DBNull.Value), ("kind", row.Location.Kind),
                ("west", row.West), ("south", row.South), ("east", row.East), ("north", row.North) }) Parameter(command, name + suffix, value);
            var boundary = row.NeighborhoodId is null ? $"ST_GeomFromGeoJSON(@geometry{suffix},1,4326)" : "source.`Boundary`";
            if (row.NeighborhoodId is null) Parameter(command, "geometry" + suffix, row.Geometry!);
            else Parameter(command, "source" + suffix, row.NeighborhoodId);
            rows.Add($"SELECT @id{suffix},@city{suffix},@district{suffix},@kind{suffix},@west{suffix},@south{suffix},@east{suffix},@north{suffix},{boundary}"
                + (row.NeighborhoodId is null ? "" : $" FROM `NeighborhoodSearchAreas` source WHERE source.`Id`=@source{suffix}"));
        }
        command.CommandText = "INSERT INTO `MatchingLocationAreas` (`Id`,`City`,`District`,`Kind`,`West`,`South`,`East`,`North`,`Boundary`) " + string.Join(" UNION ALL ", rows);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task ImportMembers(DbConnection connection, DbTransaction transaction, List<(string Selection, string Area)> members, CancellationToken cancellationToken)
    {
        foreach (var batch in members.Chunk(100))
        {
            await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 120;
            var values = new List<string>();
            for (var index = 0; index < batch.Length; index++)
            { Parameter(command, "selection" + index, batch[index].Selection); Parameter(command, "area" + index, batch[index].Area); values.Add($"(@selection{index},@area{index})"); }
            command.CommandText = "INSERT INTO `MatchingLocationMembers` (`SelectionId`,`AreaId`) VALUES " + string.Join(',', values);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }
    }

    private static async Task VerifyCounts(DbConnection connection, DbTransaction? transaction, int members, CancellationToken cancellationToken)
    {
        if (Convert.ToInt32(await Scalar(connection, transaction, "SELECT COUNT(*) FROM `MatchingLocationAreas`", cancellationToken)) != ExpectedAreaCount
            || Convert.ToInt32(await Scalar(connection, transaction, "SELECT COUNT(*) FROM `MatchingLocationMembers`", cancellationToken)) != members)
            throw new InvalidOperationException("The indexed matching geography dataset is incomplete.");
    }

    private static string LockName(DbConnection connection) => "otthonra-matching-geo-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
    private static void Parameter(DbCommand command, string name, object value)
    { var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value; command.Parameters.Add(parameter); }
    private static async Task<object?> Scalar(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 150; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        return await command.ExecuteScalarAsync(cancellationToken);
    }
    private static async Task Execute(DbConnection connection, DbTransaction? transaction, string sql, CancellationToken cancellationToken, params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand(); command.Transaction = transaction; command.CommandTimeout = 150; command.CommandText = sql;
        foreach (var (name, value) in parameters) Parameter(command, name, value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
