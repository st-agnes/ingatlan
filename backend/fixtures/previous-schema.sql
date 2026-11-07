-- CI ONLY: simulate the initial release in the disposable otthonra_ci database.
-- No application deployment executes this file.
DROP TABLE IF EXISTS `UserReports`;
ALTER TABLE `Users` DROP COLUMN `AccountType`;
ALTER TABLE `Properties`
  DROP COLUMN `LocationId`, DROP COLUMN `LotArea`,
  DROP COLUMN `ConstructionAge`, DROP COLUMN `View`, DROP COLUMN `CeilingHeight`,
  DROP COLUMN `HeatingType`, DROP COLUMN `Insulated`, DROP COLUMN `EnergyRating`,
  DROP COLUMN `AirConditioning`, DROP COLUMN `SolarPanels`, DROP COLUMN `ParkingType`,
  DROP COLUMN `WholeRooms`, DROP COLUMN `HalfRooms`,
  DROP COLUMN `SecondaryHeatingType`, DROP COLUMN `ParkingTypesJson`;
ALTER TABLE `SearchRequests`
  DROP COLUMN `LocationIdsJson`, DROP COLUMN `ConditionsJson`, DROP COLUMN `BuildingsJson`,
  DROP COLUMN `ConstructionAgesJson`, DROP COLUMN `ViewsJson`, DROP COLUMN `CeilingHeight`, DROP COLUMN `FloorsJson`,
  DROP COLUMN `HeatingTypesJson`;
DELETE FROM `__OtthonraSchemaVersions`
  WHERE `Version` IN ('20261102-locations-and-lot-area', '20261105-property-attributes', '20261106-seller-form-details', '20261107-account-types-and-reports');
