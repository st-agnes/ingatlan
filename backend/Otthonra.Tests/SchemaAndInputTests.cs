using Microsoft.EntityFrameworkCore;
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
}
