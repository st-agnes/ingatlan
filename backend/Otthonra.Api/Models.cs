using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace Otthonra.Api;

public sealed class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Name { get; set; } = "";
    public string Email { get; set; } = "";
    public string Phone { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string AccountType { get; set; } = AccountTypes.Private;
    public int Credits { get; set; }
    public int FeedbackPassCounter { get; set; }
    public string? ActiveKind { get; set; }
    public Guid? ActiveEntityId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class Property
{
    public int CreationRequestHashVersion { get; set; } = 1;
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid OwnerId { get; set; }
    public Guid? CreationRequestId { get; set; }
    public string? CreationRequestHash { get; set; }
    public string? PublicListingKey { get; set; }
    public string Title { get; set; } = "";
    public string City { get; set; } = "";
    public string District { get; set; } = "";
    public string LocationId { get; set; } = "";
    public decimal? LotArea { get; set; }
    public string Neighborhood { get; set; } = "";
    public string Address { get; set; } = "";
    public bool HideStreet { get; set; } = true;
    public bool HideHouseNumber { get; set; } = true;
    public string Street { get; set; } = "";
    public string? StreetId { get; set; }
    public string HouseNumber { get; set; } = "";
    public string PostalCode { get; set; } = "";
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public DateTime? GeocodedAt { get; set; }
    public string GeocodingProvider { get; set; } = "";
    public string GeocodingPlaceId { get; set; } = "";
    public string GeocodingQuality { get; set; } = "";
    public string GeocodingAddressKey { get; set; } = "";
    public string? NeighborhoodIdsJson { get; set; } = "[]";
    public string Description { get; set; } = "";
    public string Type { get; set; } = "Lakás";
    public decimal Price { get; set; }
    public decimal Area { get; set; }
    public decimal Rooms { get; set; }
    public int? WholeRooms { get; set; }
    public int? HalfRooms { get; set; }
    public decimal? Floor { get; set; }
    public bool FloorIsUpperRange { get; set; }
    public bool? IsAttic { get; set; }
    public int? BuildingFloors { get; set; }
    public bool? PrivateGarden { get; set; }
    // Deprecated; keep the mapped column and old input shape without exposing an active option.
    public bool? SharedGarden { get; set; }
    public string Condition { get; set; } = "";
    public string Building { get; set; } = "";
    public string ConstructionAge { get; set; } = "";
    public string View { get; set; } = "";
    public string CeilingHeight { get; set; } = "";
    public string HeatingType { get; set; } = "";
    public string SecondaryHeatingType { get; set; } = "";
    public bool? Insulated { get; set; }
    public string EnergyRating { get; set; } = "";
    public string EnergyRatingScheme { get; set; } = "";
    public bool? AirConditioning { get; set; }
    public bool? SolarPanels { get; set; }
    public string ParkingType { get; set; } = "";
    public string? ParkingTypesJson { get; set; }
    public bool? Balcony { get; set; } = false;
    public bool Elevator { get; set; }
    public string ImagesJson { get; set; } = "[]";
    public bool Archived { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class SearchRequest
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid OwnerId { get; set; }
    public Guid? CreationRequestId { get; set; }
    public string? CreationRequestHash { get; set; }
    public string? PublicListingKey { get; set; }
    public string Title { get; set; } = "";
    public string City { get; set; } = "";
    public string DistrictsJson { get; set; } = "[]";
    public string? LocationIdsJson { get; set; } = "[]";
    public string Description { get; set; } = "";
    public string Type { get; set; } = "Lakás";
    public decimal? MinPrice { get; set; }
    public decimal? MaxPrice { get; set; }
    public decimal? PublicMaxPrice { get; set; }
    public decimal? MinArea { get; set; }
    public decimal? MaxArea { get; set; }
    public decimal? MinRooms { get; set; }
    public decimal? MaxRooms { get; set; }
    public string? ConditionsJson { get; set; } = "[]";
    public string? BuildingsJson { get; set; } = "[]";
    public string? ConstructionAgesJson { get; set; } = "[]";
    public string? ViewsJson { get; set; } = "[]";
    public string CeilingHeight { get; set; } = "";
    public string? FloorsJson { get; set; } = "[]";
    public string? HeatingTypesJson { get; set; } = "[]";
    public string AtticPreference { get; set; } = "";
    public string MinEnergyRating { get; set; } = "";
    public bool Balcony { get; set; }
    public bool Elevator { get; set; }
    public string MoveIn { get; set; } = "";
    public bool ExcludeTopFloor { get; set; }
    public bool ExcludeGroundFloorAndBelow { get; set; }
    public bool AirConditioning { get; set; }
    public bool PrivateGarden { get; set; }
    // Deprecated; legacy true values must not affect recommendations.
    public bool SharedGarden { get; set; }
    public string Financing { get; set; } = "";
    public bool Archived { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class Decision
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PropertyId { get; set; }
    public Guid SearchRequestId { get; set; }
    public string ActorKind { get; set; } = "";
    public Guid ActorUserId { get; set; }
    public bool Liked { get; set; }
    public int Charged { get; set; }
    public DateTime? RefundedAt { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class Match
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PropertyId { get; set; }
    public Guid SearchRequestId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class Message
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid MatchId { get; set; }
    public Guid SenderId { get; set; }
    public string Text { get; set; } = "";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class CreditEntry
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public int Amount { get; set; }
    public string Description { get; set; } = "";
    public Guid? DecisionId { get; set; }
    public Guid? RefundedDecisionId { get; set; }
    public Guid? FeedbackPackageId { get; set; }
    public Guid? RefundedFeedbackPackageId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public sealed class UserNotification
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public Guid? DecisionId { get; set; }
    public Guid? FeedbackPackageId { get; set; }
    public string? EventKey { get; set; }
    public string? EntityKind { get; set; }
    public Guid? EntityId { get; set; }
    public Guid? PropertyId { get; set; }
    public Guid? SearchRequestId { get; set; }
    public Guid? MatchId { get; set; }
    public string Kind { get; set; } = "like_refund";
    public int Amount { get; set; }
    public string Text { get; set; } = "";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? ReadAt { get; set; }
}

public sealed class UserReport
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid ReporterId { get; set; }
    public Guid ReportedUserId { get; set; }
    public string EntityKind { get; set; } = "";
    public Guid EntityId { get; set; }
    public string Reason { get; set; } = AccountTypes.SuspectedAgentReason;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public sealed class AppDb(DbContextOptions<AppDb> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();
    public DbSet<UserReport> UserReports => Set<UserReport>();
    public DbSet<Property> Properties => Set<Property>();
    public DbSet<SearchRequest> SearchRequests => Set<SearchRequest>();
    public DbSet<SearchLocation> SearchLocations => Set<SearchLocation>();
    public DbSet<PropertyNeighborhood> PropertyNeighborhoods => Set<PropertyNeighborhood>();
    public DbSet<Decision> Decisions => Set<Decision>();
    public DbSet<Match> Matches => Set<Match>();
    public DbSet<Message> Messages => Set<Message>();
    public DbSet<CreditEntry> CreditEntries => Set<CreditEntry>();
    public DbSet<UserNotification> UserNotifications => Set<UserNotification>();
    public DbSet<PropertyImpression> PropertyImpressions => Set<PropertyImpression>();
    public DbSet<FeedbackPackage> FeedbackPackages => Set<FeedbackPackage>();
    public DbSet<FeedbackInvitation> FeedbackInvitations => Set<FeedbackInvitation>();
    private void PreparePublicListingKeys()
    {
        foreach (var entry in ChangeTracker.Entries<Property>().Where(entry => entry.State is EntityState.Added or EntityState.Modified))
            entry.Entity.PublicListingKey = PublicLanding.SourceKey("property", entry.Entity.Id);
        foreach (var entry in ChangeTracker.Entries<SearchRequest>().Where(entry => entry.State is EntityState.Added or EntityState.Modified))
            entry.Entity.PublicListingKey = PublicLanding.SourceKey("search", entry.Entity.Id);
    }
    public override Task<int> SaveChangesAsync(bool acceptAllChangesOnSuccess, CancellationToken cancellationToken = default)
    {
        PreparePublicListingKeys();
        return ActivityNotifications.SaveAsync(this, () => PropertyNeighborhoodIndex.SaveAsync(this,
            () => SearchLocationIndex.SaveAsync(this, () => MatchingGeography.SaveAsync(this,
                () => base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken), cancellationToken), cancellationToken), cancellationToken), cancellationToken);
    }
    public override int SaveChanges(bool acceptAllChangesOnSuccess)
    {
        PreparePublicListingKeys();
        return ActivityNotifications.SaveAsync(this, () => PropertyNeighborhoodIndex.SaveAsync(this,
            () => SearchLocationIndex.SaveAsync(this, () => MatchingGeography.SaveAsync(this,
                () => Task.FromResult(base.SaveChanges(acceptAllChangesOnSuccess)), CancellationToken.None), CancellationToken.None), CancellationToken.None), CancellationToken.None)
            .GetAwaiter().GetResult();
    }
    protected override void OnModelCreating(ModelBuilder b)
    {
        Payments.Configure(b);
        SellerFeedbackSchema.Configure(b);
        b.Entity<User>().ToTable("Users");
        b.Entity<UserReport>().ToTable("UserReports");
        b.Entity<Property>().ToTable("Properties");
        b.Entity<Property>().Property(property => property.HideStreet).HasDefaultValue(true).HasSentinel(true);
        b.Entity<Property>().Property(property => property.HideHouseNumber).HasDefaultValue(true).HasSentinel(true);
        b.Entity<Property>().Property(property => property.CreationRequestHashVersion).HasDefaultValue(1);
        b.Entity<Property>().HasIndex(property => property.PublicListingKey).IsUnique();
        b.Entity<SearchRequest>().HasIndex(search => search.PublicListingKey).IsUnique();
        b.Entity<Property>().Property(property => property.FloorIsUpperRange).HasDefaultValue(false);
        b.Entity<SearchRequest>().ToTable("SearchRequests");
        b.Entity<SearchLocation>().ToTable("SearchLocations");
        b.Entity<SearchLocation>().HasKey(location => new { location.SearchRequestId, location.LocationId });
        b.Entity<SearchLocation>().HasIndex(location => new { location.LocationId, location.SearchRequestId });
        b.Entity<PropertyNeighborhood>().ToTable("PropertyNeighborhoods");
        b.Entity<PropertyNeighborhood>().HasKey(location => new { location.PropertyId, location.NeighborhoodId });
        b.Entity<PropertyNeighborhood>().HasIndex(location => new { location.NeighborhoodId, location.PropertyId });
        b.Entity<Decision>().ToTable("Decisions");
        b.Entity<Match>().ToTable("Matches");
        b.Entity<Message>().ToTable("Messages");
        b.Entity<CreditEntry>().ToTable("CreditEntries");
        b.Entity<UserNotification>().ToTable("UserNotifications");
        b.Entity<User>().HasIndex(x => x.Email).IsUnique();
        foreach (var name in new[] { nameof(SearchRequest.ExcludeTopFloor), nameof(SearchRequest.ExcludeGroundFloorAndBelow),
            nameof(SearchRequest.AirConditioning), nameof(SearchRequest.PrivateGarden), nameof(SearchRequest.SharedGarden) })
            b.Entity<SearchRequest>().Property<bool>(name).HasDefaultValue(false);
        b.Entity<UserReport>().HasIndex(x => new { x.ReporterId, x.EntityKind, x.EntityId, x.Reason }).IsUnique();
        b.Entity<Decision>().HasIndex(x => new { x.PropertyId, x.SearchRequestId, x.ActorKind }).IsUnique();
        b.Entity<Match>().HasIndex(x => new { x.PropertyId, x.SearchRequestId }).IsUnique();
        b.Entity<CreditEntry>().HasIndex(x => x.DecisionId).IsUnique();
        b.Entity<CreditEntry>().HasIndex(x => x.RefundedDecisionId).IsUnique();
        b.Entity<UserNotification>().HasIndex(x => x.DecisionId).IsUnique();
        b.Entity<UserNotification>().HasIndex(x => new { x.UserId, x.CreatedAt });
        b.Entity<UserNotification>().HasIndex(x => new { x.UserId, x.EventKey }).IsUnique();
        b.Entity<UserNotification>().HasIndex(x => new { x.UserId, x.ReadAt, x.CreatedAt });
        b.Entity<Decision>().HasIndex(x => new { x.Liked, x.RefundedAt, x.CreatedAt });
        b.Entity<Property>().HasIndex(x => new { x.OwnerId, x.Archived });
        b.Entity<Property>().HasIndex(x => new { x.OwnerId, x.CreationRequestId }).IsUnique();
        b.Entity<Property>().HasIndex(x => new { x.Archived, x.Type, x.LocationId });
        b.Entity<Property>().HasIndex(x => new { x.Archived, x.Type, x.City });
        b.Entity<Property>().HasIndex(x => new { x.Archived, x.Type, x.StreetId });
        b.Entity<Decision>().HasIndex(x => new { x.SearchRequestId, x.ActorKind, x.PropertyId });
        b.Entity<SearchRequest>().HasIndex(x => new { x.OwnerId, x.Archived });
        b.Entity<SearchRequest>().HasIndex(x => new { x.OwnerId, x.CreationRequestId }).IsUnique();
        b.Entity<SearchRequest>().HasIndex(x => new { x.Archived, x.Type, x.City });
        b.Entity<Message>().HasIndex(x => new { x.MatchId, x.CreatedAt });
        b.Entity<CreditEntry>().HasIndex(x => new { x.UserId, x.CreatedAt });
        foreach (var entity in b.Model.GetEntityTypes())
        foreach (var property in entity.GetProperties())
        {
            if (property.ClrType == typeof(DateTime)) property.SetValueConverter(new ValueConverter<DateTime, DateTime>(v => v, v => DateTime.SpecifyKind(v, DateTimeKind.Utc)));
            if (property.ClrType == typeof(DateTime?)) property.SetValueConverter(new ValueConverter<DateTime?, DateTime?>(v => v, v => v.HasValue ? DateTime.SpecifyKind(v.Value, DateTimeKind.Utc) : null));
            if (property.ClrType == typeof(string))
            {
                // Several 10,000-character VARCHAR columns can exceed MySQL's
                // 65,535-byte row limit under utf8mb4. Keep bounded long content
                // off the row; the request validation still enforces its limit.
                var longContent = property.Name.EndsWith("Json") || property.Name is "Description" or "Text";
                if (longContent) property.SetColumnType("longtext");
                else property.SetMaxLength(255);
            }
            if (property.ClrType == typeof(decimal) || property.ClrType == typeof(decimal?)) { property.SetPrecision(18); property.SetScale(2); }
        }
        // Apply the floor exception after the general decimal defaults so fresh
        // databases use the same precision as the additive floor upgrade.
        b.Entity<Property>().Property(property => property.PublicListingKey).HasMaxLength(80).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<SearchRequest>().Property(search => search.PublicListingKey).HasMaxLength(80).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<Property>().Property(property => property.EnergyRatingScheme).HasMaxLength(20).HasDefaultValue("");
        b.Entity<SearchRequest>().Property(search => search.AtticPreference).HasMaxLength(20).HasDefaultValue("");
        b.Entity<SearchRequest>().Property(search => search.MinEnergyRating).HasMaxLength(20).HasDefaultValue("");
        b.Entity<Property>().Property(property => property.Floor).HasPrecision(4, 1);
        b.Entity<Property>().HasOne<User>().WithMany().HasForeignKey(x => x.OwnerId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<SearchRequest>().HasOne<User>().WithMany().HasForeignKey(x => x.OwnerId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<SearchLocation>().HasOne<SearchRequest>().WithMany().HasForeignKey(x => x.SearchRequestId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<PropertyNeighborhood>().HasOne<Property>().WithMany().HasForeignKey(x => x.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<PropertyNeighborhood>().Property(x => x.NeighborhoodId).HasMaxLength(64).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<Property>().Property(x => x.StreetId).HasMaxLength(64).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<UserNotification>().Property(x => x.EventKey).HasMaxLength(160).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<UserNotification>().Property(x => x.EntityKind).HasMaxLength(20);
        b.Entity<Property>().Property(x => x.CreationRequestHash).HasMaxLength(64).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<SearchRequest>().Property(x => x.CreationRequestHash).HasMaxLength(64).UseCollation("ascii_bin").HasCharSet("ascii");
        b.Entity<Decision>().HasOne<Property>().WithMany().HasForeignKey(x => x.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Decision>().HasOne<SearchRequest>().WithMany().HasForeignKey(x => x.SearchRequestId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Decision>().HasOne<User>().WithMany().HasForeignKey(x => x.ActorUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Match>().HasOne<Property>().WithMany().HasForeignKey(x => x.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Match>().HasOne<SearchRequest>().WithMany().HasForeignKey(x => x.SearchRequestId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Message>().HasOne<Match>().WithMany().HasForeignKey(x => x.MatchId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Message>().HasOne<User>().WithMany().HasForeignKey(x => x.SenderId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<User>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<Decision>().WithMany().HasForeignKey(x => x.DecisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<Decision>().WithMany().HasForeignKey(x => x.RefundedDecisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UserNotification>().HasOne<User>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UserNotification>().HasOne<Decision>().WithMany().HasForeignKey(x => x.DecisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<User>().Property(x => x.AccountType).HasMaxLength(20).HasDefaultValue(AccountTypes.Private);
        b.Entity<UserReport>().HasOne<User>().WithMany().HasForeignKey(x => x.ReporterId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UserReport>().HasOne<User>().WithMany().HasForeignKey(x => x.ReportedUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<User>().ToTable(t => t.HasCheckConstraint("CK_User_Credits", "`Credits` >= 0"));
    }
}

public static class Dto
{
    public static string[] Strings(string? json) => string.IsNullOrWhiteSpace(json) ? [] : JsonSerializer.Deserialize<string[]>(json) ?? [];
    public static object Profile(User u, int unreadNotificationCount = 0) => new { u.Id, u.Name, u.Email, u.Phone, u.AccountType, u.Credits, u.ActiveKind, u.ActiveEntityId, u.CreatedAt, unreadNotificationCount };
    public static string PublicAddress(Property property) => property.HideStreet ? ""
        : property.Street + (property.HideHouseNumber || string.IsNullOrWhiteSpace(property.HouseNumber) ? "" : " " + property.HouseNumber);
    // Public cards never contain owner contacts or internal geocoding data.
    public static object Property(Property p, bool own = false, string ownerAccountType = AccountTypes.Private, string? ownerName = null, bool includeOwnedLocationDetails = true)
    {
        var rooms = Rules.RoomCounts(p);
        return new { p.Id, p.OwnerId, ownerFirstName = PublicProfile.FirstName(ownerName), ownerAccountType = AccountTypes.PublicType(ownerAccountType), p.Title, p.City, p.District, p.Neighborhood, Address = own && includeOwnedLocationDetails ? p.Address : PublicAddress(p), publicAddress = PublicAddress(p), street = p.HideStreet ? "" : p.Street, houseNumber = p.HideStreet || p.HideHouseNumber ? "" : p.HouseNumber, p.HideStreet, hideHouseNumber = p.HideStreet || p.HideHouseNumber,
            addressDetails = own && includeOwnedLocationDetails ? new { street = p.Street, streetId = p.StreetId, houseNumber = p.HouseNumber, postalCode = p.PostalCode,
                latitude = p.Latitude, longitude = p.Longitude, geocodedAt = p.GeocodedAt,
                provider = p.GeocodingProvider, quality = p.GeocodingQuality,
                geocodingStatus = p.Latitude.HasValue && p.Longitude.HasValue ? "located" : "missing" } : null,
            neighborhoodIds = Strings(p.NeighborhoodIdsJson),
            neighborhoods = Strings(p.NeighborhoodIdsJson).Select(NeighborhoodCatalog.Get).Where(x => x is not null).ToArray(),
            p.Description, locationId = LocationCatalog.ForProperty(p)?.Id ?? p.LocationId, location = LocationCatalog.ForProperty(p), p.Type, p.Price, p.Area, p.LotArea, p.Rooms, wholeRooms = rooms.WholeRooms, halfRooms = rooms.HalfRooms, p.Floor, p.FloorIsUpperRange, p.IsAttic, p.BuildingFloors, p.PrivateGarden, SharedGarden = (bool?)null, condition = PropertyAttributes.NormalizeCondition(p.Condition), building = PropertyAttributes.NormalizeBuilding(p.Building), p.ConstructionAge, p.View, p.CeilingHeight, heatingType = PropertyAttributes.NormalizeHeating(p.HeatingType), p.SecondaryHeatingType, p.Insulated, p.EnergyRating, p.EnergyRatingScheme, p.AirConditioning, p.SolarPanels, p.ParkingType, parkingTypes = PropertyAttributes.Parking(p), p.Balcony, p.Elevator, Images = Strings(p.ImagesJson), p.Archived, p.CreatedAt };
    }
    public static object Search(SearchRequest s, string ownerAccountType = AccountTypes.Private, string? ownerName = null, bool own = false)
    {
        var locations = LocationCatalog.ForSearch(s);
        var declaredIds = Strings(s.LocationIdsJson);
        // Keep invalid explicit choices visible to clients. Replacing them with []
        // would make an old client's legitimate empty-selection city fallback broaden this search.
        var locationIds = declaredIds.Length > 0 && locations.Length == 0 ? declaredIds : locations.Select(x => x.Id).ToArray();
        if (own) return new { s.Id, s.OwnerId, ownerFirstName = PublicProfile.FirstName(ownerName), searchSpecificity = MatchingRanking.Prepare(s, sellerPerspective: !own).Specificity, ownerAccountType = AccountTypes.PublicType(ownerAccountType), s.Title, s.City, Districts = Strings(s.DistrictsJson), locationIds, locations, s.Description, s.Type, s.MinPrice, s.MaxPrice, s.PublicMaxPrice, s.MinArea, s.MaxArea, s.MinRooms, s.MaxRooms, conditions = Strings(s.ConditionsJson), buildings = Strings(s.BuildingsJson), constructionAges = Strings(s.ConstructionAgesJson), views = Strings(s.ViewsJson), s.CeilingHeight, floors = PropertyAttributes.Floors(s.FloorsJson), heatingTypes = Strings(s.HeatingTypesJson).Select(PropertyAttributes.NormalizeHeating).Distinct().ToArray(), s.Balcony, s.Elevator, s.ExcludeTopFloor, s.ExcludeGroundFloorAndBelow, s.AtticPreference, s.MinEnergyRating, s.AirConditioning, s.PrivateGarden, SharedGarden = false, s.MoveIn, s.Financing, s.Archived, s.CreatedAt };
        return new { s.Id, s.OwnerId, ownerFirstName = PublicProfile.FirstName(ownerName), searchSpecificity = MatchingRanking.Prepare(s, sellerPerspective: !own).Specificity, ownerAccountType = AccountTypes.PublicType(ownerAccountType), s.Title, s.City, Districts = Strings(s.DistrictsJson), locationIds, locations, s.Description, s.Type, s.MinPrice, MaxPrice = SearchBudgets.PublicMaximum(s), s.MinArea, s.MaxArea, s.MinRooms, s.MaxRooms, conditions = Strings(s.ConditionsJson), buildings = Strings(s.BuildingsJson), constructionAges = Strings(s.ConstructionAgesJson), views = Strings(s.ViewsJson), s.CeilingHeight, floors = PropertyAttributes.Floors(s.FloorsJson), heatingTypes = Strings(s.HeatingTypesJson).Select(PropertyAttributes.NormalizeHeating).Distinct().ToArray(), s.Balcony, s.Elevator, s.ExcludeTopFloor, s.ExcludeGroundFloorAndBelow, s.AtticPreference, s.MinEnergyRating, s.AirConditioning, s.PrivateGarden, SharedGarden = false, s.MoveIn, s.Financing, s.Archived, s.CreatedAt };
    }
    public static object Message(Message m) => new { m.Id, m.MatchId, m.SenderId, m.Text, m.CreatedAt };
}

public record RegisterInput(string Name, string Email, string Password, string? Phone, string? AccountType = null);
public record LoginInput(string Email, string Password);
public record ProfileInput(string Name, string Email, string? Phone);
public record ActiveInput(string Kind, Guid Id);
public record DecisionInput(Guid PropertyId, Guid SearchRequestId, bool Liked, bool AllowApproximate = false);
public record ReportInput(string EntityKind, Guid EntityId, string? Reason = null);
public record MessageInput(string Text);
public record TopupInput(int Amount);
// New optional fields omit their defaults only when serializing inputs, preserving
// the original private creation fingerprint of older, still-pending drafts.
public record PropertyInput(string Title, string City, string? District, string? Neighborhood, string? Address, string? Description, string Type, decimal Price, decimal Area, decimal Rooms, decimal? Floor, string? Condition, string? Building, bool? Balcony, bool Elevator, string[]? Images, bool Archived = false, string? LocationId = null, decimal? LotArea = null, string? ConstructionAge = null, string? View = null, string? CeilingHeight = null, string? HeatingType = null, bool? Insulated = null, string? EnergyRating = null, bool? AirConditioning = null, bool? SolarPanels = null, string? ParkingType = null, int? WholeRooms = null, int? HalfRooms = null, string? SecondaryHeatingType = null, string[]? ParkingTypes = null, string? Street = null, string? HouseNumber = null, string? PostalCode = null, string? StreetId = null, Guid? CreationRequestId = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] int? BuildingFloors = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool? PrivateGarden = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool? SharedGarden = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool FloorIsUpperRange = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool? HideStreet = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool? HideHouseNumber = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool? IsAttic = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] string? EnergyRatingScheme = null);
public record SearchInput(string Title, string City, string[]? Districts, string? Description, string Type, decimal? MinPrice, decimal? MaxPrice, decimal? MinArea, decimal? MaxArea, decimal? MinRooms, decimal? MaxRooms, bool Balcony, bool Elevator, string? MoveIn, string? Financing, bool Archived = false, string[]? LocationIds = null, string[]? Conditions = null, string[]? Buildings = null, string[]? ConstructionAges = null, string[]? Views = null, string? CeilingHeight = null, decimal[]? Floors = null, string[]? HeatingTypes = null, Guid? CreationRequestId = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool ExcludeTopFloor = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool ExcludeGroundFloorAndBelow = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool AirConditioning = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool PrivateGarden = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool SharedGarden = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] string? AtticPreference = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] string? MinEnergyRating = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] decimal? PublicMaxPrice = null);
