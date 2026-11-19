using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>Account-wide activity receipts. Source writes and their receipts commit together.</summary>
public static class ActivityNotifications
{
    public const string Version = "20261119-account-activity-notifications";
    private static string Title(string value, string fallback) => PublicProfile.Title(value, fallback);
    private static UserNotification Pair(string kind, Guid sourceId, Guid recipient, string ownKind,
        Property property, SearchRequest search, string text, DateTime at, Guid? matchId = null) => new() {
        UserId = recipient, Kind = kind, EventKey = kind + ":" + sourceId.ToString("D"),
        EntityKind = ownKind, EntityId = ownKind == "property" ? property.Id : search.Id,
        PropertyId = property.Id, SearchRequestId = search.Id, MatchId = matchId, Text = text, CreatedAt = at
    };
    public static UserNotification IncomingLike(Decision decision, Property property, SearchRequest search, string actorName = "")
    {
        var ownKind = decision.ActorKind == "property" ? "search" : "property";
        var name = PublicProfile.FirstName(actorName); if (name.Length == 0) name = "Valaki";
        var title = ownKind == "property" ? Title(property.Title, "ingatlanod") : Title(search.Title, "keresésed");
        return Pair("incoming_like", decision.Id, ownKind == "property" ? property.OwnerId : search.OwnerId,
            ownKind, property, search, $"{name} kedvelte a(z) „{title}” profilodat.", decision.CreatedAt);
    }
    public static UserNotification[] MatchCreated(Match match, Property property, SearchRequest search) => property.OwnerId == search.OwnerId ? [] : [
        Pair("match_created", match.Id, property.OwnerId, "property", property, search,
            $"Új párosításod született: „{Title(property.Title, "ingatlanod")}”.", match.CreatedAt, match.Id),
        Pair("match_created", match.Id, search.OwnerId, "search", property, search,
            $"Új párosításod született: „{Title(search.Title, "keresésed")}”.", match.CreatedAt, match.Id)
    ];
    public static UserNotification MessageReceived(Message message, Match match, Property property, SearchRequest search)
    {
        var ownKind = message.SenderId == property.OwnerId ? "search" : "property";
        var title = ownKind == "property" ? Title(property.Title, "ingatlanod") : Title(search.Title, "keresésed");
        return Pair("message_received", message.Id, ownKind == "property" ? property.OwnerId : search.OwnerId,
            ownKind, property, search, $"Új üzeneted érkezett a(z) „{title}” párosításához.", message.CreatedAt, match.Id);
    }
    public static UserNotification FeedbackReceived(FeedbackInvitation invitation, FeedbackPackage package, Property property) => new() {
        UserId = package.OwnerId, Kind = "feedback_received", EventKey = "feedback_received:" + invitation.Id,
        EntityKind = "property", EntityId = property.Id, PropertyId = property.Id,
        Text = $"Új névtelen visszajelzés érkezett a(z) „{Title(property.Title, "ingatlanod") }” ingatlanodra.",
        CreatedAt = invitation.AnsweredAt ?? invitation.CreatedAt
    };
    public static UserNotification FeedbackCompleted(FeedbackPackage package, Property property, DateTime at) => new() {
        UserId = package.OwnerId, Kind = "feedback_completed", EventKey = "feedback_completed:" + package.Id,
        EntityKind = "property", EntityId = property.Id, PropertyId = property.Id,
        Text = $"Megérkezett mind a(z) {package.Size} visszajelzés a(z) „{Title(property.Title, "ingatlanod") }” ingatlanodra.", CreatedAt = at
    };
    public static UserNotification FeedbackExpired(FeedbackPackage package, Property property, DateTime at) => new() {
        UserId = package.OwnerId, Kind = "feedback_expired", EventKey = "feedback_expired:" + package.Id,
        EntityKind = "property", EntityId = property.Id, PropertyId = property.Id,
        Text = $"Lejárt a(z) „{Title(property.Title, "ingatlanod") }” ingatlan visszajelzés-csomagjának kéthetes időszaka.", CreatedAt = at
    };
    public static UserNotification CreditAdded(CreditEntry credit) => new() {
        UserId = credit.UserId, Kind = "credit_added", EventKey = "credit_added:" + credit.Id,
        Amount = credit.Amount, Text = $"Jóváírtunk {credit.Amount} kreditet az egyenlegeden.", CreatedAt = credit.CreatedAt
    };
    public static NotificationTarget? Target(UserNotification item)
    {
        var page = item.Kind switch {
            "incoming_like" => "incoming", "match_created" or "message_received" => "messages",
            "feedback_received" or "feedback_completed" or "feedback_expired" => "insights",
            "credit_added" or "like_refund" or "feedback_refund" => "credits", _ => null
        };
        return page is null ? null : new(page, item.EntityKind, item.EntityId, item.PropertyId, item.SearchRequestId, item.MatchId);
    }

