using System.Reflection;
using System.Text.Json;
using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class ContactTextPolicyTests
{
    public static IEnumerable<object[]> SharedExamples()
    {
        using var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("Otthonra.Tests.ContactPolicyCases.json")
            ?? throw new InvalidOperationException("The shared contact-policy cases must be embedded.");
        using var document=JsonDocument.Parse(stream);
        foreach(var example in document.RootElement.EnumerateArray())
            yield return [example.GetProperty("id").GetString()!,example.GetProperty("text").GetString()!,example.GetProperty("contact").GetBoolean()];
    }

    [Theory]
    [MemberData(nameof(SharedExamples))]
    public void SharedClientAndApiExamples(string id,string text,bool contact)
    {
        Assert.True(ContactTextPolicy.ContainsContactDetails(text)==contact,id);
        if(contact){var error=Assert.Throws<ApiException>(()=>ContactTextPolicy.ValidateDescription(text));Assert.Equal(400,error.Status);Assert.Equal(ContactTextPolicy.Message,error.Message);}
        else Assert.Equal(text.Trim(),ContactTextPolicy.ValidateDescription(text));
    }

    [Fact]
    public void OptionalDescriptionAndLengthRulesArePreserved()
    {
        Assert.Equal("",ContactTextPolicy.ValidateDescription(null));
        Assert.Equal("Csendes otthon.",ContactTextPolicy.ValidateDescription("  Csendes otthon.  "));
        Assert.Equal(400,Assert.Throws<ApiException>(()=>ContactTextPolicy.ValidateDescription(new string('a',6001))).Status);
    }

    [Fact]
    public void PrivateAccountEmailValidationStillAcceptsARealEmail()
    {
        Assert.Equal("anna@example.test",Rules.Email("ANNA@example.test"));
        Assert.Equal("Elérhetőséget nem adhatsz meg a leírásban.",ContactTextPolicy.Message);
    }
}
