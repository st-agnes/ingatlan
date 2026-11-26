using System.Security.Cryptography;
using System.Text.Json;
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
    public void DistanceMatchingEmbedsTheOriginalPinnedMunicipalityBoundaries()
    {
        using var stream = typeof(MatchingGeography).Assembly.GetManifestResourceStream(MatchingGeography.MunicipalityResource);
        Assert.NotNull(stream);
        Assert.Equal(NeighborhoodCatalog.ExpectedMunicipalitiesSha256, Convert.ToHexString(SHA256.HashData(stream!)).ToLowerInvariant());
        Assert.Equal(7486, MatchingGeography.ExpectedAreaCount);
    }
}
