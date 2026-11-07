using System.ComponentModel.DataAnnotations;
using System.Text.Json;
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
    public string? ActiveKind { get; set; }
    public Guid? ActiveEntityId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class Property
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid OwnerId { get; set; }
    public string Title { get; set; } = "";
    public string City { get; set; } = "";
    public string District { get; set; } = "";
    public string LocationId { get; set; } = "";
    public decimal? LotArea { get; set; }
    public string Neighborhood { get; set; } = "";
    public string Address { get; set; } = "";
    public string Description { get; set; } = "";
    public string Type { get; set; } = "Lakás";
    public decimal Price { get; set; }
    public decimal Area { get; set; }
    public decimal Rooms { get; set; }
    public int? WholeRooms { get; set; }
    public int? HalfRooms { get; set; }
    public int? Floor { get; set; }
    public string Condition { get; set; } = "";
    public string Building { get; set; } = "";
    public string ConstructionAge { get; set; } = "";
    public string View { get; set; } = "";
    public string CeilingHeight { get; set; } = "";
    public string HeatingType { get; set; } = "";
    public string SecondaryHeatingType { get; set; } = "";
    public bool? Insulated { get; set; }
    public string EnergyRating { get; set; } = "";
    public bool? AirConditioning { get; set; }
    public bool? SolarPanels { get; set; }
    public string ParkingType { get; set; } = "";
    public string? ParkingTypesJson { get; set; }
    public bool Balcony { get; set; }
    public bool Elevator { get; set; }
    public string ImagesJson { get; set; } = "[]";
    public bool Archived { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
public sealed class SearchRequest
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid OwnerId { get; set; }
    public string Title { get; set; } = "";
    public string City { get; set; } = "";
    public string DistrictsJson { get; set; } = "[]";
    public string? LocationIdsJson { get; set; } = "[]";
    public string Description { get; set; } = "";
    public string Type { get; set; } = "Lakás";
    public decimal? MinPrice { get; set; }
    public decimal? MaxPrice { get; set; }
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
    public bool Balcony { get; set; }
    public bool Elevator { get; set; }
    public string MoveIn { get; set; } = "";
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
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
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
    public DbSet<Decision> Decisions => Set<Decision>();
    public DbSet<Match> Matches => Set<Match>();
    public DbSet<Message> Messages => Set<Message>();
    public DbSet<CreditEntry> CreditEntries => Set<CreditEntry>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        Payments.Configure(b);
        b.Entity<User>().ToTable("Users");
        b.Entity<UserReport>().ToTable("UserReports");
        b.Entity<Property>().ToTable("Properties");
        b.Entity<SearchRequest>().ToTable("SearchRequests");
        b.Entity<Decision>().ToTable("Decisions");
        b.Entity<Match>().ToTable("Matches");
        b.Entity<Message>().ToTable("Messages");
        b.Entity<CreditEntry>().ToTable("CreditEntries");
        b.Entity<User>().HasIndex(x => x.Email).IsUnique();
        b.Entity<UserReport>().HasIndex(x => new { x.ReporterId, x.EntityKind, x.EntityId, x.Reason }).IsUnique();
        b.Entity<Decision>().HasIndex(x => new { x.PropertyId, x.SearchRequestId, x.ActorKind }).IsUnique();
        b.Entity<Match>().HasIndex(x => new { x.PropertyId, x.SearchRequestId }).IsUnique();
        b.Entity<CreditEntry>().HasIndex(x => x.DecisionId).IsUnique();
        b.Entity<Property>().HasIndex(x => new { x.OwnerId, x.Archived });
        b.Entity<SearchRequest>().HasIndex(x => new { x.OwnerId, x.Archived });
        b.Entity<Message>().HasIndex(x => new { x.MatchId, x.CreatedAt });
        b.Entity<CreditEntry>().HasIndex(x => new { x.UserId, x.CreatedAt });
        foreach (var entity in b.Model.GetEntityTypes())
        foreach (var property in entity.GetProperties())
        {
            if (property.ClrType == typeof(DateTime)) property.SetValueConverter(new ValueConverter<DateTime, DateTime>(v => v, v => DateTime.SpecifyKind(v, DateTimeKind.Utc)));
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
        b.Entity<Property>().HasOne<User>().WithMany().HasForeignKey(x => x.OwnerId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<SearchRequest>().HasOne<User>().WithMany().HasForeignKey(x => x.OwnerId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Decision>().HasOne<Property>().WithMany().HasForeignKey(x => x.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Decision>().HasOne<SearchRequest>().WithMany().HasForeignKey(x => x.SearchRequestId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Decision>().HasOne<User>().WithMany().HasForeignKey(x => x.ActorUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Match>().HasOne<Property>().WithMany().HasForeignKey(x => x.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Match>().HasOne<SearchRequest>().WithMany().HasForeignKey(x => x.SearchRequestId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Message>().HasOne<Match>().WithMany().HasForeignKey(x => x.MatchId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Message>().HasOne<User>().WithMany().HasForeignKey(x => x.SenderId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<User>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<Decision>().WithMany().HasForeignKey(x => x.DecisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<User>().Property(x => x.AccountType).HasMaxLength(20).HasDefaultValue(AccountTypes.Private);
        b.Entity<UserReport>().HasOne<User>().WithMany().HasForeignKey(x => x.ReporterId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UserReport>().HasOne<User>().WithMany().HasForeignKey(x => x.ReportedUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<User>().ToTable(t => t.HasCheckConstraint("CK_User_Credits", "`Credits` >= 0"));
    }
}

public static class Dto
{
    public static string[] Strings(string? json) => string.IsNullOrWhiteSpace(json) ? [] : JsonSerializer.Deserialize<string[]>(json) ?? [];
    public static object Profile(User u) => new { u.Id, u.Name, u.Email, u.Phone, u.AccountType, u.Credits, u.ActiveKind, u.ActiveEntityId, u.CreatedAt };
    // Public cards intentionally contain no user/contact object or exact street address.
    public static object Property(Property p, bool own = false, string ownerAccountType = AccountTypes.Private)
    {
        var rooms = Rules.RoomCounts(p);
        return new { p.Id, p.OwnerId, ownerAccountType = AccountTypes.PublicType(ownerAccountType), p.Title, p.City, p.District, p.Neighborhood, Address = own ? p.Address : "", p.Description, locationId = LocationCatalog.ForProperty(p)?.Id ?? p.LocationId, location = LocationCatalog.ForProperty(p), p.Type, p.Price, p.Area, p.LotArea, p.Rooms, wholeRooms = rooms.WholeRooms, halfRooms = rooms.HalfRooms, p.Floor, condition = PropertyAttributes.NormalizeCondition(p.Condition), building = PropertyAttributes.NormalizeBuilding(p.Building), p.ConstructionAge, p.View, p.CeilingHeight, heatingType = PropertyAttributes.NormalizeHeating(p.HeatingType), p.SecondaryHeatingType, p.Insulated, p.EnergyRating, p.AirConditioning, p.SolarPanels, p.ParkingType, parkingTypes = PropertyAttributes.Parking(p), p.Balcony, p.Elevator, Images = Strings(p.ImagesJson), p.Archived, p.CreatedAt };
    }
    public static object Search(SearchRequest s, string ownerAccountType = AccountTypes.Private) => new { s.Id, s.OwnerId, ownerAccountType = AccountTypes.PublicType(ownerAccountType), s.Title, s.City, Districts = Strings(s.DistrictsJson), locationIds = LocationCatalog.ForSearch(s).Select(x => x.Id), locations = LocationCatalog.ForSearch(s), s.Description, s.Type, s.MinPrice, s.MaxPrice, s.MinArea, s.MaxArea, s.MinRooms, s.MaxRooms, conditions = Strings(s.ConditionsJson), buildings = Strings(s.BuildingsJson), constructionAges = Strings(s.ConstructionAgesJson), views = Strings(s.ViewsJson), s.CeilingHeight, floors = PropertyAttributes.Floors(s.FloorsJson), heatingTypes = Strings(s.HeatingTypesJson), s.Balcony, s.Elevator, s.MoveIn, s.Financing, s.Archived, s.CreatedAt };
    public static object Message(Message m) => new { m.Id, m.MatchId, m.SenderId, m.Text, m.CreatedAt };
}

public record RegisterInput(string Name, string Email, string Password, string? Phone, string? AccountType = null);
public record LoginInput(string Email, string Password);
public record ProfileInput(string Name, string Email, string? Phone);
public record ActiveInput(string Kind, Guid Id);
public record DecisionInput(Guid PropertyId, Guid SearchRequestId, bool Liked);
public record ReportInput(string EntityKind, Guid EntityId, string? Reason = null);
public record MessageInput(string Text);
public record TopupInput(int Amount);
public record PropertyInput(string Title, string City, string? District, string? Neighborhood, string? Address, string? Description, string Type, decimal Price, decimal Area, decimal Rooms, int? Floor, string? Condition, string? Building, bool Balcony, bool Elevator, string[]? Images, bool Archived = false, string? LocationId = null, decimal? LotArea = null, string? ConstructionAge = null, string? View = null, string? CeilingHeight = null, string? HeatingType = null, bool? Insulated = null, string? EnergyRating = null, bool? AirConditioning = null, bool? SolarPanels = null, string? ParkingType = null, int? WholeRooms = null, int? HalfRooms = null, string? SecondaryHeatingType = null, string[]? ParkingTypes = null);
public record SearchInput(string Title, string City, string[]? Districts, string? Description, string Type, decimal? MinPrice, decimal? MaxPrice, decimal? MinArea, decimal? MaxArea, decimal? MinRooms, decimal? MaxRooms, bool Balcony, bool Elevator, string? MoveIn, string? Financing, bool Archived = false, string[]? LocationIds = null, string[]? Conditions = null, string[]? Buildings = null, string[]? ConstructionAges = null, string[]? Views = null, string? CeilingHeight = null, int[]? Floors = null, string[]? HeatingTypes = null);
