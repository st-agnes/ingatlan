using System.Text.Json;
using Regex = System.Text.RegularExpressions.Regex;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicListingConnectionsTests
{
    private static readonly DateTime At = new(2026, 11, 27, 12, 0, 0, DateTimeKind.Utc);
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 4, 0))).Options);
    private static (User Seller, User Buyer, User Outsider, Property Home, SearchRequest Search, Match Match) Pair()
    {
        var seller = new User { Name = "Eladó Anna", Email = "seller@example.test", Phone = "+36 20 555 0199", AccountType = AccountTypes.Agent };
        var buyer = new User { Name = "Kereső Péter", Email = "buyer@example.test", Phone = "+36 20 555 0198", AccountType = AccountTypes.Agent };
        var home = new Property { OwnerId = seller.Id, Title = "Világos otthon", Latitude = 47.5, Longitude = 19.1, Street = "PRIVATE STREET", HouseNumber = "SECRET HOUSE" };
        var search = new SearchRequest { OwnerId = buyer.Id, Title = "Otthont keresek", MaxPrice = 98_765_432m, PublicMaxPrice = 65_000_000m };
        return (seller, buyer, new User(), home, search, new Match { PropertyId = home.Id, SearchRequestId = search.Id, CreatedAt = At });
    }

    [Fact]
    public void ConnectionIsScopedToViewedForeignEntityAndViewerParticipantInsteadOfSharedOwnerOrActiveProfile()
    {
        var f = Pair();
        var otherHome = new Property { OwnerId = f.Seller.Id };
        var otherSearch = new SearchRequest { OwnerId = f.Buyer.Id };
        var matches = new[] { f.Match }.AsQueryable(); var homes = new[] { f.Home, otherHome }.AsQueryable();
        var searches = new[] { f.Search, otherSearch }.AsQueryable(); var users = new[] { f.Seller, f.Buyer, f.Outsider }.AsQueryable();
        ListingConnectionRow? Find(Guid viewer, string kind, Guid id) => PublicListingConnections.ForListing(matches, homes, searches, users, viewer, kind, id).FirstOrDefault();
        Assert.Equal(f.Seller.Id, Find(f.Buyer.Id, "property", f.Home.Id)!.ContactId);
        Assert.Equal(f.Buyer.Id, Find(f.Seller.Id, "search", f.Search.Id)!.ContactId);
        Assert.Null(Find(f.Outsider.Id, "property", f.Home.Id)); Assert.Null(Find(f.Outsider.Id, "search", f.Search.Id));
        Assert.Null(Find(f.Seller.Id, "property", f.Home.Id)); Assert.Null(Find(f.Buyer.Id, "search", f.Search.Id));
        Assert.Null(Find(f.Buyer.Id, "property", otherHome.Id)); Assert.Null(Find(f.Seller.Id, "search", otherSearch.Id));
        Assert.Null(Find(f.Buyer.Id, "unknown", f.Home.Id));
        // Active state is deliberately irrelevant, including no active profile
        // and old agent-agent conversations which remain legitimate history.
        f.Buyer.ActiveKind = "property"; f.Buyer.ActiveEntityId = Guid.NewGuid();
        Assert.NotNull(Find(f.Buyer.Id, "property", f.Home.Id));
        f.Buyer.ActiveKind = null; f.Buyer.ActiveEntityId = null;
        Assert.NotNull(Find(f.Buyer.Id, "property", f.Home.Id));
    }

    [Fact]
    public void ArchivedOwnProfilesKeepConversationAccessButViewedArchivedProfilesAreNotPublic()
    {
        var f = Pair();
        ListingConnectionRow? Find(Guid viewer, string kind, Guid id) => PublicListingConnections.ForListing(
            new[] { f.Match }.AsQueryable(), new[] { f.Home }.AsQueryable(), new[] { f.Search }.AsQueryable(),
            new[] { f.Seller, f.Buyer }.AsQueryable(), viewer, kind, id).FirstOrDefault();
        f.Home.Archived = true;
        Assert.NotNull(Find(f.Seller.Id, "search", f.Search.Id)); Assert.Null(Find(f.Buyer.Id, "property", f.Home.Id));
        f.Home.Archived = false; f.Search.Archived = true;
        Assert.NotNull(Find(f.Buyer.Id, "property", f.Home.Id)); Assert.Null(Find(f.Seller.Id, "search", f.Search.Id));
    }

    [Fact]
    public void SeveralOwnedPairsWithSameViewedListingChooseTheNewestMatchDeterministically()
    {
        var f = Pair(); var second = new SearchRequest { OwnerId = f.Buyer.Id };
        var newest = new Match { Id = Guid.Parse("ffffffff-ffff-ffff-ffff-ffffffffffff"), PropertyId = f.Home.Id, SearchRequestId = second.Id, CreatedAt = At.AddMinutes(1) };
        var lowerTie = new Match { Id = Guid.Empty, PropertyId = f.Home.Id, SearchRequestId = second.Id, CreatedAt = newest.CreatedAt };
        var rows = PublicListingConnections.ForListing(new[] { newest, f.Match, lowerTie }.AsQueryable(), new[] { f.Home }.AsQueryable(),
            new[] { f.Search, second }.AsQueryable(), new[] { f.Seller, f.Buyer }.AsQueryable(), f.Buyer.Id, "property", f.Home.Id).ToArray();
        Assert.Equal(newest.Id, rows[0].MatchId); Assert.Equal(lowerTie.Id, rows[1].MatchId); Assert.Equal(f.Match.Id, rows[2].MatchId);
    }

    [Fact]
    public void ConnectionDtoContainsOnlyAuthorizedContactAndMinimalLinkedProfileMetadata()
    {
        var f = Pair();
        var row = PublicListingConnections.ForListing(new[] { f.Match }.AsQueryable(), new[] { f.Home }.AsQueryable(), new[] { f.Search }.AsQueryable(),
            new[] { f.Seller, f.Buyer }.AsQueryable(), f.Seller.Id, "search", f.Search.Id).Single();
        var connection = JsonSerializer.SerializeToElement(PublicListingConnections.From(row), WebJson);
        Assert.True(connection.GetProperty("connected").GetBoolean()); Assert.Equal(f.Match.Id, connection.GetProperty("matchId").GetGuid());
        Assert.Equal(f.Buyer.Email, connection.GetProperty("contact").GetProperty("email").GetString());
        Assert.Equal(f.Buyer.Phone, connection.GetProperty("contact").GetProperty("phone").GetString());
        Assert.Equal(f.Buyer.Id, connection.GetProperty("contact").GetProperty("id").GetGuid());
        Assert.Equal(PublicLanding.SourceKey("property", f.Home.Id), connection.GetProperty("property").GetProperty("publicListingKey").GetString());
        Assert.Equal(PublicLanding.SourceKey("search", f.Search.Id), connection.GetProperty("searchRequest").GetProperty("publicListingKey").GetString());
        foreach (var field in new[] { "property", "searchRequest" })
            Assert.Equal(new[] { "id", "publicListingKey", "title" }, connection.GetProperty(field).EnumerateObject().Select(value => value.Name).OrderBy(value => value));
        var text = connection.GetRawText();
        foreach (var secret in new[] { "98765432", "65000000", "PRIVATE STREET", "SECRET HOUSE", "latitude", "longitude", "ownerId", "messages", "passwordHash" }) Assert.DoesNotContain(secret, text);
        var absent = JsonSerializer.SerializeToElement(PublicListingConnections.From(null), WebJson);
        Assert.False(absent.GetProperty("connected").GetBoolean()); Assert.Equal(JsonValueKind.Null, absent.GetProperty("contact").ValueKind);
    }

    [Theory]
    [InlineData("property")]
    [InlineData("search")]
    public void QueryIsOneBoundedIndexedProjectionWithoutGeometryMessagesOrActiveUserReads(string kind)
    {
        using var db = Context();
        var sql = PublicListingConnections.ForListing(db.Matches, db.Properties, db.SearchRequests, db.Users,
            Guid.NewGuid(), kind, Guid.NewGuid()).Take(1).ToQueryString();
        var limit = Regex.Match(sql, @"LIMIT\s+(1|@\w+)"); Assert.True(limit.Success, sql);
        if (limit.Groups[1].Value.StartsWith('@')) Assert.Contains("SET " + limit.Groups[1].Value + " = 1;", sql);
        Assert.Contains("ORDER BY", sql); Assert.Contains("INNER JOIN", sql);
        Assert.Contains(kind == "property" ? "`PropertyId`" : "`SearchRequestId`", sql);
        foreach (var field in new[] { "Latitude", "Longitude", "MaxPrice", "PublicMaxPrice", "Messages", "ActiveEntityId", "ActiveKind", "Street", "PasswordHash" }) Assert.DoesNotContain(field, sql);
    }
}
