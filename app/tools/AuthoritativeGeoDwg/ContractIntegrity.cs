using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace AuthoritativeGeoDwg;

/// <summary>AutoCAD-independent, transaction-free contract preflight.</summary>
public static class ContractIntegrity
{
    public const string EnvelopeVersion = "1.0";
    public const string CanonicalizationVersion = "GEO3D-JCS-LIKE-1.0";

    public static JsonDocument VerifyAndParse(JsonElement documentRoot)
    {
        var envelope = documentRoot.TryGetProperty("geologicContractEnvelope", out var nested)
            ? nested : documentRoot;
        RequireString(envelope, "envelopeVersion", EnvelopeVersion);
        RequireString(envelope, "canonicalizationVersion", CanonicalizationVersion);
        RequireString(envelope, "payloadEncoding", "base64-utf8-json");

        var payloadBytes = Decode(envelope, "payloadBase64");
        var validationBytes = Decode(envelope, "validationBase64");
        var payloadDigest = RequireString(envelope, "payloadSha256");
        var validationDigest = RequireString(envelope, "validationSha256");
        if (!FixedEquals(Sha256(payloadBytes), payloadDigest))
            throw new InvalidDataException("payload digest mismatch");
        if (!FixedEquals(Sha256(validationBytes), validationDigest))
            throw new InvalidDataException("validation digest mismatch");

        using var validation = JsonDocument.Parse(validationBytes);
        var validationRoot = validation.RootElement;
        if (!validationRoot.GetProperty("passed").GetBoolean())
            throw new InvalidDataException("validation did not pass");
        if (validationRoot.GetProperty("payloadSha256").GetString() != payloadDigest)
            throw new InvalidDataException("validation is not bound to payload");

        var payload = JsonDocument.Parse(payloadBytes);
        ValidateFinite(payload.RootElement);
        var root = payload.RootElement;
        if (!root.TryGetProperty("lineageManifest", out var lineage) ||
            !lineage.TryGetProperty("sources", out var sources) || sources.GetArrayLength() == 0)
        {
            payload.Dispose();
            throw new InvalidDataException("source-linked lineageManifest is required");
        }
        ValidatePayload(root, validationRoot);
        return payload;
    }

    private static byte[] Decode(JsonElement root, string name)
    {
        try { return Convert.FromBase64String(root.GetProperty(name).GetString()!); }
        catch (Exception error) { throw new InvalidDataException($"invalid {name}", error); }
    }

    private static string RequireString(JsonElement root, string name, string? expected = null)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String)
            throw new InvalidDataException($"missing {name}");
        var text = value.GetString()!;
        if (expected is not null && text != expected)
            throw new InvalidDataException($"unsupported {name}");
        return text;
    }

    private static string Sha256(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static bool FixedEquals(string actual, string expected)
    {
        if (actual.Length != expected.Length) return false;
        return CryptographicOperations.FixedTimeEquals(Encoding.ASCII.GetBytes(actual), Encoding.ASCII.GetBytes(expected));
    }

    private static void ValidateFinite(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Number && !double.IsFinite(value.GetDouble()))
            throw new InvalidDataException("non-finite number is prohibited");
        if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) ValidateFinite(item);
        if (value.ValueKind == JsonValueKind.Object)
            foreach (var item in value.EnumerateObject()) ValidateFinite(item.Value);
    }

    private static void ValidatePayload(JsonElement root, JsonElement validation)
    {
        RequireString(root, "dwgVersion", "AC1032");
        if (!root.TryGetProperty("notForDesign", out var disclosure) || !disclosure.GetBoolean())
            throw new InvalidDataException("synthetic not-for-design disclosure is required");
        if (!root.TryGetProperty("polygons", out var polygons) || polygons.ValueKind != JsonValueKind.Array || polygons.GetArrayLength() == 0)
            throw new InvalidDataException("non-empty polygons are required");
        if (validation.GetProperty("polygonCount").GetInt32() != polygons.GetArrayLength())
            throw new InvalidDataException("validation polygon count mismatch");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var polygon in polygons.EnumerateArray())
        {
            var id = RequireString(polygon, "polygonId");
            if (!ids.Add(id)) throw new InvalidDataException("duplicate polygonId");
            RequireString(polygon, "unitId");
            RequireString(polygon, "boundaryLayer");
            RequireString(polygon, "hatchLayer");
            RequireString(polygon, "hatchPattern", "SOLID");
            if (!polygon.GetProperty("closed").GetBoolean() || !polygon.GetProperty("associative").GetBoolean())
                throw new InvalidDataException("closed associative polygon is required");
            var rgb = polygon.GetProperty("trueColorRGB");
            if (rgb.GetArrayLength() != 3 || rgb.EnumerateArray().Any(v => v.GetInt32() is < 0 or > 255))
                throw new InvalidDataException("invalid trueColorRGB");
            var vertices = polygon.GetProperty("vertices");
            if (vertices.GetArrayLength() < 3 || vertices.EnumerateArray().Any(v => v.GetArrayLength() != 2))
                throw new InvalidDataException("at least three UV vertices are required");
        }
    }
}
