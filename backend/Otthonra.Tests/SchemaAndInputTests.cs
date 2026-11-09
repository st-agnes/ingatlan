using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class SchemaAndInputTests
{
    [Fact]
    public void LargeContentUsesTextColumnsOutsideTheMySqlRowBudget()
    {
        var options = new DbContextOptionsBuilder<AppDb>()
            .UseMySql("Server=localhost;Database=model_only;User=test;Password=test",
                new MySqlServerVersion(new Version(8, 0, 36)))
            .Options;
        using var db = new AppDb(options);
        Assert.Equal("longtext", db.Model.FindEntityType(typeof(Property))!.FindProperty(nameof(Property.Description))!.GetColumnType());
        Assert.Equal("longtext", db.Model.FindEntityType(typeof(Property))!.FindProperty(nameof(Property.ImagesJson))!.GetColumnType());
        Assert.Equal("longtext", db.Model.FindEntityType(typeof(SearchRequest))!.FindProperty(nameof(SearchRequest.DistrictsJson))!.GetColumnType());
        Assert.Equal("longtext", db.Model.FindEntityType(typeof(SearchRequest))!.FindProperty(nameof(SearchRequest.LocationIdsJson))!.GetColumnType());
        Assert.True(db.Model.FindEntityType(typeof(SearchRequest))!.FindProperty(nameof(SearchRequest.LocationIdsJson))!.IsNullable);
        var lotArea = db.Model.FindEntityType(typeof(Property))!.FindProperty(nameof(Property.LotArea))!;
        Assert.True(lotArea.IsNullable); Assert.Equal(18, lotArea.GetPrecision()); Assert.Equal(2, lotArea.GetScale());
        Assert.Equal("longtext", db.Model.FindEntityType(typeof(Message))!.FindProperty(nameof(Message.Text))!.GetColumnType());
        Assert.Equal(255, db.Model.FindEntityType(typeof(User))!.FindProperty(nameof(User.Email))!.GetMaxLength());
    }

    private static PropertyInput ValidPropertyInput() => new(
        "Világos otthon", "Budapest", "XIII.", "Újlipótváros", null,
        "Egy szerethető lakás.", "Lakás", 79_900_000m, 68m, 3m,
        3, "Felújított", "Tégla", true, true, []);

    private static SearchInput ValidSearchInput() => new(
        "Az első otthonunk", "Budapest", ["XIII."], "Világos lakást keresünk.",
        "Lakás", 50_000_000m, 90_000_000m, 50m, 90m, 2m, 4m,
        false, false, "Rugalmas", "Saját megtakarítás");

    [Fact]
    public void NullDistrictElementIsAValidationErrorRatherThanServerFailure()
    {
        var input = ValidSearchInput() with { Districts = [null!] };
        var error = Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), input));
        Assert.Equal(400, error.Status);
    }

    [Fact]
    public void PublicMetadataCannotBeUsedToPublishAContactBeforeMatching()
    {
        var property = ValidPropertyInput();
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), property with { City = "contact@example.hu" }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), property with { Neighborhood = "+36 30 123 4567" }));
        Assert.Throws<ApiException>(() => Rules.Apply(new Property(), property with { Condition = "contact@example.hu" }));
        var search = ValidSearchInput();
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), search with { Districts = ["contact@example.hu"] }));
        Assert.Throws<ApiException>(() => Rules.Apply(new SearchRequest(), search with { MoveIn = "+36 30 123 4567" }));
    }

    [Fact]
    public void PublicCardIdentifiersCanContainPhoneSuffixWithoutExposingContactDetails()
    {
        var owner = new User {
            Id = Guid.Parse("99990000-0000-4000-8000-000000000001"),
            Email = "private-owner@example.test", Phone = "+36 30 555 9999", PasswordHash = "private-password-hash"
        };
        var property = new Property {
            Id = Guid.Parse("00000000-9999-4000-8000-000000000002"), OwnerId = owner.Id,
            LocationId = "city:Debrecen", City = "Debrecen", Address = "Private street 12", Rooms = 3
        };
        var search = new SearchRequest {
            Id = Guid.Parse("00000000-0000-4999-8999-999900000003"), OwnerId = owner.Id,
            LocationIdsJson = "[\"city:Debrecen\"]", City = "Debrecen"
        };
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        var card = JsonSerializer.SerializeToElement(new {
            propertyId = property.Id, searchRequestId = search.Id,
            property = Dto.Property(property), searchRequest = Dto.Search(search)
        }, options);

        // A numeric suffix can occur in a perfectly valid public identifier.
        // Privacy must be checked against fields and complete private values.
        Assert.Contains("9999", card.GetRawText());
        Assert.Equal(property.Id, card.GetProperty("propertyId").GetGuid());
        Assert.Equal(property.Id, card.GetProperty("property").GetProperty("id").GetGuid());
        Assert.Equal(owner.Id, card.GetProperty("property").GetProperty("ownerId").GetGuid());
        Assert.Equal(search.Id, card.GetProperty("searchRequest").GetProperty("id").GetGuid());
        Assert.Equal("", card.GetProperty("property").GetProperty("address").GetString());
        AssertNoPrivateFields(card);
        foreach (var privateValue in new[] { owner.Email, owner.Phone, owner.PasswordHash, property.Address })
            Assert.DoesNotContain(privateValue, card.GetRawText());

        var owned = JsonSerializer.SerializeToElement(Dto.Property(property, own: true), options);
        Assert.Equal(property.Address, owned.GetProperty("address").GetString());
    }

    private static void AssertNoPrivateFields(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            foreach (var field in value.EnumerateObject())
            {
                Assert.DoesNotContain(field.Name.ToLowerInvariant(),
                    new[] { "contact", "email", "phone", "password", "passwordhash", "accesstoken" });
                AssertNoPrivateFields(field.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) AssertNoPrivateFields(item);
    }
}
