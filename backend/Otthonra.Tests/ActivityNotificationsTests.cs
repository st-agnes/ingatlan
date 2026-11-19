using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class ActivityNotificationsTests
{
    private static readonly DateTime At = new(2026, 11, 19, 12, 0, 0, DateTimeKind.Utc);
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);
    private static (User Seller, User Buyer, Property Property, SearchRequest Search) Pair()
    {
        var seller = new User { Name = "Nagy Anna", ActiveKind = "search", ActiveEntityId = Guid.NewGuid() };
        var buyer = new User { Name = "Kiss Péter", ActiveKind = "property", ActiveEntityId = Guid.NewGuid() };
        return (seller, buyer,
            new Property { OwnerId = seller.Id, Title = "Kertes otthon", Price = 60_000_000, Area = 60, Rooms = 2 },
            new SearchRequest { OwnerId = buyer.Id, Title = "Csendes otthont keresek" });
    }
    private static Decision Like(Property property, SearchRequest search, string actorKind = "property") => new() {
        PropertyId = property.Id, SearchRequestId = search.Id, ActorKind = actorKind,
        ActorUserId = actorKind == "property" ? property.OwnerId : search.OwnerId, Liked = true, CreatedAt = At
    };

    [Theory]
    [InlineData("property", "search")]
    [InlineData("search", "property")]
    public void IncomingLikesBelongToTheOtherOwnerAndPointToThatOwnersExactProfile(string actorKind, string ownKind)
    {
        var pair = Pair(); var decision = Like(pair.Property, pair.Search, actorKind);
        var row = ActivityNotifications.IncomingLike(decision, pair.Property, pair.Search, "Nagy Anna");
        Assert.Equal(actorKind == "property" ? pair.Buyer.Id : pair.Seller.Id, row.UserId);
        Assert.Equal("incoming_like", row.Kind);
        Assert.Equal(ownKind, row.EntityKind);
        Assert.Equal(ownKind == "property" ? pair.Property.Id : pair.Search.Id, row.EntityId);
        Assert.Equal(pair.Property.Id, row.PropertyId); Assert.Equal(pair.Search.Id, row.SearchRequestId);
        Assert.Equal(At, row.CreatedAt); Assert.Null(row.ReadAt);
        Assert.Null(row.DecisionId); Assert.Null(row.FeedbackPackageId);
        var target = NotificationItem.From(row).Target!;
        Assert.Equal("incoming", target.Page); Assert.Equal(row.EntityKind, target.EntityKind);
        Assert.Equal(row.EntityId, target.EntityId);
        Assert.Equal(row.PropertyId, target.PropertyId); Assert.Equal(row.SearchRequestId, target.SearchRequestId);
    }

    [Fact]
    public void ReceiptIdentityIsStableAcrossDisplayChangesAndDistinctForDifferentSourceEvents()
    {
        var pair = Pair(); var decision = Like(pair.Property, pair.Search);
        var first = ActivityNotifications.IncomingLike(decision, pair.Property, pair.Search);
        pair.Property.Title = "Átnevezett ingatlan"; pair.Search.Title = "Átnevezett keresés";
        var again = ActivityNotifications.IncomingLike(decision, pair.Property, pair.Search, "Másik Név");
        Assert.Equal((first.UserId, first.EventKey), (again.UserId, again.EventKey));
        Assert.NotEqual(first.EventKey, ActivityNotifications.IncomingLike(Like(pair.Property, pair.Search), pair.Property, pair.Search).EventKey);

        var match = new Match { PropertyId = pair.Property.Id, SearchRequestId = pair.Search.Id, CreatedAt = At };
        var receipts = ActivityNotifications.MatchCreated(match, pair.Property, pair.Search);
        Assert.Equal(2, receipts.Length);
        Assert.Equal(2, receipts.Select(row => (row.UserId, row.EventKey)).Distinct().Count());
        Assert.Equal(new[] { pair.Seller.Id, pair.Buyer.Id }.Order(), receipts.Select(row => row.UserId).Order());
        Assert.All(receipts, row => {
            Assert.Equal("match_created", row.Kind); Assert.Equal(match.Id, row.MatchId);
            Assert.Equal("messages", ActivityNotifications.Target(row)!.Page); Assert.Equal(At, row.CreatedAt);
        });
        Assert.Empty(ActivityNotifications.MatchCreated(match, pair.Property, new SearchRequest { OwnerId = pair.Seller.Id }));
    }

    [Fact]
    public void NotificationsDoNotExposeContactsMessageBodiesRawOwnerIdentifiersOrPrivateEventKeys()
    {
        const string contact = "private-canary@example.test +36 30 123 4567";
        var pair = Pair(); pair.Property.Title = contact; pair.Search.Title = contact;
        pair.Property.Address = "PRIVATE STREET 12"; pair.Property.Latitude = 47.5123456789;
        var like = ActivityNotifications.IncomingLike(Like(pair.Property, pair.Search), pair.Property, pair.Search, contact);
        var match = new Match { PropertyId = pair.Property.Id, SearchRequestId = pair.Search.Id, CreatedAt = At };
        var message = new Message { MatchId = match.Id, SenderId = pair.Seller.Id, Text = "PRIVATE MESSAGE BODY " + contact, CreatedAt = At };
        foreach (var row in new[] { like, ActivityNotifications.MessageReceived(message, match, pair.Property, pair.Search) })
        {
            var json = JsonSerializer.Serialize(NotificationItem.From(row), WebJson);
            Assert.DoesNotContain(contact, json); Assert.DoesNotContain("private-canary@example.test", json);
            Assert.DoesNotContain("+36 30 123 4567", json); Assert.DoesNotContain("PRIVATE MESSAGE BODY", json);
            Assert.DoesNotContain("PRIVATE STREET", json); Assert.DoesNotContain("47.5123456789", json);
            Assert.DoesNotContain(pair.Seller.Id.ToString(), json); Assert.DoesNotContain(pair.Buyer.Id.ToString(), json);
            Assert.DoesNotContain("eventKey", json); Assert.DoesNotContain(row.EventKey!, json);
        }
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void NewMessageReceiptTargetsOnlyTheRecipientAndRetainsItsConversation(bool sellerSends)
    {
        var pair = Pair(); var match = new Match { PropertyId = pair.Property.Id, SearchRequestId = pair.Search.Id };
        var message = new Message { MatchId = match.Id, SenderId = sellerSends ? pair.Seller.Id : pair.Buyer.Id, Text = "Private", CreatedAt = At };
        var row = ActivityNotifications.MessageReceived(message, match, pair.Property, pair.Search);
        Assert.Equal(sellerSends ? pair.Buyer.Id : pair.Seller.Id, row.UserId);
        Assert.Equal(sellerSends ? "search" : "property", row.EntityKind);
        Assert.Equal(match.Id, row.MatchId); Assert.Equal("messages", ActivityNotifications.Target(row)!.Page);
        Assert.Equal(At, row.CreatedAt); Assert.Null(row.DecisionId); Assert.Null(row.FeedbackPackageId);
    }

    [Fact]
    public void FeedbackReceiptsRemainAnonymousAndUseIndependentKeysForResponseCompletionAndExpiry()
    {
        var pair = Pair(); var package = new FeedbackPackage { OwnerId = pair.Seller.Id, PropertyId = pair.Property.Id, Size = 10, ReceivedCount = 10 };
        var invitation = new FeedbackInvitation { BuyerId = pair.Buyer.Id, PackageId = package.Id,
            PropertyId = pair.Property.Id, DecisionId = Guid.NewGuid(), CreatedAt = At.AddDays(-1), AnsweredAt = At, Reason = "other" };
        var rows = new[] { ActivityNotifications.FeedbackReceived(invitation, package, pair.Property),
            ActivityNotifications.FeedbackCompleted(package, pair.Property, At), ActivityNotifications.FeedbackExpired(package, pair.Property, At.AddDays(14)) };
        Assert.Equal(3, rows.Select(row => row.EventKey).Distinct().Count());
        foreach (var row in rows)
        {
            Assert.Equal(pair.Seller.Id, row.UserId); Assert.Equal(pair.Property.Id, row.EntityId);
            Assert.Equal("property", row.EntityKind); Assert.Equal("insights", ActivityNotifications.Target(row)!.Page);
            Assert.Null(row.SearchRequestId); Assert.Null(row.DecisionId); Assert.Null(row.FeedbackPackageId);
            var json = JsonSerializer.Serialize(NotificationItem.From(row), WebJson);
            Assert.DoesNotContain(pair.Buyer.Id.ToString(), json); Assert.DoesNotContain(invitation.DecisionId.ToString(), json);
            Assert.DoesNotContain(invitation.Id.ToString(), json); Assert.DoesNotContain("buyerId", json);
        }
        Assert.Equal(At, rows[0].CreatedAt); Assert.Equal(At, rows[1].CreatedAt); Assert.Equal(At.AddDays(14), rows[2].CreatedAt);
    }

    [Fact]
    public async Task SourceAndReceiptsArePreparedTogetherEvenWhenTheRecipientsOtherProfileIsActive()
    {
        using var db = Context(); var pair = Pair();
        var decision = Like(pair.Property, pair.Search);
        db.AddRange(pair.Seller, pair.Buyer, pair.Property, pair.Search, decision);
        var persisted = false;
        var result = await ActivityNotifications.SaveAsync(db, () => {
            persisted = true;
            var row = Assert.Single(db.UserNotifications.Local);
            Assert.Equal(pair.Buyer.Id, row.UserId); Assert.Equal(pair.Search.Id, row.EntityId);
            Assert.NotEqual(pair.Buyer.ActiveEntityId, row.EntityId);
            Assert.Equal(EntityState.Added, db.Entry(decision).State); Assert.Equal(EntityState.Added, db.Entry(row).State);
            return Task.FromResult(2);
        }, CancellationToken.None);
        Assert.True(persisted); Assert.Equal(2, result);
        await ActivityNotifications.SaveAsync(db, () => Task.FromResult(0), CancellationToken.None);
        Assert.Single(db.UserNotifications.Local);
    }

    [Fact]
    public async Task PassesDeclinedFeedbackAndNonpositiveOrAlreadyRefundNotifiedCreditsDoNotCreateActivityNoise()
    {
        using var db = Context(); var pair = Pair();
        var pass = Like(pair.Property, pair.Search); pass.Liked = false;
        var package = new FeedbackPackage { OwnerId = pair.Seller.Id, PropertyId = pair.Property.Id, Size = 10, CreatedAt = At };
        var declined = new FeedbackInvitation { PropertyId = pair.Property.Id, BuyerId = pair.Buyer.Id, PackageId = package.Id,
            AnsweredAt = At, Reason = SellerFeedbackPolicy.Decline };
        db.AddRange(pair.Seller, pair.Buyer, pair.Property, pair.Search, pass, package, declined,
            new CreditEntry { UserId = pair.Seller.Id, Amount = -2 }, new CreditEntry { UserId = pair.Seller.Id, Amount = 0 },
            new CreditEntry { UserId = pair.Seller.Id, Amount = 2, RefundedDecisionId = Guid.NewGuid() },
            new CreditEntry { UserId = pair.Seller.Id, Amount = 3, RefundedFeedbackPackageId = package.Id });
        await ActivityNotifications.SaveAsync(db, () => Task.FromResult(0), CancellationToken.None);
        Assert.Empty(db.UserNotifications.Local);
    }

    [Fact]
    public async Task PositiveTopupGeneratesOnePrivateReceiptWithoutReusingLegacyRefundKeys()
    {
        using var db = Context(); var user = new User();
        var credit = new CreditEntry { UserId = user.Id, Amount = 50, Description = "Private payment detail", CreatedAt = At };
        db.AddRange(user, credit);
        await ActivityNotifications.SaveAsync(db, () => Task.FromResult(0), CancellationToken.None);
        var row = Assert.Single(db.UserNotifications.Local);
        Assert.Equal(user.Id, row.UserId); Assert.Equal("credit_added", row.Kind); Assert.Equal(50, row.Amount);
        Assert.Equal(At, row.CreatedAt); Assert.Equal("credits", ActivityNotifications.Target(row)!.Page);
        Assert.Null(row.EntityId); Assert.Null(row.DecisionId); Assert.Null(row.FeedbackPackageId);
        Assert.DoesNotContain(credit.Description, row.Text);
    }

    [Fact]
    public void LegacyRefundReceiptsKeepTheirOriginalReadTimestampAndReferences()
    {
        var readAt = At.AddHours(1); var decisionId = Guid.NewGuid(); var packageId = Guid.NewGuid();
        foreach (var kind in new[] { "like_refund", "feedback_refund" })
        {
            var row = new UserNotification { UserId = Guid.NewGuid(), Kind = kind, Amount = 2, DecisionId = decisionId,
                FeedbackPackageId = packageId, Text = "2 kredit visszatérítve", CreatedAt = At, ReadAt = readAt };
            var item = NotificationItem.From(row, 7);
            Assert.Equal(row.Id, item.Id); Assert.Equal(decisionId, item.DecisionId); Assert.Equal(packageId, item.FeedbackPackageId);
            Assert.Equal(At, item.CreatedAt); Assert.Equal(readAt, item.ReadAt); Assert.Equal(7, item.UnreadCount);
            Assert.Equal("credits", item.Target!.Page); Assert.Null(row.EventKey);
        }
        Assert.Null(ActivityNotifications.Target(new UserNotification { Kind = "unrecognized_future_kind" }));
    }

    [Fact]
    public void HistoricalBatchesAcquireRecipientForeignKeysInTheSameOrderAsLiveAccountLocks()
    {
        var firstOwner = Guid.Parse("00000001-0000-0000-0000-000000000000");
        var lastOwner = Guid.Parse("ffffffff-0000-0000-0000-000000000000");
        var firstEvent = new UserNotification { UserId = firstOwner, EventKey = "incoming_like:a" };
        var laterEvent = new UserNotification { UserId = firstOwner, EventKey = "message_received:z" };
        var lastRecipient = new UserNotification { UserId = lastOwner, EventKey = "credit_added:0" };
        // A source-primary-key page can interleave recipients in the opposite order.
        var sourcePage = new[] { lastRecipient, laterEvent, firstEvent };
        Assert.Equal(new[] { firstEvent.Id, laterEvent.Id, lastRecipient.Id },
            ActivityNotificationBackfill.OrderByRecipient(sourcePage).Select(row => row.Id));
        Assert.Equal(new[] { firstEvent.Id, laterEvent.Id, lastRecipient.Id },
            ActivityNotificationBackfill.OrderByRecipient(sourcePage.Reverse()).Select(row => row.Id));
    }

    [Fact]
    public void FreshSchemaAddsOwnerScopedActivityKeysWhilePreservingNullableUniqueRefundReceipts()
    {
        using var db = Context(); var metadata = db.Model.FindEntityType(typeof(UserNotification))!;
        var eventKey = metadata.FindProperty(nameof(UserNotification.EventKey))!;
        Assert.True(eventKey.IsNullable); Assert.Equal(160, eventKey.GetMaxLength());
        Assert.Contains(metadata.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name)
            .SequenceEqual(new[] { nameof(UserNotification.UserId), nameof(UserNotification.EventKey) }));
        foreach (var name in new[] { nameof(UserNotification.DecisionId), nameof(UserNotification.FeedbackPackageId) })
        {
            Assert.True(metadata.FindProperty(name)!.IsNullable);
            Assert.Contains(metadata.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(new[] { name }));
            Assert.Contains(metadata.GetForeignKeys(), key => key.Properties.Select(property => property.Name).SequenceEqual(new[] { name }) && key.DeleteBehavior == DeleteBehavior.Restrict);
        }
        foreach (var name in new[] { nameof(UserNotification.EntityKind), nameof(UserNotification.EntityId),
            nameof(UserNotification.PropertyId), nameof(UserNotification.SearchRequestId), nameof(UserNotification.MatchId) })
            Assert.True(metadata.FindProperty(name)!.IsNullable);
        Assert.Contains(metadata.GetIndexes(), index => index.Properties.Select(property => property.Name)
            .SequenceEqual(new[] { nameof(UserNotification.UserId), nameof(UserNotification.ReadAt), nameof(UserNotification.CreatedAt) }));
        var sql = db.Database.GenerateCreateScript();
        Assert.Contains("CREATE UNIQUE INDEX `IX_UserNotifications_UserId_EventKey` ON `UserNotifications` (`UserId`, `EventKey`)", sql);
        Assert.Matches(@"`EventKey` varchar\(160\)(?: CHARACTER SET ascii)? COLLATE ascii_bin NULL", sql);
        Assert.Equal("20261119-account-activity-notifications", ActivityNotifications.Version);
    }
}
