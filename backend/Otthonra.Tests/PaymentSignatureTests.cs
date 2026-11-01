using System.Security.Cryptography;
using System.Text;
using Otthonra.Api;
using Xunit;

public class PaymentSignatureTests
{
    private static string Sign(byte[] body, string secret, long timestamp)
    {
        var prefix = Encoding.UTF8.GetBytes(timestamp + ".");
        var data = prefix.Concat(body).ToArray();
        return $"t={timestamp},v1={Convert.ToHexString(HMACSHA256.HashData(Encoding.UTF8.GetBytes(secret), data)).ToLowerInvariant()}";
    }
    [Fact]
    public void AcceptsValidSignatureAndRotatedSigningKeyCandidate()
    {
        var now = DateTimeOffset.FromUnixTimeSeconds(1_800_000_000);
        var body = Encoding.UTF8.GetBytes("{\"type\":\"checkout.session.completed\"}");
        var header = Sign(body, "webhook-test-secret", now.ToUnixTimeSeconds()) + ",v1=abcd";
        Assert.True(Payments.VerifySignature(body, header, "webhook-test-secret", now));
    }
    [Fact]
    public void RejectsBodyTamperingWrongSecretExpiredAndFutureEvents()
    {
        var now = DateTimeOffset.FromUnixTimeSeconds(1_800_000_000);
        var body = Encoding.UTF8.GetBytes("{\"amount\":199000}");
        var header = Sign(body, "webhook-test-secret", now.ToUnixTimeSeconds());
        Assert.False(Payments.VerifySignature(Encoding.UTF8.GetBytes("{\"amount\":1}"), header, "webhook-test-secret", now));
        Assert.False(Payments.VerifySignature(body, header, "different-secret", now));
        Assert.False(Payments.VerifySignature(body, header, "webhook-test-secret", now.AddSeconds(301)));
        Assert.False(Payments.VerifySignature(body, header, "webhook-test-secret", now.AddSeconds(-301)));
        Assert.False(Payments.VerifySignature(body, "t=not-a-number,v1=invalid", "webhook-test-secret", now));
    }
}
