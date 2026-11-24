using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>
/// A browser draft keeps one owner-scoped creation key across reloads and tabs.
/// The owner lock covers lookup, external geocoding and the atomic entity/index
/// write. Legacy clients without a key keep independent creation requests.
/// </summary>
public static class EntityCreation
{
    public static Task<EntityCreationAttempt> BeginAsync(AppDb db, Guid ownerId, PropertyInput input,
        CancellationToken cancellationToken = default)
        => BeginAsync(db, ownerId, input.CreationRequestId,
            input.CreationRequestId.HasValue ? RequestHash(input) : null, cancellationToken);

    public static Task<EntityCreationAttempt> BeginAsync(AppDb db, Guid ownerId, SearchInput input,
        CancellationToken cancellationToken = default)
        => BeginAsync(db, ownerId, input.CreationRequestId,
            input.CreationRequestId.HasValue ? RequestHash(input) : null, cancellationToken);

    private static async Task<EntityCreationAttempt> BeginAsync(AppDb db, Guid ownerId, Guid? requestId,
        string? requestHash, CancellationToken cancellationToken)
    {
        ValidateRequestId(requestId);
        IDbContextTransaction? transaction = null;
        try
        {
            User? owner;
            if (requestId.HasValue)
            {
                transaction = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, cancellationToken);
                // Enumerate the locking query directly: composing it into a
                // subquery can change MySQL's row-lock semantics.
                owner = (await db.Users.FromSqlInterpolated(
                    $"SELECT * FROM `Users` WHERE `Id` = {ownerId} FOR UPDATE")
                    .ToListAsync(cancellationToken)).SingleOrDefault();
            }
            else owner = await db.Users.SingleOrDefaultAsync(user => user.Id == ownerId, cancellationToken);
            if (owner is null) throw new ApiException(401, "A fiók nem található.");
            return new EntityCreationAttempt(owner, requestId, requestHash, transaction);
        }
        catch
        {
            if (transaction is not null) await transaction.DisposeAsync();
            throw;
        }
    }

    public static void ValidateRequestId(Guid? requestId)
    {
        if (requestId == Guid.Empty) throw new ApiException(400, "Érvénytelen létrehozási azonosító.");
    }

    public static void VerifyReplay(string? previousHash, string? requestHash)
    {
        if (previousHash is null || requestHash is null || !string.Equals(previousHash, requestHash, StringComparison.Ordinal))
            throw new ApiException(409, "Ezt a létrehozási azonosítót már más adatokkal használtad. Frissítsd az oldalt.");
    }

    public static void VerifyPropertyReplay(Property previous, PropertyInput input, string? requestHash)
    {
        if (previous.CreationRequestHash == requestHash && requestHash is not null) return;
        // Prior typed inputs treated a missing balcony as false. Only receipts
        // written by that format may use this fallback; new null/false requests
        // remain distinct, even after a restart or a client upgrade.
        if (previous.CreationRequestHashVersion == 1 && input.Balcony is null
            && previous.CreationRequestHash == RequestHash(input with { Balcony = false })) return;
        VerifyReplay(previous.CreationRequestHash, requestHash);
    }

    public static string RequestHash(PropertyInput input) => Hash(input with { CreationRequestId = null });
    public static string RequestHash(SearchInput input) => Hash(input with { CreationRequestId = null });

    private static string Hash<T>(T input)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
            WriteCanonical(writer, JsonSerializer.SerializeToElement(input));
        return Convert.ToHexString(SHA256.HashData(stream.ToArray()));
    }

    private static void WriteCanonical(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonical(writer, property.Value);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray()) WriteCanonical(writer, item);
                writer.WriteEndArray();
                break;
            case JsonValueKind.Number:
                // JSON 75, 75.0 and 7.5e1 are the same typed decimal input.
                writer.WriteRawValue(value.GetDecimal().ToString("G29", CultureInfo.InvariantCulture));
                break;
            default:
                value.WriteTo(writer);
                break;
        }
    }
}

public sealed class EntityCreationAttempt(User owner, Guid? requestId, string? requestHash,
    IDbContextTransaction? transaction) : IAsyncDisposable
{
    public User Owner { get; } = owner;
    public Guid? RequestId { get; } = requestId;
    public string? RequestHash { get; } = requestHash;
    public Task CommitAsync(CancellationToken cancellationToken = default)
        => transaction?.CommitAsync(cancellationToken) ?? Task.CompletedTask;
    public ValueTask DisposeAsync() => transaction?.DisposeAsync() ?? ValueTask.CompletedTask;
}
