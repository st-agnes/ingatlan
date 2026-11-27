using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class TestActivitySeedTests
{
    private static readonly Lazy<TestDataPlan> Built = new(() => TestDataSeed.BuildPlan(TestDataSeed.LoadCatalog()));
    private static TestDataPlan Plan => Built.Value;
    private static readonly DateTime Now = new(2026, 11, 26, 12, 0, 0, DateTimeKind.Utc);

    [Fact]
    public void ActivityChargesFollowActorRolesAndBalancesEqualTheLedger()
    {
        Assert.Equal(9, Plan.Decisions.Length);
        Assert.Equal(2, Plan.Matches.Length);
        Assert.Equal(4, Plan.Messages.Length);
        Assert.Equal(14, Plan.Decisions.Sum(item => item.Charged));
        Assert.Equal(8, Plan.Decisions.Count(item => item.Charged > 0));
        Assert.Equal(9, Plan.Decisions.Select(item => (item.PropertyId, item.SearchRequestId, item.ActorKind)).Distinct().Count());
        foreach (var decision in Plan.Decisions)
        {
            var property = Plan.Properties.Single(item => item.Id == decision.PropertyId);
            var search = Plan.Searches.Single(item => item.Id == decision.SearchRequestId);
            var seller = Plan.Users.Single(item => item.Id == property.OwnerId);
            var buyer = Plan.Users.Single(item => item.Id == search.OwnerId);
            var actor = decision.ActorKind == "property" ? seller : buyer;
            Assert.Contains(decision.ActorKind, new[] { "property", "search" });
            Assert.NotEqual(seller.Id, buyer.Id);
            Assert.True(AccountTypes.CanInteract(seller.AccountType, buyer.AccountType));
            Assert.True(Rules.Compatible(property, search));
            Assert.True(MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search, sellerPerspective: true)).IsExact);
            Assert.Equal(actor.Id, decision.ActorUserId);
            Assert.True(decision.Liked); Assert.Null(decision.RefundedAt);
            Assert.Equal(decision.ActorKind == "property" ? 2 : actor.AccountType == AccountTypes.Agent ? 1 : 0, decision.Charged);
            var charges = Plan.Credits.Where(item => item.DecisionId == decision.Id).ToArray();
            if (decision.Charged == 0) Assert.Empty(charges);
            else
            {
                var charge = Assert.Single(charges);
                Assert.Equal(actor.Id, charge.UserId); Assert.Equal(-decision.Charged, charge.Amount);
                Assert.Equal(decision.CreatedAt, charge.CreatedAt);
                Assert.Null(charge.FeedbackPackageId); Assert.Null(charge.RefundedDecisionId);
            }
        }
        Assert.All(Plan.Users, user => Assert.Equal(user.Credits, Plan.Credits.Where(item => item.UserId == user.Id).Sum(item => item.Amount)));
        Assert.Equal(94, Plan.Users.Single(item => item.Email == "aktivitas-kereso@otthonra.local").Credits);
        Assert.Equal(96, Plan.Users.Single(item => item.Email == "aktivitas-elado@otthonra.local").Credits);
        Assert.Equal(96, Plan.Users.Single(item => item.Email == "aktivitas-ingatlanos@otthonra.local").Credits);
    }

    [Fact]
    public void MatchesRequireBothActorsAndMessagesAlwaysBelongToThoseParticipants()
    {
        foreach (var match in Plan.Matches)
        {
            var decisions = Plan.Decisions.Where(item => item.PropertyId == match.PropertyId && item.SearchRequestId == match.SearchRequestId).ToArray();
            Assert.Equal(new[] { "property", "search" }, decisions.Select(item => item.ActorKind).OrderBy(item => item).ToArray());
            Assert.All(decisions, item => Assert.True(item.CreatedAt < match.CreatedAt));
            var property = Plan.Properties.Single(item => item.Id == match.PropertyId);
            var search = Plan.Searches.Single(item => item.Id == match.SearchRequestId);
            var messages = Plan.Messages.Where(item => item.MatchId == match.Id).ToArray();
            Assert.Equal(2, messages.Length);
            Assert.Equal(new[] { property.OwnerId, search.OwnerId }.OrderBy(item => item), messages.Select(item => item.SenderId).OrderBy(item => item));
            Assert.All(messages, item => { Assert.True(item.CreatedAt > match.CreatedAt); Assert.False(string.IsNullOrWhiteSpace(item.Text)); });
        }
        Assert.All(Plan.Messages, item => Assert.Contains(Plan.Matches, match => match.Id == item.MatchId));
        Assert.Equal(5, Plan.Decisions.Count(item => !Plan.Matches.Any(match => match.PropertyId == item.PropertyId && match.SearchRequestId == item.SearchRequestId)));
    }

    [Fact]
    public void NotificationsHaveUniqueStableIdsCorrectOwnedTargetsAndReadTimestamps()
    {
        Assert.Equal(17, Plan.Notifications.Length);
        Assert.Equal(9, Plan.Notifications.Count(item => item.Kind == "incoming_like"));
        Assert.Equal(4, Plan.Notifications.Count(item => item.Kind == "match_created"));
        Assert.Equal(4, Plan.Notifications.Count(item => item.Kind == "message_received"));
        Assert.Equal(3, Plan.Notifications.Count(item => item.ReadAt is not null));
        Assert.Equal(14, Plan.Notifications.Count(item => item.ReadAt is null));
        var ids = Plan.Users.Select(item => item.Id).Concat(Plan.Properties.Select(item => item.Id))
            .Concat(Plan.Searches.Select(item => item.Id)).Concat(Plan.Credits.Select(item => item.Id))
            .Concat(Plan.Decisions.Select(item => item.Id)).Concat(Plan.Matches.Select(item => item.Id))
            .Concat(Plan.Messages.Select(item => item.Id)).Concat(Plan.Notifications.Select(item => item.Id)).ToArray();
        Assert.Equal(ids.Length, ids.Distinct().Count());
        Assert.Equal(17, Plan.Notifications.Select(item => (item.UserId, item.EventKey)).Distinct().Count());
        foreach (var item in Plan.Notifications)
        {
            Assert.Equal(TestDataSeed.StableId($"activity-notification:{item.UserId:D}:{item.EventKey}"), item.Id);
            var property = Plan.Properties.Single(property => property.Id == item.PropertyId);
            var search = Plan.Searches.Single(search => search.Id == item.SearchRequestId);
            Assert.Equal(item.EntityKind == "property" ? property.OwnerId : search.OwnerId, item.UserId);
            Assert.Equal(item.EntityKind == "property" ? property.Id : search.Id, item.EntityId);
            var target = ActivityNotifications.Target(item);
            Assert.NotNull(target);
            Assert.Equal(item.Kind == "incoming_like" ? "incoming" : "messages", target.Page);
            Assert.Equal(item.EntityKind, target.EntityKind); Assert.Equal(item.EntityId, target.EntityId);
            Assert.Equal(item.PropertyId, target.PropertyId); Assert.Equal(item.SearchRequestId, target.SearchRequestId);
            Assert.Equal(item.MatchId, target.MatchId);
            if (item.ReadAt is { } read) { Assert.Equal("incoming_like", item.Kind); Assert.Equal(item.CreatedAt.AddMilliseconds(1), read); Assert.Equal(DateTimeKind.Utc, read.Kind); }
            if (item.Kind == "incoming_like")
            {
                var source = Plan.Decisions.Single(source => item.EventKey == "incoming_like:" + source.Id.ToString("D"));
                Assert.NotEqual(source.ActorUserId, item.UserId); Assert.Equal(source.CreatedAt, item.CreatedAt);
            }
            else if (item.Kind == "message_received")
            {
                var source = Plan.Messages.Single(source => item.EventKey == "message_received:" + source.Id.ToString("D"));
                Assert.NotEqual(source.SenderId, item.UserId); Assert.Equal(source.MatchId, item.MatchId);
            }
            else Assert.Contains(Plan.Matches, source => item.EventKey == "match_created:" + source.Id.ToString("D") && source.Id == item.MatchId);
        }
        foreach (var user in Plan.Users.Where(item => item.Email.StartsWith("aktivitas-", StringComparison.Ordinal)))
        {
            Assert.Contains(Plan.Notifications, item => item.UserId == user.Id && item.EntityId != user.ActiveEntityId);
            Assert.Contains(Plan.Notifications, item => item.UserId == user.Id && item.ReadAt is null);
            Assert.Contains(Plan.Notifications, item => item.UserId == user.Id && item.ReadAt is not null);
        }
    }

    [Fact]
    public void TheOriginalFourteenAccountsKeepTheirSelectionsBalancesAndCleanActivity()
    {
        var catalog = TestDataSeed.LoadCatalog();
        var originals = catalog.Users.Where(item => !item.Key.StartsWith("activity", StringComparison.Ordinal)).ToArray();
        Assert.Equal(14, originals.Length);
        foreach (var definition in originals)
        {
            var user = Plan.Users.Single(item => item.Id == TestDataSeed.StableId("user:" + definition.Key));
            Assert.Equal(definition.Active.Kind, user.ActiveKind);
            Assert.Equal(TestDataSeed.StableId(definition.Active.Kind + ":" + definition.Active.Key), user.ActiveEntityId);
            Assert.Equal(definition.Email == "visszajelzes-elado@otthonra.local" ? 90 : 100, user.Credits);
            Assert.DoesNotContain(Plan.Decisions, item => item.ActorUserId == user.Id);
            Assert.DoesNotContain(Plan.Notifications, item => item.UserId == user.Id);
            Assert.DoesNotContain(Plan.Messages, item => item.SenderId == user.Id);
            Assert.DoesNotContain(Plan.Credits, item => item.UserId == user.Id && item.DecisionId is not null);
        }
    }

    [Theory]
    [InlineData("unknown-property")]
    [InlineData("wrong-kind")]
    [InlineData("duplicate-pair")]
    [InlineData("duplicate-key")]
    [InlineData("invalid-actor")]
    [InlineData("duplicate-actor")]
    [InlineData("no-actors")]
    [InlineData("invalid-key")]
    [InlineData("too-many-scenarios")]
    [InlineData("own-pair")]
    [InlineData("wrong-owner-reference")]
    [InlineData("missing-owner")]
    [InlineData("agent-pair")]
    [InlineData("different-type")]
    [InlineData("actual-budget")]
    [InlineData("public-budget")]
    [InlineData("insufficient-credits")]
    [InlineData("message-without-match")]
    [InlineData("empty-message")]
    public void InvalidActivityGraphsFailDuringPlanConstructionBeforeAnyDatabaseAccess(string failure)
    {
        var graph = new Graph();
        var scenario = graph.Scenario;
        TestActivityScenario[] scenarios = [scenario];
        switch (failure)
        {
            case "unknown-property": scenarios = [scenario with { Property = "missing" }]; break;
            case "wrong-kind": scenarios = [scenario with { Property = "search" }]; break;
            case "duplicate-pair": scenarios = [scenario, scenario with { Key = "another" }]; break;
            case "duplicate-key": scenarios = [scenario, scenario]; break;
            case "invalid-actor": scenarios = [scenario with { Actors = ["other"] }]; break;
            case "duplicate-actor": scenarios = [scenario with { Actors = ["property", "property"] }]; break;
            case "no-actors": scenarios = [scenario with { Actors = [] }]; break;
            case "invalid-key": scenarios = [scenario with { Key = "../invalid" }]; break;
            case "too-many-scenarios": scenarios = Enumerable.Repeat(scenario, 101).ToArray(); break;
            case "own-pair": graph.Search.OwnerId = graph.Seller.Id; graph.References["search"] = ("seller", "search", graph.Search.Id); break;
            case "wrong-owner-reference": graph.References["property"] = ("buyer", "property", graph.Property.Id); break;
            case "missing-owner": graph.Search.OwnerId = Guid.NewGuid(); break;
            case "agent-pair": graph.Seller.AccountType = graph.Buyer.AccountType = AccountTypes.Agent; break;
            case "different-type": graph.Search.Type = "Ház"; break;
            case "actual-budget": graph.Search.MaxPrice = 60_000_000m; break;
            case "public-budget": graph.Search.PublicMaxPrice = 60_000_000m; break;
            case "insufficient-credits": graph.Seller.Credits = 1; break;
            case "message-without-match": scenarios = [scenario with { Actors = ["property"], SearchMessage = "Nem lehet üzenet" }]; break;
            case "empty-message": scenarios = [scenario with { SearchMessage = " " }]; break;
        }
        // No AppDb or connection is available to this helper: rejection precedes reset SQL.
        Assert.ThrowsAny<Exception>(() => graph.Build(scenarios));
    }

    [Fact]
    public void PublicSearchDataAndActivityNotificationsNeverExposeThePrivateMaximum()
    {
        var graph = new Graph();
        var activity = graph.Build();
        Assert.Equal(2, activity.Decisions.Length); Assert.Single(activity.Matches); Assert.Equal(2, activity.Messages.Length);
        var json = JsonSerializer.Serialize(new { search = Dto.Search(graph.Search), activity.Notifications }, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.Contains("70000000", json); Assert.DoesNotContain("80000000", json);
        Assert.DoesNotContain("publicMaxPrice", json);
        var rebuilt = new Graph().Build();
        Assert.Equal(activity.Decisions.Select(item => item.Id), rebuilt.Decisions.Select(item => item.Id));
        Assert.Equal(activity.Matches.Select(item => item.Id), rebuilt.Matches.Select(item => item.Id));
        Assert.Equal(activity.Messages.Select(item => item.Id), rebuilt.Messages.Select(item => item.Id));
        Assert.Equal(activity.Notifications.Select(item => item.Id), rebuilt.Notifications.Select(item => item.Id));
        Assert.All(activity.Notifications, item => Assert.Equal(DateTimeKind.Utc, item.CreatedAt.Kind));
    }

    private sealed class Graph
    {
        public User Seller { get; } = new() { Id = TestDataSeed.StableId("test-seller"), Name = "Teszt Anna", Credits = 100 };
        public User Buyer { get; } = new() { Id = TestDataSeed.StableId("test-buyer"), Name = "Teszt Péter", Credits = 100 };
        public Property Property { get; }
        public SearchRequest Search { get; }
        public Dictionary<string, (string Owner, string Kind, Guid Id)> References { get; }
        public TestActivityScenario Scenario { get; } = new("test-pair", "property", "search", ["property", "search"], "Üdvözöllek!", "Köszönöm!");
        public Graph()
        {
            Property = new() { Id = TestDataSeed.StableId("test-property"), OwnerId = Seller.Id, Title = "Tesztlakás", Type = "Lakás", LocationId = "city:Debrecen", City = "Debrecen", Price = 65_000_000m, Area = 60m, Rooms = 2m };
            Search = new() { Id = TestDataSeed.StableId("test-search"), OwnerId = Buyer.Id, Title = "Tesztkeresés", Type = "Lakás", City = "Debrecen", LocationIdsJson = "[\"city:Debrecen\"]", MaxPrice = 80_000_000m, PublicMaxPrice = 70_000_000m };
            References = new(StringComparer.Ordinal) { ["property"] = ("seller", "property", Property.Id), ["search"] = ("buyer", "search", Search.Id) };
        }
        public TestActivityPlan Build(TestActivityScenario[]? scenarios = null) => TestActivitySeed.Build(scenarios ?? [Scenario], References,
            new Dictionary<string, User>(StringComparer.Ordinal) { ["seller"] = Seller, ["buyer"] = Buyer }, [Property], [Search], [], Now);
    }
}
