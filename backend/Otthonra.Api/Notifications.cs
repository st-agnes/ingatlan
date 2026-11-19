using System.Security.Claims;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.IdentityModel.Tokens;

namespace Otthonra.Api;

public record NotificationTarget(string Page, string? EntityKind = null, Guid? EntityId = null,
    Guid? PropertyId = null, Guid? SearchRequestId = null, Guid? MatchId = null);
public record NotificationContext(NotificationItem Notification, bool Available, NotificationTarget? Target, bool CanActivate, IncomingLikeItem? Item = null);
public record NotificationItem(Guid Id, string Kind, int Amount, string Text, Guid? DecisionId, DateTime CreatedAt, DateTime? ReadAt,
    Guid? FeedbackPackageId = null, NotificationTarget? Target = null, int? UnreadCount = null)
{
    public static NotificationItem From(UserNotification item, int? unreadCount = null) => new(item.Id, item.Kind, item.Amount, item.Text,
        item.DecisionId, item.CreatedAt, item.ReadAt, item.FeedbackPackageId, ActivityNotifications.Target(item), unreadCount);
}

public sealed record RefundSchedulerSettings(string Audience, string ServiceAccountEmail)
{
    public static RefundSchedulerSettings? From(IConfiguration configuration)
    {
        var audience = configuration["Scheduler:Audience"]?.Trim().TrimEnd('/');
        var email = configuration["Scheduler:ServiceAccountEmail"]?.Trim();
        if (string.IsNullOrEmpty(audience) || string.IsNullOrEmpty(email)) return null;
        if (!Uri.TryCreate(audience, UriKind.Absolute, out var uri) || uri.Scheme != "https"
            || uri.AbsolutePath != "/" || uri.Query.Length > 0 || uri.Fragment.Length > 0 || uri.UserInfo.Length > 0
            || !email.EndsWith(".gserviceaccount.com", StringComparison.Ordinal) || email.Contains(' '))
            throw new InvalidOperationException("Refund scheduler requires an HTTPS service base URL and its dedicated service-account email.");
        return new(audience, email);
    }
}

public static class RefundEndpoints
{
    public const string SchedulerScheme = "GoogleRefundScheduler";
    public const string SchedulerPolicy = "RefundScheduler";

    public static bool IsSchedulerIdentity(ClaimsPrincipal principal, string serviceAccountEmail) =>
        principal.Identity?.IsAuthenticated == true
        && principal.FindFirst("email_verified")?.Value == "true"
        && string.Equals(principal.FindFirst("email")?.Value, serviceAccountEmail, StringComparison.Ordinal);

    public static IServiceCollection AddLikeRefunds(this IServiceCollection services, IConfiguration configuration)
    {
        services.TryAddSingleton<TimeProvider>(TimeProvider.System);
        services.AddSingleton<LikeRefundService>();
        services.AddHostedService<LikeRefundWorker>();
        var settings = RefundSchedulerSettings.From(configuration);
        if (settings is not null)
        {
            services.AddSingleton(settings);
            services.AddAuthentication().AddJwtBearer(SchedulerScheme, options =>
            {
                options.Authority = "https://accounts.google.com";
                options.RequireHttpsMetadata = true;
                options.MapInboundClaims = false;
                options.TokenValidationParameters = new TokenValidationParameters {
                    ValidateIssuer = true, ValidIssuers = ["https://accounts.google.com", "accounts.google.com"],
                    ValidateAudience = true, ValidAudience = settings.Audience, ValidateLifetime = true,
                    RequireExpirationTime = true, ValidateIssuerSigningKey = true, ClockSkew = TimeSpan.FromSeconds(30)
                };
            });
            services.AddAuthorization(options => options.AddPolicy(SchedulerPolicy, policy =>
                policy.AddAuthenticationSchemes(SchedulerScheme).RequireAuthenticatedUser()
                    .RequireAssertion(context => IsSchedulerIdentity(context.User, settings.ServiceAccountEmail))));
        }
        return services;
    }

    public static WebApplication MapLikeRefunds(this WebApplication app)
    {
        if (app.Services.GetService<RefundSchedulerSettings>() is not null)
            app.MapPost("/internal/refunds/run", async (LikeRefundService refunds, CancellationToken cancellationToken) =>
                Results.Ok(new { processed = await refunds.RunAsync(cancellationToken: cancellationToken) }))
                .RequireAuthorization(SchedulerPolicy);
        return app;
    }

