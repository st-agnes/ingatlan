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
    public const string ContinuousFeedbackVersion = "20261111-continuous-seller-feedback";
    public const string NeighborhoodsVersion = "20261116-neighborhood-address-search";
    public const string StreetsVersion = "20261118-postal-street-search";
    public const string EntityCreationVersion = "20261118-idempotent-entity-creation";
    public const string AccountActivityVersion = ActivityNotifications.Version;
    public const string FlatAmenitiesVersion = "20261123-floor-and-garden-amenities";
    public const string RaisedAndUpperFloorVersion = "20261124-raised-and-upper-floor-range";
    public const string PublicListingsVersion = "20261124-public-listings-and-energy";
    public const string PublicBudgetVersion = "20261124-search-public-budget";
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
        ("Users", "FeedbackPassCounter", "int NOT NULL DEFAULT 0"),
        ("Properties", "Street", "varchar(180) NOT NULL DEFAULT ''"),
        ("Properties", "HouseNumber", "varchar(32) NOT NULL DEFAULT ''"),
        ("Properties", "PostalCode", "varchar(4) NOT NULL DEFAULT ''"),
        ("Properties", "Latitude", "double NULL"),
        ("Properties", "Longitude", "double NULL"),
        ("Properties", "GeocodedAt", "datetime(6) NULL"),
        ("Properties", "GeocodingProvider", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "GeocodingPlaceId", "varchar(255) NOT NULL DEFAULT ''"),
        ("Properties", "GeocodingQuality", "varchar(40) NOT NULL DEFAULT ''"),
        ("Properties", "GeocodingAddressKey", "varchar(64) NOT NULL DEFAULT ''"),
        ("Properties", "NeighborhoodIdsJson", "longtext NULL"),
        ("Properties", "StreetId", "varchar(64) CHARACTER SET ascii COLLATE ascii_bin NULL"),
        ("Properties", "CreationRequestId", "char(36) COLLATE ascii_general_ci NULL"),
        ("Properties", "CreationRequestHash", "varchar(64) CHARACTER SET ascii COLLATE ascii_bin NULL"),
        ("SearchRequests", "CreationRequestId", "char(36) COLLATE ascii_general_ci NULL"),
        ("SearchRequests", "CreationRequestHash", "varchar(64) CHARACTER SET ascii COLLATE ascii_bin NULL"),
        ("Properties", "BuildingFloors", "int NULL"),
        ("Properties", "FloorIsUpperRange", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("Properties", "PrivateGarden", "tinyint(1) NULL"),
        ("Properties", "SharedGarden", "tinyint(1) NULL"),
        ("SearchRequests", "ExcludeTopFloor", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("SearchRequests", "ExcludeGroundFloorAndBelow", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("SearchRequests", "AirConditioning", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("SearchRequests", "PrivateGarden", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("SearchRequests", "SharedGarden", "tinyint(1) NOT NULL DEFAULT FALSE"),
        ("Properties", "HideStreet", "tinyint(1) NOT NULL DEFAULT TRUE"),
        ("Properties", "HideHouseNumber", "tinyint(1) NOT NULL DEFAULT TRUE"),
        ("Properties", "IsAttic", "tinyint(1) NULL"),
        ("Properties", "EnergyRatingScheme", "varchar(20) NOT NULL DEFAULT ''"),
        ("Properties", "PublicListingKey", "varchar(80) CHARACTER SET ascii COLLATE ascii_bin NULL"),
        ("SearchRequests", "PublicListingKey", "varchar(80) CHARACTER SET ascii COLLATE ascii_bin NULL"),
        ("Properties", "CreationRequestHashVersion", "int NOT NULL DEFAULT 1"),
        ("SearchRequests", "AtticPreference", "varchar(20) NOT NULL DEFAULT ''"),
        ("SearchRequests", "MinEnergyRating", "varchar(20) NOT NULL DEFAULT ''"),
        ("SearchRequests", "PublicMaxPrice", "decimal(18,2) NULL")
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
            // Upgrade the former integer column without replacing rows. A decimal
            // represents raised ground (0.5) while retaining exact legacy floors.
            var floorType = Convert.ToString(await Scalar(connection,
                "SELECT DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Properties' AND COLUMN_NAME = 'Floor'", cancellationToken));
            if (floorType is not "decimal")
                await Execute(connection, "ALTER TABLE `Properties` MODIFY COLUMN `Floor` decimal(4,1) NULL", cancellationToken);
            var balconyNullable = Convert.ToString(await Scalar(connection,
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Properties' AND COLUMN_NAME = 'Balcony'", cancellationToken));
            if (balconyNullable == "NO")
                await Execute(connection, "ALTER TABLE `Properties` MODIFY COLUMN `Balcony` tinyint(1) NULL", cancellationToken);
            await EnsureIndex(connection, "Properties", "IX_Properties_PublicListingKey",
                "CREATE UNIQUE INDEX `IX_Properties_PublicListingKey` ON `Properties` (`PublicListingKey`)", cancellationToken);
            await EnsureIndex(connection, "SearchRequests", "IX_SearchRequests_PublicListingKey",
                "CREATE UNIQUE INDEX `IX_SearchRequests_PublicListingKey` ON `SearchRequests` (`PublicListingKey`)", cancellationToken);
            // The indexed nullable keys make bounded, interrupted backfills cheap
            // and preserve every previously published opaque source URL.
            await BackfillPublicKeys(connection, "Properties", "property", cancellationToken);
            await BackfillPublicKeys(connection, "SearchRequests", "search", cancellationToken);
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
            await Execute(connection, """
                CREATE TABLE IF NOT EXISTS `PropertyNeighborhoods` (
                    `PropertyId` char(36) COLLATE ascii_general_ci NOT NULL,
                    `NeighborhoodId` varchar(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                    CONSTRAINT `PK_PropertyNeighborhoods` PRIMARY KEY (`PropertyId`, `NeighborhoodId`),
                    KEY `IX_PropertyNeighborhoods_NeighborhoodId_PropertyId` (`NeighborhoodId`, `PropertyId`),
                    CONSTRAINT `FK_PropertyNeighborhoods_Properties_PropertyId` FOREIGN KEY (`PropertyId`)
                        REFERENCES `Properties` (`Id`) ON DELETE RESTRICT
                ) CHARACTER SET=utf8mb4
                """, cancellationToken);
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
            await EnsureColumn(connection, "UserNotifications", "EventKey", "varchar(160) CHARACTER SET ascii COLLATE ascii_bin NULL", cancellationToken);
            await EnsureColumn(connection, "UserNotifications", "EntityKind", "varchar(20) NULL", cancellationToken);
            foreach (var column in new[] { "EntityId", "PropertyId", "SearchRequestId", "MatchId" })
                await EnsureColumn(connection, "UserNotifications", column, "char(36) COLLATE ascii_general_ci NULL", cancellationToken);
            await EnsureIndex(connection, "UserNotifications", "IX_UserNotifications_UserId_EventKey",
                "CREATE UNIQUE INDEX `IX_UserNotifications_UserId_EventKey` ON `UserNotifications` (`UserId`, `EventKey`)", cancellationToken);
            await EnsureIndex(connection, "UserNotifications", "IX_UserNotifications_UserId_ReadAt_CreatedAt",
                "CREATE INDEX `IX_UserNotifications_UserId_ReadAt_CreatedAt` ON `UserNotifications` (`UserId`, `ReadAt`, `CreatedAt`)", cancellationToken);
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
            await EnsureIndex(connection, "Properties", "IX_Properties_Archived_Type_StreetId",
                "CREATE INDEX `IX_Properties_Archived_Type_StreetId` ON `Properties` (`Archived`, `Type`, `StreetId`)", cancellationToken);
            await EnsureIndex(connection, "SearchRequests", "IX_SearchRequests_Archived_Type_City",
                "CREATE INDEX `IX_SearchRequests_Archived_Type_City` ON `SearchRequests` (`Archived`, `Type`, `City`)", cancellationToken);
            // Existing rows keep NULL keys, so multiple legacy profiles per
            // owner remain valid under MySQL's nullable unique-key semantics.
            await EnsureIndex(connection, "Properties", "IX_Properties_OwnerId_CreationRequestId",
                "CREATE UNIQUE INDEX `IX_Properties_OwnerId_CreationRequestId` ON `Properties` (`OwnerId`, `CreationRequestId`)", cancellationToken);
            await EnsureIndex(connection, "SearchRequests", "IX_SearchRequests_OwnerId_CreationRequestId",
                "CREATE UNIQUE INDEX `IX_SearchRequests_OwnerId_CreationRequestId` ON `SearchRequests` (`OwnerId`, `CreationRequestId`)", cancellationToken);
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
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", NeighborhoodsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", StreetsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", EntityCreationVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", AccountActivityVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", FlatAmenitiesVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", RaisedAndUpperFloorVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", PublicListingsVersion));
            await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))", cancellationToken, ("version", PublicBudgetVersion));
            if (Convert.ToInt32(await Scalar(connection,
                    "SELECT COUNT(*) FROM `__OtthonraSchemaVersions` WHERE `Version` = @version",
                    cancellationToken, ("version", ContinuousFeedbackVersion))) == 0)
            {
                // Retire owner-controlled pauses without changing any paid period,
                // response count, receipt or credit balance. The update is also
                // idempotent if startup stops before recording the marker.
                await Execute(connection, """
                    UPDATE `FeedbackPackages` SET `Enabled` = TRUE
                    WHERE `Enabled` = FALSE AND `ExpiresAt` > UTC_TIMESTAMP(6)
                        AND `RefundedAt` IS NULL AND `ReceivedCount` < `Size`
                    """, cancellationToken);
                await Execute(connection, "INSERT IGNORE INTO `__OtthonraSchemaVersions` (`Version`, `AppliedAt`) VALUES (@version, UTC_TIMESTAMP(6))",
                    cancellationToken, ("version", ContinuousFeedbackVersion));
            }
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

    private static async Task BackfillPublicKeys(DbConnection connection, string table, string kind, CancellationToken cancellationToken)
    {
        // Both identifiers are fixed internal call sites, never request data.
        while (true)
        {
            await using var command = Command(connection,
                $"UPDATE `{table}` SET `PublicListingKey` = CONCAT(@kind, '-', LOWER(SHA2(CONCAT('otthonra:landing-source:v1:', @kind, ':', LOWER(REPLACE(`Id`, '-', ''))), 256))) WHERE `PublicListingKey` IS NULL OR `PublicListingKey` = '' LIMIT 500", ("kind", kind));
            if (await command.ExecuteNonQueryAsync(cancellationToken) == 0) return;
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
