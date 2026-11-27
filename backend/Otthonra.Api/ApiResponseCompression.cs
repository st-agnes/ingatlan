using System.IO.Compression;
using Microsoft.AspNetCore.ResponseCompression;

namespace Otthonra.Api;

/// <summary>Stream JSON read responses efficiently, without compressing credential exchanges.</summary>
public static class ApiResponseCompression
{
    public static IServiceCollection AddApiResponseCompression(this IServiceCollection services)
    {
        services.AddResponseCompression(options => {
            options.EnableForHttps = true;
            options.MimeTypes = ["application/json", "application/problem+json", "application/geo+json"];
            options.Providers.Add<BrotliCompressionProvider>();
            options.Providers.Add<GzipCompressionProvider>();
        });
        services.Configure<BrotliCompressionProviderOptions>(options => options.Level = CompressionLevel.Fastest);
        services.Configure<GzipCompressionProviderOptions>(options => options.Level = CompressionLevel.Fastest);
        return services;
    }

    public static bool IsEligible(HttpContext context) => HttpMethods.IsGet(context.Request.Method)
        && context.Request.Path.StartsWithSegments("/api")
        && !context.Request.Path.StartsWithSegments("/api/auth");
}
