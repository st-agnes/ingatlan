using System.Data;
using System.Data.Common;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>
/// Disposable fixtures for explicitly configured test deployments. A new Cloud
/// Run revision starts a fresh dataset; another instance of that revision does
/// not reset somebody's ongoing test session.
/// </summary>
public static class TestDataSeed
{
    public const string ResourceName = "Otthonra.Api.TestFixtures.json";
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    private static readonly Lazy<TestFixtureCatalog> Embedded = new(() =>
    {
        using var stream = typeof(TestDataSeed).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("The embedded test fixture catalog is missing.");
        return JsonSerializer.Deserialize<TestFixtureCatalog>(stream, Json)
            ?? throw new InvalidOperationException("The embedded test fixture catalog is empty.");
    });
    public static string CatalogVersion => LoadCatalog().Version;
    public static TestFixtureCatalog LoadCatalog() => Embedded.Value;

    public static string RevisionKey(string? revision, string catalogVersion)
    {
        if (!Regex.IsMatch(catalogVersion, @"\A[a-z0-9][a-z0-9.-]{0,79}\z"))
            throw new InvalidOperationException("Invalid embedded test catalog version.");
        var key = revision ?? "local:" + catalogVersion;
        if (!Regex.IsMatch(key, @"\A[a-z0-9][a-z0-9._:-]{0,199}\z"))
            throw new InvalidOperationException("Invalid test deployment revision.");
        return key;
    }

