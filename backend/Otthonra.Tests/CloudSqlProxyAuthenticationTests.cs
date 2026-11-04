using MySqlConnector;
using Xunit;

namespace Otthonra.Tests;

public sealed class MySqlCachingSha2FactAttribute : FactAttribute
{
    public MySqlCachingSha2FactAttribute()
    {
        if (Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_CACHING_SHA2") != "true")
            Skip = "Requires the disposable CI MySQL caching_sha2_password account.";
    }
}

public class CloudSqlProxyAuthenticationTests
{
    [MySqlCachingSha2Fact]
    public async Task FreshCachingSha2AuthenticationOverLoopbackTcpRequiresPublicKeyRetrieval()
    {
        // The controlled Cloud SQL Auth Proxy presents a local TCP endpoint.
        // Test the driver's corresponding full-authentication path against a
        // fresh MySQL account; this does not emulate Google's managed proxy.
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        var password = Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_PASSWORD")!;
        var settings = new MySqlConnectionStringBuilder
        {
            Server = "127.0.0.1",
            Port = 3306,
            ConnectionProtocol = MySqlConnectionProtocol.Sockets,
            Database = "otthonra_ci",
            UserID = Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_USER")!,
            Password = password,
            SslMode = MySqlSslMode.None,
            Pooling = false,
            ConnectionTimeout = 5
        };
        Assert.False(settings.AllowPublicKeyRetrieval);
        await using (var legacy = new MySqlConnection(settings.ConnectionString))
        {
            var failure = await Assert.ThrowsAsync<MySqlException>(() => legacy.OpenAsync(deadline.Token));
            Assert.Contains("AllowPublicKeyRetrieval=True", failure.Message);
            Assert.DoesNotContain(password, failure.Message);
        }

        // The failed attempt never sent the password, so this is still full
        // authentication for the fresh account, not a warmed fast-auth cache.
        settings.AllowPublicKeyRetrieval = true;
        await using var corrected = new MySqlConnection(settings.ConnectionString);
        await corrected.OpenAsync(deadline.Token);
        await using var command = new MySqlCommand("SELECT 1", corrected);
        Assert.Equal(1, Convert.ToInt32(await command.ExecuteScalarAsync(deadline.Token)));
    }
}
