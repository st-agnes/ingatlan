using Microsoft.Extensions.Configuration;
using MySqlConnector;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class DeploymentSettingsTests
{
    private static IConfiguration Configuration(string? deployment, bool topup, string? stripeKey = null) =>
        new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Deployment:Environment"] = deployment,
            ["Credits:EnableDemoTopup"] = topup.ToString(),
            ["Stripe:SecretKey"] = stripeKey
        }).Build();

    [Theory]
    [InlineData("Production", null, true, false)]
    [InlineData("Production", "production", true, false)]
    [InlineData("Production", "prod", true, false)]
    [InlineData("Production", "staging", true, false)]
    [InlineData("Production", "test", false, false)]
    [InlineData("Production", "test", true, true)]
    [InlineData("Production", " TEST ", true, true)]
    [InlineData("Development", null, true, true)]
    [InlineData("Development", null, false, false)]
    public void FreeCreditsRequireTheExplicitServerSideDeploymentAndEnableFlag(
        string host, string? deployment, bool topup, bool expected)
    {
        var result = DeploymentSettings.From(Configuration(deployment, topup), host);
        Assert.Equal(expected, result.AllowDemoTopup);
    }

    [Fact]
    public void HostedTestUsesProductionHostingButLabelsItsCreditsAsNonPayment()
    {
        var result = DeploymentSettings.From(Configuration("test", true), "Production");
        Assert.Equal("test", result.Name);
        Assert.True(result.IsTest);
        Assert.Equal("Tesztkredit-feltöltés – valódi fizetés nélkül", result.TopupDescription);
        var production = DeploymentSettings.From(Configuration(null, true), "Production");
        Assert.Equal("production", production.Name);
        Assert.False(production.IsTest);
        Assert.False(production.AllowDemoTopup);
    }

    [Theory]
    [InlineData("sk_live_this-must-not-appear-in-an-error")]
    [InlineData("rk_live_this-must-not-appear-in-an-error")]
    public void TestDeploymentRejectsRealMoneyStripeKeysWithoutDisclosingThem(string key)
    {
        var error = Assert.Throws<InvalidOperationException>(() =>
            DeploymentSettings.From(Configuration("test", true, key), "Production"));
        Assert.DoesNotContain(key, error.Message);
        Assert.Contains("Live Stripe keys", error.Message);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("sk_test_placeholder")]
    [InlineData("rk_test_placeholder")]
    public void TestDeploymentAcceptsNoPaymentSetupOrStripeTestKeys(string? key)
    {
        Assert.True(DeploymentSettings.From(Configuration("test", true, key), "Production").AllowDemoTopup);
    }

    [Fact]
    public void CloudSqlConnectionStringAcceptsItsLocalUnixSocketAndBoundedPool()
    {
        const string socket = "/cloudsql/project-id:europe-west1:otthonra-mysql-dev";
        var builder = new MySqlConnectionStringBuilder(
            $"Server={socket};ConnectionProtocol=Unix;Database=otthonra_dev;User ID=otthonra_dev;Password=placeholder;SslMode=None;MaximumPoolSize=10;ConnectionTimeout=15");
        Assert.Equal(socket, builder.Server);
        Assert.Equal(10u, builder.MaximumPoolSize);
        Assert.Equal(15u, builder.ConnectionTimeout);
        Assert.Equal(MySqlSslMode.None, builder.SslMode);
        // Building the options must not open a database connection.
        using var connection = new MySqlConnection(builder.ConnectionString);
        Assert.Equal(System.Data.ConnectionState.Closed, connection.State);
    }
}
