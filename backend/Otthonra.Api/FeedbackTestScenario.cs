using System.Data;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>Explicitly enabled, isolated test-fixture controls. Never mapped in ordinary production.</summary>
public static class FeedbackTestScenario
{
    public const string ScenarioKey = "feedback-first-pass";
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private sealed record Definition(TestFeedbackScenario Scenario, TestFixtureUser Seller, TestFixtureUser Buyer,
        TestFixture Property, TestFixture Search)
    {
        public Guid SellerId => TestDataSeed.StableId("user:" + Scenario.Seller);
        public Guid BuyerId => TestDataSeed.StableId("user:" + Scenario.Buyer);
        public Guid PropertyId => TestDataSeed.StableId("property:" + Scenario.Property);
        public Guid SearchId => TestDataSeed.StableId("search:" + Scenario.Search);
        public bool IsParticipant(Guid uid) => uid == SellerId || uid == BuyerId;
    }

    private static Definition? Load()
    {
        var catalog = TestDataSeed.LoadCatalog();
        var scenario = catalog.FeedbackScenarios?.SingleOrDefault(item => item.Key == ScenarioKey);
        if (scenario is null) return null;
        return new(scenario, catalog.Users.Single(user => user.Key == scenario.Seller),
            catalog.Users.Single(user => user.Key == scenario.Buyer),
            catalog.Fixtures.Single(fixture => fixture.Key == scenario.Property),
            catalog.Fixtures.Single(fixture => fixture.Key == scenario.Search));
    }

    private static async Task<bool> ParticipantsExist(AppDb db, Definition definition, CancellationToken cancellationToken) =>
        await db.Users.AsNoTracking().AnyAsync(user => user.Id == definition.SellerId && user.Email == definition.Seller.Email
            && user.AccountType == AccountTypes.Private, cancellationToken)
        && await db.Users.AsNoTracking().AnyAsync(user => user.Id == definition.BuyerId && user.Email == definition.Buyer.Email
            && user.AccountType == AccountTypes.Private, cancellationToken);

    private static object Describe(Definition definition, Guid uid) => new {
        available = true, role = uid == definition.BuyerId ? "buyer" : "seller",
        propertyId = definition.PropertyId, searchId = definition.SearchId,
        buyerEmail = definition.Buyer.Email, sellerEmail = definition.Seller.Email, feedbackReady = true
    };

    public static RouteGroupBuilder MapFeedbackTestScenario(this RouteGroupBuilder api)
    {
        api.MapGet("/test/feedback-scenario", async Task<IResult> (AppDb db, ClaimsPrincipal principal, CancellationToken cancellationToken) =>
        {
            var definition = Load(); var uid = principal.UserId();
            if (definition is null || !definition.IsParticipant(uid) || !await ParticipantsExist(db, definition, cancellationToken))
                return Results.Ok(new { available = false });
            return Results.Ok(Describe(definition, uid));
        });
        api.MapPost("/test/feedback-scenario/reset", async (AppDb db, ClaimsPrincipal principal, TimeProvider clock,
            CancellationToken cancellationToken) =>
        {
            var definition = Load(); var uid = principal.UserId();
            if (definition is null || !definition.IsParticipant(uid) || !await ParticipantsExist(db, definition, cancellationToken))
                throw new ApiException(404, "A visszajelzés-próba ehhez a fiókhoz nem érhető el.");
            await ResetAsync(db, definition, clock, cancellationToken);
            return Results.Ok(Describe(definition, uid));
        });
        return api;
    }

