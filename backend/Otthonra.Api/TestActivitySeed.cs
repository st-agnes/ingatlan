using System.Text.RegularExpressions;

namespace Otthonra.Api;

/// <summary>A bounded, validated activity graph for the disposable hosted test catalog.</summary>
public static class TestActivitySeed
{
    public static TestActivityPlan Build(TestActivityScenario[]? scenarios,
        IReadOnlyDictionary<string, (string Owner, string Kind, Guid Id)> references,
        IReadOnlyDictionary<string, User> users, IReadOnlyCollection<Property> properties,
        IReadOnlyCollection<SearchRequest> searches, List<CreditEntry> credits, DateTime now)
    {
        if (scenarios is { Length: > 1000 }) throw new InvalidOperationException("Too many activity fixture scenarios.");
        var decisions = new List<Decision>(); var matches = new List<Match>();
        var messages = new List<Message>(); var notifications = new List<UserNotification>();
        var keys = new HashSet<string>(StringComparer.Ordinal);
        var pairs = new HashSet<(Guid, Guid)>();
        foreach (var scenario in scenarios ?? [])
        {
            if (!Regex.IsMatch(scenario.Key ?? "", @"\A[a-z0-9][a-z0-9-]{0,199}\z") || !keys.Add(scenario.Key)
                || scenario.Actors is not { Length: >= 1 and <= 2 }
                || scenario.Actors.Distinct(StringComparer.Ordinal).Count() != scenario.Actors.Length
                || scenario.Actors.Any(kind => kind is not ("property" or "search"))
                || string.IsNullOrEmpty(scenario.Property) || string.IsNullOrEmpty(scenario.Search)
                || !references.TryGetValue(scenario.Property, out var propertyRef) || propertyRef.Kind != "property"
                || !references.TryGetValue(scenario.Search, out var searchRef) || searchRef.Kind != "search"
                || !pairs.Add((propertyRef.Id, searchRef.Id)))
                throw new InvalidOperationException("Invalid or duplicate activity fixture pair.");
            var property = properties.SingleOrDefault(item => item.Id == propertyRef.Id);
            var search = searches.SingleOrDefault(item => item.Id == searchRef.Id);
            if (property is null || search is null
                || !users.TryGetValue(propertyRef.Owner, out var seller) || seller.Id != property.OwnerId
                || !users.TryGetValue(searchRef.Owner, out var buyer) || buyer.Id != search.OwnerId)
                throw new InvalidOperationException("Activity fixture references must retain their entity owners.");
            if (seller.Id == buyer.Id || !AccountTypes.CanInteract(seller.AccountType, buyer.AccountType)
                || !Rules.Compatible(property, search)
                || !MatchingRanking.Evaluate(property, MatchingRanking.Prepare(search, sellerPerspective: true)).IsExact)
                throw new InvalidOperationException("An activity fixture needs an exact, permitted pair.");
            var at = now.AddMilliseconds(keys.Count * 10);
            foreach (var kind in scenario.Actors)
            {
                var actor = kind == "property" ? seller : buyer;
                var cost = AccountTypes.LikeCost(actor.AccountType, kind);
                if (actor.Credits < cost) throw new InvalidOperationException("Insufficient activity fixture credits.");
                var decision = new Decision {
                    Id = TestDataSeed.StableId($"activity-decision:{scenario.Key}:{kind}"),
                    PropertyId = property.Id, SearchRequestId = search.Id,
                    ActorKind = kind, ActorUserId = actor.Id, Liked = true, Charged = cost, CreatedAt = at
                };
                decisions.Add(decision); actor.Credits -= cost;
                if (cost > 0) credits.Add(new CreditEntry {
                    Id = TestDataSeed.StableId($"activity-charge:{scenario.Key}:{kind}"), UserId = actor.Id,
                    Amount = -cost, DecisionId = decision.Id, Description = "Előkészített tesztérdeklődés", CreatedAt = at
                });
                Add(ActivityNotifications.IncomingLike(decision, property, search, actor.Name), scenario.ReadIncoming);
            }
            if (scenario.Actors.Length == 1)
            {
                if (scenario.PropertyMessage is not null || scenario.SearchMessage is not null)
                    throw new InvalidOperationException("Fixture messages require mutual interest.");
                continue;
            }
            var match = new Match {
                Id = TestDataSeed.StableId("activity-match:" + scenario.Key),
                PropertyId = property.Id, SearchRequestId = search.Id, CreatedAt = at.AddMilliseconds(1)
            };
            matches.Add(match);
            foreach (var item in ActivityNotifications.MatchCreated(match, property, search)) Add(item);
            AddMessage(scenario.PropertyMessage, seller, "property");
            AddMessage(scenario.SearchMessage, buyer, "search");
            void AddMessage(string? text, User sender, string kind)
            {
                if (text is null) return;
                var message = new Message {
                    Id = TestDataSeed.StableId($"activity-message:{scenario.Key}:{kind}"),
                    MatchId = match.Id, SenderId = sender.Id, Text = Rules.Required(text, "test message", 4000),
                    CreatedAt = at.AddMilliseconds(kind == "property" ? 2 : 3)
                };
                messages.Add(message); Add(ActivityNotifications.MessageReceived(message, match, property, search));
            }
        }
        return new(decisions.ToArray(), matches.ToArray(), messages.ToArray(), notifications.ToArray());

        void Add(UserNotification item, bool read = false)
        {
            item.Id = TestDataSeed.StableId($"activity-notification:{item.UserId:D}:{item.EventKey}");
            if (read) item.ReadAt = item.CreatedAt.AddMilliseconds(1);
            notifications.Add(item);
        }
    }
}

public sealed record TestActivityScenario(string Key, string Property, string Search, string[] Actors,
    string? PropertyMessage = null, string? SearchMessage = null, bool ReadIncoming = false);
public sealed record TestActivityPlan(Decision[] Decisions, Match[] Matches, Message[] Messages, UserNotification[] Notifications);
