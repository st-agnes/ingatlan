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
    public const string PropertyAttributesVersion = "20261105-property-attributes";
    public const string SellerFormDetailsVersion = "20261106-seller-form-details";
    public const string AccountTypesAndReportsVersion = "20261107-account-types-and-reports";
    public const string InteractionsAndReportReasonsVersion = "20261107-interactions-and-report-reasons";
    public const string LikeRefundsVersion = "20261108-public-landing-and-like-refunds";
    public const string RecommendationIndexesVersion = "20261110-ranked-recommendation-indexes";
    private static readonly (string Table, string Column, string Definition)[] Additions =
    [
        ("Properties", "LocationId", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "LotArea", "decimal(18,2) NULL"),
        ("SearchRequests", "LocationIdsJson", "longtext NULL"),
        ("Properties", "ConstructionAge", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "View", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "CeilingHeight", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "HeatingType", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "Insulated", "tinyint(1) NULL"),
        ("Properties", "EnergyRating", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "AirConditioning", "tinyint(1) NULL"),
        ("Properties", "SolarPanels", "tinyint(1) NULL"),
        ("Properties", "ParkingType", "varchar(255) NOT NULL DEFAULT ''"),
        ("SearchRequests", "ConditionsJson", "longtext NULL"),
        ("SearchRequests", "BuildingsJson", "longtext NULL"),
        ("SearchRequests", "ConstructionAgesJson", "longtext NULL"),
        ("SearchRequests", "ViewsJson", "longtext NULL"),
        ("SearchRequests", "CeilingHeight", "varchar(255) NOT NULL DEFAULT ''"),
        ("SearchRequests", "FloorsJson", "longtext NULL"),
        ("Properties", "WholeRooms", "int NULL"),
        ("Properties", "HalfRooms", "int NULL"),
        ("Properties", "SecondaryHeatingType", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "ParkingTypesJson", "longtext NULL"),
        ("SearchRequests", "HeatingTypesJson", "longtext NULL"),
        ("Users", "AccountType", "varchar(20) NOT NULL DEFAULT 'private'"),
        ("Decisions", "RefundedAt", "datetime(6) NULL"),
        ("CreditEntries", "RefundedDecisionId", "char(36) COLLATE ascii_general_ci NULL")
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
            await Execute(connection, """
                CREATE TABLE IF NOT EXISTS `SearchLocations` (
                    `SearchRequestId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `LocationId` varchar(255) NOT NULL,
                    CONSTRAINT `PK_SearchLocations` PRIMARY KEY (`SearchRequestId`, `LocationId`),
                    KEY `IX_SearchLocations_LocationId_SearchRequestId` (`LocationId`, `SearchRequestId`),
                    CONSTRAINT `FK_SearchLocations_SearchRequests_SearchRequestId` FOREIGN KEY (`SearchRequestId`)
                        REFERENCES `SearchRequests` (`Id`) ON DELETE RESTRICT
                ) CHARACTER SET=utf8mb4
                """, cancellationToken);
            await SearchLocationIndex.BackfillAsync(db, cancellationToken);
            // EnsureCreated does not add tables once a database contains user
            // tables. Keep the new report table additive for those installations.
            // Guid columns match Pomelo's char(36)/ASCII mapping and user keys.
            await Execute(connection, """
                CREATE TABLE IF NOT EXISTS `UserReports` (
                    `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                    `ReporterId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `ReportedUserId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `EntityKind` varchar(255) NOT NULL,
                    `EntityId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `Reason` varchar(255) NOT NULL,
                    `CreatedAt` datetime(6) NOT NULL,
                    CONSTRAINT `PK_UserReports` PRIMARY KEY (`Id`),
                    CONSTRAINT `FK_UserReports_Users_ReporterId` FOREIGN KEY (`ReporterId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT,
                    CONSTRAINT `FK_UserReports_Users_ReportedUserId` FOREIGN KEY (`ReportedUserId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT,
                    UNIQUE KEY `IX_UserReports_ReporterId_ReportedUserId` (`ReporterId`, `ReportedUserId`),
                    KEY `IX_UserReports_ReportedUserId` (`ReportedUserId`)
                ) CHARACTER SET=utf8mb4
                """, cancellationToken);
            // Preserve historical report rows/timestamps while allowing a separate
            // report for each source entity and reason. Create the replacement first,
            // because its leading ReporterId also supports that user foreign key.
            const string reportIndex = "IX_UserReports_ReporterId_EntityKind_EntityId_Reason";
            var hasReportIndex = Convert.ToInt32(await Scalar(connection,
                "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserReports' AND INDEX_NAME = @index",
                cancellationToken, ("index", reportIndex))) > 0;
            if (!hasReportIndex)
                await Execute(connection, "CREATE UNIQUE INDEX `" + reportIndex + "` ON `UserReports` (`ReporterId`, `EntityKind`, `EntityId`, `Reason`)", cancellationToken);
            const string legacyReportIndex = "IX_UserReports_ReporterId_ReportedUserId";
            var hasLegacyReportIndex = Convert.ToInt32(await Scalar(connection,
                "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserReports' AND INDEX_NAME = @index",
                cancellationToken, ("index", legacyReportIndex))) > 0;
            if (hasLegacyReportIndex)
                await Execute(connection, "DROP INDEX `" + legacyReportIndex + "` ON `UserReports`", cancellationToken);
            await Execute(connection, """
                CREATE TABLE IF NOT EXISTS `UserNotifications` (
                    `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                    `UserId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `DecisionId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `Kind` varchar(255) NOT NULL,
                    `Amount` int NOT NULL,
                    `Text` longtext NOT NULL,
                    `CreatedAt` datetime(6) NOT NULL,
                    `ReadAt` datetime(6) NULL,
                    CONSTRAINT `PK_UserNotifications` PRIMARY KEY (`Id`),
                    CONSTRAINT `FK_UserNotifications_Users_UserId` FOREIGN KEY (`UserId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT,
                    CONSTRAINT `FK_UserNotifications_Decisions_DecisionId` FOREIGN KEY (`DecisionId`) REFERENCES `Decisions` (`Id`) ON DELETE RESTRICT,
                    UNIQUE KEY `IX_UserNotifications_DecisionId` (`DecisionId`),
                    KEY `IX_UserNotifications_UserId_CreatedAt` (`UserId`, `CreatedAt`)
                ) CHARACTER SET=utf8mb4
                """, cancellationToken);
            await EnsureIndex(connection, "CreditEntries", "IX_CreditEntries_RefundedDecisionId",
                "CREATE UNIQUE INDEX `IX_CreditEntries_RefundedDecisionId` ON `CreditEntries` (`RefundedDecisionId`)", cancellationToken);
            await EnsureIndex(connection, "Decisions", "IX_Decisions_Liked_RefundedAt_CreatedAt",
                "CREATE INDEX `IX_Decisions_Liked_RefundedAt_CreatedAt` ON `Decisions` (`Liked`, `RefundedAt`, `CreatedAt`)", cancellationToken);
            await EnsureIndex(connection, "Properties", "IX_Properties_Archived_Type_LocationId",
                "CREATE INDEX `IX_Properties_Archived_Type_LocationId` ON `Properties` (`Archived`, `Type`, `LocationId`)", cancellationToken);
            await EnsureIndex(connection, "Properties", "IX_Properties_Archived_Type_City",
                "CREATE INDEX `IX_Properties_Archived_Type_City` ON `Properties` (`Archived`, `Type`, `City`)", cancellationToken);
            await EnsureIndex(connection, "SearchRequests", "IX_SearchRequests_Archived_Type_City",
                "CREATE INDEX `IX_SearchRequests_Archived_Type_City` ON `SearchRequests` (`Archived`, `Type`, `City`)", cancellationToken);
            await EnsureIndex(connection, "Decisions", "IX_Decisions_SearchRequestId_ActorKind_PropertyId",
                "CREATE INDEX `IX_Decisions_SearchRequestId_ActorKind_PropertyId` ON `Decisions` (`SearchRequestId`, `ActorKind`, `PropertyId`)", cancellationToken);
            const string refundForeignKey = "FK_CreditEntries_Decisions_RefundedDecisionId";
            var hasRefundForeignKey = Convert.ToInt32(await Scalar(connection,
                "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'CreditEntries' AND CONSTRAINT_NAME = @name AND CONSTRAINT_TYPE = 'FOREIGN KEY'",
                cancellationToken, ("name", refundForeignKey))) > 0;
            if (!hasRefundForeignKey)
                await Execute(connection, "ALTER TABLE `CreditEntries` ADD CONSTRAINT `" + refundForeignKey + "` FOREIGN KEY (`RefundedDecisionId`) REFERENCES `Decisions` (`Id`) ON DELETE RESTRICT", cancellationToken);
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", LocationsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", PropertyAttributesVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", SellerFormDetailsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", AccountTypesAndReportsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", InteractionsAndReportReasonsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", LikeRefundsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", RecommendationIndexesVersion));
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

    private static async Task EnsureIndex(DbConnection connection, string table, string index, string sql, CancellationToken cancellationToken)
    {
        var exists = Convert.ToInt32(await Scalar(connection,
            "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = @table AND INDEX_NAME = @index",
            cancellationToken, ("table", table), ("index", index))) > 0;
        if (!exists) await Execute(connection, sql, cancellationToken);
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
