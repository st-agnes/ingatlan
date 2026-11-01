using System.Data;
using System.Globalization;
using System.Net.Http.Headers;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Otthonra.Api;

// Orders are server-priced and credited only after an authenticated Stripe event.
public sealed class PaymentOrder
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public int Credits { get; set; }
    public long AmountMinor { get; set; }
    public string Currency { get; set; } = "huf";
    public string? StripeSessionId { get; set; }
    public string Status { get; set; } = "pending";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? CreditedAt { get; set; }
}
public record CheckoutInput(int Amount);

public static class Payments
{
    private const long MaximumWebhookBytes = 256 * 1024;
    // HUF card charges use two decimal minor units in Stripe, unlike HUF payouts.
    private static readonly IReadOnlyDictionary<int, long> Packages = new Dictionary<int, long>
    {
        [20] = 199_000, [60] = 499_000, [150] = 999_000
    };

    public static void Configure(ModelBuilder b)
    {
        b.Entity<PaymentOrder>().ToTable("PaymentOrders");
        b.Entity<PaymentOrder>().HasIndex(x => x.StripeSessionId).IsUnique();
        b.Entity<PaymentOrder>().HasIndex(x => new { x.UserId, x.CreatedAt });
        b.Entity<PaymentOrder>().HasOne<User>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
    }

