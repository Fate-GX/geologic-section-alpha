using System.Text.Json;
using AuthoritativeGeoDwg;

if (args.Length != 2 || (args[1] != "valid" && args[1] != "invalid"))
    throw new ArgumentException("usage: <envelope.json> <valid|invalid>");

try
{
    using var outer = JsonDocument.Parse(File.ReadAllBytes(args[0]));
    using var payload = ContractIntegrity.VerifyAndParse(outer.RootElement);
    if (args[1] == "invalid") throw new Exception("invalid envelope was accepted");
    Console.WriteLine($"CSHARP_CONTRACT_INTEGRITY=OK;POLYGONS={payload.RootElement.GetProperty("polygons").GetArrayLength()}");
}
catch (Exception error) when (args[1] == "invalid")
{
    Console.WriteLine($"CSHARP_CONTRACT_REJECTION=OK;TYPE={error.GetType().Name}");
}
