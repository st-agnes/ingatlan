using System.IO.Compression;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.ResponseCompression;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class ApiResponseCompressionTests
{
    [Theory]
    [InlineData("GET", "/api/me/entities", true)]
    [InlineData("GET", "/api/public/landing", true)]
    [InlineData("GET", "/api/listings/property/key/context", true)]
    [InlineData("GET", "/api/auth/login", false)]
    [InlineData("POST", "/api/auth/login", false)]
    [InlineData("POST", "/api/auth/register", false)]
    [InlineData("POST", "/api/decisions", false)]
    [InlineData("PUT", "/api/me", false)]
    [InlineData("HEAD", "/api/me", false)]
    [InlineData("GET", "/internal/refunds/run", false)]
    [InlineData("GET", "/apiary/image.jpg", false)]
    [InlineData("GET", "/assets/photo.jpg", false)]
    public void OnlyApiReadsAreEligibleAndCredentialExchangesStayOutside(string method, string path, bool expected)
    {
        var context = new DefaultHttpContext(); context.Request.Method = method; context.Request.Path = path;
        Assert.Equal(expected, ApiResponseCompression.IsEligible(context));
    }

    [Fact]
    public void JsonReadsUseFastStreamingNegotiatedBrotliAndGzipAlsoOnHttps()
    {
        using var provider = new ServiceCollection().AddApiResponseCompression().BuildServiceProvider();
        var options = provider.GetRequiredService<IOptions<ResponseCompressionOptions>>().Value;
        Assert.True(options.EnableForHttps);
        Assert.Equal(new[] { "application/json", "application/problem+json", "application/geo+json" }, options.MimeTypes);
        Assert.Equal(CompressionLevel.Fastest, provider.GetRequiredService<IOptions<BrotliCompressionProviderOptions>>().Value.Level);
        Assert.Equal(CompressionLevel.Fastest, provider.GetRequiredService<IOptions<GzipCompressionProviderOptions>>().Value.Level);
    }
}