    public static void MapPayments(this WebApplication app)
    {
        app.MapPost("/api/credits/checkout", async Task<IResult> (CheckoutInput input, ClaimsPrincipal principal, AppDb db, IConfiguration config, IHttpClientFactory clients, CancellationToken cancellationToken) =>
        {
            if (!Packages.TryGetValue(input.Amount, out var price)) throw new ApiException(400, "Válassz 20, 60 vagy 150 kredites csomagot.");
            var secret = config["Stripe:SecretKey"];
            var success = config["Stripe:SuccessUrl"];
            var cancel = config["Stripe:CancelUrl"];
            if (string.IsNullOrWhiteSpace(secret) || !ReturnUrl(success, app.Environment.IsDevelopment()) || !ReturnUrl(cancel, app.Environment.IsDevelopment()))
                throw new ApiException(503, "A bankkártyás fizetés még nincs beállítva. Kérjük, próbáld később.");
            var userId = principal.UserId();
            if (!await db.Users.AnyAsync(u => u.Id == userId, cancellationToken)) throw new ApiException(401, "A fiók nem található.");
            var order = new PaymentOrder { UserId = userId, Credits = input.Amount, AmountMinor = price };
            db.Set<PaymentOrder>().Add(order);
            await db.SaveChangesAsync(cancellationToken);
            using var request = new HttpRequestMessage(HttpMethod.Post, "https://api.stripe.com/v1/checkout/sessions");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", secret);
            request.Headers.Add("Idempotency-Key", "otthonra-order-" + order.Id.ToString("N"));
            request.Content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                ["mode"] = "payment",
                ["payment_method_types[0]"] = "card",
                ["success_url"] = success!,
                ["cancel_url"] = cancel!,
                ["client_reference_id"] = order.Id.ToString(),
                ["metadata[orderId]"] = order.Id.ToString(),
                ["metadata[userId]"] = userId.ToString(),
                ["line_items[0][quantity]"] = "1",
                ["line_items[0][price_data][currency]"] = "huf",
                ["line_items[0][price_data][unit_amount]"] = price.ToString(CultureInfo.InvariantCulture),
                ["line_items[0][price_data][product_data][name]"] = $"Otthonra – {input.Amount} kredit"
            });
            HttpResponseMessage response;
            try { response = await clients.CreateClient("stripe").SendAsync(request, cancellationToken); }
            catch (HttpRequestException) { throw new ApiException(502, "A fizetési szolgáltató jelenleg nem érhető el. Próbáld később."); }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested) { throw new ApiException(502, "A fizetési szolgáltató nem válaszolt időben. Próbáld később."); }
            using (response)
            {
                if (!response.IsSuccessStatusCode) throw new ApiException(502, "A fizetési szolgáltató nem tudta elindítani a vásárlást. Próbáld később.");
                using var result = ParseStripeResponse(await response.Content.ReadAsStringAsync(cancellationToken));
                var session = result.RootElement;
                var sessionId = String(session, "id");
                var url = String(session, "url");
                if (string.IsNullOrWhiteSpace(sessionId) || !Uri.TryCreate(url, UriKind.Absolute, out var checkoutUri) || checkoutUri.Scheme != "https" || checkoutUri.Host != "checkout.stripe.com")
                    throw new ApiException(502, "A fizetési szolgáltató érvénytelen választ küldött.");
                order.StripeSessionId = sessionId;
                await db.SaveChangesAsync(cancellationToken);
                return Results.Ok(new { orderId = order.Id, checkoutUrl = url });
            }
        }).RequireAuthorization();

        app.MapPost("/api/payments/stripe/webhook", async Task<IResult> (HttpRequest request, AppDb db, IConfiguration config, CancellationToken cancellationToken) =>
        {
            var webhookSecret = config["Stripe:WebhookSecret"];
            if (string.IsNullOrWhiteSpace(webhookSecret)) throw new ApiException(503, "A fizetési webhook nincs beállítva.");
            if (request.ContentLength > MaximumWebhookBytes) return Results.StatusCode(413);
            await using var buffer = new MemoryStream();
            var chunk = new byte[8192];
            int read;
            while ((read = await request.Body.ReadAsync(chunk.AsMemory(), cancellationToken)) > 0)
            {
                if (buffer.Length + read > MaximumWebhookBytes) return Results.StatusCode(413);
                await buffer.WriteAsync(chunk.AsMemory(0, read), cancellationToken);
            }
            var raw = buffer.ToArray();
            if (!VerifySignature(raw, request.Headers["Stripe-Signature"].ToString(), webhookSecret, DateTimeOffset.UtcNow))
                return Results.BadRequest(new { message = "Érvénytelen fizetési aláírás." });
            JsonDocument document;
            try { document = JsonDocument.Parse(raw); }
            catch (JsonException) { return Results.BadRequest(new { message = "Érvénytelen JSON." }); }
            using (document)
            {
                var evt = document.RootElement;
                var eventType = String(evt, "type");
                if (eventType is not ("checkout.session.completed" or "checkout.session.async_payment_succeeded")) return Results.Ok(new { received = true });
                if (!evt.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Object || !data.TryGetProperty("object", out var session)) return Results.BadRequest();
                if (String(session, "payment_status") != "paid") return Results.Ok(new { received = true });
                if (!session.TryGetProperty("metadata", out var metadata) || metadata.ValueKind != JsonValueKind.Object || !Guid.TryParse(String(metadata, "orderId"), out var orderId)) return Results.Ok(new { received = true });
                var sessionId = String(session, "id");
                if (string.IsNullOrWhiteSpace(sessionId)) return Results.BadRequest();
                await using var tx = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
                var order = (await db.Set<PaymentOrder>().FromSqlInterpolated($"SELECT * FROM `PaymentOrders` WHERE `Id` = {orderId} FOR UPDATE").ToListAsync(cancellationToken)).SingleOrDefault();
                if (order is null) return Results.BadRequest(new { message = "Ismeretlen fizetési rendelés." });
                if ((order.StripeSessionId is not null && order.StripeSessionId != sessionId) || String(session, "client_reference_id") != order.Id.ToString() || String(metadata, "userId") != order.UserId.ToString() || String(session, "currency") != order.Currency || !session.TryGetProperty("amount_total", out var amount) || amount.ValueKind != JsonValueKind.Number || !amount.TryGetInt64(out var paidAmount) || paidAmount != order.AmountMinor)
                    return Results.BadRequest(new { message = "A fizetési rendelés adatai nem egyeznek." });
                if (order.Status == "credited") { await tx.CommitAsync(cancellationToken); return Results.Ok(new { received = true }); }
                var user = (await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {order.UserId} FOR UPDATE").ToListAsync(cancellationToken)).SingleOrDefault();
                if (user is null) throw new ApiException(409, "A fizető fiókja nem található.");
                if (user.Credits > int.MaxValue - order.Credits) throw new ApiException(409, "A kreditegyenleg elérte a felső korlátot.");
                user.Credits += order.Credits;
                order.StripeSessionId = sessionId;
                order.Status = "credited";
                order.CreditedAt = DateTime.UtcNow;
                // Reusing order ID as ledger ID gives a second uniqueness barrier.
                db.CreditEntries.Add(new CreditEntry { Id = order.Id, UserId = user.Id, Amount = order.Credits, Description = $"Bankkártyás vásárlás – {order.Credits} kredit" });
                await db.SaveChangesAsync(cancellationToken);
                await tx.CommitAsync(cancellationToken);
                return Results.Ok(new { received = true });
            }
        });
    }

    public static bool VerifySignature(byte[] body, string header, string secret, DateTimeOffset now)
    {
        var fields = header.Split(',').Select(p => p.Split('=', 2)).Where(p => p.Length == 2).ToArray();
        var timestamp = fields.FirstOrDefault(p => p[0] == "t")?[1];
        var current = now.ToUnixTimeSeconds();
        if (!long.TryParse(timestamp, NumberStyles.None, CultureInfo.InvariantCulture, out var seconds) || seconds < current - 300 || seconds > current + 300) return false;
        var prefix = Encoding.UTF8.GetBytes(timestamp + ".");
        var signed = new byte[prefix.Length + body.Length];
        prefix.CopyTo(signed, 0); body.CopyTo(signed, prefix.Length);
        var expected = HMACSHA256.HashData(Encoding.UTF8.GetBytes(secret), signed);
        foreach (var candidate in fields.Where(p => p[0] == "v1"))
        {
            try { if (CryptographicOperations.FixedTimeEquals(expected, Convert.FromHexString(candidate[1]))) return true; }
            catch (FormatException) { }
        }
        return false;
    }
    private static JsonDocument ParseStripeResponse(string body)
    {
        try { return JsonDocument.Parse(body); }
        catch (JsonException) { throw new ApiException(502, "A fizetési szolgáltató érvénytelen választ küldött."); }
    }
    private static string? String(JsonElement value, string name) => value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out var p) && p.ValueKind == JsonValueKind.String ? p.GetString() : null;
    private static bool ReturnUrl(string? value, bool development) => Uri.TryCreate(value, UriKind.Absolute, out var uri) && (uri.Scheme == "https" || development && uri.Scheme == "http" && uri.IsLoopback) && string.IsNullOrEmpty(uri.UserInfo);
}
