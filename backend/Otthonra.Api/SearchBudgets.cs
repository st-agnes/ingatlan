namespace Otthonra.Api;

/// <summary>
/// The owner's ceiling is private. Existing searches without a separate public
/// ceiling retain their former advertised amount; public projections never need
/// the owner's ceiling after this one constant-time resolution.
/// </summary>
public static class SearchBudgets
{
    public static decimal? PublicMaximum(SearchRequest search) => search.PublicMaxPrice ?? search.MaxPrice;

    public static void Validate(decimal? minimum, decimal? maximum, decimal? publicMaximum)
    {
        if (publicMaximum.HasValue && (publicMaximum <= 0 || publicMaximum > 1_000_000_000_000m
            || maximum.HasValue && publicMaximum > maximum || minimum.HasValue && publicMaximum < minimum))
            throw new ApiException(400, "A publikus maximum ár pozitív legyen, a minimum és a valódi maximum ár között.");
    }
}
