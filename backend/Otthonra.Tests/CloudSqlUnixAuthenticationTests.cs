using System.Net;
using System.Net.Sockets;
using MySqlConnector;
using Xunit;

namespace Otthonra.Tests;

public sealed class MySqlCachingSha2FactAttribute : FactAttribute
{
    public MySqlCachingSha2FactAttribute()
    {
        if (!OperatingSystem.IsLinux()
            || Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_CACHING_SHA2") != "true")
            Skip = "Requires the disposable CI MySQL caching_sha2_password account on Linux.";
    }
}

public class CloudSqlUnixAuthenticationTests
{
    [MySqlCachingSha2Fact]
    public async Task FreshCachingSha2AuthenticationOverTheProxyUnixSocketRequiresPublicKeyRetrieval()
    {
        // A Cloud SQL proxy accepts a local Unix socket but forwards the MySQL
        // wire protocol over a remote connection. Use a local TCP upstream here:
        // native mysqld Unix sockets follow a different, server-secure auth path.
        var socketPath = Path.Combine(Path.GetTempPath(), $"otthonra-mysql-{Guid.NewGuid():N}.sock");
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        using var listener = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        listener.Bind(new UnixDomainSocketEndPoint(socketPath));
        File.SetUnixFileMode(socketPath, UnixFileMode.UserRead | UnixFileMode.UserWrite);
        listener.Listen(2);
        var relays = new List<Task>();
        try
        {
            var settings = new MySqlConnectionStringBuilder
            {
                Server = socketPath,
                ConnectionProtocol = MySqlConnectionProtocol.UnixSocket,
                Database = "otthonra_ci",
                UserID = Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_USER")!,
                Password = Environment.GetEnvironmentVariable("OTTHONRA_TEST_MYSQL_PASSWORD")!,
                SslMode = MySqlSslMode.None,
                Pooling = false,
                ConnectionTimeout = 5
            };
            Assert.False(settings.AllowPublicKeyRetrieval);
            relays.Add(RelayOneConnectionAsync(listener, deadline.Token));
            await using (var legacy = new MySqlConnection(settings.ConnectionString))
            {
                var failure = await Assert.ThrowsAsync<MySqlException>(() => legacy.OpenAsync(deadline.Token));
                Assert.Contains("AllowPublicKeyRetrieval=True", failure.Message);
            }
            await relays[^1].WaitAsync(deadline.Token);

            // The failed attempt never sent the password, so this is still full
            // authentication for the fresh account, not a warmed fast-auth cache.
            settings.AllowPublicKeyRetrieval = true;
            relays.Add(RelayOneConnectionAsync(listener, deadline.Token));
            await using (var corrected = new MySqlConnection(settings.ConnectionString))
            {
                await corrected.OpenAsync(deadline.Token);
                await using var command = new MySqlCommand("SELECT 1", corrected);
                Assert.Equal(1, Convert.ToInt32(await command.ExecuteScalarAsync(deadline.Token)));
            }
            await relays[^1].WaitAsync(deadline.Token);
        }
        finally
        {
            await deadline.CancelAsync();
            listener.Dispose();
            try { await Task.WhenAll(relays); } catch { /* Preserve the test's primary failure. */ }
            File.Delete(socketPath);
        }
    }

    private static async Task RelayOneConnectionAsync(Socket listener, CancellationToken cancellationToken)
    {
        using var local = await listener.AcceptAsync(cancellationToken);
        using var upstream = new TcpClient();
        await upstream.ConnectAsync(IPAddress.Loopback, 3306, cancellationToken);
        using var localStream = new NetworkStream(local, ownsSocket: false);
        using var upstreamStream = upstream.GetStream();
        var uploads = localStream.CopyToAsync(upstreamStream, cancellationToken);
        var downloads = upstreamStream.CopyToAsync(localStream, cancellationToken);
        await Task.WhenAny(uploads, downloads);
        try { local.Shutdown(SocketShutdown.Both); } catch (SocketException) { }
        upstream.Close();
        try { await Task.WhenAll(uploads, downloads); }
        catch (IOException) { }
        catch (ObjectDisposedException) { }
        catch (SocketException) { }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { }
    }
}
