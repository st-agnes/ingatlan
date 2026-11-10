using System.Data;
using System.Security.Claims;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace Otthonra.Api;

public sealed record FeedbackOption(string Value, string Label);
public sealed record FeedbackPrompt(Guid Id, Guid PropertyId, string SellerFirstName, string Title, string Question,
    IReadOnlyList<FeedbackOption> Options, DateTime ExpiresAt);
public sealed record FeedbackPackageItem(Guid Id, int Size, int ReceivedCount, int Remaining, bool Enabled,
    DateTime CreatedAt, DateTime ExpiresAt, DateTime? RefundedAt, int RefundedCredits, string Status);
public sealed record FeedbackPackageInput(int Size, Guid RequestId);
public sealed record FeedbackToggleInput(bool Enabled);
public sealed record FeedbackAnswerInput(string? Reason);
public sealed record ImpressionInput(Guid PropertyId, Guid SearchRequestId);

public static class SellerFeedbackPolicy
{
    public const int DurationDays = 14;
    public const int PromptSpacing = 20;
    public const int InvitationMinutes = 15;
    public const string Decline = "decline";
    public static readonly int[] PackageSizes = [10, 20, 50];
    public static readonly FeedbackOption[] Options = [
        new("insufficient_information", "Túl kevés információ van megosztva az ingatlanról"),
        new("layout", "Nem tetszik az ingatlan elrendezése"),
        new("lighting", "Nem jók a fényviszonyok az ingatlanban"),
        new("location", "Az ingatlan elhelyezkedése nem szimpatikus"),
        new("view", "Nem tetszik, vagy nem látszik a képeken a kilátás az ablakokból"),
        new("incorrect_parameters", "Az ingatlan nem felel meg a róla feltüntetett paramétereknek"),
        new("other", "Egyéb"),
        new(Decline, "Nem szeretnék válaszolni")
    ];
    public static bool IsReason(string? value) => value is not null && Options.Any(option => option.Value == value);
    public static string Label(string value) => Options.Single(option => option.Value == value).Label;
    public static bool IsPeriodActive(FeedbackPackage package, DateTime now) => now < package.ExpiresAt && package.RefundedAt is null;
    public static int Missing(FeedbackPackage package) => Math.Max(0, package.Size - package.ReceivedCount);
    public static FeedbackPackageItem Package(FeedbackPackage package, DateTime now) => new(package.Id, package.Size,
        package.ReceivedCount, Missing(package), package.Enabled, package.CreatedAt, package.ExpiresAt,
        package.RefundedAt, package.RefundedCredits,
        !IsPeriodActive(package, now) ? "expired" : package.ReceivedCount >= package.Size ? "completed" : "active");

    public static string PromptTitle(string? name)
    {
        var givenName = PublicProfile.FirstName(name);
        if (givenName.Length == 0) return "Segíts az eladónak egy visszajelzéssel";
        string dative;
        if (givenName.EndsWith('a')) dative = givenName[..^1] + "ának";
        else if (givenName.EndsWith('e')) dative = givenName[..^1] + "ének";
        else
        {
            // Neutral i/í/é follow the last non-neutral vowel; this common
            // mixed-vowel name has an established front-vowel ending.
            var frontException = givenName.Equals("Noémi", StringComparison.OrdinalIgnoreCase);
            var vowel = givenName.ToLowerInvariant().Reverse().FirstOrDefault(character => "aáoóuúeöőüű".Contains(character));
            dative = givenName + (!frontException && "aáoóuú".Contains(vowel) ? "nak" : "nek");
        }
        return $"Segíts {dative} egy visszajelzéssel";
    }
}

/// <summary>All writes use the existing actor-user / property lock order.</summary>
public static class SellerFeedback
{
    public static IServiceCollection AddSellerFeedback(this IServiceCollection services)
    {
        services.TryAddSingleton<TimeProvider>(TimeProvider.System);
        services.AddSingleton<FeedbackRefundService>();
        return services;
    }

