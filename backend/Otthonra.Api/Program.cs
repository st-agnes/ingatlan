using System.Data;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Otthonra.Api;

var builder = WebApplication.CreateBuilder(args);
var development = builder.Environment.IsDevelopment();
var deployment = DeploymentSettings.From(builder.Configuration, builder.Environment.EnvironmentName);
var connection = builder.Configuration.GetConnectionString("MySql") ?? (development ? "Server=localhost;Port=3306;Database=otthonra;User=otthonra;Password=local-only-change-me" : throw new InvalidOperationException("ConnectionStrings__MySql is required."));
var signingKey = builder.Configuration["Jwt:Key"] ?? (development ? "otthonra-development-only-signing-key-change-before-production" : "");
if (signingKey.Length < 32 || (!development && signingKey.Contains("development-only"))) throw new InvalidOperationException("Jwt__Key must be a private random key of at least 32 characters.");
const string issuer = "otthonra-api";
builder.Services.AddDbContext<AppDb>(o => o.UseMySql(connection, new MySqlServerVersion(new Version(8, 0, 36))));
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(o => o.TokenValidationParameters = new TokenValidationParameters
{
    ValidateIssuerSigningKey = true, IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(signingKey)),
    ValidateIssuer = true, ValidIssuer = issuer, ValidateAudience = true, ValidAudience = "otthonra-clients", ValidateLifetime = true, ClockSkew = TimeSpan.FromSeconds(30)
});
builder.Services.AddAuthorization();
builder.Services.AddHttpClient("stripe", c => c.Timeout = TimeSpan.FromSeconds(20));
var origins = builder.Configuration.GetSection("Cors:Origins").Get<string[]>() ?? [];
builder.Services.AddCors(o => o.AddDefaultPolicy(p => { if (origins.Length > 0) p.WithOrigins(origins).AllowAnyHeader().AllowAnyMethod(); else if (development) p.WithOrigins("http://localhost:8080", "http://localhost:5173").AllowAnyHeader().AllowAnyMethod(); }));
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = 429;
    o.AddPolicy("auth", context => RateLimitPartition.GetFixedWindowLimiter(context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions { PermitLimit = 10, Window = TimeSpan.FromMinutes(1), QueueLimit = 0 }));
});
var app = builder.Build();
app.Use(async (context, next) =>
{
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    context.Response.Headers["Cache-Control"] = "no-store";
    try { await next(); }
    catch (ApiException e) { context.Response.StatusCode = e.Status; await context.Response.WriteAsJsonAsync(new { message = e.Message }); }
    catch (DbUpdateException e) { app.Logger.LogWarning(e, "Database write rejected"); context.Response.StatusCode = 409; await context.Response.WriteAsJsonAsync(new { message = "Az adat közben megváltozott, vagy már létezik. Frissítsd az oldalt, és próbáld újra." }); }
});
app.UseCors();
app.UseRateLimiter();
app.UseAuthentication();
app.UseAuthorization();

// Initial empty databases can be provisioned explicitly. Never seed user data in production.
if (builder.Configuration.GetValue<bool>("Database:Initialize"))
{
    await using var scope = app.Services.CreateAsyncScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDb>();
    await db.Database.EnsureCreatedAsync();
    await SchemaUpgrade.ApplyAsync(db);
    if (development && builder.Configuration.GetValue<bool>("Database:SeedDemo")) await Seed.Run(db);
}
app.MapGet("/api/locations", (string? q, int? limit) => Results.Ok(new { items = LocationCatalog.Search(q, limit ?? 8) }));
app.MapGet("/api/health", async Task<IResult> (AppDb db) => await db.Database.CanConnectAsync()
    ? Results.Ok(new { status = "ready", deployment = deployment.Name, testCreditsEnabled = deployment.AllowDemoTopup })
    : Results.Json(new { status = "database-unavailable", deployment = deployment.Name, testCreditsEnabled = deployment.AllowDemoTopup }, statusCode: 503));

