using System.Data;
using System.Data.Common;
using System.Security.Cryptography;
using System.Text;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>
/// Additive upgrade for databases created by the initial release's EnsureCreated.
/// Each DDL step is independently repeatable; existing rows are never recreated.
/// </summary>
public static class SchemaUpgrade
{
    public const string LocationsVersion = "20261102-locations-and-lot-area";
    private static readonly (string Table, string Column, string Definition)[] Additions =
    [
        ("Properties", "LocationId", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "LotArea", "decimal(18,2) NULL"),
        ("SearchRequests", "LocationIdsJson", "longtext NULL")
    ];

    public static async Task ApplyAsync(AppDb db, CancellationToken cancellationToken = default)
    {
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        var lockName = "otthonra-schema-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
        var acquired = false;
        try
        {
            acquired = Convert.ToInt32(await Scalar(connection, "SELECT GET_LOCK(@name, 30)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the database schema upgrade lock.");
            await Execute(connection, "CREATE TABLE IF NOT EXISTS `__OtthonraSchemaVersions` (`Version` varchar(80) NOT NULL PRIMARY KEY, `AppliedAt` datetime(6) NOT NULL)", cancellationToken);
            foreach (var addition in Additions)
            {
                var exists = Convert.ToInt32(await Scalar(connection,
                    "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = @table AND COLUMN_NAME = @column",
                    cancellationToken, ("table", addition.Table), ("column", addition.Column))) > 0;
                if (!exists)
                    await Execute(connection, $"ALTER TABLE `{addition.Table}` ADD COLUMN `{addition.Column}` {addition.Definition}", cancellationToken);
            }
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", LocationsVersion));
        }
        finally
        {
            try
            {
                if (acquired) await Scalar(connection, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName));
            }
            finally { if (openedHere) await db.Database.CloseConnectionAsync(); }
        }
    }

    private static DbCommand Command(DbConnection connection, string sql, params (string Name, string Value)[] parameters)
    {
        var command = connection.CreateCommand(); command.CommandText = sql; command.CommandTimeout = 40;
        foreach (var (name, value) in parameters)
        {
            var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value; command.Parameters.Add(parameter);
        }
        return command;
    }
    private static async Task<object?> Scalar(DbConnection connection, string sql, CancellationToken cancellationToken, params (string Name, string Value)[] parameters)
    {
        await using var command = Command(connection, sql, parameters);
        return await command.ExecuteScalarAsync(cancellationToken);
    }
    private static async Task Execute(DbConnection connection, string sql, CancellationToken cancellationToken, params (string Name, string Value)[] parameters)
    {
        await using var command = Command(connection, sql, parameters);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
