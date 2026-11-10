using System.Data;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

public static class LikeRefundPolicy
{
    public const int ResponseDays = 14;
    public static DateTime Deadline(Decision decision) => decision.CreatedAt.AddDays(ResponseDays);

    // A delayed job must still refund a late reply; both likes and passes are replies.
    public static bool IsDue(Decision decision, DateTime now, DateTime? repliedAt) =>
        decision.Liked && decision.Charged > 0 && decision.RefundedAt is null
        && now >= Deadline(decision) && (!repliedAt.HasValue || repliedAt.Value > Deadline(decision));
}

/// <summary>Durable, replay-safe refunds. Every call uses fresh contexts and database locks.</summary>
public sealed class LikeRefundService(IServiceScopeFactory scopes, TimeProvider clock, ILogger<LikeRefundService> logger, FeedbackRefundService? feedbackRefunds = null)
{
    public const int BatchSize = 500;

    public async Task<int> RunAsync(Guid? userId = null, CancellationToken cancellationToken = default)
    {
        if (feedbackRefunds is not null) await feedbackRefunds.RunAsync(userId, cancellationToken);
        var now = clock.GetUtcNow().UtcDateTime;
        var cutoff = now.AddDays(-LikeRefundPolicy.ResponseDays);
        List<Guid> candidates;
        await using (var scope = scopes.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDb>();
            var query = db.Decisions.AsNoTracking().Where(decision => decision.Liked && decision.Charged > 0
                && decision.RefundedAt == null && decision.CreatedAt <= cutoff
                && !db.Decisions.Any(reply => reply.PropertyId == decision.PropertyId
                    && reply.SearchRequestId == decision.SearchRequestId && reply.ActorKind != decision.ActorKind
                    && reply.CreatedAt <= decision.CreatedAt.AddDays(LikeRefundPolicy.ResponseDays)));
            if (userId.HasValue) query = query.Where(decision => decision.ActorUserId == userId.Value);
            candidates = await query.OrderBy(decision => decision.CreatedAt).ThenBy(decision => decision.Id)
                .Select(decision => decision.Id).Take(BatchSize).ToListAsync(cancellationToken);
        }
        var refunded = 0;
        foreach (var id in candidates)
        {
            try { if (await RefundOneAsync(id, now, cancellationToken)) refunded++; }
            catch (OverflowException error)
            {
                // Its transaction rolls back; an exceptional balance must not block other users.
                logger.LogError(error, "Refund for decision {DecisionId} exceeds the credit balance range; continuing the batch.", id);
            }
        }
        return refunded;
    }

    public async Task<bool> RefundOneAsync(Guid decisionId, DateTime now, CancellationToken cancellationToken = default)
    {
        await using var scope = scopes.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDb>();
        var candidate = await db.Decisions.AsNoTracking().SingleOrDefaultAsync(decision => decision.Id == decisionId, cancellationToken);
        if (candidate is null || !LikeRefundPolicy.IsDue(candidate, now, null)) return false;
        await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
        // Keep the same lock order as /decisions: actor user, property, search.
        // The pair locks serialize replies/refunds across all Cloud Run instances.
        var user = (await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {candidate.ActorUserId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        if (user is null) return false;
        var property = (await db.Properties.FromSqlInterpolated($"SELECT * FROM `Properties` WHERE `Id` = {candidate.PropertyId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        var search = (await db.SearchRequests.FromSqlInterpolated($"SELECT * FROM `SearchRequests` WHERE `Id` = {candidate.SearchRequestId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        if (property is null || search is null) return false;
        var original = await db.Decisions.SingleAsync(decision => decision.Id == decisionId, cancellationToken);
        var repliedAt = await db.Decisions.AsNoTracking().Where(reply => reply.PropertyId == original.PropertyId
                && reply.SearchRequestId == original.SearchRequestId && reply.ActorKind != original.ActorKind)
            .Select(reply => (DateTime?)reply.CreatedAt).SingleOrDefaultAsync(cancellationToken);
        if (!LikeRefundPolicy.IsDue(original, now, repliedAt)) return false;
        // The immutable original charge remains attached to its unique DecisionId;
        // the separate unique refund key prevents duplicate positive ledger entries.
        original.RefundedAt = now;
        user.Credits = checked(user.Credits + original.Charged);
        var text = $"Visszakaptál {original.Charged} kreditet, mert egy kedvelésedre 14 napon belül nem érkezett válasz.";
        db.CreditEntries.Add(new CreditEntry {
            UserId = user.Id, Amount = original.Charged, Description = "14 napja megválaszolatlan kedvelés visszatérítése",
            RefundedDecisionId = original.Id, CreatedAt = now
        });
        db.UserNotifications.Add(new UserNotification {
            UserId = user.Id, DecisionId = original.Id, Amount = original.Charged, Text = text, CreatedAt = now
        });
        await db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return true;
    }
}

public sealed class LikeRefundWorker(IServiceScopeFactory scopes, ILogger<LikeRefundWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        // Cloud Scheduler is the durable trigger when Cloud Run scales to zero;
        // this worker and authenticated reads are additional catch-up paths.
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(5));
        do
        {
            try
            {
                await using var scope = scopes.CreateAsyncScope();
                await scope.ServiceProvider.GetRequiredService<LikeRefundService>().RunAsync(cancellationToken: stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception error) { logger.LogError(error, "Could not process overdue like refunds; a later invocation will retry."); }
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }
}
