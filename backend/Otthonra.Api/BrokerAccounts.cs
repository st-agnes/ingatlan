using System.Data;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>Registration-only account identity and server-controlled decision pricing.</summary>
public static class AccountTypes
{
    public const string Private = "private";
    public const string Agent = "agent";
    public const string SuspectedAgentReason = "suspected_agent";

    public static string RegistrationType(string? value)
    {
        if (value is null) return Private; // Preserve older registration clients.
        var type = value.Trim().ToLowerInvariant();
        if (type is not (Private or Agent)) throw new ApiException(400, "Válassz a magánszemély és az ingatlanközvetítő fióktípus közül.");
        return type;
    }

    public static string PublicType(string? value) => value == Agent ? Agent : Private;
    public static int LikeCost(string accountType, string? kind) => kind switch
    {
        "property" => Rules.SellerLikeCost,
        "search" when accountType == Agent => Rules.AgentSearchLikeCost,
        _ => 0
    };

    public static bool CanInteract(string? firstType, string? secondType) =>
        PublicType(firstType) != Agent || PublicType(secondType) != Agent;

    public static int DecisionCost(string accountType, string? kind, bool liked) => liked ? LikeCost(accountType, kind) : 0;

    public static void ValidateReportTarget(Guid reporterId, Guid reportedUserId, string accountType, string? reason = null)
    {
        if (reporterId == reportedUserId) throw new ApiException(400, "A saját fiókodat nem jelentheted.");
        if (ReportReasons.Normalize(reason) == SuspectedAgentReason && accountType == Agent)
            throw new ApiException(400, "Ez a fiók már ingatlanközvetítőként szerepel.");
    }
}

public static class ReportReasons
{
    public const string MisleadingContent = "misleading_content";
    public const string OtherViolation = "other_violation";
    public const string NoLongerCurrent = "no_longer_current";
    public static readonly string[] Values = [AccountTypes.SuspectedAgentReason, MisleadingContent, OtherViolation, NoLongerCurrent];
    public static string Normalize(string? reason)
    {
        if (reason is null) return AccountTypes.SuspectedAgentReason;
        var value = reason.Trim().ToLowerInvariant();
        if (!Values.Contains(value)) throw new ApiException(400, "Érvénytelen jelentési ok.");
        return value;
    }
}

public static class IncomingLikes
{
    public static (int Offset, int Limit) Page(int? offset, int? limit)
    {
        var start = offset ?? 0; var count = limit ?? 50;
        if (start < 0 || start > 1_000_000 || count < 1 || count > 100)
            throw new ApiException(400, "Érvénytelen lapozási beállítás.");
        return (start, count);
    }
}

public record ReportReceipt(Guid Id, bool Reported, Guid ReportedOwnerId, bool AlreadyReported,
    string EntityKind = "", Guid EntityId = default, string Reason = AccountTypes.SuspectedAgentReason);

public static class AccountReports
{
    public static async Task<ReportReceipt> CreateAsync(AppDb db, Guid reporterId, ReportInput input)
    {
        if (input.EntityKind is not ("property" or "search")) throw new ApiException(400, "Érvénytelen profiltípus.");
        var reason = ReportReasons.Normalize(input.Reason);
        await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted);
        var ownerId = input.EntityKind == "property"
            ? await db.Properties.AsNoTracking().Where(entity => entity.Id == input.EntityId && !entity.Archived).Select(entity => (Guid?)entity.OwnerId).SingleOrDefaultAsync()
            : await db.SearchRequests.AsNoTracking().Where(entity => entity.Id == input.EntityId && !entity.Archived).Select(entity => (Guid?)entity.OwnerId).SingleOrDefaultAsync();
        if (!ownerId.HasValue) throw new ApiException(404, "A jelentett profil nem található.");
        // Lock both user FK rows in a stable order. This serializes duplicate
        // reports and avoids reciprocal A-reports-B/B-reports-A FK deadlocks.
        var users = await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {reporterId} OR `Id` = {ownerId.Value} ORDER BY `Id` FOR UPDATE").ToListAsync();
        var reporter = users.SingleOrDefault(user => user.Id == reporterId)
            ?? throw new ApiException(401, "A fiók nem található.");
        var owner = users.SingleOrDefault(user => user.Id == ownerId.Value)
            ?? throw new ApiException(404, "A jelentett profil nem található.");
        AccountTypes.ValidateReportTarget(reporter.Id, owner.Id, owner.AccountType, reason);
        var previous = await db.UserReports.SingleOrDefaultAsync(report => report.ReporterId == reporter.Id && report.EntityKind == input.EntityKind
            && report.EntityId == input.EntityId && report.Reason == reason);
        if (previous is not null)
        {
            await transaction.CommitAsync();
            return new(previous.Id, true, owner.Id, true, previous.EntityKind, previous.EntityId, previous.Reason);
        }
        var report = new UserReport { ReporterId = reporter.Id, ReportedUserId = owner.Id, EntityKind = input.EntityKind, EntityId = input.EntityId, Reason = reason };
        db.UserReports.Add(report);
        await db.SaveChangesAsync();
        await transaction.CommitAsync();
        return new(report.Id, true, owner.Id, false, report.EntityKind, report.EntityId, report.Reason);
    }
}
