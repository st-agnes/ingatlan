using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class IncomingLikeCountTests
{
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test", new MySqlServerVersion(new Version(8, 4, 0))).Options);

    [Theory]
    [InlineData("property")]
    [InlineData("search")]
    public void BadgeIsAnOwnerScopedSqlAggregateWithoutCardOrGeographyMaterialization(string kind)
    {
        using var db = Context();
        var user = new User { Id = Guid.NewGuid(), ActiveKind = kind, ActiveEntityId = Guid.NewGuid() };
        var query = IncomingLikes.Awaiting(db, user);
        var sql = query.GroupBy(_ => 1).Select(group => group.Count()).ToQueryString();
        Assert.Contains("COUNT(*)", sql); Assert.Contains(user.Id.ToString(), sql); Assert.Contains(user.ActiveEntityId.ToString()!, sql);
        Assert.Contains("`Archived`", sql); Assert.Contains("`ActorKind`", sql); Assert.Contains("`ActorUserId`", sql);
        Assert.Contains("`Matches`", sql); Assert.Contains("NOT EXISTS", sql); Assert.Contains("`AccountType`", sql);
        Assert.DoesNotContain("`Description`", sql); Assert.DoesNotContain("`ImagesJson`", sql);
        Assert.DoesNotContain("ST_Distance", sql); Assert.DoesNotContain("MatchingAreas", sql);
        // The same query must support ordered bounded list projection as well.
        var pageSql = query.OrderByDescending(row => row.Decision.CreatedAt).ThenByDescending(row => row.Decision.Id)
            .Take(50).ToQueryString();
        Assert.Contains("LIMIT", pageSql);
    }

    [Fact]
    public void ProfileBadgeIsDistinctFromBothNotificationCounters()
    {
        var json = JsonSerializer.SerializeToElement(Dto.Profile(new User(), unreadNotificationCount: 9,
            newNotificationCount: 7, pendingIncomingLikeCount: 4), new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.Equal(9, json.GetProperty("unreadNotificationCount").GetInt32());
        Assert.Equal(7, json.GetProperty("newNotificationCount").GetInt32());
        Assert.Equal(4, json.GetProperty("pendingIncomingLikeCount").GetInt32());
    }
}
