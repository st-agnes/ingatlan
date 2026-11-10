using System.Globalization;
using System.Text.RegularExpressions;

namespace Otthonra.Api;

/// <summary>Small public display fields, derived from the current owner rather than listing input.</summary>
public static class PublicProfile
{
    private static readonly Regex Email = new(@"[\w.+-]+@[\w.-]+\.[\p{L}]{2,}", RegexOptions.CultureInvariant);
    private static readonly Regex Link = new(@"https?://|www\.|(?:[\p{L}\p{N}-]+\.)+(?:hu|com|net|org|eu|io|dev|app|test)(?:[/?#\s.,;!)]|$)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex Phone = new(@"(?<!\d)(?:\+\d{1,3}|0036|06)[\s().-]*(?:\d[\s().-]*){6,12}|(?:tel(?:efon)?|mobil|hívj)\s*[:.]?\s*\+?\d(?:[\s().-]*\d){5,14}", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex NameToken = new(@"^[\p{L}\p{M}]+(?:['’\-][\p{L}\p{M}]+)*$", RegexOptions.CultureInvariant);
    private static readonly HashSet<string> Honorifics = new(["dr", "prof", "ifj", "id", "özv"], StringComparer.OrdinalIgnoreCase);

    private static string Clean(string? input)
    {
        var value = new string((input ?? "").Take(2048).Select(character =>
            char.IsControl(character) || char.GetUnicodeCategory(character) == UnicodeCategory.Format ? ' ' : character).ToArray());
        return Regex.Replace(value, @"\s+", " ").Trim();
    }
    private static bool HasContact(string value) => Email.IsMatch(value) || Link.IsMatch(value) || Phone.IsMatch(value);

    public static string FirstName(string? name)
    {
        var value = Clean(name);
        if (value.Length == 0 || value.Contains('@') || value.Contains('<') || value.Contains('>') || HasContact(value)) return "";
        var suffix = value.IndexOfAny(['·', '|', ',', ';', '(', '[', '—', '–']);
        if (suffix >= 0) value = value[..suffix].Trim();
        if (value.Any(char.IsDigit)) return "";
        var words = value.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Where(word => !Honorifics.Contains(word.TrimEnd('.'))).ToArray();
        if (words.Length == 0 || words.Any(word => !NameToken.IsMatch(word))) return "";
        var firstName = words[^1]; // Hungarian display names normally place given names last.
        return firstName.Length <= 40 ? firstName : "";
    }

    public static string Title(string? title, string fallback)
    {
        var value = Clean(Regex.Replace(title ?? "", @"<[^>]*>", " "));
        if (value.Length == 0 || HasContact(value)) return fallback;
        return value.Length <= 150 ? value : value[..150].TrimEnd();
    }
}
