namespace Otthonra.Api;

/// <summary>The 2023 Hungarian energetic-quality scale, never the separate CO2 indicator.</summary>
public static class EnergyCertificates
{
    public const string Scheme = "2023";
    public static int Rank(string? rating) => Array.IndexOf(PropertyAttributes.EnergyRatings, rating ?? "");
    public static bool IsCurrent(Property property) => property.EnergyRatingScheme == Scheme && Rank(property.EnergyRating) >= 0;
    public static bool MinimumSatisfied(Property property, string? minimum) => string.IsNullOrEmpty(minimum)
        || Rank(minimum) >= 0 && IsCurrent(property) && Rank(property.EnergyRating) >= Rank(minimum);
    public static decimal Loss(Property property, string minimum) => !IsCurrent(property) || Rank(minimum) < 0 ? 1m
        : Math.Clamp((Rank(minimum) - Rank(property.EnergyRating)) / 11m, 0m, 1m);
    public static void Apply(Property property, PropertyInput input)
    {
        var rating = Rules.PublicText(input.EnergyRating, 20);
        if (input.EnergyRatingScheme is not null)
        {
            var scheme = Rules.Optional(input.EnergyRatingScheme, 20);
            if (scheme is not ("" or Scheme)) throw new ApiException(400, "Érvénytelen energetikai tanúsítvány-rendszer.");
            if (scheme == Scheme && rating.Length > 0)
                rating = PropertyAttributes.Choice(rating, PropertyAttributes.EnergyRatings, "energetikai tanúsítvány");
            property.EnergyRatingScheme = rating.Length == 0 ? "" : scheme;
        }
        else if (rating != property.EnergyRating || !IsCurrent(property)) property.EnergyRatingScheme = "";
        property.EnergyRating = rating;
    }
}
