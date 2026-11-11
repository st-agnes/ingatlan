using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class SellerFeedbackSchemaTests
{
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 0, 36))).Options);

    private static void Unique(IEntityType entity, params string[] fields) =>
        Assert.Contains(entity.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(fields));
    private static void Indexed(IEntityType entity, params string[] fields) =>
        Assert.Contains(entity.GetIndexes(), index => index.Properties.Select(property => property.Name).SequenceEqual(fields));

    [Fact]
    public void ImpressionsDeduplicatePeopleAcrossProfilesAndKeepTheFirstSearchReference()
    {
        using var db = Context();
        var impression = db.Model.FindEntityType(typeof(PropertyImpression))!;
        Unique(impression, "PropertyId", "ViewerUserId");
        Assert.Equal(new[] { "Id" }, impression.FindPrimaryKey()!.Properties.Select(property => property.Name));
        Assert.Equal(new[] { typeof(Property), typeof(SearchRequest), typeof(User) },
            impression.GetForeignKeys().Select(key => key.PrincipalEntityType.ClrType).OrderBy(type => type.Name).ToArray());
        Assert.All(impression.GetForeignKeys(), key => Assert.Equal(DeleteBehavior.Restrict, key.DeleteBehavior));
        Indexed(db.Model.FindEntityType(typeof(Decision))!, "PropertyId", "ActorKind", "Liked", "ActorUserId", "SearchRequestId");
    }

    [Fact]
    public void PurchasesAnswersAndRefundsHaveIndependentReplaySafeUniqueKeys()
    {
        using var db = Context();
        var package = db.Model.FindEntityType(typeof(FeedbackPackage))!;
        Unique(package, "OwnerId", "RequestId");
        Indexed(package, "PropertyId", "ExpiresAt");
        Indexed(package, "OwnerId", "ExpiresAt");
        Indexed(package, "RefundedAt", "ExpiresAt");
        var invitation = db.Model.FindEntityType(typeof(FeedbackInvitation))!;
        Unique(invitation, "DecisionId");
        Unique(invitation, "PackageId", "BuyerId");
        Indexed(invitation, "BuyerId", "AnsweredAt", "ExpiresAt");
        Indexed(invitation, "PackageId", "AnsweredAt", "ExpiresAt");
        Indexed(invitation, "PackageId", "Reason");
        Assert.True(invitation.FindProperty("Reason")!.IsNullable);
        var ledger = db.Model.FindEntityType(typeof(CreditEntry))!;
        foreach (var field in new[] { "FeedbackPackageId", "RefundedFeedbackPackageId" })
        {
            Unique(ledger, field); Assert.True(ledger.FindProperty(field)!.IsNullable);
            Assert.Contains(ledger.GetForeignKeys(), key => key.PrincipalEntityType.ClrType == typeof(FeedbackPackage)
                && key.Properties.Single().Name == field && key.DeleteBehavior == DeleteBehavior.Restrict);
        }
    }

    [Fact]
    public void PackageNotificationsNeedNoSyntheticDecisionAndRetainTheirOwnerOnlyReceipt()
    {
        using var db = Context();
        var entity = db.Model.FindEntityType(typeof(UserNotification))!;
        Assert.True(entity.FindProperty("DecisionId")!.IsNullable);
        Assert.True(entity.FindProperty("FeedbackPackageId")!.IsNullable);
        Unique(entity, "DecisionId"); Unique(entity, "FeedbackPackageId");
        var row = new UserNotification { UserId = Guid.NewGuid(), FeedbackPackageId = Guid.NewGuid(),
            Kind = "feedback_refund", Amount = 7, Text = "7 kredit visszatérítve" };
        var receipt = JsonSerializer.SerializeToElement(NotificationItem.From(row), new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.Equal(JsonValueKind.Null, receipt.GetProperty("decisionId").ValueKind);
        Assert.Equal(row.FeedbackPackageId, receipt.GetProperty("feedbackPackageId").GetGuid());
        Assert.False(receipt.TryGetProperty("userId", out _));
        Assert.Equal(row.Amount, receipt.GetProperty("amount").GetInt32());
    }

    [Fact]
    public void NewTablesParticipateInUtcConversionAndForeignKeySafeTestReset()
    {
        using var db = Context();
        var order = TestDataSeed.DeletionOrder(db.Model).ToList();
        foreach (var type in new[] { typeof(PropertyImpression), typeof(FeedbackPackage), typeof(FeedbackInvitation) })
        {
            var entity = db.Model.FindEntityType(type)!;
            Assert.Contains(entity.GetTableName()!, order);
            foreach (var key in entity.GetForeignKeys())
            {
                Assert.Equal(DeleteBehavior.Restrict, key.DeleteBehavior);
                Assert.True(order.IndexOf(entity.GetTableName()!) < order.IndexOf(key.PrincipalEntityType.GetTableName()!));
            }
            var created = entity.FindProperty("CreatedAt")!;
            var unspecified = DateTime.SpecifyKind(new DateTime(2026, 11, 10), DateTimeKind.Unspecified);
            Assert.Equal(DateTimeKind.Utc, ((DateTime)created.GetValueConverter()!.ConvertFromProvider(unspecified)!).Kind);
        }
        Assert.True(order.IndexOf("CreditEntries") < order.IndexOf("FeedbackPackages"));
        Assert.True(order.IndexOf("UserNotifications") < order.IndexOf("FeedbackPackages"));
        Assert.Equal(0, db.Model.FindEntityType(typeof(User))!.FindProperty("FeedbackPassCounter")!.GetDefaultValue());
    }

    [Fact]
    public void FreshMySqlDdlIncludesTheSameUniquenessAndConstraintsUsedByTheAdditiveUpgrade()
    {
        using var db = Context();
        var sql = db.Database.GenerateCreateScript();
        foreach (var identifier in new[] { "PropertyImpressions", "FeedbackPackages", "FeedbackInvitations",
            "IX_PropertyImpressions_PropertyId_ViewerUserId", "IX_FeedbackPackages_OwnerId_RequestId",
            "IX_FeedbackInvitations_PackageId_BuyerId", "IX_FeedbackInvitations_DecisionId",
            "IX_CreditEntries_FeedbackPackageId", "IX_CreditEntries_RefundedFeedbackPackageId",
            "IX_UserNotifications_FeedbackPackageId", "IX_Decisions_PropertyStats", "CK_FeedbackPackages_Size", "CK_FeedbackPackages_Counts" })
            Assert.Contains("`" + identifier + "`", sql);
        Assert.Equal("20261110-seller-feedback-and-insights", SchemaUpgrade.SellerFeedbackVersion);
        Assert.Equal("20261111-continuous-seller-feedback", SchemaUpgrade.ContinuousFeedbackVersion);
    }
}