    public static RouteGroupBuilder MapNotifications(this RouteGroupBuilder api)
    {
        api.MapGet("/notifications", async (int? offset, int? limit, AppDb db, ClaimsPrincipal principal,
            LikeRefundService refunds, CancellationToken cancellationToken) =>
        {
            var (start, count) = IncomingLikes.Page(offset, limit);
            var userId = principal.UserId();
            await refunds.RunAsync(userId, cancellationToken);
            var query = db.UserNotifications.AsNoTracking().Where(item => item.UserId == userId);
            var total = await query.CountAsync(cancellationToken);
            var unreadCount = await query.CountAsync(item => item.ReadAt == null, cancellationToken);
            var rows = await query.OrderByDescending(item => item.CreatedAt).ThenByDescending(item => item.Id)
                .Skip(start).Take(count).ToListAsync(cancellationToken);
            return Results.Ok(new { items = rows.Select(row => NotificationItem.From(row)), total, unreadCount,
                offset = start, limit = count, hasMore = start + rows.Count < total });
        });
        api.MapPut("/notifications/{id:guid}/read", async (Guid id, AppDb db, ClaimsPrincipal principal,
            TimeProvider clock, CancellationToken cancellationToken) =>
        {
            var userId = principal.UserId();
            var now = clock.GetUtcNow().UtcDateTime;
            // Conditional SQL preserves the first acknowledgement even on retries or concurrent tabs.
            await db.UserNotifications.Where(item => item.Id == id && item.UserId == userId && item.ReadAt == null)
                .ExecuteUpdateAsync(setters => setters.SetProperty(item => item.ReadAt, now), cancellationToken);
            var item = await db.UserNotifications.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id && item.UserId == userId, cancellationToken)
                ?? throw new ApiException(404, "Az értesítés nem található.");
            var unreadCount = await db.UserNotifications.CountAsync(row => row.UserId == userId && row.ReadAt == null, cancellationToken);
            return Results.Ok(NotificationItem.From(item, unreadCount));
        });
        api.MapGet("/notifications/{id:guid}/context", async (Guid id, AppDb db, ClaimsPrincipal principal, CancellationToken cancellationToken) =>
            Results.Ok(await ResolveContextAsync(db, id, principal.UserId(), cancellationToken)));
        return api;
    }

    private static async Task<NotificationContext> ResolveContextAsync(AppDb db, Guid id, Guid userId, CancellationToken ct)
    {
        var row = await db.UserNotifications.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id && item.UserId == userId, ct)
            ?? throw new ApiException(404, "Az értesítés nem található.");
        var notification = NotificationItem.From(row); var target = notification.Target;
        NotificationContext Result(bool available, bool activate = false, IncomingLikeItem? item = null) => new(notification, available, target, activate, item);
        if (target is null) return Result(false);
        if (target.Page == "credits") return Result(true);
        var property = row.PropertyId is { } propertyId ? await db.Properties.AsNoTracking().SingleOrDefaultAsync(p => p.Id == propertyId, ct) : null;
        var search = row.SearchRequestId is { } searchId ? await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(s => s.Id == searchId, ct) : null;
        var owned = row.EntityKind == "property" ? property?.OwnerId == userId && property.Id == row.EntityId
            : row.EntityKind == "search" && search?.OwnerId == userId && search.Id == row.EntityId;
        if (!owned) return Result(false);
        var canActivate = row.EntityKind == "property" ? !property!.Archived : !search!.Archived;
        if (target.Page == "insights") return Result(canActivate, canActivate);
        if (target.Page == "messages")
        {
            var exists = property is not null && search is not null && row.MatchId is { } matchId
                && await db.Matches.AsNoTracking().AnyAsync(m => m.Id == matchId && m.PropertyId == property.Id && m.SearchRequestId == search.Id, ct);
            return Result(exists, exists && canActivate);
        }
        if (target.Page != "incoming" || property is null || search is null || property.Archived || search.Archived || property.OwnerId == search.OwnerId) return Result(false);
        if (row.EventKey is null || !row.EventKey.StartsWith("incoming_like:", StringComparison.Ordinal)
            || !Guid.TryParse(row.EventKey["incoming_like:".Length..], out var decisionId)) return Result(false);
        var opposite = row.EntityKind == "property" ? "search" : "property";
        var incoming = await db.Decisions.AsNoTracking().SingleOrDefaultAsync(d => d.Id == decisionId && d.Liked
            && d.PropertyId == property.Id && d.SearchRequestId == search.Id && d.ActorKind == opposite
            && d.ActorUserId == (opposite == "property" ? property.OwnerId : search.OwnerId), ct);
        if (incoming is null) return Result(false);
        var owners = await db.Users.AsNoTracking().Where(user => user.Id == property.OwnerId || user.Id == search.OwnerId).ToListAsync(ct);
        var seller = owners.SingleOrDefault(user => user.Id == property.OwnerId); var buyer = owners.SingleOrDefault(user => user.Id == search.OwnerId);
        if (seller is null || buyer is null || !AccountTypes.CanInteract(seller.AccountType, buyer.AccountType)) return Result(false);
        var own = await db.Decisions.AsNoTracking().SingleOrDefaultAsync(d => d.PropertyId == property.Id && d.SearchRequestId == search.Id
            && d.ActorKind == row.EntityKind && d.ActorUserId == userId, ct);
        var match = await db.Matches.AsNoTracking().SingleOrDefaultAsync(m => m.PropertyId == property.Id && m.SearchRequestId == search.Id, ct);
        var prepared = MatchingRanking.Prepare(search); var evaluation = MatchingRanking.Evaluate(property, prepared); var compatible = evaluation.Eligible;
        var item = new IncomingLikeItem(Dto.Property(property, ownerAccountType: seller.AccountType, ownerName: seller.Name),
            Dto.Search(search, buyer.AccountType, buyer.Name), property.Id, search.Id, compatible ? evaluation.Score : 0,
            compatible ? evaluation.Reasons : [], true, incoming.CreatedAt, own is null ? null : own.Liked ? "liked" : "passed", match?.Id,
            compatible, evaluation.IsExact, MatchingRanking.ValueForMoney(property), prepared.Specificity, compatible ? evaluation.MatchDetails : []);
        return Result(true, true, item);
    }
}
