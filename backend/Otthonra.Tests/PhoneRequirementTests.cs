using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class PhoneRequirementTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" \t\r\n ")]
    public void RegistrationAndProfilePhoneCannotBeMissingOrWhitespace(string? phone)
    {
        var error = Assert.Throws<ApiException>(() => Rules.Phone(phone));
        Assert.Equal(400, error.Status);
        Assert.Contains("telefonszám", error.Message);
    }

    [Fact]
    public void PhoneRetainsTheExistingLengthLimitAndTrimsOuterWhitespace()
    {
        Assert.Equal("+36 30 555 0199", Rules.Phone("  +36 30 555 0199  "));
        Assert.Equal(new string('1', 40), Rules.Phone(new string('1', 40)));
        Assert.Equal(400, Assert.Throws<ApiException>(() => Rules.Phone(new string('1', 41))).Status);
    }

    [Fact]
    public void LegacyUsersWithoutPhoneRemainReadableAndPublicListingsNeverGainContactFields()
    {
        var legacy = new User { Name = "Kovács Anna", Email = "anna@example.test", Phone = "" };
        using var own = JsonDocument.Parse(JsonSerializer.Serialize(Dto.Profile(legacy)));
        Assert.Contains(own.RootElement.EnumerateObject(), field => field.Name.Equals("Phone", StringComparison.OrdinalIgnoreCase) && field.Value.GetString() == "");
        foreach (var item in new[] { Dto.Property(new Property { OwnerId = legacy.Id }, ownerName: legacy.Name), Dto.Search(new SearchRequest { OwnerId = legacy.Id }, ownerName: legacy.Name) })
        {
            using var dto = JsonDocument.Parse(JsonSerializer.Serialize(item));
            Assert.DoesNotContain(dto.RootElement.EnumerateObject(), field => field.Name.Equals("Phone", StringComparison.OrdinalIgnoreCase) || field.Name.Equals("Email", StringComparison.OrdinalIgnoreCase));
        }
    }
}
