using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;

namespace AuthoritativeGeoDwg;

/// <summary>
/// Universal publication gate shared by every geological DWG generator.
/// It records the governing standards in the DWG and prevents a legacy or
/// unverified generator from being represented as publication-ready.
/// </summary>
public static class GeologicStandardsGate
{
    public const string GateVersion = "1.0.0";
    public const string JapaneseCartography = "JIS A 0204:2019";
    public const string DigitalSchema = "USGS GeMS TM 11-B10 (2020); delivery guidance checked 2026-08-24";
    public const string SymbolStandard = "FGDC Digital Cartographic Standard for Geologic Map Symbolization";
    public const string LithologyVocabulary = "IUGS CGI/GeoSciML; IUGS igneous nomenclature Le Maitre 2002 pending published successor";
    public const string TimeScale = "ICS International Chronostratigraphic Chart 2026/06";

    public sealed record Profile(
        string GeneratorId,
        string ResearchScope,
        string TerminologyStatus,
        string EvidenceStatus,
        string RequestedDecision);

    public static string Apply(Database db, Transaction tr, BlockTableRecord modelSpace, Profile profile)
    {
        if (string.IsNullOrWhiteSpace(profile.GeneratorId))
            throw new InvalidOperationException("GeneratorId is required by the universal standards gate.");
        if (string.IsNullOrWhiteSpace(profile.ResearchScope))
            throw new InvalidOperationException("ResearchScope is required by the universal standards gate.");

        int hatches=0, invalidHatches=0;
        foreach(ObjectId id in modelSpace)
        {
            if (tr.GetObject(id,OpenMode.ForRead) is not Hatch h) continue;
            hatches++;
            var valid=h.PatternName.Equals("SOLID",StringComparison.OrdinalIgnoreCase)
                && h.NumberOfLoops>0;
            for(int i=0;i<h.NumberOfLoops;i++)
            {
                var t=h.GetLoopAt(i).LoopType;
                valid &= (t&(HatchLoopTypes.NotClosed|HatchLoopTypes.SelfIntersecting))==0;
            }
            if(!valid) invalidHatches++;
        }
        if(invalidHatches>0) throw new InvalidOperationException($"Universal standards gate: {invalidHatches} invalid hatch(es).");

        var normalized=profile.TerminologyStatus.Equals("CurrentNormalized",StringComparison.OrdinalIgnoreCase);
        var evidenced=profile.EvidenceStatus.Equals("SourceLinked",StringComparison.OrdinalIgnoreCase);
        var decision=profile.RequestedDecision;
        if(decision.Equals("Accepted",StringComparison.OrdinalIgnoreCase) && (!normalized||!evidenced))
            decision="Experimental";

        var manifest=new {
            gateVersion=GateVersion,profile.GeneratorId,profile.ResearchScope,
            profile.TerminologyStatus,profile.EvidenceStatus,
            requestedDecision=profile.RequestedDecision,effectiveDecision=decision,
            standards=new {JapaneseCartography,DigitalSchema,SymbolStandard,LithologyVocabulary,TimeScale},
            geometry=new {nativeAutoCadEntities=true,hatches,invalidHatches},
            rules=new[]{"PreserveSourceLabel","SeparateNormalizedLabel","SeparateObservedAndInterpreted","MapUnitPolygonAndContactTopology","VersionEveryAuthority"}
        };
        WriteManifest(db,tr,JsonSerializer.Serialize(manifest));
        return decision;
    }

    private static void WriteManifest(Database db,Transaction tr,string json)
    {
        var nod=(DBDictionary)tr.GetObject(db.NamedObjectsDictionaryId,OpenMode.ForWrite);
        const string key="GEODWG_UNIVERSAL_STANDARDS";
        Xrecord x;
        if(nod.Contains(key)) x=(Xrecord)tr.GetObject(nod.GetAt(key),OpenMode.ForWrite);
        else {x=new Xrecord();nod.SetAt(key,x);tr.AddNewlyCreatedDBObject(x,true);}
        // XRecord strings are split to remain comfortably below DXF text limits.
        var values=new List<TypedValue>();
        for(int i=0;i<json.Length;i+=240)values.Add(new TypedValue((int)DxfCode.Text,json.Substring(i,Math.Min(240,json.Length-i))));
        x.Data=new ResultBuffer(values.ToArray());
    }
}