    public static RouteGroupBuilder MapSellerFeedback(this RouteGroupBuilder api)
    {
        api.MapGet("/properties/{id:guid}/insights", async (Guid id, int? offset, int? limit, AppDb db,
            ClaimsPrincipal principal, FeedbackRefundService refunds, TimeProvider clock, CancellationToken cancellationToken) =>
        {
            var uid = principal.UserId();
            await refunds.RunAsync(uid, cancellationToken);
            await using var snapshot = await db.Database.BeginTransactionAsync(IsolationLevel.RepeatableRead, cancellationToken);
            _ = await OwnedPropertyAsync(db, id, uid, cancellationToken);
            var page = IncomingLikes.Page(offset, limit);
            var now = clock.GetUtcNow().UtcDateTime;
            var impressions = db.PropertyImpressions.AsNoTracking().Where(row => row.PropertyId == id);
            var uniqueViewers = await impressions.CountAsync(cancellationToken);
            var buyerLikes = await db.Decisions.AsNoTracking().Where(row => row.PropertyId == id && row.ActorKind == "search" && row.Liked)
                .Select(row => row.ActorUserId).Distinct().CountAsync(cancellationToken);
            var sellerLikes = await db.Decisions.AsNoTracking().CountAsync(row => row.PropertyId == id && row.ActorKind == "property" && row.Liked, cancellationToken);
            var matchedUsers = from match in db.Matches.AsNoTracking()
                join search in db.SearchRequests.AsNoTracking() on match.SearchRequestId equals search.Id
                where match.PropertyId == id
                select search.OwnerId;
            var matchedViewers = await impressions.Where(row => matchedUsers.Contains(row.ViewerUserId)).CountAsync(cancellationToken);
            var responses = from invitation in db.FeedbackInvitations.AsNoTracking()
                join package in db.FeedbackPackages.AsNoTracking() on invitation.PackageId equals package.Id
                where package.PropertyId == id && package.OwnerId == uid && invitation.AnsweredAt != null
                    && invitation.Reason != null && invitation.Reason != SellerFeedbackPolicy.Decline
                select invitation;
            var total = await responses.CountAsync(cancellationToken);
            var counts = await responses.GroupBy(row => row.Reason).Select(group => new { Reason = group.Key!, Count = group.Count() })
                .ToDictionaryAsync(row => row.Reason, row => row.Count, cancellationToken);
            var responseRows = await responses.OrderByDescending(row => row.AnsweredAt).ThenByDescending(row => row.Id)
                .Skip(page.Offset).Take(page.Limit).Select(row => new { row.Id, Reason = row.Reason!, CreatedAt = row.AnsweredAt!.Value })
                .ToListAsync(cancellationToken);
            var packages = await db.FeedbackPackages.AsNoTracking().Where(row => row.PropertyId == id && row.OwnerId == uid)
                .OrderByDescending(row => row.CreatedAt).ThenByDescending(row => row.Id).Take(20).ToListAsync(cancellationToken);
            var current = packages.FirstOrDefault(row => SellerFeedbackPolicy.IsPeriodActive(row, now));
            var result = new {
                propertyId = id,
                stats = new { uniqueViewers, buyerLikes, sellerLikes, matchedViewers,
                    matchRate = uniqueViewers == 0 ? 0m : Math.Round(100m * matchedViewers / uniqueViewers, 1, MidpointRounding.AwayFromZero) },
                feedback = new { total, items = responseRows.Select(row => new { row.Id, row.Reason, label = SellerFeedbackPolicy.Label(row.Reason), row.CreatedAt }),
                    reasonCounts = SellerFeedbackPolicy.Options.Where(option => option.Value != SellerFeedbackPolicy.Decline)
                        .Select(option => new { reason = option.Value, label = option.Label, count = counts.GetValueOrDefault(option.Value) }),
                    offset = page.Offset, limit = page.Limit, hasMore = page.Offset + responseRows.Count < total },
                activePackage = current is null ? null : SellerFeedbackPolicy.Package(current, now),
                packages = packages.Select(row => SellerFeedbackPolicy.Package(row, now)),
                packageSizes = SellerFeedbackPolicy.PackageSizes, durationDays = SellerFeedbackPolicy.DurationDays, creditCostPerFeedback = 1
            };
            await snapshot.CommitAsync(cancellationToken);
            return Results.Ok(result);
        });

        api.MapPost("/properties/{id:guid}/feedback-packages", async (Guid id, FeedbackPackageInput input, AppDb db,
            ClaimsPrincipal principal, FeedbackRefundService refunds, TimeProvider clock, CancellationToken cancellationToken) =>
        {
            if (!SellerFeedbackPolicy.PackageSizes.Contains(input.Size) || input.RequestId == Guid.Empty)
                throw new ApiException(400, "Válassz 10, 20 vagy 50 visszajelzéses csomagot.");
            var uid = principal.UserId();
            await refunds.RunAsync(uid, cancellationToken);
            var now = clock.GetUtcNow().UtcDateTime;
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            var user = await LockedUserAsync(db, uid, cancellationToken);
            var property = await LockedPropertyAsync(db, id, cancellationToken);
            if (property.OwnerId != uid) throw new ApiException(404, "Az ingatlan nem található.");
            now = clock.GetUtcNow().UtcDateTime;
            var prior = await db.FeedbackPackages.SingleOrDefaultAsync(row => row.OwnerId == uid && row.RequestId == input.RequestId, cancellationToken);
            if (prior is not null)
            {
                if (prior.PropertyId != id || prior.Size != input.Size) throw new ApiException(409, "Ezt a vásárlási azonosítót már felhasználtad.");
                await transaction.CommitAsync(cancellationToken);
                return Results.Ok(new { package = SellerFeedbackPolicy.Package(prior, now), charged = 0, credits = user.Credits });
            }
            if (property.Archived) throw new ApiException(400, "Archivált ingatlanhoz nem kérhető új visszajelzés.");
            if (await db.FeedbackPackages.AnyAsync(row => row.PropertyId == id && row.ExpiresAt > now && row.RefundedAt == null, cancellationToken))
                throw new ApiException(409, "Ehhez az ingatlanhoz már van aktív visszajelzés-csomag.");
            if (user.Credits < input.Size) throw new ApiException(402, "Nincs elegendő kredited a visszajelzés-csomaghoz.");
            var package = new FeedbackPackage { OwnerId = uid, PropertyId = id, RequestId = input.RequestId,
                Size = input.Size, CreatedAt = now, ExpiresAt = now.AddDays(SellerFeedbackPolicy.DurationDays), Enabled = true };
            user.Credits -= input.Size;
            db.FeedbackPackages.Add(package);
            db.CreditEntries.Add(new CreditEntry { UserId = uid, Amount = -input.Size, FeedbackPackageId = package.Id,
                Description = $"{input.Size} visszajelzéses csomag", CreatedAt = now });
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            return Results.Ok(new { package = SellerFeedbackPolicy.Package(package, now), charged = input.Size, credits = user.Credits });
        });

        api.MapPut("/properties/{id:guid}/feedback", async (Guid id, FeedbackToggleInput input, AppDb db,
            ClaimsPrincipal principal, TimeProvider clock, CancellationToken cancellationToken) =>
        {
            var uid = principal.UserId(); var now = clock.GetUtcNow().UtcDateTime;
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            _ = await LockedUserAsync(db, uid, cancellationToken);
            var property = await LockedPropertyAsync(db, id, cancellationToken);
            if (property.OwnerId != uid) throw new ApiException(404, "Az ingatlan nem található.");
            now = clock.GetUtcNow().UtcDateTime;
            if (property.Archived && input.Enabled) throw new ApiException(400, "Archivált ingatlanhoz nem kapcsolható be a visszajelzéskérés.");
            var package = (await db.FeedbackPackages.FromSqlInterpolated($"SELECT * FROM `FeedbackPackages` WHERE `PropertyId` = {id} AND `ExpiresAt` > {now} AND `RefundedAt` IS NULL ORDER BY `CreatedAt` DESC LIMIT 1 FOR UPDATE")
                .ToListAsync(cancellationToken)).SingleOrDefault() ?? throw new ApiException(409, "Előbb válassz visszajelzés-csomagot.");
            package.Enabled = input.Enabled;
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            return Results.Ok(new { package = SellerFeedbackPolicy.Package(package, now) });
        });

        api.MapPost("/impressions", async (ImpressionInput input, AppDb db, ClaimsPrincipal principal,
            TimeProvider clock, CancellationToken cancellationToken) =>
        {
            if (input.PropertyId == Guid.Empty || input.SearchRequestId == Guid.Empty) throw new ApiException(400, "Hiányzó ingatlan vagy keresés.");
            var uid = principal.UserId();
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            var user = await LockedUserAsync(db, uid, cancellationToken);
            var property = await LockedPropertyAsync(db, input.PropertyId, cancellationToken);
            var search = (await db.SearchRequests.FromSqlInterpolated($"SELECT * FROM `SearchRequests` WHERE `Id` = {input.SearchRequestId} FOR UPDATE")
                .ToListAsync(cancellationToken)).SingleOrDefault() ?? throw new ApiException(404, "A keresés nem található.");
            if (user.ActiveKind != "search" || user.ActiveEntityId != search.Id || search.OwnerId != uid)
                throw new ApiException(403, "A megjelenéshez aktiváld a saját keresésedet.");
            var ownerType = await db.Users.AsNoTracking().Where(row => row.Id == property.OwnerId).Select(row => row.AccountType).SingleAsync(cancellationToken);
            if (!MatchingRanking.CanRecommend(property, search) || !AccountTypes.CanInteract(user.AccountType, ownerType))
                throw new ApiException(400, "Ez az ingatlan nem ajánlható az aktív kereséshez.");
            var recorded = !await db.PropertyImpressions.AnyAsync(row => row.PropertyId == property.Id && row.ViewerUserId == uid, cancellationToken);
            if (recorded)
            {
                db.PropertyImpressions.Add(new PropertyImpression { PropertyId = property.Id, ViewerUserId = uid,
                    SearchRequestId = search.Id, CreatedAt = clock.GetUtcNow().UtcDateTime });
                await db.SaveChangesAsync(cancellationToken);
            }
            await transaction.CommitAsync(cancellationToken);
            return Results.Ok(new { recorded });
        });

        api.MapGet("/feedback/pending", async (AppDb db, ClaimsPrincipal principal, TimeProvider clock, CancellationToken cancellationToken) =>
            Results.Ok(new { feedbackPrompt = await PendingAsync(db, principal.UserId(), clock.GetUtcNow().UtcDateTime, cancellationToken) }));

        api.MapPost("/feedback/{id:guid}", async (Guid id, FeedbackAnswerInput input, AppDb db, ClaimsPrincipal principal,
            TimeProvider clock, CancellationToken cancellationToken) =>
        {
            if (!SellerFeedbackPolicy.IsReason(input.Reason)) throw new ApiException(400, "Válassz egy visszajelzési lehetőséget.");
            var uid = principal.UserId(); var now = clock.GetUtcNow().UtcDateTime;
            // The first read locates the property's lock; authorization is checked again under the actor lock.
            var candidate = await db.FeedbackInvitations.AsNoTracking().SingleOrDefaultAsync(row => row.Id == id && row.BuyerId == uid, cancellationToken)
                ?? throw new ApiException(404, "A visszajelzéskérés nem található.");
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            _ = await LockedUserAsync(db, uid, cancellationToken);
            _ = await LockedPropertyAsync(db, candidate.PropertyId, cancellationToken);
            var package = (await db.FeedbackPackages.FromSqlInterpolated($"SELECT * FROM `FeedbackPackages` WHERE `Id` = {candidate.PackageId} FOR UPDATE")
                .ToListAsync(cancellationToken)).SingleOrDefault();
            var invitation = (await db.FeedbackInvitations.FromSqlInterpolated($"SELECT * FROM `FeedbackInvitations` WHERE `Id` = {id} FOR UPDATE")
                .ToListAsync(cancellationToken)).SingleOrDefault();
            if (package is null || invitation is null)
            {
                // A scoped test reset may replace the rows while this request
                // waits for its locks. The old question is then expired.
                await transaction.CommitAsync(cancellationToken);
                return Results.Json(new { message = "Ez a visszajelzéskérés már lejárt.", accepted = false }, statusCode: 410);
            }
            if (invitation.BuyerId != uid) throw new ApiException(404, "A visszajelzéskérés nem található.");
            now = clock.GetUtcNow().UtcDateTime;
            if (invitation.AnsweredAt is not null)
            {
                if (invitation.Reason != input.Reason) throw new ApiException(409, "Ezt a visszajelzést már elküldted.");
                await transaction.CommitAsync(cancellationToken);
                return Results.Ok(new { accepted = invitation.Reason != SellerFeedbackPolicy.Decline, alreadyAnswered = true });
            }
            if (invitation.ExpiresAt <= now || !SellerFeedbackPolicy.IsPeriodActive(package, now) || package.ReceivedCount >= package.Size)
            {
                await transaction.CommitAsync(cancellationToken);
                return Results.Json(new { message = "Ez a visszajelzéskérés már lejárt.", accepted = false }, statusCode: 410);
            }
            invitation.Reason = input.Reason;
            invitation.AnsweredAt = now;
            var accepted = input.Reason != SellerFeedbackPolicy.Decline;
            if (accepted) package.ReceivedCount++;
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            return Results.Ok(new { accepted, alreadyAnswered = false });
        });
        return api;
    }

