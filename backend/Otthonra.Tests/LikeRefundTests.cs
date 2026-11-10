using System.Text.Json;
using System.Security.Claims;
using Microsoft.Extensions.Configuration;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class LikeRefundTests
{
    private static readonly DateTime Created = new(2026, 1, 1, 12, 30, 0, DateTimeKind.Utc);
    private static Decision Paid(int charged = 2) => new() { Liked = true, Charged = charged, CreatedAt = Created };

    [Fact]
    public void AFullFourteenDaysMustElapseBeforeARefundIsDue()
    {
        var decision = Paid();
        var deadline = Created.AddDays(14);
        Assert.Equal(deadline, LikeRefundPolicy.Deadline(decision));
        Assert.False(LikeRefundPolicy.IsDue(decision, deadline.AddTicks(-1), null));
        Assert.True(LikeRefundPolicy.IsDue(decision, deadline, null));
        Assert.True(LikeRefundPolicy.IsDue(decision, deadline.AddDays(100), null));
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(0)]
    public void AReplyAtOrBeforeTheDeadlineSuppressesARefund(int ticksAfterDeadline)
    {
        Assert.False(LikeRefundPolicy.IsDue(Paid(), Created.AddDays(30), Created.AddDays(14).AddTicks(ticksAfterDeadline)));
        Assert.False(LikeRefundPolicy.IsDue(Paid(), Created.AddDays(30), Created.AddDays(-1)));
    }

    [Fact]
    public void ALateReactionDoesNotEraseARefundOwedDuringScaleToZero()
    {
        Assert.True(LikeRefundPolicy.IsDue(Paid(), Created.AddDays(30), Created.AddDays(14).AddTicks(1)));
    }

    [Theory]
    [InlineData(true, 0)]
    [InlineData(false, 0)]
    [InlineData(false, 2)]
    public void FreeLikesAndPassesNeverGenerateCredits(bool liked, int charged)
    {
        var decision = Paid(charged); decision.Liked = liked;
        Assert.False(LikeRefundPolicy.IsDue(decision, Created.AddYears(1), null));
    }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    public void BothPaidRolesQualifyAndARefundedLikeRemainsLiked(int charge)
    {
        var decision = Paid(charge);
        Assert.True(LikeRefundPolicy.IsDue(decision, Created.AddDays(15), null));
        decision.RefundedAt = Created.AddDays(15);
        Assert.False(LikeRefundPolicy.IsDue(decision, Created.AddDays(30), null));
        Assert.True(decision.Liked);
        Assert.Equal(charge, decision.Charged);
    }

    [Fact]
    public void NotificationsExposeOnlyTheirOwnersReceiptFields()
    {
        var row = new UserNotification { UserId = Guid.NewGuid(), DecisionId = Guid.NewGuid(), Amount = 2, Text = "2 kredit visszatérítve" };
        using var document = JsonDocument.Parse(JsonSerializer.Serialize(NotificationItem.From(row)));
        Assert.DoesNotContain(document.RootElement.EnumerateObject(), field => new[] { "userId", "email", "phone", "address" }.Contains(field.Name, StringComparer.OrdinalIgnoreCase));
        Assert.Equal(DateTimeKind.Utc, row.CreatedAt.Kind);
        Assert.Null(row.ReadAt);
        Assert.Contains(document.RootElement.EnumerateObject(), field => field.Name.Equals("DecisionId", StringComparison.OrdinalIgnoreCase) && field.Value.GetGuid() == row.DecisionId);
    }

    [Theory]
    [InlineData("jobs@test.iam.gserviceaccount.com", "true", true)]
    [InlineData("jobs@test.iam.gserviceaccount.com", "false", false)]
    [InlineData("other@test.iam.gserviceaccount.com", "true", false)]
    [InlineData("jobs@test.iam.gserviceaccount.com.evil.example", "true", false)]
    public void SchedulerRequiresTheExactVerifiedServiceAccount(string email, string verified, bool expected)
    {
        var claims = new[] { new Claim("email", email), new Claim("email_verified", verified) };
        Assert.Equal(expected, RefundEndpoints.IsSchedulerIdentity(new ClaimsPrincipal(new ClaimsIdentity(claims, "Google")), "jobs@test.iam.gserviceaccount.com"));
        Assert.False(RefundEndpoints.IsSchedulerIdentity(new ClaimsPrincipal(new ClaimsIdentity(claims)), "jobs@test.iam.gserviceaccount.com"));
    }

    [Fact]
    public void MissingSchedulerConfigurationKeepsTheInternalEndpointDisabled()
    {
        Assert.Null(RefundSchedulerSettings.From(new ConfigurationBuilder().Build()));
        Assert.Null(RefundSchedulerSettings.From(new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?> {
            ["Scheduler:Audience"] = "https://test.run.app"
        }).Build()));
    }

    [Theory]
    [InlineData("http://test.run.app", "jobs@test.iam.gserviceaccount.com")]
    [InlineData("https://test.run.app/internal/refunds/run", "jobs@test.iam.gserviceaccount.com")]
    [InlineData("https://test.run.app?override=true", "jobs@test.iam.gserviceaccount.com")]
    [InlineData("https://test.run.app", "person@example.com")]
    public void InvalidSchedulerConfigurationFailsClosed(string audience, string email)
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?> {
            ["Scheduler:Audience"] = audience, ["Scheduler:ServiceAccountEmail"] = email
        }).Build();
        Assert.Throws<InvalidOperationException>(() => RefundSchedulerSettings.From(configuration));
    }

    [Fact]
    public void SchedulerAudienceIsTheStableServiceBaseUrl()
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?> {
            ["Scheduler:Audience"] = "https://test.run.app/", ["Scheduler:ServiceAccountEmail"] = "jobs@test.iam.gserviceaccount.com"
        }).Build();
        var settings = RefundSchedulerSettings.From(configuration)!;
        Assert.Equal("https://test.run.app", settings.Audience);
        Assert.Equal("jobs@test.iam.gserviceaccount.com", settings.ServiceAccountEmail);
    }

    [Fact]
    public void RefundLedgerAndNotificationHaveIndependentUniqueDecisionKeysAndRestrictForeignKeys()
    {
        var options = new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options;
        using var db = new AppDb(options);
        var ledger = db.Model.FindEntityType(typeof(CreditEntry))!;
        Assert.Contains(ledger.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(new[] { "DecisionId" }));
        Assert.Contains(ledger.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(new[] { "RefundedDecisionId" }));
        foreach (var name in new[] { "UserId", "DecisionId", "RefundedDecisionId" })
            Assert.Contains(ledger.GetForeignKeys(), key => key.Properties.Select(property => property.Name).SequenceEqual(new[] { name }));
        Assert.All(ledger.GetForeignKeys(), key => Assert.Equal(DeleteBehavior.Restrict, key.DeleteBehavior));
        var notification = db.Model.FindEntityType(typeof(UserNotification))!;
        Assert.Contains(notification.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(new[] { "DecisionId" }));
        foreach (var name in new[] { "UserId", "DecisionId" })
            Assert.Contains(notification.GetForeignKeys(), key => key.Properties.Select(property => property.Name).SequenceEqual(new[] { name }));
        Assert.All(notification.GetForeignKeys(), key => Assert.Equal(DeleteBehavior.Restrict, key.DeleteBehavior));
        Assert.True(db.Model.FindEntityType(typeof(Decision))!.FindProperty("RefundedAt")!.IsNullable);
        Assert.Equal("20261108-public-landing-and-like-refunds", SchemaUpgrade.LikeRefundsVersion);
        var sql = db.Database.GenerateCreateScript();
        Assert.Contains("IX_CreditEntries_RefundedDecisionId", sql);
        Assert.Contains("IX_UserNotifications_DecisionId", sql);
        Assert.Contains("IX_Decisions_Liked_RefundedAt_CreatedAt", sql);
    }
}
