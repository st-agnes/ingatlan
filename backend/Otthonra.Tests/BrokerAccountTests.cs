using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class BrokerAccountTests
{
    private static JsonElement Field(JsonElement item, string name) =>
        item.EnumerateObject().Single(value => value.Name.Equals(name, StringComparison.OrdinalIgnoreCase)).Value;

    [Theory]
    [InlineData(null, "private")]
    [InlineData("private", "private")]
    [InlineData("agent", "agent")]
    [InlineData(" AGENT ", "agent")]
    public void RegistrationUsesCanonicalTypesAndPreservesOldClients(string? input, string expected)
    {
        Assert.Equal(expected, AccountTypes.RegistrationType(input));
        Assert.Equal("private", new User().AccountType);
        Assert.Null(new RegisterInput("Anna", "anna@example.test", "ComplexPassword2026!", null).AccountType);
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("broker")]
    [InlineData("admin")]
    public void UnknownOrExplicitlyEmptyRegistrationTypeIsRejected(string input)
        => Assert.Equal(400, Assert.Throws<ApiException>(() => AccountTypes.RegistrationType(input)).Status);

    [Theory]
    [InlineData("private", "search", true, 0)]
    [InlineData("agent", "search", true, 1)]
    [InlineData("private", "property", true, 2)]
    [InlineData("agent", "property", true, 2)]
    [InlineData("private", "search", false, 0)]
    [InlineData("agent", "search", false, 0)]
    [InlineData("private", "property", false, 0)]
    [InlineData("agent", "property", false, 0)]
    [InlineData("private", null, true, 0)]
    [InlineData("agent", null, true, 0)]
    public void PricingDependsOnActorAccountAndSideAndNeverChargesPasses(string type, string? side, bool liked, int expected)
        => Assert.Equal(expected, AccountTypes.DecisionCost(type, side, liked));

    [Fact]
    public void BothPublicEntityDtosExposeOnlyTheOwnerTypeAlongsideExistingPublicData()
    {
        var property = new Property { OwnerId = Guid.NewGuid(), Address = "Titkos utca 12.", Rooms = 3 };
        var search = new SearchRequest { OwnerId = Guid.NewGuid() };
        using var propertyDto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property, ownerAccountType: AccountTypes.Agent)));
        using var searchDto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Search(search, AccountTypes.Agent)));
        Assert.Equal("agent", Field(propertyDto.RootElement, "ownerAccountType").GetString());
        Assert.Equal("agent", Field(searchDto.RootElement, "ownerAccountType").GetString());
        Assert.Equal("", Field(propertyDto.RootElement, "address").GetString());
        foreach (var dto in new[] { propertyDto, searchDto })
            Assert.DoesNotContain(dto.RootElement.EnumerateObject(), item => new[] { "Email", "Phone", "PasswordHash" }.Contains(item.Name, StringComparer.OrdinalIgnoreCase));
        using var own = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Property(property, true, AccountTypes.Agent)));
        Assert.Equal("Titkos utca 12.", Field(own.RootElement, "address").GetString());
        using var legacy = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Search(search)));
        Assert.Equal("private", Field(legacy.RootElement, "ownerAccountType").GetString());
    }

    [Fact]
    public void SessionProfileIncludesItsRegistrationType()
    {
        using var dto = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Profile(new User { AccountType = AccountTypes.Agent })));
        Assert.Equal("agent", Field(dto.RootElement, "accountType").GetString());
    }

    [Fact]
    public void ReportsMayTargetOnlyAnotherPrivateAccount()
    {
        var reporter = Guid.NewGuid(); var target = Guid.NewGuid();
        AccountTypes.ValidateReportTarget(reporter, target, AccountTypes.Private);
        Assert.Equal(400, Assert.Throws<ApiException>(() => AccountTypes.ValidateReportTarget(reporter, reporter, AccountTypes.Private)).Status);
        Assert.Equal(400, Assert.Throws<ApiException>(() => AccountTypes.ValidateReportTarget(reporter, target, AccountTypes.Agent)).Status);
    }

    [Fact]
    public void ReportTimestampIsUtcAuditDataAndNotPartOfTheReceipt()
    {
        var before = DateTime.UtcNow;
        var report = new UserReport { ReporterId = Guid.NewGuid(), ReportedUserId = Guid.NewGuid() };
        Assert.Equal(DateTimeKind.Utc, report.CreatedAt.Kind);
        Assert.InRange(report.CreatedAt, before, DateTime.UtcNow);
        Assert.Equal("suspected_agent", report.Reason);
        using var receipt = JsonDocument.Parse(JsonSerializer.Serialize(new ReportReceipt(report.Id, true, report.ReportedUserId, false)));
        Assert.True(Field(receipt.RootElement, "reported").GetBoolean());
        Assert.DoesNotContain(receipt.RootElement.EnumerateObject(), field => field.Name.Contains("At", StringComparison.OrdinalIgnoreCase) || field.Name.Contains("Time", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void ReportSchemaHasUserForeignKeysUniqueReporterTargetAndLegacyTypeDefault()
    {
        var options = new DbContextOptionsBuilder<AppDb>().UseMySql(
            "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 0, 36))).Options;
        using var db = new AppDb(options);
        var userType = db.Model.FindEntityType(typeof(User))!.FindProperty(nameof(User.AccountType))!;
        Assert.Equal("private", userType.GetDefaultValue());
        Assert.Equal(20, userType.GetMaxLength());
        var report = db.Model.FindEntityType(typeof(UserReport))!;
        var unique = Assert.Single(report.GetIndexes(), index => index.IsUnique);
        Assert.Equal(new[] { nameof(UserReport.ReporterId), nameof(UserReport.ReportedUserId) }, unique.Properties.Select(property => property.Name));
        Assert.Equal(2, report.GetForeignKeys().Count());
        Assert.All(report.GetForeignKeys(), foreignKey => Assert.Equal(DeleteBehavior.Restrict, foreignKey.DeleteBehavior));
        Assert.False(report.FindProperty(nameof(UserReport.CreatedAt))!.IsNullable);
        var ddl = db.Database.GenerateCreateScript();
        Assert.Contains("CREATE TABLE `UserReports`", ddl);
        Assert.Contains("COLLATE ascii_general_ci", ddl);
        Assert.Contains("`CreatedAt` datetime(6)", ddl);
        Assert.Equal("20261107-account-types-and-reports", SchemaUpgrade.AccountTypesAndReportsVersion);
    }
}