    /// <summary>Called inside /decisions after its actor/property/search row locks, only for a fresh pass.</summary>
    public static async Task<FeedbackPrompt?> OnPassAsync(AppDb db, User buyer, Property property, Decision decision,
        DateTime now, CancellationToken cancellationToken)
    {
        buyer.FeedbackPassCounter = Math.Min(SellerFeedbackPolicy.PromptSpacing, Math.Clamp(buyer.FeedbackPassCounter, 0, SellerFeedbackPolicy.PromptSpacing) + 1);
        var pending = await PendingAsync(db, buyer.Id, now, cancellationToken);
        if (pending is not null) return pending;
        if (buyer.FeedbackPassCounter < SellerFeedbackPolicy.PromptSpacing) return null;
        var package = (await db.FeedbackPackages.FromSqlInterpolated($"SELECT * FROM `FeedbackPackages` WHERE `PropertyId` = {property.Id} AND `Enabled` = TRUE AND `ReceivedCount` < `Size` AND `ExpiresAt` > {now} AND `RefundedAt` IS NULL ORDER BY `CreatedAt` DESC LIMIT 1 FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        if (package is null) return null;
        if (await db.FeedbackInvitations.AnyAsync(row => row.PackageId == package.Id && row.BuyerId == buyer.Id, cancellationToken)) return null;
        var reserved = await db.FeedbackInvitations.CountAsync(row => row.PackageId == package.Id && row.AnsweredAt == null && row.ExpiresAt > now, cancellationToken);
        if (package.ReceivedCount + reserved >= package.Size) return null;
        var invitation = new FeedbackInvitation { PackageId = package.Id, PropertyId = property.Id, DecisionId = decision.Id,
            BuyerId = buyer.Id, CreatedAt = now,
            ExpiresAt = new[] { now.AddMinutes(SellerFeedbackPolicy.InvitationMinutes), package.ExpiresAt }.Min() };
        db.FeedbackInvitations.Add(invitation);
        buyer.FeedbackPassCounter = 0;
        var ownerName = await db.Users.AsNoTracking().Where(row => row.Id == package.OwnerId).Select(row => row.Name).SingleAsync(cancellationToken);
        return Prompt(invitation, ownerName);
    }

    public static async Task<FeedbackPrompt?> PendingAsync(AppDb db, Guid buyerId, DateTime now, CancellationToken cancellationToken = default)
    {
        var row = await (from invitation in db.FeedbackInvitations.AsNoTracking()
            join package in db.FeedbackPackages.AsNoTracking() on invitation.PackageId equals package.Id
            join owner in db.Users.AsNoTracking() on package.OwnerId equals owner.Id
            where invitation.BuyerId == buyerId && invitation.AnsweredAt == null && invitation.ExpiresAt > now
                && package.ExpiresAt > now && package.RefundedAt == null && package.ReceivedCount < package.Size
            orderby invitation.CreatedAt, invitation.Id
            select new { Invitation = invitation, owner.Name }).FirstOrDefaultAsync(cancellationToken);
        return row is null ? null : Prompt(row.Invitation, row.Name);
    }

    private static FeedbackPrompt Prompt(FeedbackInvitation invitation, string ownerName)
    {
        var firstName = PublicProfile.FirstName(ownerName);
        return new(invitation.Id, invitation.PropertyId, firstName, SellerFeedbackPolicy.PromptTitle(firstName),
            "Miért nem tetszett az ingatlan?", SellerFeedbackPolicy.Options, invitation.ExpiresAt);
    }
    private static async Task<Property> OwnedPropertyAsync(AppDb db, Guid id, Guid uid, CancellationToken cancellationToken) =>
        await db.Properties.AsNoTracking().SingleOrDefaultAsync(row => row.Id == id && row.OwnerId == uid, cancellationToken)
            ?? throw new ApiException(404, "Az ingatlan nem található.");
    internal static async Task<User> LockedUserAsync(AppDb db, Guid uid, CancellationToken cancellationToken) =>
        (await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {uid} FOR UPDATE").ToListAsync(cancellationToken))
            .SingleOrDefault() ?? throw new ApiException(401, "A fiók nem található.");
    internal static async Task<Property> LockedPropertyAsync(AppDb db, Guid id, CancellationToken cancellationToken) =>
        (await db.Properties.FromSqlInterpolated($"SELECT * FROM `Properties` WHERE `Id` = {id} FOR UPDATE").ToListAsync(cancellationToken))
            .SingleOrDefault() ?? throw new ApiException(404, "Az ingatlan nem található.");
}

/// <summary>Uses the existing durable scheduler and user-read catch-up; no serverless-instance timers are required.</summary>
public sealed class FeedbackRefundService(IServiceScopeFactory scopes, TimeProvider clock, ILogger<FeedbackRefundService> logger)
{
    public const int BatchSize = 500;
    public async Task<int> RunAsync(Guid? userId = null, CancellationToken cancellationToken = default)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        List<Guid> candidates;
        await using (var scope = scopes.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDb>();
            var query = db.FeedbackPackages.AsNoTracking().Where(row => row.ExpiresAt <= now && row.RefundedAt == null);
            if (userId.HasValue) query = query.Where(row => row.OwnerId == userId.Value);
            candidates = await query.OrderBy(row => row.ExpiresAt).ThenBy(row => row.Id).Select(row => row.Id).Take(BatchSize).ToListAsync(cancellationToken);
        }
        var refunded = 0;
        foreach (var id in candidates)
        {
            try { if (await RefundOneAsync(id, now, cancellationToken)) refunded++; }
            catch (OverflowException error) { logger.LogError(error, "Feedback refund for package {PackageId} exceeds the credit balance range; continuing the batch.", id); }
        }
        return refunded;
    }
    public async Task<bool> RefundOneAsync(Guid packageId, DateTime now, CancellationToken cancellationToken = default)
    {
        await using var scope = scopes.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDb>();
        var candidate = await db.FeedbackPackages.AsNoTracking().SingleOrDefaultAsync(row => row.Id == packageId, cancellationToken);
        if (candidate is null || candidate.RefundedAt is not null || candidate.ExpiresAt > now) return false;
        await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
        var owner = await SellerFeedback.LockedUserAsync(db, candidate.OwnerId, cancellationToken);
        var property = await SellerFeedback.LockedPropertyAsync(db, candidate.PropertyId, cancellationToken);
        var package = (await db.FeedbackPackages.FromSqlInterpolated($"SELECT * FROM `FeedbackPackages` WHERE `Id` = {packageId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        if (package is null || package.RefundedAt is not null || package.ExpiresAt > now) return false;
        var missing = SellerFeedbackPolicy.Missing(package);
        package.RefundedAt = now;
        package.RefundedCredits = missing;
        package.Enabled = false;
        if (missing > 0)
        {
            owner.Credits = checked(owner.Credits + missing);
            db.CreditEntries.Add(new CreditEntry { UserId = owner.Id, Amount = missing, RefundedFeedbackPackageId = package.Id,
                Description = "Lejárt visszajelzés-csomag fel nem használt keretének visszatérítése", CreatedAt = now });
            db.UserNotifications.Add(new UserNotification { UserId = owner.Id, FeedbackPackageId = package.Id,
                Kind = "feedback_refund", Amount = missing,
                Text = $"Visszakaptál {missing} kreditet a(z) „{PublicProfile.Title(property.Title, "ingatlan") }” visszajelzés-csomagjából: ennyi válasz maradt felhasználatlanul a két hét alatt.", CreatedAt = now });
        }
        await db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return missing > 0;
    }
}
