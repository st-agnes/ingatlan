using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class InteractionTests
{
    private static JsonElement Field(JsonElement item, string name) =>
        item.EnumerateObject().Single(value => value.Name.Equals(name, StringComparison.OrdinalIgnoreCase)).Value;

    [Theory]
    [InlineData("private", "private", true)]
    [InlineData("agent", "private", true)]
    [InlineData("private", "agent", true)]
    [InlineData("agent", "agent", false)]
    [InlineData(null, "agent", true)]
    [InlineData("agent", null, true)]
    public void AgentPairRestrictionIsSymmetricAndPreservesLegacyPrivateAccounts(string? first, string? second, bool allowed)
    {
        Assert.Equal(allowed, AccountTypes.CanInteract(first, second));
        Assert.Equal(allowed, AccountTypes.CanInteract(second, first));
    }

    [Theory]
    [InlineData(null, "suspected_agent")]
    [InlineData("suspected_agent", "suspected_agent")]
    [InlineData(" MISLEADING_CONTENT ", "misleading_content")]
    [InlineData("other_violation", "other_violation")]
    public void ReportReasonsAreCanonicalAndOldClientsRetainTheirOriginalMeaning(string? value, string expected)
    {
        Assert.Equal(expected, ReportReasons.Normalize(value));
        Assert.Null(new ReportInput("property", Guid.NewGuid()).Reason);
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("unknown")]
    public void ExplicitlyEmptyOrUnknownReportReasonCannotBeStored(string value)
        => Assert.Equal(400, Assert.Throws<ApiException>(() => ReportReasons.Normalize(value)).Status);

    [Theory]
    [InlineData("private", "suspected_agent", true)]
    [InlineData("agent", "suspected_agent", false)]
    [InlineData("private", "misleading_content", true)]
    [InlineData("agent", "misleading_content", true)]
    [InlineData("private", "other_violation", true)]
    [InlineData("agent", "other_violation", true)]
    public void GeneralReportsAllowEveryForeignOwnerButSuspectedAgentRequiresAPrivateOwner(string ownerType, string reason, bool allowed)
    {
        var reporter = Guid.NewGuid(); var owner = Guid.NewGuid();
        if (allowed) AccountTypes.ValidateReportTarget(reporter, owner, ownerType, reason);
        else Assert.Equal(400, Assert.Throws<ApiException>(() => AccountTypes.ValidateReportTarget(reporter, owner, ownerType, reason)).Status);
        Assert.Equal(400, Assert.Throws<ApiException>(() => AccountTypes.ValidateReportTarget(owner, owner, ownerType, reason)).Status);
    }

    [Fact]
    public void ReportReceiptsExposeTheChosenReasonAndSourceWithoutAuditTimestampsOrContacts()
    {
        var report = new UserReport {
            ReporterId = Guid.NewGuid(), ReportedUserId = Guid.NewGuid(), EntityKind = "search",
            EntityId = Guid.NewGuid(), Reason = ReportReasons.MisleadingContent
        };
        using var document = JsonDocument.Parse(JsonSerializer.Serialize(new ReportReceipt(report.Id, true,
            report.ReportedUserId, false, report.EntityKind, report.EntityId, report.Reason)));
        var dto = document.RootElement;
        Assert.Equal(report.EntityId, Field(dto, "entityId").GetGuid());
        Assert.Equal("search", Field(dto, "entityKind").GetString());
        Assert.Equal("misleading_content", Field(dto, "reason").GetString());
        Assert.Equal(DateTimeKind.Utc, report.CreatedAt.Kind);
        Assert.DoesNotContain(dto.EnumerateObject(), item => new[] { "createdAt", "reporterId", "email", "phone" }.Contains(item.Name, StringComparer.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData(null, null, 0, 50)]
    [InlineData(0, 1, 0, 1)]
    [InlineData(1_000_000, 100, 1_000_000, 100)]
    public void IncomingLikesUseBoundedPagination(int? offset, int? limit, int expectedOffset, int expectedLimit)
        => Assert.Equal((expectedOffset, expectedLimit), IncomingLikes.Page(offset, limit));

    [Theory]
    [InlineData(-1, 50)]
    [InlineData(1_000_001, 50)]
    [InlineData(0, 0)]
    [InlineData(0, 101)]
    public void InvalidIncomingPaginationIsRejectedBeforeAQuery(int offset, int limit)
        => Assert.Equal(400, Assert.Throws<ApiException>(() => IncomingLikes.Page(offset, limit)).Status);

    [Theory]
    [InlineData(null, false)]
    [InlineData("liked", true)]
    [InlineData("passed", false)]
    public void IncomingLikeDtoPreservesJudgmentAndCompatibilityWithoutUnlockingContact(string? decision, bool compatible)
    {
        var property = new Property { OwnerId = Guid.NewGuid(), Rooms = 3m, Address = "Private street 12" };
        var search = new SearchRequest { OwnerId = Guid.NewGuid() };
        var item = new IncomingLikeItem(Dto.Property(property, ownerAccountType: AccountTypes.Agent), Dto.Search(search),
            property.Id, search.Id, compatible ? 97 : 0, compatible ? ["Megfelelő elhelyezkedés"] : [],
            true, DateTime.UtcNow, decision, null, compatible);
        using var document = JsonDocument.Parse(JsonSerializer.Serialize(item));
        var dto = document.RootElement;
        Assert.Equal(compatible, Field(dto, "compatible").GetBoolean());
        Assert.Equal(decision, Field(dto, "myDecision").ValueKind == JsonValueKind.Null ? null : Field(dto, "myDecision").GetString());
        Assert.Equal(JsonValueKind.Null, Field(dto, "matchId").ValueKind);
        Assert.Equal("", Field(Field(dto, "property"), "address").GetString());
        Assert.Equal("agent", Field(Field(dto, "property"), "ownerAccountType").GetString());
        Assert.DoesNotContain(dto.EnumerateObject(), field => new[] { "contact", "phone", "email" }.Contains(field.Name, StringComparer.OrdinalIgnoreCase));
        Assert.DoesNotContain(Field(dto, "searchRequest").EnumerateObject(), field => new[] { "contact", "phone", "email" }.Contains(field.Name, StringComparer.OrdinalIgnoreCase));
    }

    [Fact]
    public void ReportUniquenessTracksReporterSourceAndReasonWhilePreservingTheOriginalAuditColumns()
    {
        var options = new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options;
        using var db = new AppDb(options);
        var report = db.Model.FindEntityType(typeof(UserReport))!;
        var index = Assert.Single(report.GetIndexes(), item => item.IsUnique);
        Assert.Equal(new[] { "ReporterId", "EntityKind", "EntityId", "Reason" }, index.Properties.Select(property => property.Name));
        Assert.NotNull(report.FindProperty("ReportedUserId"));
        Assert.NotNull(report.FindProperty("CreatedAt"));
        Assert.Equal(2, report.GetForeignKeys().Count());
        Assert.Contains("UNIQUE INDEX `IX_UserReports_ReporterId_EntityKind_EntityId_Reason`", db.Database.GenerateCreateScript());
        Assert.Equal("20261107-interactions-and-report-reasons", SchemaUpgrade.InteractionsAndReportReasonsVersion);
    }
}