    public static Guid StableId(string key)
    {
        if (string.IsNullOrWhiteSpace(key)) throw new ArgumentException("A stable fixture key is required.", nameof(key));
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes("otthonra-test-fixtures:" + key))[..16];
        // A namespaced deterministic UUID; no database IDs depend on row order.
        bytes[6] = (byte)((bytes[6] & 0x0f) | 0x50);
        bytes[8] = (byte)((bytes[8] & 0x3f) | 0x80);
        return Guid.ParseExact(Convert.ToHexString(bytes), "N");
    }

    /// <summary>Fully validate and construct the fixture graph before touching existing data.</summary>
    public static TestDataPlan BuildPlan(TestFixtureCatalog catalog)
    {
        _ = RevisionKey(null, catalog.Version);
        Rules.Password(catalog.Password);
        if (catalog.Users is null || catalog.Users.Length is < 1 or > 100
            || catalog.Fixtures is null || catalog.Fixtures.Length is < 1 or > 10000)
            throw new InvalidOperationException("Invalid test fixture catalog size.");
        var users = new Dictionary<string, User>(StringComparer.Ordinal);
        var fixtureEntities = new Dictionary<string, (string Owner, string Kind, Guid Id)>(StringComparer.Ordinal);
        var emails = new HashSet<string>(StringComparer.Ordinal);
        var properties = new List<Property>();
        var searches = new List<SearchRequest>();
        var credits = new List<CreditEntry>();
        var feedbackPackages = new List<FeedbackPackage>();
        var now = DateTime.UtcNow;
        foreach (var definition in catalog.Users)
        {
            Key(definition.Key);
            var email = Rules.Email(definition.Email);
            if (users.ContainsKey(definition.Key) || !emails.Add(email))
                throw new InvalidOperationException("Duplicate test account key or email.");
            var user = new User {
                Id = StableId("user:" + definition.Key),
                Name = Rules.Required(definition.Name, "test account name", 100), Email = email,
                Phone = Rules.Optional(definition.Phone, 40),
                AccountType = AccountTypes.RegistrationType(definition.AccountType),
                PasswordHash = Passwords.Hash(catalog.Password), Credits = 100, CreatedAt = now
            };
            users.Add(definition.Key, user);
            credits.Add(new CreditEntry {
                Id = StableId("credit:" + definition.Key), UserId = user.Id, Amount = 100,
                Description = "Kezdő tesztkreditek – valódi fizetés nélkül", CreatedAt = now
            });
        }
        foreach (var fixture in catalog.Fixtures)
        {
            Key(fixture.Key);
            if (!users.TryGetValue(fixture.Owner, out var owner))
                throw new InvalidOperationException("A test fixture refers to an unknown owner.");
            if (fixtureEntities.ContainsKey(fixture.Key) || fixture.Input.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("Duplicate or invalid test fixture.");
            var id = StableId(fixture.Kind + ":" + fixture.Key);
            if (fixture.Kind == "property")
            {
                var input = fixture.Input.Deserialize<PropertyInput>(Json)
                    ?? throw new InvalidOperationException("A property fixture is empty.");
                var property = new Property { Id = id, OwnerId = owner.Id, CreatedAt = now };
                Rules.Apply(property, input);
                AssignSyntheticCoordinates(property, fixture.Key);
                if (property.Archived) throw new InvalidOperationException("Initial test properties must be active.");
                properties.Add(property);
            }
            else if (fixture.Kind == "search")
            {
                var input = fixture.Input.Deserialize<SearchInput>(Json)
                    ?? throw new InvalidOperationException("A search fixture is empty.");
                var search = new SearchRequest { Id = id, OwnerId = owner.Id, CreatedAt = now };
                Rules.Apply(search, input);
                if (search.Archived) throw new InvalidOperationException("Initial test searches must be active.");
                searches.Add(search);
            }
            else throw new InvalidOperationException("Unknown test fixture kind.");
            fixtureEntities.Add(fixture.Key, (fixture.Owner, fixture.Kind, id));
        }
        foreach (var definition in catalog.Users)
        {
            if (definition.Active is null || !fixtureEntities.TryGetValue(definition.Active.Key, out var active)
                || active.Owner != definition.Key || active.Kind != definition.Active.Kind)
                throw new InvalidOperationException("An initial active profile must belong to its test account.");
            users[definition.Key].ActiveKind = active.Kind;
            users[definition.Key].ActiveEntityId = active.Id;
        }
        var scenarioUsers = new HashSet<Guid>();
        foreach (var scenario in catalog.FeedbackScenarios ?? [])
        {
            Key(scenario.Key);
            if (!users.TryGetValue(scenario.Seller, out var seller) || !users.TryGetValue(scenario.Buyer, out var buyer)
                || seller.Id == buyer.Id || !scenarioUsers.Add(seller.Id) || !scenarioUsers.Add(buyer.Id)
                || seller.AccountType != AccountTypes.Private || buyer.AccountType != AccountTypes.Private
                || !SellerFeedbackPolicy.PackageSizes.Contains(scenario.Size))
                throw new InvalidOperationException("Invalid feedback test scenario participants or package.");
            if (!fixtureEntities.TryGetValue(scenario.Property, out var propertyRef) || propertyRef.Kind != "property" || propertyRef.Owner != scenario.Seller
                || !fixtureEntities.TryGetValue(scenario.Search, out var searchRef) || searchRef.Kind != "search" || searchRef.Owner != scenario.Buyer)
                throw new InvalidOperationException("A feedback test scenario must refer to its participants' own entities.");
            var property = properties.Single(item => item.Id == propertyRef.Id);
            var search = searches.Single(item => item.Id == searchRef.Id);
            if (!Rules.Compatible(property, search) || seller.Credits < scenario.Size
                || seller.ActiveKind != "property" || seller.ActiveEntityId != property.Id
                || buyer.ActiveKind != "search" || buyer.ActiveEntityId != search.Id)
                throw new InvalidOperationException("The feedback test pair must be exact, active and prepaid.");
            var package = new FeedbackPackage {
                Id = StableId("feedback-package:" + scenario.Key), RequestId = StableId("feedback-request:" + scenario.Key),
                PropertyId = property.Id, OwnerId = seller.Id, Size = scenario.Size, Enabled = true,
                CreatedAt = now, ExpiresAt = now.AddDays(SellerFeedbackPolicy.DurationDays)
            };
            seller.Credits -= scenario.Size;
            buyer.FeedbackPassCounter = SellerFeedbackPolicy.PromptSpacing - 1;
            feedbackPackages.Add(package);
            credits.Add(new CreditEntry {
                Id = StableId("feedback-charge:" + scenario.Key), UserId = seller.Id, Amount = -scenario.Size,
                FeedbackPackageId = package.Id, Description = "Előkészített visszajelzés-próba – 10 válaszos csomag", CreatedAt = now
            });
        }
        var activity = TestActivitySeed.Build(catalog.ActivityScenarios, fixtureEntities, users, properties, searches, credits, now);
        return new(catalog.Version, users.Values.ToArray(), properties.ToArray(), searches.ToArray(), credits.ToArray()) {
            FeedbackPackages = feedbackPackages.ToArray(), Decisions = activity.Decisions,
            Matches = activity.Matches, Messages = activity.Messages, Notifications = activity.Notifications
        };
    }

    private static void Key(string? key)
    {
        if (key is null || !Regex.IsMatch(key, @"\A[a-z0-9][a-z0-9-]{0,199}\z"))
            throw new InvalidOperationException("Invalid stable fixture key.");
    }

    /// <summary>
    /// Fixture-only coordinates. These deliberately fictional addresses have
    /// never been sent to Google and must never be described as validated homes.
    /// </summary>
    public static void AssignSyntheticCoordinates(Property property, string? fixtureKey = null)
    {
        // Only these named fixtures may pair a source street with the visibly
        // fictional 99999 house number. Normal property saves still geocode.
        var postalFixture = fixtureKey is not null && property.City == "Debrecen" && property.HouseNumber == "99999"
            && ((Regex.IsMatch(fixtureKey, @"\Areka(?:--[a-z0-9][a-z0-9-]{0,31})?-debrecen-1\z")
                    && property.StreetId == "street:aae22ff8e2d0fa698c0291dc" && property.Street == "Böszörményi út" && property.PostalCode == "4027")
                || (Regex.IsMatch(fixtureKey, @"\Abence(?:--[a-z0-9][a-z0-9-]{0,31})?-debrecen-1\z")
                    && property.StreetId == "street:6cd1dbc01d7aec3be234b7ba" && property.Street == "Egyetem sugárút" && property.PostalCode == "4032"));
        if (property.Street != "OTTHONRA TEST" && !postalFixture)
            throw new InvalidOperationException("Synthetic fixture coordinates require the reserved street or an explicit fictional postal fixture.");
        var areas = NeighborhoodCatalog.All.Where(area => area.City == property.City).ToArray();
        var districtFixtureName = property.LocationId switch {
            "district:Budapest:2" => "Rózsadomb", "district:Budapest:9" => "Belső-Ferencváros",
            "district:Budapest:11" => "Lágymányos", "district:Budapest:13" => "Újlipótváros", _ => null
        };
        var area = areas.FirstOrDefault(candidate => candidate.Name == property.Neighborhood)
            ?? areas.FirstOrDefault(candidate => candidate.Name == districtFixtureName) ?? areas.FirstOrDefault();
        var point = area is null ? NeighborhoodCatalog.TestPointForCity(property.City) : NeighborhoodCatalog.RepresentativePoint(area.Id);
        if (point is null)
            throw new InvalidOperationException("A fictional fixture requires a synthetic point in its own municipality.");
        property.Latitude = point.Latitude;
        property.Longitude = point.Longitude;
        property.GeocodedAt = DateTime.UtcNow;
        property.GeocodingProvider = "synthetic-test-fixture";
        property.GeocodingQuality = "SYNTHETIC";
        property.GeocodingPlaceId = "synthetic:" + (area?.Id ?? "city:" + property.City);
        property.GeocodingAddressKey = PropertyGeocodingService.AddressKey(property);
        property.NeighborhoodIdsJson = "[]";
    }

    /// <summary>Classify fixture points with the same native polygon query as real saved properties.</summary>
    public static async Task AssignSyntheticMembershipAsync(AppDb db, IEnumerable<Property> properties, CancellationToken cancellationToken = default)
    {
        var classified = new Dictionary<(double Latitude, double Longitude), string>();
        foreach (var property in properties)
        {
            if (property.GeocodingProvider != "synthetic-test-fixture" || property.Latitude is not double latitude || property.Longitude is not double longitude)
                throw new InvalidOperationException("Only explicitly synthetic fixture points can use fixture membership assignment.");
            var coordinate = (latitude, longitude);
            if (!classified.TryGetValue(coordinate, out var membership))
            {
                membership = JsonSerializer.Serialize(await NeighborhoodData.ComputeMembershipAsync(db, latitude, longitude, cancellationToken));
                classified.Add(coordinate, membership);
            }
            property.NeighborhoodIdsJson = membership;
        }
    }

    /// <summary>Delete dependent rows first, keeping real MySQL foreign keys enabled.</summary>
    public static IReadOnlyList<string> DeletionOrder(IModel model)
    {
        var entities = model.GetEntityTypes().ToArray();
        var tables = entities.Select(entity => entity.GetTableName()
            ?? throw new InvalidOperationException("A test data entity has no table.")).Distinct(StringComparer.Ordinal).ToArray();
        var dependencies = tables.ToDictionary(table => table, _ => new HashSet<string>(StringComparer.Ordinal), StringComparer.Ordinal);
        foreach (var entity in entities)
        foreach (var foreignKey in entity.GetForeignKeys())
        {
            var table = entity.GetTableName()!;
            var principal = foreignKey.PrincipalEntityType.GetTableName()!;
            if (table == principal) throw new InvalidOperationException("Self-referencing test data requires an explicit reset strategy.");
            dependencies[table].Add(principal);
        }
        var visiting = new HashSet<string>(StringComparer.Ordinal);
        var complete = new HashSet<string>(StringComparer.Ordinal);
        var parentFirst = new List<string>();
        void Visit(string table)
        {
            if (complete.Contains(table)) return;
            if (!visiting.Add(table)) throw new InvalidOperationException("Cyclic test data cannot be reset safely.");
            foreach (var parent in dependencies[table].Order(StringComparer.Ordinal)) Visit(parent);
            visiting.Remove(table); complete.Add(table); parentFirst.Add(table);
        }
        foreach (var table in tables.Order(StringComparer.Ordinal)) Visit(table);
        parentFirst.Reverse();
        return parentFirst;
    }

    public static async Task<bool> RunAsync(AppDb db, DeploymentSettings deployment, string? revision, CancellationToken cancellationToken = default)
    {
        // This check deliberately precedes catalog loading, opening connections,
        // or issuing any SQL. The flag alone must never authorize a production reset.
        if (!deployment.IsTest || deployment.Name != "test")
            throw new InvalidOperationException("Disposable fixture initialization is allowed only in an explicit test deployment.");
        var catalog = LoadCatalog();
        var revisionKey = RevisionKey(revision, catalog.Version);
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        var lockName = "otthonra-test-seed-" + Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(connection.Database)))[..24];
        var acquired = false;
        try
        {
            acquired = Convert.ToInt32(await Scalar(db, connection, "SELECT GET_LOCK(@name, 120)", cancellationToken, ("name", lockName))) == 1;
            if (!acquired) throw new InvalidOperationException("Could not acquire the test fixture initialization lock.");
            // This history is deliberately not an AppDb entity and is never
            // deleted by fixture reset. Older revisions therefore cannot wipe
            // a newer revision's sessions when a tagged instance starts again.
            await Execute(db, connection, "CREATE TABLE IF NOT EXISTS `__OtthonraTestSeeds` (`RevisionId` varchar(200) NOT NULL PRIMARY KEY, `Version` varchar(80) NOT NULL, `AppliedAt` datetime(6) NOT NULL) ENGINE=InnoDB", cancellationToken);
            if (Convert.ToInt32(await Scalar(db, connection,
                    "SELECT COUNT(*) FROM `__OtthonraTestSeeds` WHERE `RevisionId` = @revision", cancellationToken, ("revision", revisionKey))) > 0)
                return false;
            var plan = BuildPlan(catalog); // Validation precedes DELETE.
            await AssignSyntheticMembershipAsync(db, plan.Properties, cancellationToken);
            var tables = DeletionOrder(db.Model);
            db.ChangeTracker.Clear();
            await using var transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
            foreach (var table in tables)
                await Execute(db, connection, "DELETE FROM `" + table.Replace("`", "``") + "`", cancellationToken);
            db.Users.AddRange(plan.Users);
            db.Properties.AddRange(plan.Properties);
            db.SearchRequests.AddRange(plan.Searches);
            db.FeedbackPackages.AddRange(plan.FeedbackPackages);
            db.Decisions.AddRange(plan.Decisions);
            db.Matches.AddRange(plan.Matches);
            db.Messages.AddRange(plan.Messages);
            db.UserNotifications.AddRange(plan.Notifications);
            db.CreditEntries.AddRange(plan.Credits);
            await db.SaveChangesAsync(cancellationToken);
            await Execute(db, connection,
                "INSERT INTO `__OtthonraTestSeeds` (`RevisionId`, `Version`, `AppliedAt`) VALUES (@revision, @version, UTC_TIMESTAMP(6))",
                cancellationToken, ("revision", revisionKey), ("version", plan.Version));
            await transaction.CommitAsync(cancellationToken);
            db.ChangeTracker.Clear();
            return true;
        }
        finally
        {
            try
            {
                if (acquired) await Scalar(db, connection, "SELECT RELEASE_LOCK(@name)", CancellationToken.None, ("name", lockName));
            }
            finally { if (openedHere) await db.Database.CloseConnectionAsync(); }
        }
    }

    private static DbCommand Command(AppDb db, DbConnection connection, string sql, params (string Name, string Value)[] parameters)
    {
        var command = connection.CreateCommand(); command.CommandText = sql; command.CommandTimeout = 150;
        command.Transaction = db.Database.CurrentTransaction?.GetDbTransaction();
        foreach (var (name, value) in parameters)
        {
            var parameter = command.CreateParameter(); parameter.ParameterName = "@" + name; parameter.Value = value; command.Parameters.Add(parameter);
        }
        return command;
    }
    private static async Task<object?> Scalar(AppDb db, DbConnection connection, string sql, CancellationToken cancellationToken, params (string Name, string Value)[] parameters)
    {
        await using var command = Command(db, connection, sql, parameters);
        return await command.ExecuteScalarAsync(cancellationToken);
    }
    private static async Task Execute(AppDb db, DbConnection connection, string sql, CancellationToken cancellationToken, params (string Name, string Value)[] parameters)
    {
        await using var command = Command(db, connection, sql, parameters);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}

public sealed record TestFixtureCatalog(string Version, string Password, TestFixtureUser[] Users, TestFixture[] Fixtures,
    TestFeedbackScenario[]? FeedbackScenarios = null, TestActivityScenario[]? ActivityScenarios = null);
public sealed record TestFeedbackScenario(string Key, string Seller, string Buyer, string Property, string Search, int Size);
public sealed record TestFixtureUser(string Key, string Name, string Email, string? Phone, string? AccountType, TestFixtureActive Active);
public sealed record TestFixtureActive(string Kind, string Key);
public sealed record TestFixture(string Key, string Owner, string Kind, JsonElement Input);
public sealed record TestDataPlan(string Version, User[] Users, Property[] Properties, SearchRequest[] Searches, CreditEntry[] Credits)
{
    public FeedbackPackage[] FeedbackPackages { get; init; } = [];
    public Decision[] Decisions { get; init; } = [];
    public Match[] Matches { get; init; } = [];
    public Message[] Messages { get; init; } = [];
    public UserNotification[] Notifications { get; init; } = [];
}
