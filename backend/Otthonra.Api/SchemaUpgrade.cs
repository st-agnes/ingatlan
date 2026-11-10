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
    public const string SellerFeedbackVersion = "20261110-seller-feedback-and-insights";
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
        ("CreditEntries", "RefundedDecisionId", "char(36) COLLATE ascii_general_ci NULL"),
        ("CreditEntries", "FeedbackPackageId", "char(36) COLLATE ascii_general_ci NULL"),
        ("CreditEntries", "RefundedFeedbackPackageId", "char(36) COLLATE ascii_general_ci NULL"),
        ("Users", "FeedbackPassCounter", "int NOT NULL DEFAULT 0")
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
            await EnsureSellerFeedbackTables(connection, cancellationToken);
            await Execute(connection, """
                CREATE TABLE IF NOT EXISTS `UserNotifications` (
                    `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                    `UserId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `DecisionId` char(36) COLLATE ascii_general_ci NULL,
                    `FeedbackPackageId` char(36) COLLATE ascii_general_ci NULL,
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
            // Existing like-refund receipts keep their IDs and decision links.
            // A package refund uses its own key instead of a synthetic Decision.
            var nullableNotificationDecision = Convert.ToString(await Scalar(connection,
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserNotifications' AND COLUMN_NAME = 'DecisionId'", cancellationToken));
            if (nullableNotificationDecision == "NO")
            {
                // MySQL can reject a MODIFY on a foreign-key column (1832).
                // Keep the index and all receipts, temporarily remove only this
                // child constraint, then restore it after the column change.
                // Restoration also runs when a previous startup stopped after
                // MODIFY, so an interrupted upgrade cannot leave the FK absent.
                const string notificationDecisionForeignKey = "FK_UserNotifications_Decisions_DecisionId";
                var hasDecisionForeignKey = Convert.ToInt32(await Scalar(connection,
                    "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'UserNotifications' AND CONSTRAINT_NAME = @name AND CONSTRAINT_TYPE = 'FOREIGN KEY'",
                    cancellationToken, ("name", notificationDecisionForeignKey))) > 0;
                if (hasDecisionForeignKey)
                    await Execute(connection, "ALTER TABLE `UserNotifications` DROP FOREIGN KEY `" + notificationDecisionForeignKey + "`", cancellationToken);
                await Execute(connection, "ALTER TABLE `UserNotifications` MODIFY COLUMN `DecisionId` char(36) COLLATE ascii_general_ci NULL", cancellationToken);
            }
            await EnsureForeignKey(connection, "UserNotifications", "FK_UserNotifications_Decisions_DecisionId",
                "ALTER TABLE `UserNotifications` ADD CONSTRAINT `FK_UserNotifications_Decisions_DecisionId` FOREIGN KEY (`DecisionId`) REFERENCES `Decisions` (`Id`) ON DELETE RESTRICT", cancellationToken);
            await EnsureColumn(connection, "UserNotifications", "FeedbackPackageId", "char(36) COLLATE ascii_general_ci NULL", cancellationToken);
            await EnsureIndex(connection, "UserNotifications", "IX_UserNotifications_FeedbackPackageId",
                "CREATE UNIQUE INDEX `IX_UserNotifications_FeedbackPackageId` ON `UserNotifications` (`FeedbackPackageId`)", cancellationToken);
            await EnsureForeignKey(connection, "UserNotifications", "FK_UserNotifications_FeedbackPackages_FeedbackPackageId",
                "ALTER TABLE `UserNotifications` ADD CONSTRAINT `FK_UserNotifications_FeedbackPackages_FeedbackPackageId` FOREIGN KEY (`FeedbackPackageId`) REFERENCES `FeedbackPackages` (`Id`) ON DELETE RESTRICT", cancellationToken);
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
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", SellerFeedbackVersion));
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

    private static async Task EnsureSellerFeedbackTables(DbConnection connection, CancellationToken cancellationToken)
    {
        await Execute(connection, """
            CREATE TABLE IF NOT EXISTS `PropertyImpressions` (
                `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                `PropertyId` char(36) COLLATE ascii_general_ci NOT NULL,
                `ViewerUserId` char(36) COLLATE ascii_general_ci NOT NULL,
                `SearchRequestId` char(36) COLLATE ascii_general_ci NOT NULL,
                `CreatedAt` datetime(6) NOT NULL,
                CONSTRAINT `PK_PropertyImpressions` PRIMARY KEY (`Id`),
                UNIQUE KEY `IX_PropertyImpressions_PropertyId_ViewerUserId` (`PropertyId`, `ViewerUserId`),
                KEY `IX_PropertyImpressions_ViewerUserId` (`ViewerUserId`),
                KEY `IX_PropertyImpressions_SearchRequestId` (`SearchRequestId`),
                CONSTRAINT `FK_PropertyImpressions_Properties_PropertyId` FOREIGN KEY (`PropertyId`) REFERENCES `Properties` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_PropertyImpressions_Users_ViewerUserId` FOREIGN KEY (`ViewerUserId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_PropertyImpressions_SearchRequests_SearchRequestId` FOREIGN KEY (`SearchRequestId`) REFERENCES `SearchRequests` (`Id`) ON DELETE RESTRICT
            ) CHARACTER SET=utf8mb4
            """, cancellationToken);
        await Execute(connection, """
            CREATE TABLE IF NOT EXISTS `FeedbackPackages` (
                `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                `PropertyId` char(36) COLLATE ascii_general_ci NOT NULL,
                `OwnerId` char(36) COLLATE ascii_general_ci NOT NULL,
                `RequestId` char(36) COLLATE ascii_general_ci NOT NULL,
                `Size` int NOT NULL,
                `ReceivedCount` int NOT NULL DEFAULT 0,
                `Enabled` tinyint(1) NOT NULL,
                `CreatedAt` datetime(6) NOT NULL,
                `ExpiresAt` datetime(6) NOT NULL,
                `RefundedAt` datetime(6) NULL,
                `RefundedCredits` int NOT NULL DEFAULT 0,
                CONSTRAINT `PK_FeedbackPackages` PRIMARY KEY (`Id`),
                CONSTRAINT `CK_FeedbackPackages_Size` CHECK (`Size` IN (10, 20, 50)),
                CONSTRAINT `CK_FeedbackPackages_Counts` CHECK (`ReceivedCount` >= 0 AND `ReceivedCount` <= `Size` AND `RefundedCredits` >= 0 AND `RefundedCredits` <= `Size`),
                UNIQUE KEY `IX_FeedbackPackages_OwnerId_RequestId` (`OwnerId`, `RequestId`),
                KEY `IX_FeedbackPackages_PropertyId_ExpiresAt` (`PropertyId`, `ExpiresAt`),
                KEY `IX_FeedbackPackages_OwnerId_ExpiresAt` (`OwnerId`, `ExpiresAt`),
                KEY `IX_FeedbackPackages_RefundedAt_ExpiresAt` (`RefundedAt`, `ExpiresAt`),
                CONSTRAINT `FK_FeedbackPackages_Properties_PropertyId` FOREIGN KEY (`PropertyId`) REFERENCES `Properties` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_FeedbackPackages_Users_OwnerId` FOREIGN KEY (`OwnerId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT
            ) CHARACTER SET=utf8mb4
            """, cancellationToken);
        await Execute(connection, """
            CREATE TABLE IF NOT EXISTS `FeedbackInvitations` (
                `Id` char(36) COLLATE ascii_general_ci NOT NULL,
                `PackageId` char(36) COLLATE ascii_general_ci NOT NULL,
                `PropertyId` char(36) COLLATE ascii_general_ci NOT NULL,
                `DecisionId` char(36) COLLATE ascii_general_ci NOT NULL,
                `BuyerId` char(36) COLLATE ascii_general_ci NOT NULL,
                `CreatedAt` datetime(6) NOT NULL,
                `ExpiresAt` datetime(6) NOT NULL,
                `AnsweredAt` datetime(6) NULL,
                `Reason` varchar(255) NULL,
                CONSTRAINT `PK_FeedbackInvitations` PRIMARY KEY (`Id`),
                UNIQUE KEY `IX_FeedbackInvitations_DecisionId` (`DecisionId`),
                UNIQUE KEY `IX_FeedbackInvitations_PackageId_BuyerId` (`PackageId`, `BuyerId`),
                KEY `IX_FeedbackInvitations_PropertyId` (`PropertyId`),
                KEY `IX_FeedbackInvitations_BuyerId_AnsweredAt_ExpiresAt` (`BuyerId`, `AnsweredAt`, `ExpiresAt`),
                KEY `IX_FeedbackInvitations_PackageId_AnsweredAt_ExpiresAt` (`PackageId`, `AnsweredAt`, `ExpiresAt`),
                KEY `IX_FeedbackInvitations_PackageId_Reason` (`PackageId`, `Reason`),
                CONSTRAINT `FK_FeedbackInvitations_FeedbackPackages_PackageId` FOREIGN KEY (`PackageId`) REFERENCES `FeedbackPackages` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_FeedbackInvitations_Properties_PropertyId` FOREIGN KEY (`PropertyId`) REFERENCES `Properties` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_FeedbackInvitations_Users_BuyerId` FOREIGN KEY (`BuyerId`) REFERENCES `Users` (`Id`) ON DELETE RESTRICT,
                CONSTRAINT `FK_FeedbackInvitations_Decisions_DecisionId` FOREIGN KEY (`DecisionId`) REFERENCES `Decisions` (`Id`) ON DELETE RESTRICT
            ) CHARACTER SET=utf8mb4
            """, cancellationToken);
        await EnsureIndex(connection, "FeedbackInvitations", "IX_FeedbackInvitations_PackageId_BuyerId",
            "CREATE UNIQUE INDEX `IX_FeedbackInvitations_PackageId_BuyerId` ON `FeedbackInvitations` (`PackageId`, `BuyerId`)", cancellationToken);
        await EnsureIndex(connection, "CreditEntries", "IX_CreditEntries_FeedbackPackageId",
            "CREATE UNIQUE INDEX `IX_CreditEntries_FeedbackPackageId` ON `CreditEntries` (`FeedbackPackageId`)", cancellationToken);
        await EnsureIndex(connection, "CreditEntries", "IX_CreditEntries_RefundedFeedbackPackageId",
            "CREATE UNIQUE INDEX `IX_CreditEntries_RefundedFeedbackPackageId` ON `CreditEntries` (`RefundedFeedbackPackageId`)", cancellationToken);
        await EnsureForeignKey(connection, "CreditEntries", "FK_CreditEntries_FeedbackPackages_FeedbackPackageId",
            "ALTER TABLE `CreditEntries` ADD CONSTRAINT `FK_CreditEntries_FeedbackPackages_FeedbackPackageId` FOREIGN KEY (`FeedbackPackageId`) REFERENCES `FeedbackPackages` (`Id`) ON DELETE RESTRICT", cancellationToken);
        await EnsureForeignKey(connection, "CreditEntries", "FK_CreditEntries_FeedbackPackages_RefundedFeedbackPackageId",
            "ALTER TABLE `CreditEntries` ADD CONSTRAINT `FK_CreditEntries_FeedbackPackages_RefundedFeedbackPackageId` FOREIGN KEY (`RefundedFeedbackPackageId`) REFERENCES `FeedbackPackages` (`Id`) ON DELETE RESTRICT", cancellationToken);
        await EnsureIndex(connection, "Decisions", "IX_Decisions_PropertyStats",
            "CREATE INDEX `IX_Decisions_PropertyStats` ON `Decisions` (`PropertyId`, `ActorKind`, `Liked`, `ActorUserId`, `SearchRequestId`)", cancellationToken);
    }

    private static async Task EnsureColumn(DbConnection connection, string table, string column, string definition, CancellationToken cancellationToken)
    {
        var exists = Convert.ToInt32(await Scalar(connection,
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = @table AND COLUMN_NAME = @column",
            cancellationToken, ("table", table), ("column", column))) > 0;
        if (!exists) await Execute(connection, $"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}", cancellationToken);
    }

    private static async Task EnsureForeignKey(DbConnection connection, string table, string name, string sql, CancellationToken cancellationToken)
    {
        var exists = Convert.ToInt32(await Scalar(connection,
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = @table AND CONSTRAINT_NAME = @name AND CONSTRAINT_TYPE = 'FOREIGN KEY'",
            cancellationToken, ("table", table), ("name", name))) > 0;
        if (!exists) await Execute(connection, sql, cancellationToken);
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
