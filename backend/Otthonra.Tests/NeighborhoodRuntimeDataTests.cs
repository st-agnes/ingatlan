using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public sealed class NeighborhoodRuntimeDataTests
{
    [Fact]
    public void EmbeddedMetadataHasAllPersistentIdsAndSourceVersion()
    {
        Assert.Equal(4308, NeighborhoodCatalog.All.Count);
        Assert.Equal(4308, NeighborhoodCatalog.All.Select(area => area.Id).Distinct().Count());
        Assert.Equal("367af069d58c60e171d189e23673fe20fd5cef51792769c161c3eccb87321e4d", NeighborhoodCatalog.DatasetVersion);
        Assert.All(NeighborhoodCatalog.All, area => {
            Assert.Matches("^neighborhood:[0-9a-f]{24}$", area.Id);
            Assert.Same(area, NeighborhoodCatalog.Get(area.Id));
            Assert.False(string.IsNullOrWhiteSpace(area.City));
            Assert.False(string.IsNullOrWhiteSpace(area.Name));
        });
        Assert.Null(NeighborhoodCatalog.Get("neighborhood:unknown"));
    }

    [Fact]
    public void SearchFindsAccentsCityAndAliasesWithoutMergingNamesAcrossCities()
    {
        const string venkertId = "neighborhood:e8c749e1fc0a306c717ad312";
        Assert.Contains(NeighborhoodCatalog.Search("venkert"), area => area.Id == venkertId);
        Assert.Contains(NeighborhoodCatalog.Search("Debrecen Venkert"), area => area.Id == venkertId);
        var aliasArea = NeighborhoodCatalog.All.First(area => area.Aliases.Length > 0);
        Assert.Contains(NeighborhoodCatalog.Search(aliasArea.Aliases[0], 25), area => area.Id == aliasArea.Id);
        var downtowns = NeighborhoodCatalog.All.Where(area => area.Name == "Belváros").ToArray();
        Assert.True(downtowns.Length > 10);
        Assert.Equal(downtowns.Length, downtowns.Select(area => area.Id).Distinct().Count());
        Assert.Empty(NeighborhoodCatalog.Search(" "));
    }

    [Fact]
    public void SyntheticFixtureCoordinatesUseLatitudeLongitudeContract()
    {
        var point = NeighborhoodCatalog.RepresentativePoint("neighborhood:e8c749e1fc0a306c717ad312");
        Assert.NotNull(point);
        Assert.InRange(point.Latitude, 47.53, 47.55);
        Assert.InRange(point.Longitude, 21.60, 21.63);
        Assert.Null(NeighborhoodCatalog.RepresentativePoint("unknown"));
        Assert.NotNull(NeighborhoodCatalog.TestPointForCity("Hajdúszoboszló"));
        Assert.NotNull(NeighborhoodCatalog.TestPointForCity("Abádszalók"));
        Assert.Null(NeighborhoodCatalog.TestPointForCity("Invented unknown city"));
    }
}
