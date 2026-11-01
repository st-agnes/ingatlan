using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;
public class MatchingTests
{
    private static (Property, SearchRequest) Pair()
    {
        var p = new Property { OwnerId = Guid.NewGuid(), City = "Budapest", District = "XIII.", Type = "Lakás", Price = 80_000_000, Area = 60, Rooms = 3, Balcony = true, Elevator = true };
        var s = new SearchRequest { OwnerId = Guid.NewGuid(), City = "budapest", DistrictsJson = "[\"XIII.\"]", Type = "lakas", MinPrice = 70_000_000, MaxPrice = 80_000_000, MinArea = 60, MaxArea = 80, MinRooms = 2, MaxRooms = 3, Balcony = true, Elevator = true };
        return (p, s);
    }
    [Fact] public void PriceAreaRoomsBoundariesAreInclusive() { var (p, s) = Pair(); Assert.True(Rules.Compatible(p, s)); }
    [Theory] [InlineData("price")] [InlineData("area")] [InlineData("rooms")] [InlineData("city")] [InlineData("district")] [InlineData("type")] [InlineData("balcony")] [InlineData("elevator")]
    public void EveryHardConstraintExcludesNonMatchingProperty(string field)
    {
        var (p, s) = Pair();
        switch (field) { case "price": p.Price++; break; case "area": p.Area--; break; case "rooms": p.Rooms++; break; case "city": p.City = "Szeged"; break; case "district": p.District = "XI."; break; case "type": p.Type = "Ház"; break; case "balcony": p.Balcony = false; break; case "elevator": p.Elevator = false; break; }
        Assert.False(Rules.Compatible(p, s));
    }
    [Fact] public void ArchivedAndSameOwnerPairsCannotMatch()
    {
        var (p, s) = Pair(); p.Archived = true; Assert.False(Rules.Compatible(p, s)); p.Archived = false; s.Archived = true; Assert.False(Rules.Compatible(p, s)); s.Archived = false; s.OwnerId = p.OwnerId; Assert.False(Rules.Compatible(p, s));
    }
    [Fact] public void OpenRangesAndNoDistrictAreUnrestricted()
    {
        var (p, s) = Pair(); s.MinPrice = s.MaxPrice = s.MinArea = s.MaxArea = s.MinRooms = s.MaxRooms = null; s.DistrictsJson = "[]"; p.District = "II."; Assert.True(Rules.Compatible(p, s));
    }
    [Fact] public void OptionalAmenitiesDoNotExcludePropertiesThatHaveThem()
    {
        var (p, s) = Pair(); s.Balcony = s.Elevator = false; Assert.True(Rules.Compatible(p, s));
    }
    [Fact] public void PublicPropertyDtoHidesExactAddress()
    {
        var (p, s) = Pair(); p.Address = "Titkos utca 12.";
        var json = JsonSerializer.Serialize(Dto.Property(p)); Assert.DoesNotContain("Titkos", json); Assert.DoesNotContain("PasswordHash", json); Assert.DoesNotContain("Email", json); Assert.Contains("Titkos", JsonSerializer.Serialize(Dto.Property(p, true)));
    }
    [Fact] public void PasswordHashesAreSaltedAndVerified()
    {
        const string password = "ComplexPassword2026!"; var a = Passwords.Hash(password); var b = Passwords.Hash(password); Assert.NotEqual(a, b); Assert.True(Passwords.Verify(password, a)); Assert.False(Passwords.Verify("wrong", a));
    }
    [Theory] [InlineData("Írj ide: hello@example.com")] [InlineData("Hívj: +36 30 123 4567")]
    public void PublicTextRejectsCommonContactDetails(string text) => Assert.Throws<ApiException>(() => Rules.PublicText(text));
    [Fact] public void ReversedSearchRangesAreRejected() => Assert.Throws<ApiException>(() => Rules.Range(100, 50, "ár"));
}
