-- CI ONLY: simulate the initial release in the disposable otthonra_ci database.
-- No application deployment executes this file.
DROP TABLE IF EXISTS `MatchingPropertyPoints`;
DROP TABLE IF EXISTS `MatchingLocationMembers`;
DROP TABLE IF EXISTS `MatchingLocationAreas`;
DROP TABLE IF EXISTS `__OtthonraMatchingGeography`;
DROP TABLE IF EXISTS `SearchLocations`;
DROP TABLE IF EXISTS `PropertyNeighborhoods`;
ALTER TABLE `Properties` DROP INDEX `IX_Properties_PublicListingKey`;
ALTER TABLE `SearchRequests` DROP INDEX `IX_SearchRequests_PublicListingKey`;
ALTER TABLE `Properties` DROP INDEX `IX_Properties_Archived_Type_LocationId`, DROP INDEX `IX_Properties_Archived_Type_City`, DROP INDEX `IX_Properties_Archived_Type_StreetId`;
ALTER TABLE `SearchRequests` DROP INDEX `IX_SearchRequests_Archived_Type_City`;
-- The current composite index also supports the search foreign key. Restore
-- a legacy-style supporting index before removing the new recommendation one.
ALTER TABLE `Decisions`
  ADD INDEX `IX_Decisions_SearchRequestId_UpgradeFixture` (`SearchRequestId`),
  DROP INDEX `IX_Decisions_SearchRequestId_ActorKind_PropertyId`;
DROP TABLE IF EXISTS `UserNotifications`;
DROP TABLE IF EXISTS `__OtthonraNotificationBackfills`;
DROP TABLE IF EXISTS `FeedbackInvitations`;
DROP TABLE IF EXISTS `PropertyImpressions`;
ALTER TABLE `CreditEntries`
  DROP FOREIGN KEY `FK_CreditEntries_FeedbackPackages_FeedbackPackageId`,
  DROP FOREIGN KEY `FK_CreditEntries_FeedbackPackages_RefundedFeedbackPackageId`,
  DROP INDEX `IX_CreditEntries_FeedbackPackageId`,
  DROP INDEX `IX_CreditEntries_RefundedFeedbackPackageId`,
  DROP COLUMN `FeedbackPackageId`, DROP COLUMN `RefundedFeedbackPackageId`;
DROP TABLE IF EXISTS `FeedbackPackages`;
ALTER TABLE `Users` DROP COLUMN `FeedbackPassCounter`;
ALTER TABLE `Decisions` DROP INDEX `IX_Decisions_PropertyStats`;
DROP TABLE IF EXISTS `UserReports`;
ALTER TABLE `CreditEntries` DROP FOREIGN KEY `FK_CreditEntries_Decisions_RefundedDecisionId`, DROP INDEX `IX_CreditEntries_RefundedDecisionId`, DROP COLUMN `RefundedDecisionId`;
ALTER TABLE `Decisions` DROP INDEX `IX_Decisions_Liked_RefundedAt_CreatedAt`, DROP COLUMN `RefundedAt`;
ALTER TABLE `Users` DROP COLUMN `AccountType`;
ALTER TABLE `Properties` DROP INDEX `IX_Properties_OwnerId_CreationRequestId`,
  DROP COLUMN `CreationRequestId`, DROP COLUMN `CreationRequestHash`, DROP COLUMN `CreationRequestHashVersion`;
ALTER TABLE `SearchRequests` DROP INDEX `IX_SearchRequests_OwnerId_CreationRequestId`,
  DROP COLUMN `CreationRequestId`, DROP COLUMN `CreationRequestHash`;
ALTER TABLE `Properties`
  DROP COLUMN `Street`, DROP COLUMN `StreetId`, DROP COLUMN `HouseNumber`, DROP COLUMN `PostalCode`,
  DROP COLUMN `Latitude`, DROP COLUMN `Longitude`, DROP COLUMN `GeocodedAt`,
  DROP COLUMN `GeocodingProvider`, DROP COLUMN `GeocodingPlaceId`,
  DROP COLUMN `GeocodingQuality`, DROP COLUMN `GeocodingAddressKey`, DROP COLUMN `NeighborhoodIdsJson`,
  DROP COLUMN `LocationId`, DROP COLUMN `LotArea`,
  DROP COLUMN `ConstructionAge`, DROP COLUMN `View`, DROP COLUMN `CeilingHeight`,
  DROP COLUMN `HeatingType`, DROP COLUMN `Insulated`, DROP COLUMN `EnergyRating`,
  DROP COLUMN `AirConditioning`, DROP COLUMN `SolarPanels`, DROP COLUMN `ParkingType`,
  DROP COLUMN `WholeRooms`, DROP COLUMN `HalfRooms`,
  DROP COLUMN `SecondaryHeatingType`, DROP COLUMN `ParkingTypesJson`,
  DROP COLUMN `BuildingFloors`, DROP COLUMN `PrivateGarden`, DROP COLUMN `SharedGarden`,
  DROP COLUMN `FloorIsUpperRange`, DROP COLUMN `PublicListingKey`,
  DROP COLUMN `HideStreet`, DROP COLUMN `HideHouseNumber`, DROP COLUMN `IsAttic`, DROP COLUMN `EnergyRatingScheme`;
ALTER TABLE `Properties` MODIFY COLUMN `Floor` int NULL;
-- Only this disposable fixture collapses NULL to 0 to reproduce the old
-- mandatory boolean column. The application upgrade preserves existing values.
UPDATE `Properties` SET `Balcony` = 0 WHERE `Balcony` IS NULL;
ALTER TABLE `Properties` MODIFY COLUMN `Balcony` tinyint(1) NOT NULL;
ALTER TABLE `SearchRequests`
  DROP COLUMN `LocationIdsJson`, DROP COLUMN `ConditionsJson`, DROP COLUMN `BuildingsJson`,
  DROP COLUMN `ConstructionAgesJson`, DROP COLUMN `ViewsJson`, DROP COLUMN `CeilingHeight`, DROP COLUMN `FloorsJson`,
  DROP COLUMN `HeatingTypesJson`, DROP COLUMN `ExcludeTopFloor`, DROP COLUMN `ExcludeGroundFloorAndBelow`,
  DROP COLUMN `AirConditioning`, DROP COLUMN `PrivateGarden`, DROP COLUMN `SharedGarden`,
  DROP COLUMN `PublicListingKey`, DROP COLUMN `AtticPreference`, DROP COLUMN `MinEnergyRating`, DROP COLUMN `PublicMaxPrice`;
DELETE FROM `__OtthonraSchemaVersions`
  WHERE `Version` IN ('20261102-locations-and-lot-area', '20261105-property-attributes', '20261106-seller-form-details', '20261107-account-types-and-reports', '20261107-interactions-and-report-reasons', '20261108-public-landing-and-like-refunds', '20261110-ranked-recommendation-indexes', '20261110-seller-feedback-and-insights', '20261111-continuous-seller-feedback', '20261116-neighborhood-address-search', '20261118-postal-street-search', '20261118-idempotent-entity-creation', '20261119-account-activity-notifications', '20261123-floor-and-garden-amenities', '20261124-raised-and-upper-floor-range', '20261124-public-listings-and-energy', '20261124-search-public-budget');
