using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class EntityCreationTests
{
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    private static PropertyInput PropertyInput() => new(
        "Világos otthon", "Debrecen", null, null, null, "Otthon a városban.",
        "Lakás", 75_000_000m, 65m, 2.5m, 2, null, null, false, false, [],
        LocationId: "city:Debrecen", WholeRooms: 2, HalfRooms: 1,
        Street: "Fiktív teszt utca", HouseNumber: "12");

    private static SearchInput SearchInput() => new(
        "Városi otthont keresek", "Debrecen", [], "Világos otthont keresek.",
        "Lakás", null, 90_000_000m, 50m, null, 2m, null, false, false, "Rugalmas", "",
        LocationIds: ["city:Debrecen"]);

    [Fact]
    public async Task EmptyKeysFailBeforeOpeningADatabaseConnectionAndLegacyNullIsAllowed()
    {
        EntityCreation.ValidateRequestId(null);
        EntityCreation.ValidateRequestId(Guid.NewGuid());
        using var db = Context();
        var propertyError = await Assert.ThrowsAsync<ApiException>(() => EntityCreation.BeginAsync(
            db, Guid.NewGuid(), PropertyInput() with { CreationRequestId = Guid.Empty }));
        var searchError = await Assert.ThrowsAsync<ApiException>(() => EntityCreation.BeginAsync(
            db, Guid.NewGuid(), SearchInput() with { CreationRequestId = Guid.Empty }));
        Assert.Equal(400, propertyError.Status);
        Assert.Equal(400, searchError.Status);
        Assert.Null(db.Database.CurrentTransaction);
    }

    [Fact]
    public void FingerprintsBindPayloadsWithoutDependingOnCreationKeyOrDecimalScale()
    {
        var property = PropertyInput() with { CreationRequestId = Guid.NewGuid() };
        var propertyHash = EntityCreation.RequestHash(property);
        Assert.Matches("^[0-9A-F]{64}$", propertyHash);
        Assert.Equal(propertyHash, EntityCreation.RequestHash(property with {
            CreationRequestId = Guid.NewGuid(), Price = 75_000_000.00m, Area = 65.000m, Rooms = 2.50m
        }));
        Assert.NotEqual(propertyHash, EntityCreation.RequestHash(property with { Price = 75_000_001m }));
        Assert.NotEqual(propertyHash, EntityCreation.RequestHash(property with { HouseNumber = "13" }));
        Assert.NotEqual(propertyHash, EntityCreation.RequestHash(property with { Title = "Másik otthon" }));

        var search = SearchInput() with { CreationRequestId = Guid.NewGuid() };
        var searchHash = EntityCreation.RequestHash(search);
        Assert.Equal(searchHash, EntityCreation.RequestHash(search with {
            CreationRequestId = null, MaxPrice = 90_000_000.000m, MinArea = 50.0m, MinRooms = 2.00m
        }));
        Assert.NotEqual(searchHash, EntityCreation.RequestHash(search with { MinPrice = 0m }));
        Assert.NotEqual(searchHash, EntityCreation.RequestHash(search with { LocationIds = ["city:Szeged"] }));
        Assert.NotEqual(searchHash, EntityCreation.RequestHash(search with { Balcony = true }));
    }

    [Fact]
    public void ReplayRequiresTheOriginalPayloadHash()
    {
        var hash = EntityCreation.RequestHash(SearchInput());
        EntityCreation.VerifyReplay(hash, hash);
        foreach (var previous in new[] { null, "", EntityCreation.RequestHash(SearchInput() with { MaxPrice = 95_000_000m }) })
            Assert.Equal(409, Assert.Throws<ApiException>(() => EntityCreation.VerifyReplay(previous, hash)).Status);
        Assert.Equal(409, Assert.Throws<ApiException>(() => EntityCreation.VerifyReplay(hash, null)).Status);
    }

    [Fact]
    public void EditingCannotReplaceCreationKeysOrTheirOriginalPayloadFingerprint()
    {
        var key = Guid.NewGuid();
        var property = new Property { CreationRequestId = key, CreationRequestHash = "original-property-hash" };
        Rules.Apply(property, PropertyInput() with { CreationRequestId = Guid.NewGuid() });
        Assert.Equal(key, property.CreationRequestId);
        Assert.Equal("original-property-hash", property.CreationRequestHash);
        var search = new SearchRequest { CreationRequestId = key, CreationRequestHash = "original-search-hash" };
        Rules.Apply(search, SearchInput() with { CreationRequestId = Guid.NewGuid() });
        Assert.Equal(key, search.CreationRequestId);
        Assert.Equal("original-search-hash", search.CreationRequestHash);
    }

    [Fact]
    public void FreshSchemaKeepsNullableOwnerScopedUniqueKeysAndBoundedPrivateHashes()
    {
        using var db = Context();
        foreach (var type in new[] { typeof(Property), typeof(SearchRequest) })
        {
            var entity = db.Model.FindEntityType(type)!;
            Assert.True(entity.FindProperty("CreationRequestId")!.IsNullable);
            var hash = entity.FindProperty("CreationRequestHash")!;
            Assert.True(hash.IsNullable);
            Assert.Equal(64, hash.GetMaxLength());
            Assert.Contains(entity.GetIndexes(), index => index.IsUnique && index.Properties
                .Select(property => property.Name).SequenceEqual(new[] { "OwnerId", "CreationRequestId" }));
        }
        var sql = db.Database.GenerateCreateScript();
        Assert.Contains("UNIQUE INDEX `IX_Properties_OwnerId_CreationRequestId` (`OwnerId`, `CreationRequestId`)", sql);
        Assert.Contains("UNIQUE INDEX `IX_SearchRequests_OwnerId_CreationRequestId` (`OwnerId`, `CreationRequestId`)", sql);
        Assert.Contains("`CreationRequestId` char(36) COLLATE ascii_general_ci NULL", sql);
    }

    [Fact]
    public void CreationReceiptsStayPrivateOnOwnedPublicAndLandingDtos()
    {
        var key = Guid.NewGuid();
        const string hash = "private-payload-fingerprint";
        var property = new Property { CreationRequestId = key, CreationRequestHash = hash };
        Rules.Apply(property, PropertyInput());
        var search = new SearchRequest { CreationRequestId = key, CreationRequestHash = hash };
        Rules.Apply(search, SearchInput());
        var snapshot = new PublicLandingSnapshot();
        snapshot.Add(property, AccountTypes.Private);
        snapshot.Add(search, AccountTypes.Private);
        foreach (var value in new[] { Dto.Property(property), Dto.Property(property, own: true), Dto.Search(search), snapshot.Response(null) })
        {
            var json = JsonSerializer.Serialize(value, new JsonSerializerOptions(JsonSerializerDefaults.Web));
            Assert.DoesNotContain("creationRequest", json);
            Assert.DoesNotContain(key.ToString(), json);
            Assert.DoesNotContain(hash, json);
        }
    }
}