    public static async Task<int> SaveAsync(AppDb db, Func<Task<int>> save, CancellationToken cancellationToken)
    {
        await PrepareAsync(db, cancellationToken).ConfigureAwait(false);
        return await save().ConfigureAwait(false);
    }
    private static async Task PrepareAsync(AppDb db, CancellationToken ct)
    {
        db.ChangeTracker.DetectChanges();
        var likes = db.ChangeTracker.Entries<Decision>().Where(e => e.State == EntityState.Added && e.Entity.Liked).Select(e => e.Entity).ToArray();
        var matches = db.ChangeTracker.Entries<Match>().Where(e => e.State == EntityState.Added).Select(e => e.Entity).ToArray();
        var messages = db.ChangeTracker.Entries<Message>().Where(e => e.State == EntityState.Added).Select(e => e.Entity).ToArray();
        var credits = db.ChangeTracker.Entries<CreditEntry>().Where(e => e.State == EntityState.Added && e.Entity.Amount > 0
            && e.Entity.RefundedDecisionId == null && e.Entity.RefundedFeedbackPackageId == null).Select(e => e.Entity).ToArray();
        var answers = db.ChangeTracker.Entries<FeedbackInvitation>().Where(e => e.Entity.AnsweredAt != null && e.Entity.Reason != null
            && e.Entity.Reason != SellerFeedbackPolicy.Decline && (e.State == EntityState.Added || e.State == EntityState.Modified && e.Property(nameof(FeedbackInvitation.AnsweredAt)).OriginalValue == null))
            .Select(e => e.Entity).ToArray();
        var packages = db.ChangeTracker.Entries<FeedbackPackage>().Where(e => e.State is EntityState.Added or EntityState.Modified).ToArray();
        var legacy = db.ChangeTracker.Entries<UserNotification>().Where(e => e.State == EntityState.Added && e.Entity.EventKey == null).Select(e => e.Entity).ToArray();
        if (likes.Length + matches.Length + messages.Length + credits.Length + answers.Length + packages.Length + legacy.Length == 0) return;
        var cache = new Dictionary<(Type, Guid), object?>();
        async Task<T?> Find<T>(Guid id) where T : class
        {
            if (cache.TryGetValue((typeof(T), id), out var cached)) return (T?)cached;
            var local = db.Set<T>().Local.FirstOrDefault(row => (Guid)db.Entry(row).Property("Id").CurrentValue! == id);
            var value = local ?? await db.Set<T>().AsNoTracking().SingleOrDefaultAsync(row => EF.Property<Guid>(row, "Id") == id, ct);
            cache[(typeof(T), id)] = value; return value;
        }
        var existing = db.UserNotifications.Local.Where(n => n.EventKey != null).Select(n => (n.UserId, n.EventKey!)).ToHashSet();
        void Add(UserNotification item) { if (existing.Add((item.UserId, item.EventKey!))) db.UserNotifications.Add(item); }
        foreach (var decision in likes)
        {
            var p = await Find<Property>(decision.PropertyId); var s = await Find<SearchRequest>(decision.SearchRequestId);
            if (p is null || s is null || p.OwnerId == s.OwnerId || !(decision.ActorKind == "property" && decision.ActorUserId == p.OwnerId
                || decision.ActorKind == "search" && decision.ActorUserId == s.OwnerId)) continue;
            var actor = await Find<User>(decision.ActorUserId);
            Add(IncomingLike(decision, p, s, actor?.Name ?? ""));
        }
        foreach (var match in matches)
        {
            var p = await Find<Property>(match.PropertyId); var s = await Find<SearchRequest>(match.SearchRequestId);
            if (p is null || s is null) continue;
            foreach (var item in MatchCreated(match, p, s)) Add(item);
        }
        foreach (var message in messages)
        {
            var match = await Find<Match>(message.MatchId); if (match is null) continue;
            var p = await Find<Property>(match.PropertyId); var s = await Find<SearchRequest>(match.SearchRequestId);
            if (p is null || s is null || p.OwnerId == s.OwnerId || message.SenderId != p.OwnerId && message.SenderId != s.OwnerId) continue;
            Add(MessageReceived(message, match, p, s));
        }
        foreach (var credit in credits) Add(CreditAdded(credit));
        foreach (var answer in answers)
        {
            var package = await Find<FeedbackPackage>(answer.PackageId); var p = await Find<Property>(answer.PropertyId);
            if (package is not null && p is not null) Add(FeedbackReceived(answer, package, p));
        }
        foreach (var entry in packages)
        {
            var package = entry.Entity; var p = await Find<Property>(package.PropertyId); if (p is null) continue;
            if (package.ReceivedCount >= package.Size && (entry.State == EntityState.Added || Convert.ToInt32(entry.Property(nameof(FeedbackPackage.ReceivedCount)).OriginalValue) < package.Size))
                Add(FeedbackCompleted(package, p, answers.Where(a => a.PackageId == package.Id).Select(a => a.AnsweredAt!.Value).DefaultIfEmpty(package.CreatedAt).Max()));
            if (package.RefundedAt is { } expired && (entry.State == EntityState.Added || entry.Property(nameof(FeedbackPackage.RefundedAt)).OriginalValue == null))
                Add(FeedbackExpired(package, p, expired));
        }
        foreach (var item in legacy)
        {
            if (item.Kind == "like_refund" && item.DecisionId is { } decisionId)
            {
                item.EventKey = "like_refund:" + decisionId;
                var d = await Find<Decision>(decisionId);
                if (d is null || d.ActorUserId != item.UserId) continue;
                item.EntityKind = d.ActorKind; item.EntityId = d.ActorKind == "property" ? d.PropertyId : d.SearchRequestId;
                item.PropertyId = d.PropertyId; item.SearchRequestId = d.SearchRequestId;
            }
            else if (item.Kind == "feedback_refund" && item.FeedbackPackageId is { } packageId)
            {
                item.EventKey = "feedback_refund:" + packageId; var package = await Find<FeedbackPackage>(packageId);
                if (package is null || package.OwnerId != item.UserId) continue;
                item.EntityKind = "property"; item.EntityId = package.PropertyId; item.PropertyId = package.PropertyId;
            }
        }
    }

    /// <summary>Acquire all account locks before any pair/property lock, preventing reciprocal-event FK deadlocks.</summary>
    public static async Task<User[]> LockUsersAsync(AppDb db, IEnumerable<Guid> ids, CancellationToken ct = default)
    {
        var ordered = ids.Distinct().OrderBy(id => id.ToString("D"), StringComparer.Ordinal).ToArray();
        var result = new List<User>();
        foreach (var id in ordered)
            result.Add((await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {id} FOR UPDATE").ToListAsync(ct))
                .SingleOrDefault() ?? throw new ApiException(401, "A fiók nem található."));
        return result.ToArray();
    }
}
