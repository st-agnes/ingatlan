using System.Collections.Concurrent;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace Otthonra.Api;

/// <summary>Bounded description-only contact checks; keep in parity with contact-policy.js.</summary>
public static class ContactTextPolicy
{
    public const string Message = "Elérhetőséget nem adhatsz meg a leírásban.";
    private static readonly ConcurrentDictionary<string, Regex> Patterns = new();
    private static Regex Pattern(string value) => Patterns.GetOrAdd(value, pattern =>
        new Regex(pattern, RegexOptions.CultureInvariant | RegexOptions.IgnoreCase, TimeSpan.FromMilliseconds(100)));
    private static bool Is(string text, string pattern) => Pattern(pattern).IsMatch(text);
    private static string Replace(string text, string pattern, string replacement) => Pattern(pattern).Replace(text, replacement);
    private static string Replace(string text, string pattern, MatchEvaluator replacement) => Pattern(pattern).Replace(text, replacement);
    private static readonly Dictionary<string, string> Digits = new(StringComparer.Ordinal) {
        ["nulla"]="0",["null"]="0",["nula"]="0",["zero"]="0",["o"]="0",["oh"]="0",["egy"]="1",["one"]="1",["ket"]="2",["ketto"]="2",["two"]="2",["harom"]="3",["three"]="3",["negy"]="4",["four"]="4",["ot"]="5",["five"]="5",["hat"]="6",["six"]="6",["het"]="7",["seven"]="7",["nyolc"]="8",["eight"]="8",["kilenc"]="9",["nine"]="9"
    };
    private static readonly Dictionary<string, int> Tens = new(StringComparer.Ordinal) {
        ["tiz"]=10,["husz"]=20,["harminc"]=30,["negyven"]=40,["otven"]=50,["hatvan"]=60,["hetven"]=70,["nyolcvan"]=80,["kilencven"]=90,["ten"]=10,["eleven"]=11,["twelve"]=12,["thirteen"]=13,["fourteen"]=14,["fifteen"]=15,["sixteen"]=16,["seventeen"]=17,["eighteen"]=18,["nineteen"]=19,["twenty"]=20,["thirty"]=30,["forty"]=40,["fifty"]=50,["sixty"]=60,["seventy"]=70,["eighty"]=80,["ninety"]=90
    };
    private static readonly KeyValuePair<string, string>[] NumberPieces = Digits
        .Concat(Tens.Select(pair => new KeyValuePair<string, string>(pair.Key, pair.Value.ToString(CultureInfo.InvariantCulture))))
        .OrderByDescending(pair => pair.Key.Length).ToArray();
    private static readonly KeyValuePair<string, int>[] SmallPrefixes = Tens.Where(pair => pair.Value >= 20)
        .Concat(new Dictionary<string, int> { ["tizen"]=10,["huszon"]=20 })
        .OrderByDescending(pair => pair.Key.Length).ToArray();
    private static readonly Dictionary<string, string> Entities = new(StringComparer.Ordinal) {
        ["amp"]="&",["commat"]="@",["period"]=".",["plus"]="+",["nbsp"]=" ",["tab"]=" ",["newline"]=" ",["zerowidthspace"]="",["shy"]=""
    };
    private sealed record Token(string Text, int Start, int End);
    private sealed record Atom(int Start, int End, string Digits, int Last);

    public static string ValidateDescription(string? value)
    {
        var text = Rules.Optional(value, 6000);
        if (ContainsContactDetails(text)) throw new ApiException(400, Message);
        return text;
    }

    public static bool ContainsContactDetails(string? value)
    {
        try
        {
            var text = Normalize(value);
            return EmailLike(text) || PhoneLike(text);
        }
        catch (RegexMatchTimeoutException)
        {
            // A bounded check that could not finish must not approve contact
            // text or leak a regex exception through writes/public listings.
            return true;
        }
    }

