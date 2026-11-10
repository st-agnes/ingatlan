using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>A real visible discovery card, deduplicated by person rather than search profile.</summary>
public sealed class PropertyImpression
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PropertyId { get; set; }
    public Guid ViewerUserId { get; set; }
    public Guid SearchRequestId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public sealed class FeedbackPackage
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PropertyId { get; set; }
    public Guid OwnerId { get; set; }
    public Guid RequestId { get; set; }
    public int Size { get; set; }
    public int ReceivedCount { get; set; }
    public bool Enabled { get; set; } = true;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime ExpiresAt { get; set; }
    public DateTime? RefundedAt { get; set; }
    public int RefundedCredits { get; set; }
}

/// <summary>A short-lived reserved response slot. Declines have a reason but consume no paid response.</summary>
public sealed class FeedbackInvitation
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PackageId { get; set; }
    public Guid PropertyId { get; set; }
    public Guid DecisionId { get; set; }
    public Guid BuyerId { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime ExpiresAt { get; set; }
    public DateTime? AnsweredAt { get; set; }
    public string? Reason { get; set; }
}

public static class SellerFeedbackSchema
{
    public static void Configure(ModelBuilder b)
    {
        b.Entity<PropertyImpression>().ToTable("PropertyImpressions");
        b.Entity<PropertyImpression>().HasIndex(row => new { row.PropertyId, row.ViewerUserId }).IsUnique();
        b.Entity<PropertyImpression>().HasOne<Property>().WithMany().HasForeignKey(row => row.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<PropertyImpression>().HasOne<User>().WithMany().HasForeignKey(row => row.ViewerUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<PropertyImpression>().HasOne<SearchRequest>().WithMany().HasForeignKey(row => row.SearchRequestId).OnDelete(DeleteBehavior.Restrict);

        b.Entity<FeedbackPackage>().ToTable("FeedbackPackages", table => {
            table.HasCheckConstraint("CK_FeedbackPackages_Size", "`Size` IN (10, 20, 50)");
            table.HasCheckConstraint("CK_FeedbackPackages_Counts", "`ReceivedCount` >= 0 AND `ReceivedCount` <= `Size` AND `RefundedCredits` >= 0 AND `RefundedCredits` <= `Size`");
        });
        b.Entity<FeedbackPackage>().HasIndex(row => new { row.OwnerId, row.RequestId }).IsUnique();
        b.Entity<FeedbackPackage>().HasIndex(row => new { row.PropertyId, row.ExpiresAt });
        b.Entity<FeedbackPackage>().HasIndex(row => new { row.OwnerId, row.ExpiresAt });
        b.Entity<FeedbackPackage>().HasIndex(row => new { row.RefundedAt, row.ExpiresAt });
        b.Entity<FeedbackPackage>().HasOne<Property>().WithMany().HasForeignKey(row => row.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<FeedbackPackage>().HasOne<User>().WithMany().HasForeignKey(row => row.OwnerId).OnDelete(DeleteBehavior.Restrict);

        b.Entity<FeedbackInvitation>().ToTable("FeedbackInvitations");
        b.Entity<FeedbackInvitation>().HasIndex(row => row.DecisionId).IsUnique();
        b.Entity<FeedbackInvitation>().HasIndex(row => new { row.PackageId, row.BuyerId }).IsUnique();
        b.Entity<FeedbackInvitation>().HasIndex(row => new { row.BuyerId, row.AnsweredAt, row.ExpiresAt });
        b.Entity<FeedbackInvitation>().HasIndex(row => new { row.PackageId, row.AnsweredAt, row.ExpiresAt });
        b.Entity<FeedbackInvitation>().HasIndex(row => new { row.PackageId, row.Reason });
        b.Entity<FeedbackInvitation>().HasOne<FeedbackPackage>().WithMany().HasForeignKey(row => row.PackageId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<FeedbackInvitation>().HasOne<Property>().WithMany().HasForeignKey(row => row.PropertyId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<FeedbackInvitation>().HasOne<User>().WithMany().HasForeignKey(row => row.BuyerId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<FeedbackInvitation>().HasOne<Decision>().WithMany().HasForeignKey(row => row.DecisionId).OnDelete(DeleteBehavior.Restrict);

        b.Entity<CreditEntry>().HasIndex(row => row.FeedbackPackageId).IsUnique();
        b.Entity<CreditEntry>().HasIndex(row => row.RefundedFeedbackPackageId).IsUnique();
        b.Entity<CreditEntry>().HasOne<FeedbackPackage>().WithMany().HasForeignKey(row => row.FeedbackPackageId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<CreditEntry>().HasOne<FeedbackPackage>().WithMany().HasForeignKey(row => row.RefundedFeedbackPackageId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UserNotification>().HasIndex(row => row.FeedbackPackageId).IsUnique();
        b.Entity<UserNotification>().HasOne<FeedbackPackage>().WithMany().HasForeignKey(row => row.FeedbackPackageId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<User>().Property(row => row.FeedbackPassCounter).HasDefaultValue(0);
        b.Entity<Decision>().HasIndex(row => new { row.PropertyId, row.ActorKind, row.Liked, row.ActorUserId, row.SearchRequestId })
            .HasDatabaseName("IX_Decisions_PropertyStats");
    }
}
