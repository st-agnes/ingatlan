using System.Security.Claims;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.IdentityModel.Tokens;

namespace Otthonra.Api;

public record NotificationItem(Guid Id, string Kind, int Amount, string Text, Guid DecisionId, DateTime CreatedAt, DateTime? ReadAt)
{
    public static NotificationItem From(UserNotification item) => new(item.Id, item.Kind, item.Amount, item.Text, item.DecisionId, item.CreatedAt, item.ReadAt);
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
            return Results.Ok(new { items = rows.Select(NotificationItem.From), total, unreadCount,
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
            return Results.Ok(NotificationItem.From(item));
        });
        return api;
    }
}
