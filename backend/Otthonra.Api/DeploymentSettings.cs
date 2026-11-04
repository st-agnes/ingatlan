namespace Otthonra.Api;

/// <summary>
/// Deployment capabilities are read once from server configuration. A hosted
/// test installation can use ASP.NET Production settings without real payments.
/// </summary>
public sealed record DeploymentSettings(string Name, bool IsTest, bool AllowDemoTopup)
{
    public string TopupDescription => IsTest
        ? "Tesztkredit-feltöltés – valódi fizetés nélkül"
        : "Demófeltöltés – valódi fizetés nélkül";

    public static DeploymentSettings From(IConfiguration configuration, string hostEnvironment)
    {
        var development = string.Equals(hostEnvironment, "Development", StringComparison.OrdinalIgnoreCase);
        var test = string.Equals(configuration["Deployment:Environment"]?.Trim(), "test", StringComparison.OrdinalIgnoreCase);
        var name = test ? "test" : development ? "development" : "production";

        // A configuration mistake must not turn a test installation into a
        // checkout for real money. Do not include the offending key in errors.
        var stripeKey = configuration["Stripe:SecretKey"]?.Trim();
        if (test && (stripeKey?.StartsWith("sk_live_", StringComparison.Ordinal) == true
            || stripeKey?.StartsWith("rk_live_", StringComparison.Ordinal) == true))
            throw new InvalidOperationException("Live Stripe keys cannot be used in a test deployment.");

        return new(name, test, (development || test) && configuration.GetValue<bool>("Credits:EnableDemoTopup"));
    }
}
