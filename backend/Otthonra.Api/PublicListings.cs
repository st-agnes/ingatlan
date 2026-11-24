using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

/// <summary>A public listing is a deliberate whitelist, never an owned entity DTO.</summary>
public sealed record PublicListingDetail(string Kind, string Key, string SourceKey, string Title,
    string OwnerFirstName, string OwnerAccountType, object Listing, object Prefill, object? ClonePrefill = null)
{
    public string Href => "#listing/" + Kind + "/" + SourceKey;
}

public static class PublicListings
{
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);

    public static IEndpointRouteBuilder MapPublicListings(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/public/listings/{kind}/{key}", async Task<IResult>
            (string kind, string key, AppDb db, HttpContext context, CancellationToken cancellationToken) =>
        {
            // Privacy switches and deletion must take effect on the next read,
            // including when the browser revisits a previously shared URL.
            context.Response.Headers.CacheControl = "no-store";
            if (!ValidKey(kind, key)) return Results.NotFound();
            if (kind == "property")
            {
                var row = await (from property in db.Properties.AsNoTracking()
                    join owner in db.Users.AsNoTracking() on property.OwnerId equals owner.Id
                    where !property.Archived && property.PublicListingKey == key
                    select new { Property = property, owner.Name, owner.AccountType })
                    .SingleOrDefaultAsync(cancellationToken);
                var listing = row is null ? null : Property(row.Property, row.AccountType, row.Name);
                return listing is null ? Results.NotFound() : Results.Ok(listing);
            }
            var result = await (from search in db.SearchRequests.AsNoTracking()
                join owner in db.Users.AsNoTracking() on search.OwnerId equals owner.Id
                where !search.Archived && search.PublicListingKey == key
                select new { Search = search, owner.Name, owner.AccountType })
                .SingleOrDefaultAsync(cancellationToken);
            var detail = result is null ? null : Search(result.Search, result.AccountType, result.Name);
            return detail is null ? Results.NotFound() : Results.Ok(detail);
        }).AllowAnonymous();
        return endpoints;
    }

    public static bool ValidKey(string kind, string? key) => kind is "property" or "search"
        && key is not null && key.Length == kind.Length + 65 && key.StartsWith(kind + "-", StringComparison.Ordinal)
        && key[(kind.Length + 1)..].All(character => character is >= 'a' and <= 'f' or >= '0' and <= '9');

    public static string Description(string? text)
    {
        var value = new string((text ?? "").Take(6000).Where(character => !char.IsControl(character) || char.IsWhiteSpace(character)).ToArray()).Trim();
        // Old rows predate description validation. A public page must not turn
        // them into a new anonymous contact directory.
        return ContactTextPolicy.ContainsContactDetails(value) ? "" : value;
    }

    public static string Title(string? title, string fallback)
    {
        var value = PublicProfile.Title(title, fallback);
        return ContactTextPolicy.ContainsContactDetails(value) ? fallback : value;
    }

    private static string Text(string? text) => PublicProfile.Title(text, "") is { } value
        && !ContactTextPolicy.ContainsContactDetails(value) ? value : "";

    public static string[] Images(string? json)
    {
        if (string.IsNullOrWhiteSpace(json) || json.Length > 10000) return [];
        try
        {
            return Dto.Strings(json).Where(value => value is not null && value.Length <= 2000
                && !value.Any(character => char.IsControl(character) || char.IsWhiteSpace(character))
                && Uri.TryCreate(value, UriKind.Absolute, out var uri) && uri.Scheme == "https" && uri.UserInfo.Length == 0)
                .Distinct(StringComparer.Ordinal).Take(12).ToArray();
        }
        catch (JsonException) { return []; }
    }

    private static string[] Parking(Property property)
    {
        try { return PropertyAttributes.Parking(property).Select(Text).Where(value => value.Length > 0).Take(20).ToArray(); }
        catch (JsonException) { return []; }
    }

    private static NeighborhoodArea[] Areas(Property property, Location location)
    {
        if (property.NeighborhoodIdsJson is null || property.NeighborhoodIdsJson.Length > 16384) return [];
        try { return Dto.Strings(property.NeighborhoodIdsJson).Select(NeighborhoodCatalog.Get).Where(area => area is not null)
            .Select(area => area!).Where(area => area.City == location.City).DistinctBy(area => area.Id).Take(50).ToArray(); }
        catch (JsonException) { return []; }
    }

    public static PublicListingDetail? Property(Property property, string? accountType, string? ownerName = null)
    {
        var teaser = PublicLanding.PropertyTeaser(property, accountType, ownerName)?.Teaser;
        if (teaser?.Prefill is not { } seed) return null;
        var location = LocationCatalog.ForProperty(property)!;
        var house = teaser.Type == "Ház";
        var street = property.HideStreet ? "" : property.Street;
        var houseNumber = property.HideStreet || property.HideHouseNumber ? "" : property.HouseNumber;
        var address = string.Join(" ", new[] { street, houseNumber }.Where(value => value.Length > 0));
        var areas = Areas(property, location);
        var listing = new {
            title = teaser.Title, type = teaser.Type, ownerFirstName = teaser.OwnerFirstName, ownerAccountType = teaser.OwnerAccountType,
            city = location.City, district = location.District ?? "", locationId = location.Id, location = location.Label,
            neighborhood = string.Join(", ", areas.Select(area => area.Name)), neighborhoods = areas,
            neighborhoodIds = areas.Select(area => area.Id).ToArray(), address, street, houseNumber,
            hideStreet = property.HideStreet, hideHouseNumber = property.HideStreet || property.HideHouseNumber,
            description = Description(property.Description), price = property.Price, area = property.Area, rooms = property.Rooms,
            wholeRooms = seed.WholeRooms, halfRooms = seed.HalfRooms, lotArea = seed.LotArea,
            condition = Text(PropertyAttributes.NormalizeCondition(property.Condition)), building = Text(PropertyAttributes.NormalizeBuilding(property.Building)),
            constructionAge = Text(property.ConstructionAge), view = Text(property.View), ceilingHeight = Text(property.CeilingHeight),
            floor = seed.Floor, floorIsUpperRange = seed.FloorIsUpperRange, buildingFloors = seed.BuildingFloors,
            isAttic = house ? null : property.IsAttic, elevator = !house && property.Elevator,
            balcony = house ? null : property.Balcony, airConditioning = property.AirConditioning,
            privateGarden = teaser.Type == "Lakás" ? property.PrivateGarden : null,
            heatingType = Text(PropertyAttributes.NormalizeHeating(property.HeatingType)), insulated = property.Insulated,
            energyRating = Text(property.EnergyRating), energyRatingScheme = property.EnergyRatingScheme == "2023" ? "2023" : "",
            solarPanels = property.SolarPanels, parkingTypes = Parking(property), images = Images(property.ImagesJson), property.CreatedAt
        };
        return new("property", teaser.SourceKey, teaser.SourceKey, teaser.Title, teaser.OwnerFirstName, teaser.OwnerAccountType, listing, seed);
    }

    public static PublicListingDetail? Search(SearchRequest search, string? accountType, string? ownerName = null)
    {
        var teaser = PublicLanding.SearchTeaser(search, accountType, ownerName)?.Teaser;
        if (teaser?.Prefill is not { } seed) return null;
        var description = Description(search.Description);
        var moveIn = Text(search.MoveIn); var financing = Text(search.Financing);
        var listing = new {
            title = teaser.Title, type = seed.Type, ownerFirstName = teaser.OwnerFirstName, ownerAccountType = teaser.OwnerAccountType,
            locations = seed.Locations, locationIds = seed.Locations.Select(location => location.Id).ToArray(),
            city = seed.Locations[0].City, description,
            minPrice = seed.MinPrice, maxPrice = seed.MaxPrice, minArea = seed.MinArea, maxArea = seed.MaxArea,
            minRooms = seed.MinRooms, maxRooms = seed.MaxRooms, conditions = seed.Conditions, buildings = seed.Buildings,
            constructionAges = seed.ConstructionAges, views = seed.Views, ceilingHeight = seed.CeilingHeight, floors = seed.Floors,
            heatingTypes = seed.HeatingTypes, balcony = seed.Balcony, elevator = seed.Elevator,
            excludeTopFloor = seed.ExcludeTopFloor, excludeGroundFloorAndBelow = seed.ExcludeGroundFloorAndBelow,
            airConditioning = seed.AirConditioning, privateGarden = seed.PrivateGarden,
            atticPreference = seed.AtticPreference, minEnergyRating = seed.MinEnergyRating,
            moveIn, financing, search.CreatedAt
        };
        var clone = JsonSerializer.SerializeToElement(seed, WebJson).EnumerateObject()
            .ToDictionary(value => value.Name, value => (object?)value.Value.Clone(), StringComparer.Ordinal);
        clone["moveIn"] = moveIn; clone["financing"] = financing;
        clone["description"] = description;
        return new("search", teaser.SourceKey, teaser.SourceKey, teaser.Title, teaser.OwnerFirstName, teaser.OwnerAccountType, listing, seed, clone);
    }
}
