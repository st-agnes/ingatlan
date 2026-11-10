using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class PublicProfileTests
{
    [Theory]
    [InlineData("Kovács Anna", "Anna")]
    [InlineData("Nagy Péter", "Péter")]
    [InlineData("Dr. ifj. Szabó Eszter", "Eszter")]
    [InlineData("Anna", "Anna")]
    [InlineData("Kiss Anna-Mária", "Anna-Mária")]
    [InlineData("Kiss O’Anna", "O’Anna")]
    [InlineData("Kiss Kata · import-12", "Kata")]
    [InlineData("Varga Dániel (teszt)", "Dániel")]
    [InlineData("  Tóth\nRéka  ", "Réka")]
    public void ExtractsOnlyTheGivenName(string name, string expected) => Assert.Equal(expected, PublicProfile.FirstName(name));

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("Anna123")]
    [InlineData("Anna anna@example.test")]
    [InlineData("Anna +36 30 123 4567")]
    [InlineData("www.example.hu")]
    [InlineData("https://example.test/Anna")]
    [InlineData("Anna<script>alert</script>")]
    [InlineData("Kiss A.")]
    public void UnsafeNamesStayPrivate(string? name) => Assert.Equal("", PublicProfile.FirstName(name));

    [Theory]
    [InlineData("Kertes családi otthont keresünk")]
    [InlineData("Felújított lakás 65 m², 2 + 1 fél szoba")]
    [InlineData("2006-ban épült családi ház")]
    [InlineData("120 m² ház 60 000 000 Ft-ért")]
    [InlineData("2–3 szobás otthont keresek 80M-ig")]
    public void RealTitlesPreserveOrdinaryNumericDetails(string title) => Assert.Equal(title, PublicProfile.Title(title, "Cím"));

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("Írj: anna@example.test")]
    [InlineData("Hívj +36 30 123 4567")]
    [InlineData("Telefon: 555 1234")]
    [InlineData("Ház 06 20 123 4567")]
    [InlineData("Otthon https://example.test")]
    [InlineData("Otthon www.example.hu")]
    [InlineData("További képek: example.hu, érdeklődj!")]
    public void ContactTitlesUseTheGeneratedFallback(string? title) => Assert.Equal("Eladó lakás", PublicProfile.Title(title, "Eladó lakás"));

    [Fact]
    public void PublicCardDtosContainOnlyGivenNamesAndNeverAnOwnerContactObject()
    {
        var property = new Property { OwnerId = Guid.NewGuid(), Title = "Kertes otthon", Address = "Titkos utca 12" };
        var search = new SearchRequest { OwnerId = Guid.NewGuid(), LocationIdsJson = "[\"city:Debrecen\"]" };
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
        foreach (var (dto, expected) in new[] { (Dto.Property(property, ownerName: "Nagy Péter"), "Péter"), (Dto.Search(search, ownerName: "Kovács Anna"), "Anna") })
        {
            using var json = JsonDocument.Parse(JsonSerializer.Serialize(dto, options));
            Assert.True(json.RootElement.TryGetProperty("ownerFirstName", out var name));
            Assert.Equal(expected, name.GetString());
            foreach (var field in new[] { "ownerName", "owner", "email", "phone" }) Assert.False(json.RootElement.TryGetProperty(field, out _));
        }
        Assert.DoesNotContain("Titkos utca", JsonSerializer.Serialize(Dto.Property(property, ownerName: "Nagy Péter"), options));
    }
}