    private static async Task ResetAsync(AppDb db, Definition definition, TimeProvider clock, CancellationToken cancellationToken)
    {
        // Lock both dedicated users first in database key order, then the pair.
        // Normal answer/purchase/refund operations cannot interleave with this reset.
        await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
        var users = await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` IN ({definition.SellerId}, {definition.BuyerId}) ORDER BY `Id` FOR UPDATE")
            .ToListAsync(cancellationToken);
        var seller = users.SingleOrDefault(user => user.Id == definition.SellerId && user.Email == definition.Seller.Email);
        var buyer = users.SingleOrDefault(user => user.Id == definition.BuyerId && user.Email == definition.Buyer.Email);
        if (seller is null || buyer is null) throw new ApiException(404, "A tesztfiókok nem érhetők el.");
        var property = (await db.Properties.FromSqlInterpolated($"SELECT * FROM `Properties` WHERE `Id` = {definition.PropertyId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        var search = (await db.SearchRequests.FromSqlInterpolated($"SELECT * FROM `SearchRequests` WHERE `Id` = {definition.SearchId} FOR UPDATE")
            .ToListAsync(cancellationToken)).SingleOrDefault();
        if (property?.OwnerId != seller.Id || search?.OwnerId != buyer.Id)
            throw new ApiException(409, "A tesztpár megváltozott; a következő teszttelepítés visszaállítja.");
        var now = clock.GetUtcNow().UtcDateTime;

        var packages = await db.FeedbackPackages.Where(item => item.PropertyId == property.Id && item.OwnerId == seller.Id).ToListAsync(cancellationToken);
        var packageIds = packages.Select(item => item.Id).ToArray();
        var decisions = await db.Decisions.Where(item => item.PropertyId == property.Id && item.SearchRequestId == search.Id).ToListAsync(cancellationToken);
        var decisionIds = decisions.Select(item => item.Id).ToArray();
        var matches = await db.Matches.Where(item => item.PropertyId == property.Id && item.SearchRequestId == search.Id).ToListAsync(cancellationToken);
        var matchIds = matches.Select(item => item.Id).ToArray();
        var entries = await db.CreditEntries.Where(item => item.FeedbackPackageId.HasValue && packageIds.Contains(item.FeedbackPackageId.Value)
            || item.RefundedFeedbackPackageId.HasValue && packageIds.Contains(item.RefundedFeedbackPackageId.Value)
            || item.DecisionId.HasValue && decisionIds.Contains(item.DecisionId.Value)
            || item.RefundedDecisionId.HasValue && decisionIds.Contains(item.RefundedDecisionId.Value)).ToListAsync(cancellationToken);
        // Undo only the dedicated scenario's net charges/refunds. Any unrelated
        // activity and balances belonging to normal accounts remain untouched.
        foreach (var user in new[] { seller, buyer })
            user.Credits = checked(user.Credits - entries.Where(entry => entry.UserId == user.Id).Sum(entry => entry.Amount));
        if (entries.Any(entry => entry.UserId != seller.Id && entry.UserId != buyer.Id))
            throw new ApiException(409, "A tesztkönyvelés megváltozott; nem indítható újra biztonságosan.");

        await db.UserNotifications.Where(item => item.FeedbackPackageId.HasValue && packageIds.Contains(item.FeedbackPackageId.Value)
            || item.DecisionId.HasValue && decisionIds.Contains(item.DecisionId.Value)).ExecuteDeleteAsync(cancellationToken);
        await db.Messages.Where(item => matchIds.Contains(item.MatchId)).ExecuteDeleteAsync(cancellationToken);
        await db.Matches.Where(item => matchIds.Contains(item.Id)).ExecuteDeleteAsync(cancellationToken);
        await db.FeedbackInvitations.Where(item => packageIds.Contains(item.PackageId) || decisionIds.Contains(item.DecisionId)).ExecuteDeleteAsync(cancellationToken);
        await db.PropertyImpressions.Where(item => item.PropertyId == property.Id).ExecuteDeleteAsync(cancellationToken);
        db.CreditEntries.RemoveRange(entries);
        db.Decisions.RemoveRange(decisions);
        await db.SaveChangesAsync(cancellationToken);
        db.FeedbackPackages.RemoveRange(packages);
        await db.SaveChangesAsync(cancellationToken);
        // A deliberately reused test buyer must not be blocked by a pending
        // question from another test property. Declining releases that slot.
        await db.FeedbackInvitations.Where(item => item.BuyerId == buyer.Id && item.AnsweredAt == null)
            .ExecuteUpdateAsync(setters => setters.SetProperty(item => item.AnsweredAt, now)
                .SetProperty(item => item.Reason, SellerFeedbackPolicy.Decline), cancellationToken);

        Rules.Apply(property, definition.Property.Input.Deserialize<PropertyInput>(Json)!);
        Rules.Apply(search, definition.Search.Input.Deserialize<SearchInput>(Json)!);
        seller.ActiveKind = "property"; seller.ActiveEntityId = property.Id;
        buyer.ActiveKind = "search"; buyer.ActiveEntityId = search.Id;
        buyer.FeedbackPassCounter = SellerFeedbackPolicy.PromptSpacing - 1;
        if (seller.Credits < definition.Scenario.Size)
        {
            var amount = definition.Scenario.Size - seller.Credits;
            seller.Credits += amount;
            db.CreditEntries.Add(new CreditEntry { UserId = seller.Id, Amount = amount,
                Description = "Visszajelzés-próba tesztkredit-kiegészítése", CreatedAt = now });
        }
        var package = new FeedbackPackage { PropertyId = property.Id, OwnerId = seller.Id, RequestId = Guid.NewGuid(),
            Size = definition.Scenario.Size, Enabled = true, CreatedAt = now,
            ExpiresAt = now.AddDays(SellerFeedbackPolicy.DurationDays) };
        seller.Credits -= package.Size;
        db.FeedbackPackages.Add(package);
        db.CreditEntries.Add(new CreditEntry { UserId = seller.Id, Amount = -package.Size, FeedbackPackageId = package.Id,
            Description = "Újraindított visszajelzés-próba – 10 válaszos csomag", CreatedAt = now });
        await db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
    }
}
