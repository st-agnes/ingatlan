using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public sealed record NotificationVisitInput(DateTime? Through = null);
public sealed record NotificationVisitReceipt(int NewCount, DateTime? VisitedAt);

/// <summary>Menu visits acknowledge a time boundary, independently of individual read receipts.</summary>
public static class NotificationVisits
{
    public const string Version = "20261127-notification-menu-visits";

    // MySQL datetime(6) stores microseconds. Normalize before serializing and
    // comparing so a server round-trip cannot move an acknowledged boundary.
    public static DateTime Normalize(DateTime value)
    {
        var utc = value.Kind == DateTimeKind.Local ? value.ToUniversalTime() : DateTime.SpecifyKind(value, DateTimeKind.Utc);
        return new DateTime(utc.Ticks - utc.Ticks % 10, DateTimeKind.Utc);
    }
    public static DateTime? Normalize(DateTime? value) => value is DateTime at ? Normalize(at) : null;

    public static DateTime Boundary(DateTime? requested, DateTime serverNow)
    {
        if (requested is not DateTime requestedAt || requestedAt.Year < 1000)
            throw new ApiException(400, "Érvényes értesítési időpont szükséges.");
        var now = Normalize(serverNow);
        var through = Normalize(requestedAt);
        return through > now ? now : through;
    }

    public static IQueryable<UserNotification> Since(IQueryable<UserNotification> source, Guid userId, DateTime? visitedAt)
    {
        var owned = source.Where(item => item.UserId == userId);
        return visitedAt is DateTime boundary ? owned.Where(item => item.CreatedAt > boundary) : owned;
    }

    public static async Task<NotificationVisitReceipt> RecordAsync(AppDb db, Guid userId, DateTime? requested,
        DateTime serverNow, CancellationToken cancellationToken)
    {
        var through = Boundary(requested, serverNow);
        // Atomic max: a delayed response/retry or an older tab may never move
        // the watermark backwards. This intentionally does not modify ReadAt.
        await db.Users.Where(user => user.Id == userId
                && (user.NotificationLastVisitAt == null || user.NotificationLastVisitAt < through))
            .ExecuteUpdateAsync(setters => setters.SetProperty(user => user.NotificationLastVisitAt, through), cancellationToken);
        var user = await db.Users.AsNoTracking().SingleOrDefaultAsync(row => row.Id == userId, cancellationToken)
            ?? throw new ApiException(404, "A felhasználó nem található.");
        var visitedAt = Normalize(user.NotificationLastVisitAt);
        var count = await Since(db.UserNotifications.AsNoTracking(), userId, visitedAt).CountAsync(cancellationToken);
        return new(count, visitedAt);
    }
}
