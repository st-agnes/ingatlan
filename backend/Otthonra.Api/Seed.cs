using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;
public static class Seed
{
    public static async Task Run(AppDb db)
    {
        if (await db.Users.AnyAsync()) return;
        var buyer = new User { Name = "Kovács Anna", Email = "anna@otthonra.local", Phone = "+36 30 555 0101", PasswordHash = Passwords.Hash("OtthonraDemo2026!"), Credits = 50 };
        var seller = new User { Name = "Nagy Péter", Email = "peter@otthonra.local", Phone = "+36 30 555 0102", PasswordHash = Passwords.Hash("OtthonraDemo2026!"), Credits = 50 };
        var third = new User { Name = "Szabó Eszter", Email = "eszter@otthonra.local", Phone = "+36 30 555 0103", PasswordHash = Passwords.Hash("OtthonraDemo2026!"), Credits = 50 };
        db.Users.AddRange(buyer, seller, third);
        var search = new SearchRequest { OwnerId = buyer.Id, Title = "Világos otthon Újlipótvárosban", City = "Budapest", DistrictsJson = "[\"XIII.\",\"II.\"]", Type = "Lakás", MinPrice = 45_000_000, MaxPrice = 100_000_000, MinArea = 45, MaxArea = 100, MinRooms = 2, MaxRooms = 4, Financing = "Önerő és előminősített lakáshitel", Description = "Ketten költöznénk, hosszú távra keresünk egy szerethető otthont.", MoveIn = "3 hónapon belül" };
        var search2 = new SearchRequest { OwnerId = third.Id, Title = "Erkélyes lakást keresek Budán", City = "Budapest", DistrictsJson = "[\"II.\",\"XIII.\"]", Type = "Lakás", MinPrice = 40_000_000, MaxPrice = 110_000_000, MinArea = 40, MaxArea = 100, MinRooms = 2, MaxRooms = 4, Balcony = true, Financing = "Készpénzes vásárlás", Description = "Csendes, zöld környéken keresek napfényes lakást." };
        var photos = new[] { "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1400&q=85", "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1400&q=85" };
        var property = new Property { OwnerId = seller.Id, Title = "Napfényes otthon a Pozsonyi útnál", City = "Budapest", District = "XIII.", Neighborhood = "Újlipótváros", Address = "Pozsonyi út 12.", Type = "Lakás", Price = 79_900_000, Area = 68, Rooms = 3, Floor = 3, Condition = "Felújított", Building = "Tégla", Balcony = true, Elevator = true, Description = "Világos, átgondolt elrendezésű lakás egy rendezett, liftes házban. A Duna-part és a Szent István park néhány perc séta.", ImagesJson = JsonSerializer.Serialize(photos) };
        var property2 = new Property { OwnerId = third.Id, Title = "Zöldre néző lakás a Rózsadombon", City = "Budapest", District = "II.", Neighborhood = "Rózsadomb", Type = "Lakás", Price = 92_000_000, Area = 74, Rooms = 3, Floor = 1, Condition = "Jó állapotú", Building = "Tégla", Balcony = true, Elevator = false, Description = "Csendes környezet, tágas nappali és saját erkély.", ImagesJson = JsonSerializer.Serialize(photos.Reverse()) };
        db.Properties.AddRange(property, property2); db.SearchRequests.AddRange(search, search2);
        buyer.ActiveKind = "search"; buyer.ActiveEntityId = search.Id; seller.ActiveKind = "property"; seller.ActiveEntityId = property.Id;
        foreach (var u in new[] { buyer, seller, third }) db.CreditEntries.Add(new CreditEntry { UserId = u.Id, Amount = 50, Description = "Kezdő demóegyenleg" });
        // Seller interest awaits Anna's choice; contact remains locked until Anna likes too.
        var decision = new Decision { PropertyId = property.Id, SearchRequestId = search.Id, ActorKind = "property", ActorUserId = seller.Id, Liked = true, Charged = Rules.SellerLikeCost };
        db.Decisions.Add(decision); seller.Credits -= Rules.SellerLikeCost; db.CreditEntries.Add(new CreditEntry { UserId = seller.Id, Amount = -Rules.SellerLikeCost, Description = "Ingatlan ajánlása egy keresőnek", DecisionId = decision.Id });
        await db.SaveChangesAsync();
    }
}
