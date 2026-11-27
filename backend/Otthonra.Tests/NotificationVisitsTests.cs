using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class NotificationVisitsTests
{
    private static readonly DateTime At = new(2026, 11, 27, 12, 0, 0, DateTimeKind.Utc);
    private static AppDb Context() => new(new DbContextOptionsBuilder<AppDb>().UseMySql(
        "Server=localhost;Database=model_only;User=test;Password=test",
        new MySqlServerVersion(new Version(8, 4, 0))).Options);

    [Fact]
    public void VisitBoundaryIsUtcMicrosecondPrecisionAndCannotAcknowledgeFutureEvents()
    {
        var precise = At.AddTicks(1234567);
        Assert.Equal(At.AddTicks(1234560), NotificationVisits.Normalize(precise));
        Assert.Equal(DateTimeKind.Utc, NotificationVisits.Normalize(DateTime.SpecifyKind(precise, DateTimeKind.Unspecified)).Kind);
        Assert.Equal(NotificationVisits.Normalize(precise), NotificationVisits.Normalize(precise.ToLocalTime()));
        Assert.Throws<ApiException>(() => NotificationVisits.Boundary(null, precise));
        Assert.Throws<ApiException>(() => NotificationVisits.Boundary(DateTime.MinValue, precise));
        Assert.Equal(NotificationVisits.Normalize(precise), NotificationVisits.Boundary(precise.AddYears(1), precise));
        Assert.Equal(At.AddMinutes(-1), NotificationVisits.Boundary(At.AddMinutes(-1), precise));
    }

    [Fact]
    public void BadgeCountsAllOwnerEventsAfterVisitEvenWhenIndividuallyRead()
    {
        var owner = Guid.NewGuid(); var otherOwner = Guid.NewGuid();
        var rows = new[] {
            new UserNotification { UserId = owner, CreatedAt = At.AddMinutes(-1) },
            new UserNotification { UserId = owner, CreatedAt = At },
            new UserNotification { UserId = owner, CreatedAt = At.AddTicks(10), ReadAt = At.AddMinutes(2) },
            new UserNotification { UserId = owner, CreatedAt = At.AddMinutes(1) },
            new UserNotification { UserId = otherOwner, CreatedAt = At.AddMinutes(1) }
        };
        var before = rows.Select(row => row.ReadAt).ToArray();
        Assert.Equal(4, NotificationVisits.Since(rows.AsQueryable(), owner, null).Count());
        Assert.Equal(new[] { rows[2].Id, rows[3].Id }, NotificationVisits.Since(rows.AsQueryable(), owner, At).Select(row => row.Id));
        Assert.Empty(NotificationVisits.Since(rows.AsQueryable(), owner, At.AddMinutes(1)));
        Assert.Equal(before, rows.Select(row => row.ReadAt));
    }

    [Fact]
    public void NewBadgeIsAnIndexedOwnerAndTimeQueryIndependentOfReadReceipts()
    {
        using var db = Context();
        var sql = NotificationVisits.Since(db.UserNotifications.AsNoTracking(), Guid.NewGuid(), At)
            .Select(row => row.Id).ToQueryString();
        Assert.Contains("`UserId`", sql); Assert.Contains("`CreatedAt` >", sql);
        Assert.DoesNotContain("`ReadAt`", sql);
        var metadata = db.Model.FindEntityType(typeof(UserNotification))!;
        Assert.Contains(metadata.GetIndexes(), index => index.Properties.Select(property => property.Name)
            .SequenceEqual(new[] { nameof(UserNotification.UserId), nameof(UserNotification.CreatedAt) }));
        var visit = db.Model.FindEntityType(typeof(User))!.FindProperty(nameof(User.NotificationLastVisitAt))!;
        Assert.True(visit.IsNullable); Assert.Equal("datetime(6)", visit.GetColumnType());
        Assert.Equal(NotificationVisits.Version, SchemaUpgrade.NotificationVisitsVersion);
        Assert.Contains("`NotificationLastVisitAt` datetime(6) NULL", db.Database.GenerateCreateScript());
    }

    [Fact]
    public void AuthenticatedAccountDtoKeepsBadgeCountsAndTheirVisitBoundarySeparate()
    {
        var user = new User { Name = "Nagy Anna", PasswordHash = "private-password", NotificationLastVisitAt = DateTime.SpecifyKind(At, DateTimeKind.Unspecified) };
        var json = JsonSerializer.SerializeToElement(Dto.Profile(user, unreadNotificationCount: 8, newNotificationCount: 2),
            new JsonSerializerOptions(JsonSerializerDefaults.Web));
        Assert.Equal(8, json.GetProperty("unreadNotificationCount").GetInt32());
        Assert.Equal(2, json.GetProperty("newNotificationCount").GetInt32());
        Assert.Equal(At, json.GetProperty("notificationLastVisitAt").GetDateTime());
        Assert.EndsWith("Z", json.GetProperty("notificationLastVisitAt").GetString());
        Assert.False(json.TryGetProperty("passwordHash", out _));
        foreach (var listing in new[] { Dto.Property(new Property()), Dto.Search(new SearchRequest()) })
        {
            var publicJson = JsonSerializer.Serialize(listing, new JsonSerializerOptions(JsonSerializerDefaults.Web));
            Assert.DoesNotContain("notificationLastVisitAt", publicJson);
            Assert.DoesNotContain("visitedAt", publicJson);
        }
    }
}