object Session(User user)
{
    var token = new JwtSecurityToken(issuer, "otthonra-clients", [new Claim(ClaimTypes.NameIdentifier, user.Id.ToString())], expires: DateTime.UtcNow.AddHours(12), signingCredentials: new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(signingKey)), SecurityAlgorithms.HmacSha256));
    return new { accessToken = new JwtSecurityTokenHandler().WriteToken(token), expiresIn = 43200, user = Dto.Profile(user) };
}
var auth = app.MapGroup("/api/auth").RequireRateLimiting("auth");
auth.MapPost("/register", async (RegisterInput input, AppDb db) =>
{
    Rules.Password(input.Password);
    var email = Rules.Email(input.Email);
    if (await db.Users.AnyAsync(x => x.Email == email)) throw new ApiException(409, "Ezzel az e-mail-címmel már létezik fiók.");
    var user = new User { Name = Rules.Required(input.Name, "név", 100), Email = email, Phone = Rules.Optional(input.Phone, 40), PasswordHash = Passwords.Hash(input.Password) };
    db.Users.Add(user); await db.SaveChangesAsync(); return Results.Ok(Session(user));
});
auth.MapPost("/login", async (LoginInput input, AppDb db) =>
{
    var email = Rules.Email(input.Email);
    if (input.Password is null || input.Password.Length > 128) throw new ApiException(401, "Hibás e-mail-cím vagy jelszó.");
    var user = await db.Users.SingleOrDefaultAsync(x => x.Email == email);
    if (user is null || !Passwords.Verify(input.Password, user.PasswordHash)) throw new ApiException(401, "Hibás e-mail-cím vagy jelszó.");
    return Results.Ok(Session(user));
});
var api = app.MapGroup("/api").RequireAuthorization();
api.MapGet("/me", async (AppDb db, ClaimsPrincipal principal) => Results.Ok(Dto.Profile(await CurrentUser(db, principal))));
api.MapPut("/me", async (ProfileInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var user = await CurrentUser(db, principal); var email = Rules.Email(input.Email);
    if (await db.Users.AnyAsync(x => x.Id != user.Id && x.Email == email)) throw new ApiException(409, "Ez az e-mail-cím már foglalt.");
    user.Name = Rules.Required(input.Name, "név", 100); user.Email = email; user.Phone = Rules.Optional(input.Phone, 40);
    await db.SaveChangesAsync(); return Results.Ok(Dto.Profile(user));
});
api.MapGet("/me/entities", async (AppDb db, ClaimsPrincipal principal) =>
{
    var user = await CurrentUser(db, principal);
    var properties = await db.Properties.AsNoTracking().Where(x => x.OwnerId == user.Id && !x.Archived).OrderByDescending(x => x.CreatedAt).ToListAsync();
    var searches = await db.SearchRequests.AsNoTracking().Where(x => x.OwnerId == user.Id && !x.Archived).OrderByDescending(x => x.CreatedAt).ToListAsync();
    var decisionRows = await (from d in db.Decisions.AsNoTracking()
        join p in db.Properties.AsNoTracking() on d.PropertyId equals p.Id
        join s in db.SearchRequests.AsNoTracking() on d.SearchRequestId equals s.Id
        where d.ActorUserId == user.Id
        orderby d.CreatedAt descending
        select new { Decision = d, Property = p, Search = s }).ToListAsync();
    var decisions = decisionRows.Select(row => new {
        row.Decision.Id, row.Decision.ActorKind,
        actorId = row.Decision.ActorKind == "property" ? row.Decision.PropertyId : row.Decision.SearchRequestId,
        row.Decision.PropertyId, searchId = row.Decision.SearchRequestId, row.Decision.SearchRequestId,
        row.Decision.Liked, row.Decision.CreatedAt,
        property = Dto.Property(row.Property), search = Dto.Search(row.Search)
    });
    return Results.Ok(new { properties = properties.Select(p => Dto.Property(p, true)), searchRequests = searches.Select(Dto.Search), decisions, active = user.ActiveKind is null ? null : new { kind = user.ActiveKind, id = user.ActiveEntityId } });
});
api.MapPut("/me/active", async (ActiveInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var user = await CurrentUser(db, principal); var kind = input.Kind?.ToLowerInvariant();
    var owned = kind == "property" ? await db.Properties.AnyAsync(x => x.Id == input.Id && x.OwnerId == user.Id && !x.Archived) : kind == "search" && await db.SearchRequests.AnyAsync(x => x.Id == input.Id && x.OwnerId == user.Id && !x.Archived);
    if (!owned) throw new ApiException(404, "Az entitás nem található vagy nem aktiválható.");
    user.ActiveKind = kind; user.ActiveEntityId = input.Id; await db.SaveChangesAsync(); return Results.Ok(new { kind, id = input.Id });
});
api.MapGet("/properties", async (AppDb db, ClaimsPrincipal principal) => { var uid = principal.UserId(); var items = await db.Properties.AsNoTracking().Where(x => x.OwnerId == uid && !x.Archived).ToListAsync(); return Results.Ok(items.Select(p => Dto.Property(p, true))); });
api.MapPost("/properties", async (PropertyInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var p = new Property { OwnerId = principal.UserId() }; Rules.Apply(p, input); db.Properties.Add(p); await db.SaveChangesAsync(); return Results.Created($"/api/properties/{p.Id}", Dto.Property(p, true));
});
api.MapPut("/properties/{id:guid}", async (Guid id, PropertyInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId(); var p = await db.Properties.SingleOrDefaultAsync(x => x.Id == id && x.OwnerId == uid && !x.Archived) ?? throw new ApiException(404, "Az ingatlan nem található.");
    Rules.Apply(p, input); await ClearArchivedActive(db, uid, p.Id, p.Archived); await db.SaveChangesAsync(); return Results.Ok(Dto.Property(p, true));
});
api.MapDelete("/properties/{id:guid}", async (Guid id, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId(); var p = await db.Properties.SingleOrDefaultAsync(x => x.Id == id && x.OwnerId == uid) ?? throw new ApiException(404, "Az ingatlan nem található.");
    p.Archived = true; await ClearArchivedActive(db, uid, id, true); await db.SaveChangesAsync(); return Results.NoContent();
});
api.MapGet("/searches", async (AppDb db, ClaimsPrincipal principal) => { var uid = principal.UserId(); var items = await db.SearchRequests.AsNoTracking().Where(x => x.OwnerId == uid && !x.Archived).ToListAsync(); return Results.Ok(items.Select(Dto.Search)); });
api.MapPost("/searches", async (SearchInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var s = new SearchRequest { OwnerId = principal.UserId() }; Rules.Apply(s, input); db.SearchRequests.Add(s); await db.SaveChangesAsync(); return Results.Created($"/api/searches/{s.Id}", Dto.Search(s));
});
api.MapPut("/searches/{id:guid}", async (Guid id, SearchInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId(); var s = await db.SearchRequests.SingleOrDefaultAsync(x => x.Id == id && x.OwnerId == uid && !x.Archived) ?? throw new ApiException(404, "A keresési igény nem található.");
    Rules.Apply(s, input); await ClearArchivedActive(db, uid, id, s.Archived); await db.SaveChangesAsync(); return Results.Ok(Dto.Search(s));
});
api.MapDelete("/searches/{id:guid}", async (Guid id, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId(); var s = await db.SearchRequests.SingleOrDefaultAsync(x => x.Id == id && x.OwnerId == uid) ?? throw new ApiException(404, "A keresési igény nem található.");
    s.Archived = true; await ClearArchivedActive(db, uid, id, true); await db.SaveChangesAsync(); return Results.NoContent();
});
api.MapGet("/feed", async (AppDb db, ClaimsPrincipal principal) =>
{
    var user = await CurrentUser(db, principal); var items = new List<FeedItem>();
    if (user.ActiveKind == "search")
    {
        var s = await db.SearchRequests.AsNoTracking().SingleOrDefaultAsync(x => x.Id == user.ActiveEntityId && x.OwnerId == user.Id && !x.Archived);
        if (s is not null)
        {
            var seen = await db.Decisions.Where(x => x.SearchRequestId == s.Id && x.ActorKind == "search").Select(x => x.PropertyId).ToListAsync();
            var likes = await db.Decisions.Where(x => x.SearchRequestId == s.Id && x.ActorKind == "property" && x.Liked).Select(x => x.PropertyId).ToListAsync();
            var properties = await db.Properties.AsNoTracking().Where(x => x.OwnerId != user.Id && !x.Archived && !seen.Contains(x.Id)).ToListAsync();
            items.AddRange(properties.Where(p => Rules.Compatible(p, s)).Select(p => new FeedItem(Dto.Property(p), Dto.Search(s), p.Id, s.Id, Rules.Score(p, s), Rules.Reasons(p, s), likes.Contains(p.Id))));
        }
    }
    else if (user.ActiveKind == "property")
    {
        var p = await db.Properties.AsNoTracking().SingleOrDefaultAsync(x => x.Id == user.ActiveEntityId && x.OwnerId == user.Id && !x.Archived);
        if (p is not null)
        {
            var seen = await db.Decisions.Where(x => x.PropertyId == p.Id && x.ActorKind == "property").Select(x => x.SearchRequestId).ToListAsync();
            var likes = await db.Decisions.Where(x => x.PropertyId == p.Id && x.ActorKind == "search" && x.Liked).Select(x => x.SearchRequestId).ToListAsync();
            var searches = await db.SearchRequests.AsNoTracking().Where(x => x.OwnerId != user.Id && !x.Archived && !seen.Contains(x.Id)).ToListAsync();
            items.AddRange(searches.Where(s => Rules.Compatible(p, s)).Select(s => new FeedItem(Dto.Property(p, true), Dto.Search(s), p.Id, s.Id, Rules.Score(p, s), Rules.Reasons(p, s), likes.Contains(s.Id))));
        }
    }
    return Results.Ok(new { items = items.OrderByDescending(x => x.LikedYou).ThenByDescending(x => x.CompatibilityScore).ThenBy(x => x.PropertyId).ThenBy(x => x.SearchRequestId).Take(50), sellerLikeCost = Rules.SellerLikeCost });
});
api.MapPost("/decisions", async (DecisionInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId();
    await using var tx = await db.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted);
    // Lock the actor's balance and both pair rows in the same order for every request.
    var user = (await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {uid} FOR UPDATE").ToListAsync()).SingleOrDefault() ?? throw new ApiException(401, "A fiók nem található.");
    var p = (await db.Properties.FromSqlInterpolated($"SELECT * FROM `Properties` WHERE `Id` = {input.PropertyId} FOR UPDATE").ToListAsync()).SingleOrDefault() ?? throw new ApiException(404, "Az ingatlan nem található.");
    var s = (await db.SearchRequests.FromSqlInterpolated($"SELECT * FROM `SearchRequests` WHERE `Id` = {input.SearchRequestId} FOR UPDATE").ToListAsync()).SingleOrDefault() ?? throw new ApiException(404, "A keresés nem található.");
    var kind = user.ActiveKind;
    var ownsActive = kind == "property" && p.OwnerId == uid && user.ActiveEntityId == p.Id || kind == "search" && s.OwnerId == uid && user.ActiveEntityId == s.Id;
    if (!ownsActive) throw new ApiException(403, "A döntéshez előbb aktiváld a saját ingatlanodat vagy keresésedet.");
    var prior = await db.Decisions.SingleOrDefaultAsync(x => x.PropertyId == p.Id && x.SearchRequestId == s.Id && x.ActorKind == kind);
    if (prior is not null)
    {
        if (prior.Liked != input.Liked) throw new ApiException(409, "Ezt a párost már elbíráltad. A döntés végleges.");
        var previousMatch = await db.Matches.SingleOrDefaultAsync(x => x.PropertyId == p.Id && x.SearchRequestId == s.Id);
        await tx.CommitAsync(); return Results.Ok(new { matchId = previousMatch?.Id, charged = 0, credits = user.Credits });
    }
    if (!Rules.Compatible(p, s)) throw new ApiException(400, "Az ingatlan nem felel meg az aktív keresési feltételeknek.");
    var charge = kind == "property" && input.Liked ? Rules.SellerLikeCost : 0;
    if (user.Credits < charge) throw new ApiException(402, "Nincs elegendő kredited az ajánláshoz.");
    var decision = new Decision { PropertyId = p.Id, SearchRequestId = s.Id, ActorKind = kind!, ActorUserId = uid, Liked = input.Liked, Charged = charge };
    db.Decisions.Add(decision);
    if (charge > 0) { user.Credits -= charge; db.CreditEntries.Add(new CreditEntry { UserId = uid, Amount = -charge, Description = "Ingatlan ajánlása egy keresőnek", DecisionId = decision.Id }); }
    Match? match = null;
    if (input.Liked && await db.Decisions.AnyAsync(x => x.PropertyId == p.Id && x.SearchRequestId == s.Id && x.ActorKind != kind && x.Liked))
    {
        match = new Match { PropertyId = p.Id, SearchRequestId = s.Id }; db.Matches.Add(match);
    }
    await db.SaveChangesAsync(); await tx.CommitAsync(); return Results.Ok(new { matchId = match?.Id, charged = charge, credits = user.Credits });
});
api.MapGet("/matches", async (AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId();
    var rows = await (from m in db.Matches.AsNoTracking() join p in db.Properties.AsNoTracking() on m.PropertyId equals p.Id join s in db.SearchRequests.AsNoTracking() on m.SearchRequestId equals s.Id where p.OwnerId == uid || s.OwnerId == uid orderby m.CreatedAt descending select new { Match = m, Property = p, Search = s }).ToListAsync();
    var results = new List<object>();
    foreach (var row in rows)
    {
        var partnerId = row.Property.OwnerId == uid ? row.Search.OwnerId : row.Property.OwnerId;
        var contact = await db.Users.AsNoTracking().SingleAsync(x => x.Id == partnerId);
        var messages = await db.Messages.AsNoTracking().Where(x => x.MatchId == row.Match.Id).OrderBy(x => x.CreatedAt).ToListAsync();
        results.Add(new { row.Match.Id, row.Match.CreatedAt, property = Dto.Property(row.Property, true), searchRequest = Dto.Search(row.Search), contact = new { contact.Id, contact.Name, contact.Email, contact.Phone }, messages = messages.Select(Dto.Message), unread = 0 });
    }
    return Results.Ok(results);
});
api.MapPost("/matches/{id:guid}/messages", async (Guid id, MessageInput input, AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId();
    var allowed = await (from m in db.Matches join p in db.Properties on m.PropertyId equals p.Id join s in db.SearchRequests on m.SearchRequestId equals s.Id where m.Id == id && (p.OwnerId == uid || s.OwnerId == uid) select m.Id).AnyAsync();
    if (!allowed) throw new ApiException(404, "A párosítás nem található.");
    var message = new Message { MatchId = id, SenderId = uid, Text = Rules.Required(input.Text, "üzenet", 4000) };
    db.Messages.Add(message); await db.SaveChangesAsync(); return Results.Created($"/api/matches/{id}/messages/{message.Id}", Dto.Message(message));
});
api.MapGet("/credits/ledger", async (AppDb db, ClaimsPrincipal principal) =>
{
    var uid = principal.UserId(); return Results.Ok(await db.CreditEntries.AsNoTracking().Where(x => x.UserId == uid).OrderByDescending(x => x.CreatedAt).Select(x => new { x.Id, x.Amount, x.Description, x.CreatedAt }).ToListAsync());
});
if (deployment.AllowDemoTopup)
{
    api.MapPost("/credits/demo-topup", async (TopupInput input, AppDb db, ClaimsPrincipal principal) =>
    {
        if (input.Amount is not (20 or 50 or 100 or 250)) throw new ApiException(400, "Válassz 20, 50, 100 vagy 250 tesztkreditet.");
        var uid = principal.UserId(); await using var tx = await db.Database.BeginTransactionAsync();
        var user = (await db.Users.FromSqlInterpolated($"SELECT * FROM `Users` WHERE `Id` = {uid} FOR UPDATE").ToListAsync()).SingleOrDefault() ?? throw new ApiException(401, "A fiók nem található.");
        if (user.Credits > 1_000_000 - input.Amount) throw new ApiException(400, "Elérted a tesztegyenleg felső korlátját.");
        user.Credits += input.Amount; db.CreditEntries.Add(new CreditEntry { UserId = uid, Amount = input.Amount, Description = deployment.TopupDescription });
        await db.SaveChangesAsync(); await tx.CommitAsync(); return Results.Ok(new { credits = user.Credits });
    });
}
app.MapPayments();
app.Run();

static async Task<User> CurrentUser(AppDb db, ClaimsPrincipal principal) => await db.Users.SingleOrDefaultAsync(x => x.Id == principal.UserId()) ?? throw new ApiException(401, "A fiók nem található.");
static async Task ClearArchivedActive(AppDb db, Guid uid, Guid entityId, bool archived)
{
    if (!archived) return;
    var user = await db.Users.SingleAsync(x => x.Id == uid);
    if (user.ActiveEntityId == entityId) { user.ActiveEntityId = null; user.ActiveKind = null; }
}
public record FeedItem(object Property, object SearchRequest, Guid PropertyId, Guid SearchRequestId, int CompatibilityScore, string[] Reasons, bool LikedYou);
public partial class Program { }
