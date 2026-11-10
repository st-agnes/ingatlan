using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class SellerFeedbackPolicyTests
{
    private static readonly DateTime Start = new(2026, 11, 10, 12, 0, 0, DateTimeKind.Utc);
    private static FeedbackPackage Package(int size = 10, int received = 0) => new() {
        Size = size, ReceivedCount = received, CreatedAt = Start,
        ExpiresAt = Start.AddDays(SellerFeedbackPolicy.DurationDays), Enabled = true
    };

    [Fact]
    public void PackagesAndFixedAnswerChoicesRepresentExactlyTheOfferedProduct()
    {
        Assert.Equal(new[] { 10, 20, 50 }, SellerFeedbackPolicy.PackageSizes);
        Assert.Equal(14, SellerFeedbackPolicy.DurationDays);
        Assert.InRange(SellerFeedbackPolicy.PromptSpacing, 18, 25);
        Assert.Equal(new[] { "insufficient_information", "layout", "lighting", "location", "view",
            "incorrect_parameters", "other", "decline" }, SellerFeedbackPolicy.Options.Select(option => option.Value));
        Assert.Equal(SellerFeedbackPolicy.Options.Length, SellerFeedbackPolicy.Options.Select(option => option.Value).Distinct().Count());
        Assert.Equal("Nem szeretnék válaszolni", SellerFeedbackPolicy.Label(SellerFeedbackPolicy.Decline));
        Assert.Equal("Az ingatlan nem felel meg a róla feltüntetett paramétereknek", SellerFeedbackPolicy.Label("incorrect_parameters"));
        Assert.All(SellerFeedbackPolicy.Options, option => {
            Assert.True(SellerFeedbackPolicy.IsReason(option.Value)); Assert.False(string.IsNullOrWhiteSpace(option.Label));
        });
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("unknown")]
    [InlineData("LAYOUT")]
    [InlineData("layout ")]
    public void OnlyExactKnownReasonKeysAreAccepted(string? reason)
        => Assert.False(SellerFeedbackPolicy.IsReason(reason));

    [Fact]
    public void ACompletedQuotaStillOccupiesItsWholeTwoWeekPeriod()
    {
        var package = Package(received: 10);
        Assert.True(SellerFeedbackPolicy.IsPeriodActive(package, package.ExpiresAt.AddTicks(-1)));
        Assert.Equal("completed", SellerFeedbackPolicy.Package(package, Start.AddDays(2)).Status);
        Assert.Equal(0, SellerFeedbackPolicy.Package(package, Start.AddDays(2)).Remaining);
        Assert.False(SellerFeedbackPolicy.IsPeriodActive(package, package.ExpiresAt));
        Assert.Equal("expired", SellerFeedbackPolicy.Package(package, package.ExpiresAt).Status);
    }

    [Fact]
    public void PausingDoesNotExtendThePaidPeriodAndFinalizedRefundsStayClosed()
    {
        var package = Package(); package.Enabled = false;
        Assert.True(SellerFeedbackPolicy.IsPeriodActive(package, Start.AddDays(1)));
        Assert.Equal(Start.AddDays(14), SellerFeedbackPolicy.Package(package, Start.AddDays(1)).ExpiresAt);
        package.RefundedAt = Start.AddDays(14);
        Assert.False(SellerFeedbackPolicy.IsPeriodActive(package, Start.AddDays(20)));
        Assert.Equal("expired", SellerFeedbackPolicy.Package(package, Start.AddDays(20)).Status);
    }

    [Theory]
    [InlineData(10, 0, 10)]
    [InlineData(10, 3, 7)]
    [InlineData(20, 19, 1)]
    [InlineData(50, 50, 0)]
    public void RefundQuotaUsesOnlyTheMissingCount(int size, int received, int expected)
    {
        var package = Package(size, received);
        Assert.Equal(expected, SellerFeedbackPolicy.Missing(package));
        Assert.Equal(expected, SellerFeedbackPolicy.Package(package, Start).Remaining);
        Assert.Equal(size, SellerFeedbackPolicy.Package(package, Start).Size);
        Assert.Equal(received, SellerFeedbackPolicy.Package(package, Start).ReceivedCount);
    }

    [Theory]
    [InlineData("Nagy Anna", "Segíts Annának egy visszajelzéssel")]
    [InlineData("Dr. Nagy Péter", "Segíts Péternek egy visszajelzéssel")]
    [InlineData("Kovács Bence", "Segíts Bencének egy visszajelzéssel")]
    [InlineData("Júlia", "Segíts Júliának egy visszajelzéssel")]
    [InlineData("Máté", "Segíts Máténak egy visszajelzéssel")]
    [InlineData("Zsófi", "Segíts Zsófinak egy visszajelzéssel")]
    [InlineData("Eszter", "Segíts Eszternek egy visszajelzéssel")]
    [InlineData("Márk", "Segíts Márknak egy visszajelzéssel")]
    [InlineData("Noémi", "Segíts Noéminek egy visszajelzéssel")]
    [InlineData(null, "Segíts az eladónak egy visszajelzéssel")]
    [InlineData("seller@example.test", "Segíts az eladónak egy visszajelzéssel")]
    [InlineData("+36 30 555 0123", "Segíts az eladónak egy visszajelzéssel")]
    public void PromptUsesOnlyTheSanitizedGivenNameWithTheHungarianSuffix(string? name, string expected)
        => Assert.Equal(expected, SellerFeedbackPolicy.PromptTitle(name));
}
