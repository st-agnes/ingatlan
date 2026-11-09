using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class TestDataSeedTests
{
    private static readonly Lazy<TestDataPlan> Built = new(() => TestDataSeed.BuildPlan(TestDataSeed.LoadCatalog()));
    private static TestDataPlan Plan => Built.Value;
    private static AppDb ModelOnly() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options);

    [Fact]
    public void EmbeddedCatalogBuildsTheEntireReadyDatasetWithRolesCreditsAndStableIds()
    {
        Assert.Equal("20261109-test-fixtures-v3", TestDataSeed.CatalogVersion);
        Assert.Equal(12, Plan.Users.Length);
        Assert.Equal(3, Plan.Users.Count(user => user.AccountType == AccountTypes.Agent));
        Assert.Equal(354, Plan.Properties.Length);
        Assert.Equal(352, Plan.Searches.Length);
        Assert.Equal(12, Plan.Credits.Length);
        Assert.All(Plan.Users, user => {
            Assert.Equal(100, user.Credits);
            Assert.True(Passwords.Verify("OtthonraDemo2026!", user.PasswordHash));
            var entry = Assert.Single(Plan.Credits, credit => credit.UserId == user.Id);
            Assert.Equal(100, entry.Amount); Assert.Null(entry.DecisionId);
            Assert.NotNull(user.ActiveEntityId);
        });
        var ids = Plan.Users.Select(user => user.Id).Concat(Plan.Properties.Select(property => property.Id))
            .Concat(Plan.Searches.Select(search => search.Id)).Concat(Plan.Credits.Select(credit => credit.Id)).ToArray();
        Assert.Equal(ids.Length, ids.Distinct().Count());
        Assert.All(Plan.Properties, property => Assert.Contains(Plan.Users, user => user.Id == property.OwnerId));
        Assert.All(Plan.Searches, search => Assert.Contains(Plan.Users, user => user.Id == search.OwnerId));
    }

    [Fact]
    public void EmbeddedFixturesCoverEveryCountyWithVariedPricesSizesRoomsAndBothHousingTypes()
    {
        // These are the embedded startup fixtures deployed to Cloud Run, not a
        // separately constructed selector fixture or the browser-only demo.
        foreach (var region in RegionCatalog.All)
        {
            var properties = Plan.Properties.Where(property =>
                RegionCatalog.ForLocation(LocationCatalog.ForProperty(property)!).Contains(region.Id)).ToArray();
            var searches = Plan.Searches.Where(search =>
                RegionCatalog.ForLocations(LocationCatalog.ForSearch(search)).Contains(region.Id)).ToArray();
            Assert.True(properties.Length >= 12, $"{region.Label} needs real seeded properties.");
            Assert.True(searches.Length >= 12, $"{region.Label} needs real seeded searches.");
            Assert.Contains(properties, item => item.Type == "Lakás");
            Assert.Contains(properties, item => item.Type == "Ház");
            Assert.Contains(searches, item => item.Type == "Lakás");
            Assert.Contains(searches, item => item.Type == "Ház");
            Assert.True(properties.Select(item => item.Price).Distinct().Count() >= 6, region.Label);
            Assert.True(properties.Select(item => item.Area).Distinct().Count() >= 6, region.Label);
            Assert.True(properties.Select(item => item.Rooms).Distinct().Count() >= 6, region.Label);
            Assert.True(searches.Select(item => (item.MinPrice, item.MaxPrice)).Distinct().Count() >= 6, region.Label);
            Assert.True(searches.Select(item => (item.MinArea, item.MaxArea)).Distinct().Count() >= 6, region.Label);
            Assert.True(searches.Select(item => (item.MinRooms, item.MaxRooms)).Distinct().Count() >= 6, region.Label);
            Assert.All(properties.Where(item => item.Type == "Ház"), item => Assert.True(item.LotArea > 0));
            Assert.All(properties, property => Assert.Contains(searches, search =>
                property.OwnerId != search.OwnerId && Rules.Compatible(property, search)
                && AccountTypes.CanInteract(Plan.Users.Single(user => user.Id == property.OwnerId).AccountType,
                    Plan.Users.Single(user => user.Id == search.OwnerId).AccountType)));
        }
    }

    [Theory]
    [InlineData("anna@otthonra.local")]
    [InlineData("peter@otthonra.local")]
    [InlineData("eszter@otthonra.local")]
    public void OriginalDefaultProfilesReceiveDozensOfPrivateAndAgentRecommendations(string email)
    {
        var user = Assert.Single(Plan.Users, item => item.Email == email);
        IEnumerable<Guid> owners;
        if (user.ActiveKind == "search")
        {
            var search = Assert.Single(Plan.Searches, item => item.Id == user.ActiveEntityId);
            Assert.Equal(user.Id, search.OwnerId);
            owners = Plan.Properties.Where(property => Rules.Compatible(property, search)).Select(property => property.OwnerId);
        }
        else
        {
            var property = Assert.Single(Plan.Properties, item => item.Id == user.ActiveEntityId);
            Assert.Equal(user.Id, property.OwnerId);
            owners = Plan.Searches.Where(search => Rules.Compatible(property, search)).Select(search => search.OwnerId);
        }
        var matches = owners.ToArray();
        Assert.True(matches.Length >= 30, "The original test profile needs many fresh candidates.");
        Assert.Contains(matches, id => Plan.Users.Single(candidate => candidate.Id == id).AccountType == AccountTypes.Agent);
        Assert.Contains(matches, id => Plan.Users.Single(candidate => candidate.Id == id).AccountType == AccountTypes.Private);
    }

    [Fact]
    public void EveryAgentStartsWithACompatibleSearchAndTheCorrectOneCreditCost()
    {
        var peter = Plan.Users.Single(user => user.Email == "peter@otthonra.local");
        var property = Plan.Properties.Single(item => item.Id == peter.ActiveEntityId);
        foreach (var agent in Plan.Users.Where(user => user.AccountType == AccountTypes.Agent))
        {
            Assert.Equal("search", agent.ActiveKind);
            var search = Assert.Single(Plan.Searches, item => item.Id == agent.ActiveEntityId && item.OwnerId == agent.Id);
            Assert.True(Rules.Compatible(property, search));
            Assert.Equal(1, AccountTypes.LikeCost(agent.AccountType, agent.ActiveKind));
            Assert.Contains(Plan.Properties, item => item.OwnerId == agent.Id);
        }
    }

    [Fact]
    public void FixtureIdsAreNamespacedStableAndIndependentOfRandomDatabaseKeys()
    {
        Assert.Equal(TestDataSeed.StableId("user:anna"), TestDataSeed.StableId("user:anna"));
        Assert.NotEqual(TestDataSeed.StableId("user:anna"), TestDataSeed.StableId("property:anna"));
        Assert.Equal(Plan.Users.Single(user => user.Email == "anna@otthonra.local").Id, TestDataSeed.StableId("user:anna"));
        Assert.Throws<ArgumentException>(() => TestDataSeed.StableId(" "));
    }

    [Fact]
    public void DeploymentHistoryKeysDistinguishRevisionsAndLocalCatalogVersions()
    {
        Assert.Equal("local:20261109-test-fixtures-v3", TestDataSeed.RevisionKey(null, TestDataSeed.CatalogVersion));
        Assert.Equal("ci-fixtures-a", TestDataSeed.RevisionKey("ci-fixtures-a", TestDataSeed.CatalogVersion));
        Assert.NotEqual(TestDataSeed.RevisionKey("ci-fixtures-a", TestDataSeed.CatalogVersion), TestDataSeed.RevisionKey("ci-fixtures-b", TestDataSeed.CatalogVersion));
        Assert.NotEqual(TestDataSeed.RevisionKey(null, "catalog-v1"), TestDataSeed.RevisionKey(null, "catalog-v2"));
        foreach (var revision in new[] { "", "../production", "UPPERCASE", "x\ny", "x\n", new string('x', 201) })
            Assert.Throws<InvalidOperationException>(() => TestDataSeed.RevisionKey(revision, TestDataSeed.CatalogVersion));
    }

    [Fact]
    public void DeleteOrderIncludesEveryApplicationTableAndRespectsAllForeignKeysWithoutTouchingSeedHistory()
    {
        using var db = ModelOnly();
        var order = TestDataSeed.DeletionOrder(db.Model).ToList();
        var tables = db.Model.GetEntityTypes().Select(entity => entity.GetTableName()!).Distinct().ToArray();
        Assert.Equal(tables.Length, order.Count);
        Assert.Contains("PaymentOrders", order); Assert.Contains("UserReports", order);
        Assert.DoesNotContain("__OtthonraTestSeeds", order); Assert.DoesNotContain("__OtthonraSchemaVersions", order);
        foreach (var entity in db.Model.GetEntityTypes())
        foreach (var foreignKey in entity.GetForeignKeys())
            Assert.True(order.IndexOf(entity.GetTableName()!) < order.IndexOf(foreignKey.PrincipalEntityType.GetTableName()!),
                "Child records must be deleted before their referenced user/entity.");
    }

    [Theory]
    [InlineData("production", false)]
    [InlineData("development", false)]
    [InlineData("test", false)]
    [InlineData("production", true)]
    public async Task AFlagOrMisleadingNameCannotAuthorizeOrdinaryProductionOrDevelopmentResets(string name, bool isTest)
    {
        // A null context proves validation happens before opening any DB connection.
        await Assert.ThrowsAsync<InvalidOperationException>(() => TestDataSeed.RunAsync(null!, new DeploymentSettings(name, isTest, false), "ci-fixtures-a"));
    }

    private static TestFixtureCatalog MinimalCatalog()
    {
        var original = TestDataSeed.LoadCatalog().Fixtures[0];
        return new("test-catalog", "FixturePassword2026!",
            [new("owner", "Kitalált tesztelő", "fixture@example.test", "", AccountTypes.Private, new(original.Kind, original.Key))],
            [original with { Owner = "owner" }]);
    }

    [Fact]
    public void InvalidCatalogGraphIsRejectedBeforeItCanBeUsedForReset()
    {
        var catalog = MinimalCatalog();
        Assert.Throws<InvalidOperationException>(() => TestDataSeed.BuildPlan(catalog with {
            Fixtures = [catalog.Fixtures[0] with { Owner = "missing" }]
        }));
        Assert.Throws<InvalidOperationException>(() => TestDataSeed.BuildPlan(catalog with {
            Fixtures = [catalog.Fixtures[0], catalog.Fixtures[0]]
        }));
        Assert.Throws<InvalidOperationException>(() => TestDataSeed.BuildPlan(catalog with {
            Users = [catalog.Users[0] with { Active = new("search", catalog.Fixtures[0].Key) }]
        }));
        Assert.Throws<ApiException>(() => TestDataSeed.BuildPlan(catalog with {
            Users = [catalog.Users[0] with { AccountType = "admin" }]
        }));
        Assert.Throws<InvalidOperationException>(() => TestDataSeed.BuildPlan(catalog with {
            Fixtures = [catalog.Fixtures[0] with { Kind = "unknown", Input = JsonSerializer.SerializeToElement(new { title = "Invalid" }) }]
        }));
    }
}