    private static string Scalar(int code, string fallback) => code >= 0 && code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff)
        ? char.ConvertFromUtf32(code) : fallback;
    private static int Parse(string value, bool hex = false) => int.TryParse(value,
        hex ? NumberStyles.AllowHexSpecifier : NumberStyles.Integer, CultureInfo.InvariantCulture, out var code) ? code : -1;
    private static string Normalize(string? value)
    {
        var text = (value ?? ""); if (text.Length > 6000) text = text[..6000];
        for (var pass = 0; pass < 2; pass++)
        {
            text = Replace(text, @"&(#x[0-9a-f]{1,6}|#[0-9]{1,7}|amp|commat|period|plus|nbsp|tab|newline|zerowidthspace|shy);?", match => {
                var key = match.Groups[1].Value.ToLowerInvariant();
                return key[0] == '#' ? Scalar(Parse(key[(key[1] == 'x' ? 2 : 1)..], key[1] == 'x'), match.Value) : Entities[key];
            });
            text = Replace(text, @"%([0-9a-f]{2})", match => {var code=Parse(match.Groups[1].Value,true);return code>=32&&code<=126?((char)code).ToString():match.Value;});
            text = Replace(text, @"\\u([0-9a-f]{4})|\\x([0-9a-f]{2})", match => Scalar(Parse(match.Groups[1].Success?match.Groups[1].Value:match.Groups[2].Value,true),match.Value));
        }
        text = Replace(text, @"</?[a-z][^<>\r\n]{0,120}>", " ");
        // JSON normally supplies valid Unicode; do not let a directly supplied
        // isolated surrogate turn a public validation method into an exception.
        var valid = new StringBuilder(text.Length);
        for (var index=0;index<text.Length;index++) {
            var character=text[index];
            if (char.IsHighSurrogate(character)) {if(index+1<text.Length&&char.IsLowSurrogate(text[index+1])){valid.Append(character).Append(text[++index]);}else valid.Append(' ');}
            else valid.Append(char.IsLowSurrogate(character)?' ':character);
        }
        text = Replace(valid.ToString().Normalize(NormalizationForm.FormKC), @"(^|[^\p{L}\p{N}_])át(?=$|[^\p{L}\p{N}_])", "$1at_hu").Normalize(NormalizationForm.FormD);
        var result = new StringBuilder(text.Length);
        foreach (var character in text) {
            var category=CharUnicodeInfo.GetUnicodeCategory(character);
            if (category is UnicodeCategory.NonSpacingMark or UnicodeCategory.SpacingCombiningMark or UnicodeCategory.EnclosingMark or UnicodeCategory.Format
                || char.IsControl(character)&&!char.IsWhiteSpace(character)) continue;
            var digit=character is >= '\u0966' and <= '\u096f' ? character-'\u0966' : character is >= '\u06f0' and <= '\u06f9' ? character-'\u06f0' : character is >= '\u0660' and <= '\u0669' ? character-'\u0660' : -1;
            result.Append(digit>=0?(char)('0'+digit):character);
        }
        text=result.ToString().ToLowerInvariant().Replace('。','.').Replace('｡','.').Replace('–','-').Replace('—','-').Replace('−','-');
        return Replace(text, @"\b(?:plusz|plus)\b", "+");
    }

    private static bool PlainAtIsEmail(string rest) =>
        Is(rest,@"^\s+(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s*(?:\.|dot|pont|\s)\s*(?:hu|com|net|org|eu|de|test)\b")
        || Is(rest,@"^\s+[a-z0-9-]{1,63}(?:\s+[a-z0-9-]{1,63}){0,2}\s+(?:dot|pont)\s+[a-z]{2,24}\b")
        || Is(rest,@"^\s+[a-z0-9-]{1,63}\.[a-z]{2,24}\b")
        || Is(rest,@"^\s+[a-z0-9-]{1,63}\s*\.\s*(?:hu|com|net|org|eu|de|test)\b");
    private static bool EmailLike(string text)
    {
        // Maximum-length ordinary prose must not enter an address candidate regex.
        if(!new[]{"@","kukac","arroba","at","email","e-mail","e mail","mailcim"}.Any(marker=>text.Contains(marker,StringComparison.Ordinal)))return false;
        var email=Replace(Replace(text,@"[\[({]\s*(?:kukac|at|arroba)\s*[\])}]","@"),@"kukac|arroba","@");
        email=Replace(email,@"\bat\b",match=>PlainAtIsEmail(email[(match.Index+2)..Math.Min(email.Length,match.Index+202)])?"@":match.Value);
        email=Replace(Replace(email,@"[\[({]\s*(?:pont|dot)\s*[\])}]","."),@"pont|dot",".");
        email=Replace(Replace(email,@"(?:\b[a-z]\s+){1,30}[a-z]\b",match=>Replace(match.Value,@"\s","")),@"\s+"," ");
        // Each @ examines only its disjoint following segment, capped above the
        // maximum supported domain size. The domain patterns are anchored.
        for(var at=email.IndexOf('@');at>=0;){
            var next=email.IndexOf('@',at+1);var end=at;while(end>0&&email[end-1]==' ')end--;
            if(Is(email[Math.Max(0,end-2)..end],@"[\p{L}\p{N}._%+\-]$")){
                var rest=email[(at+1)..Math.Min(at+769,next>=0?next:email.Length)];
                if(Is(rest,@"^\s*[\p{L}\p{N}\-]{1,63}(?:\s*\.\s*[\p{L}\p{N}\-]{1,63}){0,7}\s*\.\s*[\p{L}]{1,24}")
                    || Is(rest,@"^\s*(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s+(?:hu|com|net|org|eu|de|test)\b"))return true;
            }
            at=next;
        }
        foreach(System.Text.RegularExpressions.Match marker in Pattern(@"\b(?:emailcim|mailcim|e-mail|e mail|email)").Matches(email)){
            var start=marker.Index+marker.Length;
            if(Is(email[start..Math.Min(email.Length,start+220)],@"^\s*[:=]?\s*[a-z0-9._%+\-]{1,80}\s+(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s*\.\s*[a-z]{2,12}\b"))return true;
        }
        return false;
    }
    private static int? UnderHundred(string word)
    {
        if (Digits.TryGetValue(word,out var digit))return int.Parse(digit,CultureInfo.InvariantCulture);
        if (Tens.TryGetValue(word,out var ten))return ten;
        foreach(var prefix in SmallPrefixes)if(word.StartsWith(prefix.Key,StringComparison.Ordinal)){
            var rest=word[prefix.Key.Length..];if(Digits.TryGetValue(rest,out var unit)&&unit!="0")return prefix.Value+int.Parse(unit,CultureInfo.InvariantCulture);
        }
        return null;
    }
    private static int? UnderThousand(string word)
    {
        var small=UnderHundred(word);if(small.HasValue)return small;
        foreach(var unit in new[]{"szaz","hundred"}){
            var index=word.IndexOf(unit,StringComparison.Ordinal);if(index<0)continue;
            var prefix=word[..index];var head=prefix.Length>0?UnderHundred(prefix):1;
            var tail=word[(index+unit.Length)..];if(tail.StartsWith("and",StringComparison.Ordinal))tail=tail[3..];
            var rest=tail.Length>0?UnderHundred(tail):0;
            if(head is >=1 and <=9&&rest.HasValue)return head*100+rest;
        }
        return null;
    }
    private static string? NumberWord(string word)
    {
        if(word.Length==0||word.Length>80)return null;
        var small=UnderThousand(word);if(small.HasValue)return small.Value.ToString(CultureInfo.InvariantCulture);
        foreach(var unit in new[]{"ezer","thousand"}){
            var index=word.IndexOf(unit,StringComparison.Ordinal);if(index<0)continue;
            var prefix=word[..index];var head=prefix.Length>0?UnderHundred(prefix):1;
            var tail=word[(index+unit.Length)..];if(tail.StartsWith("and",StringComparison.Ordinal))tail=tail[3..];
            var rest=tail.Length>0?UnderThousand(tail):0;
            if(head is >=1 and <=9&&rest.HasValue)return (head.Value*1000+rest.Value).ToString(CultureInfo.InvariantCulture);
        }
        var at=0;var count=0;var result=new StringBuilder();
        while(at<word.Length){var piece=NumberPieces.FirstOrDefault(piece=>word.AsSpan(at).StartsWith(piece.Key,StringComparison.Ordinal));if(piece.Key is null)return null;result.Append(piece.Value);at+=piece.Key.Length;count++;}
        return count>=2?result.ToString():null;
    }
    private static Atom? AtomAt(Token[] tokens,int index,string text)
    {
        var token=tokens[index];if(Is(token.Text,@"^\d+$"))return new(token.Start,token.End,token.Text,index);
        var word="";Atom? best=null;
        for(var next=index;next<tokens.Length&&next<index+6;next++){
            var current=tokens[next];if(!Is(current.Text,@"^[a-z]+$")||next>index&&!Is(text[tokens[next-1].End..current.Start],@"^[\s-]+$"))break;
            word+=current.Text;if(word.Length>80)break;var value=NumberWord(word);if(value is not null)best=new(token.Start,current.End,value,next);
        }
        return best;
    }
    private static bool PhoneContext(string text,int start,int end) => Is(text[Math.Max(0,start-64)..start]+" "+text[end..Math.Min(text.Length,end+24)],@"\b(?:telefon|tel|mobil|hivj|hivjon|hivhato|elerhetoseg|elerhetsz|whatsapp|viber|sms|phone|call|contact)\b");
    private static bool SafeNumberRun(string text,List<Atom> run)
    {
        var start=run[0].Start;var end=run[^1].End;if(PhoneContext(text,start,end))return false;
        var before=text[Math.Max(0,start-64)..start];var after=text[end..Math.Min(text.Length,end+36)];var raw=text[start..end];
        if(Is(after,@"^\s*(?:ft|huf|eur|euro|usd|forint|millio|milliard|nm|m2|cm|mm|meter|negyzetmeter|hektar|ha|kw|kwh|w|fo|db|szoba|emelet|ev|eves)(?![a-z0-9])")||Is(after,@"^\s*[€$%]"))return true;
        if(Is(before,@"\b(?:ar|ara|iranyar|iranyara|vetelar|vetelara|keret|budget|price|alapterulet|telekmeret|terulet|fogyasztas|hrsz|azonosito|gps|koordinata)\s*[:=]?\s*$")||Is(before,@"helyrajzi\s+szam\s*[:=]?\s*$"))return true;
        if(Is(before,@"\b(?:busz|buszjarat|buszjaratok|jarat|jaratok|villamos|tram)\b")&&raw.Contains(','))return true;
        var values=run.Select(atom=>double.TryParse(atom.Digits,NumberStyles.None,CultureInfo.InvariantCulture,out var value)?value:double.PositiveInfinity).ToArray();
        var sizes=run.Select(atom=>atom.Digits.Length).ToArray();
        if(run.Count==2&&sizes.All(size=>size==4)&&values.All(value=>value>=1800&&value<=2200))return true;
        if(run.Count==3&&((sizes[0]==4&&values[0]>=1800&&values[0]<=2200&&values[1]>=1&&values[1]<=12&&values[2]>=1&&values[2]<=31)||(sizes[2]==4&&values[2]>=1800&&values[2]<=2200&&values[1]>=1&&values[1]<=12&&values[0]>=1&&values[0]<=31)))return true;
        return Is(raw,@"^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$");
    }
    private static bool PhoneNumber(string number,bool hasPlus)
    {
        if(hasPlus&&number.Length>=8&&number.Length<=15&&number[0]!='0')return true;
        if(number.StartsWith("00",StringComparison.Ordinal)&&number.Length>=10&&number.Length<=17&&number[2]!='0')return true;
        if((number.StartsWith("06",StringComparison.Ordinal)||number.StartsWith("36",StringComparison.Ordinal))&&(number.Length==10||number.Length==11))return true;
        return number.Length>=7&&number.Length<=15;
    }
    private static bool RunHasPhone(string text,List<Atom> run)
    {
        if(run.Count==0)return false;
        var all=string.Concat(run.Select(atom=>atom.Digits));var start=run[0].Start;
        var plus=Is(text[Math.Max(0,start-12)..start],@"\+\s*$");
        var explicitPrefix=plus&&all.Length>=8&&all.Length<=15&&all[0]!='0'||all.StartsWith("00",StringComparison.Ordinal)&&all.Length>=10&&all.Length<=17&&all[2]!='0'||all.StartsWith("06",StringComparison.Ordinal)&&(all.Length==10||all.Length==11);
        if(explicitPrefix)return true;
        if(SafeNumberRun(text,run))return false;
        if(PhoneNumber(all,plus))return true;
        for(var first=0;first<run.Count;first++){
            var number="";for(var last=first;last<run.Count&&last<first+15;last++){
                number+=run[last].Digits;if(number.Length>17)break;
                if((number.StartsWith("06",StringComparison.Ordinal)||number.StartsWith("36",StringComparison.Ordinal))&&(number.Length==10||number.Length==11)||number.StartsWith("00",StringComparison.Ordinal)&&number.Length>=10)return true;
            }
        }
        return false;
    }
    private static bool PhoneLike(string text)
    {
        var tokens=Pattern(@"[a-z]+|[0-9]+").Matches(text).Cast<System.Text.RegularExpressions.Match>().Select(match=>new Token(match.Value,match.Index,match.Index+match.Length)).ToArray();
        List<Atom> run=[];
        for(var index=0;index<tokens.Length;index++){
            var atom=AtomAt(tokens,index,text);
            if(atom is null){if(RunHasPhone(text,run))return true;run=[];continue;}
            if(run.Count>0&&!Is(text[run[^1].End..atom.Start],@"^[^a-z0-9]{0,16}$")){if(RunHasPhone(text,run))return true;run=[];}
            run.Add(atom);index=atom.Last;
        }
        return RunHasPhone(text,run);
    }
}
