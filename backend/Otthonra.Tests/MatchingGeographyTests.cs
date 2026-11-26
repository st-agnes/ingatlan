using System.Security.Cryptography;
using System.Text.Json;
using MySqlConnector;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class MatchingGeographyTests
{
    private static SearchRequest Search(params string[] ids) => new() {
        City = "Debrecen", Type = "Lakás", LocationIdsJson = JsonSerializer.Serialize(ids)
    };

    [Fact]
    public void StreetChoicesNeverInventAPolygonAnchorOrBroadenToTheirTown()
    {
        var street = StreetCatalog.All.First();
        Assert.Empty(MatchingGeography.SelectedAreaIds(Search(street.Id)));
        Assert.Equal(new[] { "city:Debrecen" }, MatchingGeography.SelectedAreaIds(Search(street.Id, "city:Debrecen")));
        Assert.Empty(MatchingGeography.SelectedAreaIds(Search("street:000000000000000000000000")));
    }

    [Fact]
    public void AreaSelectionsExpandToEveryMemberOnceAndRetainNeighborhoodAndDistrictGeometry()
    {
        const string venkert = "neighborhood:e8c749e1fc0a306c717ad312";
        var search = Search("area:Budapest", "city:Solymár", "district:Budapest:5", venkert);
        var ids = MatchingGeography.SelectedAreaIds(search);
        Assert.Contains("city:Budapest", ids); Assert.Contains("city:Solymár", ids);
        Assert.Contains("district:Budapest:5", ids); Assert.Contains(venkert, ids);
        Assert.Equal(ids.Distinct(StringComparer.Ordinal).Count(), ids.Length);
        Assert.DoesNotContain("area:Budapest", ids);
        Assert.DoesNotContain(ids, id => id.StartsWith("street:", StringComparison.Ordinal));
        Assert.Equal(ids.Order(StringComparer.Ordinal), ids);
    }

    [Fact]
    public void UnknownChoicesDoNotFallBackToTheLegacyCityForProximity()
    {
        Assert.Empty(MatchingGeography.SelectedAreaIds(Search("city:unknown")));
        Assert.Empty(MatchingGeography.SelectedAreaIds(Search("city:Debrecen", "city:unknown")));
    }

    [Fact]
    public void CanonicalTownIdentitiesPreserveDistinctHungarianAccents()
    {
        Assert.NotNull(LocationCatalog.Get("city:Komló"));
        Assert.NotNull(LocationCatalog.Get("city:Kömlő"));
        Assert.Equal(new[] { "city:Komló", "city:Kömlő" },
            MatchingGeography.SelectedAreaIds(Search("city:Komló", "city:Kömlő")));
        Assert.Equal("utf8mb4_bin", MatchingGeography.IdentityCollation);
    }

    [MySqlCachingSha2Fact]
    public async Task MySqlCanonicalPrimaryKeysKeepKomloAndKomloDistinct()
    {
        // Exercise the actual MySQL identity collation on both CI engine
        // versions without creating permanent tables or changing fixture data.
        var connectionString = Environment.GetEnvironmentVariable("ConnectionStrings__MySql");
        Assert.False(string.IsNullOrWhiteSpace(connectionString));
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        await using var connection = new MySqlConnection(connectionString);
        await connection.OpenAsync(deadline.Token);
        await using var command = connection.CreateCommand();
        command.CommandText = $"CREATE TEMPORARY TABLE `MatchingCanonicalIdentityRegression` (`Id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE {MatchingGeography.IdentityCollation} NOT NULL PRIMARY KEY) ENGINE=InnoDB";
        await command.ExecuteNonQueryAsync(deadline.Token);
        command.CommandText = "INSERT INTO `MatchingCanonicalIdentityRegression` (`Id`) VALUES (@first),(@second)";
        command.Parameters.AddWithValue("@first", "city:Komló");
        command.Parameters.AddWithValue("@second", "city:Kömlő");
        Assert.Equal(2, await command.ExecuteNonQueryAsync(deadline.Token));
        command.Parameters.Clear();
        command.CommandText = "SELECT COUNT(*) FROM `MatchingCanonicalIdentityRegression`";
        Assert.Equal(2, Convert.ToInt32(await command.ExecuteScalarAsync(deadline.Token)));
        command.CommandText = "SELECT COLLATION(`Id`) FROM `MatchingCanonicalIdentityRegression` LIMIT 1";
        Assert.Equal(MatchingGeography.IdentityCollation, Convert.ToString(await command.ExecuteScalarAsync(deadline.Token)));
    }

    [Fact]
    public void DistanceMatchingEmbedsTheOriginalPinnedMunicipalityBoundaries()
    {
        using var stream = typeof(MatchingGeography).Assembly.GetManifestResourceStream(MatchingGeography.MunicipalityResource);
        Assert.NotNull(stream);
        Assert.Equal(NeighborhoodCatalog.ExpectedMunicipalitiesSha256, Convert.ToHexString(SHA256.HashData(stream!)).ToLowerInvariant());
        Assert.Equal(7486, MatchingGeography.ExpectedAreaCount);
    }
}
