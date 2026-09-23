using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.PlottingServices;
using Autodesk.AutoCAD.Runtime;
using AuthoritativeGeoDwg;
using FontDescriptor = Autodesk.AutoCAD.GraphicsInterface.FontDescriptor;

namespace AdvancedV2GeoDwg;

public sealed class AdvancedV2Commands
{
    private const string AnnotationLayer = "90_注記";
    private const string CommonAnnotationLayer = "90_注記_共通";
    private const string GridLayer = "05_座標目盛";
    private const string SheetLayerPrefix = "91_モデル空間図面_";
    private const string ViewportLayerPrefix = "92_ビューポート_";
    private static readonly string[] RequiredLayouts =
        ["GEO_JP", "GEO_EN", "GEO_TOPOLOGY_QA", "GEO_MONOCHROME_QA"];

    [CommandMethod("SETADVANCEDGEOPATHS")]
    public static void SetInteractivePaths()
    {
        var editor=Application.DocumentManager.MdiActiveDocument.Editor;
        var contract=editor.GetString(new Autodesk.AutoCAD.EditorInput.PromptStringOptions("\nContract envelope path: "){AllowSpaces=true});
        if(contract.Status!=Autodesk.AutoCAD.EditorInput.PromptStatus.OK)return;
        var output=editor.GetString(new Autodesk.AutoCAD.EditorInput.PromptStringOptions("\nOutput DWG path: "){AllowSpaces=true});
        if(output.Status!=Autodesk.AutoCAD.EditorInput.PromptStatus.OK)return;
        Environment.SetEnvironmentVariable("GEO3D_EXPORT_CONTRACT",contract.StringResult,EnvironmentVariableTarget.Process);
        Environment.SetEnvironmentVariable("GEO3D_DWG_OUTPUT",output.StringResult,EnvironmentVariableTarget.Process);
        editor.WriteMessage("\nADVANCED_V2_PATHS_SET=OK");
    }

    [CommandMethod("CREATEADVANCEDGEOSECTION")]
    public static void Create()
    {
      try
      {
        var doc = Application.DocumentManager.MdiActiveDocument;
        var contractPath = Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT")
            ?? throw new InvalidOperationException("GEO3D_EXPORT_CONTRACT is required.");
        var outputPath = Environment.GetEnvironmentVariable("GEO3D_DWG_OUTPUT")
            ?? throw new InvalidOperationException("GEO3D_DWG_OUTPUT is required.");
        using var json = JsonDocument.Parse(File.ReadAllBytes(contractPath));
        using var verified = ContractIntegrity.VerifyAndParse(json.RootElement);
        var root = verified.RootElement;
        if (root.GetProperty("dwgVersion").GetString() != "AC1032" ||
            !root.GetProperty("notForDesign").GetBoolean())
            throw new InvalidOperationException("Unsafe DWG contract.");

        var db = doc.Database;
        doc.Editor.WriteMessage("\nADVANCED_V2_CREATE_STAGE=MODEL_BEGIN");
        using (var tr = db.TransactionManager.StartTransaction())
        {
            var layers = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            var model = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForWrite);
            var hatchIds = new ObjectIdCollection();
            var foreground = new ObjectIdCollection();
            foreach (var polygon in root.GetProperty("polygons").EnumerateArray())
            {
                var boundaryLayer = EnsureLayer(layers, tr, polygon.GetProperty("boundaryLayer").GetString()!, Color.FromRgb(255,255,255), false);
                var rgb = polygon.GetProperty("trueColorRGB").EnumerateArray().Select(v => v.GetByte()).ToArray();
                var hatchLayer = EnsureLayer(layers, tr, polygon.GetProperty("hatchLayer").GetString()!, Color.FromRgb(rgb[0],rgb[1],rgb[2]), true);
                var boundary = CreatePolyline(polygon.GetProperty("vertices"), boundaryLayer, true);
                model.AppendEntity(boundary); tr.AddNewlyCreatedDBObject(boundary, true);
                var hatch = new Hatch(); hatch.SetDatabaseDefaults(db); hatch.LayerId = hatchLayer;
                hatch.Color = Color.FromRgb(rgb[0],rgb[1],rgb[2]);
                var pattern = polygon.TryGetProperty("displayHatchPattern", out var displayPattern)
                    ? displayPattern.GetString()!
                    : polygon.GetProperty("hatchPattern").GetString()!;
                hatch.SetHatchPattern(HatchPatternType.PreDefined,pattern);
                if(polygon.TryGetProperty("hatchPatternScale",out var patternScale))
                    hatch.PatternScale=patternScale.GetDouble();
                model.AppendEntity(hatch); tr.AddNewlyCreatedDBObject(hatch, true);
                hatch.Associative = true;
                hatch.AppendLoop(HatchLoopTypes.Outermost, new ObjectIdCollection { boundary.ObjectId });
                hatch.EvaluateHatch(true); hatchIds.Add(hatch.ObjectId);
            }
            if (root.TryGetProperty("contactLines", out var contacts))
                foreach (var contact in contacts.EnumerateArray())
                {
                    // ACI 7 stays legible on both AutoCAD's dark model-space background
                    // and a light plotted sheet. Fixed dark RGB values disappear in model space.
                    var layer = EnsureLayer(layers,tr,contact.GetProperty("layer").GetString()!,Color.FromColorIndex(ColorMethod.ByAci,7),true);
                    var line=CreatePolyline(contact.GetProperty("vertices"),layer,false); line.LineWeight=LineWeight.LineWeight035;
                    model.AppendEntity(line); tr.AddNewlyCreatedDBObject(line,true); foreground.Add(line.ObjectId);
                }
            var terrain=root.GetProperty("terrainLine");
            var terrainLayer=EnsureLayer(layers,tr,terrain.GetProperty("layer").GetString()!,Color.FromColorIndex(ColorMethod.ByAci,7),true);
            var terrainLine=CreatePolyline(terrain.GetProperty("vertices"),terrainLayer,false); terrainLine.LineWeight=LineWeight.LineWeight050;
            model.AppendEntity(terrainLine); tr.AddNewlyCreatedDBObject(terrainLine,true); foreground.Add(terrainLine.ObjectId);
            AddDrafting(db,model,layers,tr,root.GetProperty("drafting"),foreground);
            AddModelSpaceSheets(db,model,layers,tr,root,foreground);
            var order=(DrawOrderTable)tr.GetObject(model.DrawOrderTableId,OpenMode.ForWrite);
            order.MoveToBottom(hatchIds); order.MoveToTop(foreground);
            GeologicStandardsGate.Apply(db,tr,model,new("ADVANCED_V2_NATIVE","Global:SyntheticGeologic3dEngine","Unverified","ModelOutputOnly","Experimental"));
            tr.Commit();
        }
        doc.Editor.WriteMessage("\nADVANCED_V2_CREATE_STAGE=MODEL_COMMITTED");
        CreateLayouts(db, root);
        doc.Editor.WriteMessage("\nADVANCED_V2_CREATE_STAGE=LAYOUTS_COMMITTED");
        db.SaveAs(outputPath,DwgVersion.AC1032);
        doc.Editor.WriteMessage($"\nADVANCED_V2_DWG_CREATED={outputPath}");
      }
      catch(System.Exception error)
      {
        Application.DocumentManager.MdiActiveDocument.Editor.WriteMessage($"\nADVANCED_V2_CREATE_FAILED={error}");
        throw;
      }
    }

    [CommandMethod("VALIDATEADVANCEDGEOSECTION")]
    public static void Validate()
    {
        var doc=Application.DocumentManager.MdiActiveDocument; var db=doc.Database;
        int boundaries=0,hatches=0,basalContinuationHatches=0,invalid=0,texts=0,substituted=0,japaneseStyle=0,contacts=0,terrain=0,collisions=0;
        double minX=double.PositiveInfinity,maxX=double.NegativeInfinity,minY=double.PositiveInfinity,maxY=double.NegativeInfinity;
        double gridMinX=double.PositiveInfinity,gridMaxX=double.NegativeInfinity,gridMinY=double.PositiveInfinity,gridMaxY=double.NegativeInfinity;
        var layouts=new HashSet<string>(StringComparer.Ordinal);
        var lockedLayoutViewports=new HashSet<string>(StringComparer.Ordinal);
        var populatedLayouts=new HashSet<string>(StringComparer.Ordinal);
        var configuredLayouts=new HashSet<string>(StringComparer.Ordinal);
        var namedPageSetups=new HashSet<string>(StringComparer.Ordinal);
        var publicationLayouts=new HashSet<string>(StringComparer.Ordinal);
        var boundedPublicationSheets=new HashSet<string>(StringComparer.Ordinal);
        var enabledModelViewports=new HashSet<string>(StringComparer.Ordinal);
        var viewportDiagnostics=new List<string>();
        var expectedViewport=ExpectedViewportRectFromContract();
        var expectedViewportWidth=expectedViewport.Right-expectedViewport.Left;
        var expectedViewportHeight=expectedViewport.Top-expectedViewport.Bottom;
        var observedText=new List<string>(); var textExtents=new List<Extents3d>();
        bool gridStrokesOk=false;
        using(var tr=db.TransactionManager.StartOpenCloseTransaction())
        {
            var model=(BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db),OpenMode.ForRead);
            gridStrokesOk=ValidateGridStrokes(db,model,tr);
            foreach(ObjectId id in model)
            {
                var obj=tr.GetObject(id,OpenMode.ForRead);
                if(obj is Polyline p)
                {
                    if(p.Layer=="19_ハッチ境界_非印刷" || (p.Layer=="20_岩相区分線_推定" && p.Closed)) boundaries++;
                    if(p.Layer=="20_岩相区分線_推定" && !p.Closed) contacts++;
                    if(p.Layer=="10_地表面" && !p.Closed) terrain++;
                    if(p.Layer==GridLayer) UpdateExtents(p.GeometricExtents,ref gridMinX,ref gridMaxX,ref gridMinY,ref gridMaxY);
                    if(p.Layer=="19_ハッチ境界_非印刷") UpdateExtents(p.GeometricExtents,ref minX,ref maxX,ref minY,ref maxY);
                }
                if(obj is Hatch h && h.Layer.StartsWith("30_岩相カラー_"))
                { hatches++; if(!h.Associative || h.PatternName!="SOLID" || h.NumberOfLoops<1) invalid++; }
                if(obj is DBText t && (t.Layer==AnnotationLayer || t.Layer==CommonAnnotationLayer || t.Layer.StartsWith(SheetLayerPrefix,StringComparison.Ordinal)))
                {
                    texts++; if(t.TextString.Contains('?')) substituted++;
                    observedText.Add(t.TextString);
                    // Sheet text is authored in Model Space as well.  Include
                    // it in the same persisted collision audit so a layout
                    // cannot pass merely because overlapping publication
                    // annotations live on a sheet-specific layer.
                    if(t.Layer==AnnotationLayer || t.Layer==CommonAnnotationLayer ||
                       t.Layer.StartsWith(SheetLayerPrefix,StringComparison.Ordinal))
                        textExtents.Add(t.GeometricExtents);
                    var style=(TextStyleTableRecord)tr.GetObject(t.TextStyleId,OpenMode.ForRead);
                    var typeface=style.Font.TypeFace;
                    if(style.Name=="MS_GOTHIC" &&
                       (style.FileName.EndsWith("msgothic.ttc",StringComparison.OrdinalIgnoreCase) || typeface=="ＭＳ ゴシック")) japaneseStyle++;
                }
            }
            var dict=(DBDictionary)tr.GetObject(db.LayoutDictionaryId,OpenMode.ForRead);
            foreach(DBDictionaryEntry entry in dict)
            {
                layouts.Add(entry.Key);
                if(!RequiredLayouts.Contains(entry.Key))continue;
                var layout=(Layout)tr.GetObject(entry.Value,OpenMode.ForRead);
                var paper=(BlockTableRecord)tr.GetObject(layout.BlockTableRecordId,OpenMode.ForRead);
                var paperObjects=paper.Cast<ObjectId>().Select(id=>tr.GetObject(id,OpenMode.ForRead)).ToArray();
                // In Core Console a newly appended paper-space viewport can
                // retain Number == 1 after SaveAs/reopen even though it is the
                // intended model viewport.  Identify our viewport by its
                // dedicated layout layer and declared sheet geometry instead
                // of relying on that session-dependent ordinal.
                var expectedViewportLayer=ViewportLayerPrefix+entry.Key;
                var paperLow=PaperPoint(layout,expectedViewport.Left,expectedViewport.Bottom);
                var paperHigh=PaperPoint(layout,expectedViewport.Right,expectedViewport.Top);
                var modelViewports=paperObjects.OfType<Viewport>()
                    .Where(v=>v.Layer.Equals(expectedViewportLayer,StringComparison.Ordinal) &&
                              Math.Abs(v.Width-(paperHigh.X-paperLow.X))<=1e-6 && Math.Abs(v.Height-(paperHigh.Y-paperLow.Y))<=1e-6 &&
                              Math.Abs(v.CenterPoint.X-(paperLow.X+paperHigh.X)/2)<=1e-6 &&
                              Math.Abs(v.CenterPoint.Y-(paperLow.Y+paperHigh.Y)/2)<=1e-6)
                    .ToArray();
                if(modelViewports.Any(v=>v.Locked))
                    lockedLayoutViewports.Add(entry.Key);
                // AutoCAD persists On=false for viewports belonging to layouts
                // that were not current at SaveAs; activating the layout turns
                // its viewport on.  Persistence QA therefore validates the
                // saved camera and positive aperture, while the later visual
                // plot pass activates and renders every required layout.
                if(modelViewports.Any(v=>v.ViewHeight>0 && v.Width>0 && v.Height>0 &&
                                             double.IsFinite(v.ViewCenter.X) && double.IsFinite(v.ViewCenter.Y)))
                    enabledModelViewports.Add(entry.Key);
                foreach(var view in modelViewports)
                    viewportDiagnostics.Add($"{entry.Key}:N={view.Number},ON={view.On},LOCKED={view.Locked},VC=({view.ViewCenter.X:0.###},{view.ViewCenter.Y:0.###}),VH={view.ViewHeight:0.###},SIZE=({view.Width:0.###},{view.Height:0.###})");
                foreach(var view in paperObjects.OfType<Viewport>().Where(v=>Math.Abs(v.Width-400*PaperScale(layout))<1e-6))
                    viewportDiagnostics.Add($"{entry.Key}:SHEET:PC={view.CenterPoint};VC={view.ViewCenter};VH={view.ViewHeight};SIZE={view.Width},{view.Height}");
                viewportDiagnostics.Add($"{entry.Key}:PAPER:SIZE={layout.PlotPaperSize};MARGINS={layout.PlotPaperMargins};ORIGIN={layout.PlotOrigin};ROTATION={layout.PlotRotation};SCALE={layout.StdScaleType};DEVICE={layout.PlotConfigurationName}");
                if(paperObjects.Where(value=>value is Entity).All(value=>value is Viewport))
                    populatedLayouts.Add(entry.Key);
                var sheetLayer=SheetLayerPrefix+entry.Key;
                var sheetObjects=model.Cast<ObjectId>().Select(id=>tr.GetObject(id,OpenMode.ForRead))
                    .Where(value=>value is Entity entity && entity.Layer==sheetLayer).ToArray();
                var drafting=ReadDraftingFromContract();
                var sheetLength=drafting.Length;
                var sheetRelief=Math.Max(1.0,drafting.High-drafting.Low);
                var sheetIndex=Array.IndexOf(RequiredLayouts,entry.Key);
                var sheetOffset=SheetOffset(sheetLength,sheetIndex);
                var sheetMinX=sheetOffset+10;
                var sheetMaxX=sheetOffset+410;
                var sheetMinY=10.0;
                var sheetMaxY=287.0;
                if(sheetObjects.OfType<Entity>().All(entity =>
                {
                    var extent=entity.GeometricExtents;
                    return extent.MinPoint.X>=sheetMinX-1e-7 && extent.MaxPoint.X<=sheetMaxX+1e-7 &&
                           extent.MinPoint.Y>=sheetMinY-1e-7 && extent.MaxPoint.Y<=sheetMaxY+1e-7;
                })) boundedPublicationSheets.Add(entry.Key);
                var expectedTitle=LayoutTitle(entry.Key);
                if(sheetObjects.OfType<DBText>().Any(value=>value.TextString==expectedTitle) &&
                   sheetObjects.OfType<Solid>().Any() &&
                   sheetObjects.OfType<Polyline>().Any(value=>value.Closed))publicationLayouts.Add(entry.Key);
                if(!string.IsNullOrWhiteSpace(layout.PlotConfigurationName) &&
                   layout.CanonicalMediaName.Contains("A3",StringComparison.OrdinalIgnoreCase))
                    configuredLayouts.Add(entry.Key);
            }
            var plotSettings=(DBDictionary)tr.GetObject(db.PlotSettingsDictionaryId,OpenMode.ForRead);
            foreach(DBDictionaryEntry entry in plotSettings)namedPageSetups.Add(entry.Key);
            tr.Commit();
        }
        for(int i=0;i<textExtents.Count;i++)for(int j=i+1;j<textExtents.Count;j++)
            if(Intersects(textExtents[i],textExtents[j]))collisions++;
        var extentOk=gridMinX<=minX+1e-7 && gridMaxX>=maxX-1e-7 && gridMinY<=minY+1e-7 && gridMaxY>=maxY-1e-7;
        var expectedLowerLimit=ExpectedFrameLowerFromContract();
        var lowerLimitOk=Math.Abs(minY-expectedLowerLimit)<=1e-7 && Math.Abs(gridMinY-expectedLowerLimit)<=1e-7;
        var layoutOk=RequiredLayouts.All(layouts.Contains) && RequiredLayouts.All(lockedLayoutViewports.Contains) &&
                     RequiredLayouts.All(enabledModelViewports.Contains) &&
                     RequiredLayouts.All(populatedLayouts.Contains) && RequiredLayouts.All(configuredLayouts.Contains) &&
                     RequiredLayouts.All(publicationLayouts.Contains) && RequiredLayouts.All(boundedPublicationSheets.Contains) &&
                     namedPageSetups.Contains("ADV2_A3_LANDSCAPE_COLOR");
        var expectedText=ExpectedTextFromContract();
        var textMatch=expectedText.OrderBy(v=>v,StringComparer.Ordinal).SequenceEqual(observedText.OrderBy(v=>v,StringComparer.Ordinal),StringComparer.Ordinal);
        basalContinuationHatches=CountBasalContinuationPolygonsFromContract();
        if(!gridStrokesOk || !extentOk || !lowerLimitOk || !layoutOk || !textMatch || substituted>0 || collisions>0 || japaneseStyle!=texts || boundaries!=hatches || hatches==0 || basalContinuationHatches!=1) invalid++;
        var status=invalid==0?"OK":"FAILED";
        var report=$"ADVANCED_V2_REOPEN_VALIDATION={status}{Environment.NewLine}"+
          $"BOUNDARIES={boundaries};CONTACTS={contacts};TERRAIN={terrain};HATCHES={hatches};BASAL_CONTINUATION_HATCHES={basalContinuationHatches};TEXTS={texts};JAPANESE_STYLE={japaneseStyle};SUBSTITUTED={substituted};TEXT_MATCH={textMatch.ToString().ToLowerInvariant()};TEXT_COLLISIONS={collisions};EXTENTS_OK={extentOk.ToString().ToLowerInvariant()};LOWER_LIMIT_OK={lowerLimitOk.ToString().ToLowerInvariant()};LAYOUTS_OK={layoutOk.ToString().ToLowerInvariant()};INVALID={invalid}"+
          $"{Environment.NewLine}GRID_STROKES_OK={gridStrokesOk.ToString().ToLowerInvariant()}{Environment.NewLine}VIEWPORTS={string.Join("|",viewportDiagnostics)}";
        var path=Environment.GetEnvironmentVariable("GEO3D_VERIFY_REPORT"); if(!string.IsNullOrWhiteSpace(path))File.WriteAllText(path,report);
        doc.Editor.WriteMessage($"\n{report.Replace(Environment.NewLine,"\n")}");
    }

    [CommandMethod("PLOTADVANCEDGEOLAYOUTS")]
    public static void PlotLayouts()
    {
        var document=Application.DocumentManager.MdiActiveDocument;
        var db=document.Database;
        var outputDirectory=Environment.GetEnvironmentVariable("GEO3D_LAYOUT_PDF_DIR");
        if(string.IsNullOrWhiteSpace(outputDirectory))
            throw new InvalidOperationException("GEO3D_LAYOUT_PDF_DIR is required.");
        Directory.CreateDirectory(outputDirectory);
        if(PlotFactory.ProcessPlotState!=ProcessPlotState.NotPlotting)
            throw new InvalidOperationException("Another plot is already in progress.");
        var requested=Environment.GetEnvironmentVariable("GEO3D_LAYOUT_NAME");
        var layoutsToPlot=string.IsNullOrWhiteSpace(requested) ? RequiredLayouts :
            RequiredLayouts.Where(value=>value.Equals(requested,StringComparison.Ordinal)).ToArray();
        if(layoutsToPlot.Length==0)throw new InvalidOperationException("Unknown requested Advanced V2 layout.");
        foreach(var name in layoutsToPlot)
        {
            LayoutManager.Current.CurrentLayout=name;
            document.Editor.SwitchToPaperSpace();
            document.Editor.Regen();
            using var tr=db.TransactionManager.StartTransaction();
            var dictionary=(DBDictionary)tr.GetObject(db.LayoutDictionaryId,OpenMode.ForRead);
            if(!dictionary.Contains(name))throw new InvalidOperationException($"Missing layout: {name}");
            var layout=(Layout)tr.GetObject(dictionary.GetAt(name),OpenMode.ForRead);
            var info=new PlotInfo{Layout=layout.ObjectId};
            var settings=new PlotSettings(layout.ModelType);
            settings.CopyFrom(layout);
            info.OverrideSettings=settings;
            var validator=new PlotInfoValidator{MediaMatchingPolicy=MatchingPolicy.MatchEnabled};
            validator.Validate(info);
            using var engine=PlotFactory.CreatePublishEngine();
            using var progress=new PlotProgressDialog(false,1,true);
            progress.set_PlotMsgString(PlotMessageIndex.DialogTitle,$"Advanced V2 {name}");
            progress.OnBeginPlot(); progress.IsVisible=false;
            engine.BeginPlot(progress,null);
            var pdf=Path.Combine(outputDirectory,$"{name}.pdf");
            engine.BeginDocument(info,document.Name,null,1,true,pdf);
            var pageInfo=new PlotPageInfo();
            progress.OnBeginSheet();
            engine.BeginPage(pageInfo,info,true,null);
            engine.BeginGenerateGraphics(null);
            engine.EndGenerateGraphics(null);
            engine.EndPage(null);
            progress.OnEndSheet();
            engine.EndDocument(null);
            progress.OnEndPlot();
            engine.EndPlot(null);
            tr.Commit();
        }
        document.Editor.WriteMessage("\nADVANCED_V2_LAYOUT_PLOT=OK");
    }

    private static void AddDrafting(Database db,BlockTableRecord model,LayerTable layers,Transaction tr,JsonElement drafting,ObjectIdCollection foreground)
    {
        var annotation=EnsureLayer(layers,tr,AnnotationLayer,Color.FromColorIndex(ColorMethod.ByAci,7),true);
        var commonAnnotation=EnsureLayer(layers,tr,CommonAnnotationLayer,Color.FromColorIndex(ColorMethod.ByAci,7),true);
        var grid=EnsureLayer(layers,tr,GridLayer,Color.FromRgb(150,150,150),true);
        var style=EnsureJapaneseStyle(db,tr);
        var length=drafting.GetProperty("actualSectionLengthM").GetDouble();
        var ys=drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
        var low=ys.Min(); var high=ys.Max(); var labelHeight=Math.Max(1.8,Math.Min(3.0,(high-low)/50.0));
        foreach(var y in ys)
        {
            var line=new Polyline(); line.SetDatabaseDefaults(); line.LayerId=grid;
            line.AddVertexAt(0,new Point2d(0,y),0,0,0); line.AddVertexAt(1,new Point2d(length,y),0,0,0);
            model.AppendEntity(line);tr.AddNewlyCreatedDBObject(line,true);
            // Elevation values belong outside the geological field.  Placing
            // them over a hatch makes the scale ambiguous and violates the
            // publication rule that annotation must not cross geology.
            AddText(model,tr,commonAnnotation,style,$"EL {y:0} m",new Point3d(-8,y,0),labelHeight,TextHorizontalMode.TextRight,foreground);
            AddText(model,tr,commonAnnotation,style,$"EL {y:0} m",new Point3d(length+8,y,0),labelHeight,TextHorizontalMode.TextLeft,foreground);
        }
        foreach(var x in drafting.GetProperty("horizontalTicksM").EnumerateArray().Select(v=>v.GetDouble()))
            AddText(model,tr,commonAnnotation,style,$"{x:0.##} m",new Point3d(x,low-7,0),labelHeight,TextHorizontalMode.TextCenter,foreground);
        foreach(var x in new[]{0.0,length})
        {
            var axis=new Polyline();axis.SetDatabaseDefaults();axis.LayerId=grid;
            axis.AddVertexAt(0,new Point2d(x,low),0,0,0);axis.AddVertexAt(1,new Point2d(x,high),0,0,0);
            model.AppendEntity(axis);tr.AddNewlyCreatedDBObject(axis,true);
        }
    }

    private static bool ValidateGridStrokes(Database db,BlockTableRecord model,Transaction tr)
    {
        using var envelope=JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT")!));
        using var verified=ContractIntegrity.VerifyAndParse(envelope.RootElement);
        var drafting=verified.RootElement.GetProperty("drafting");
        var length=drafting.GetProperty("actualSectionLengthM").GetDouble();
        var ys=drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
        var expected=ys.Select(y=>(new Point2d(0,y),new Point2d(length,y))).ToList();
        expected.Add((new Point2d(0,ys.Min()),new Point2d(0,ys.Max())));
        expected.Add((new Point2d(length,ys.Min()),new Point2d(length,ys.Max())));
        var entities=model.Cast<ObjectId>().Select(id=>tr.GetObject(id,OpenMode.ForRead)).OfType<Entity>()
            .Where(e=>e.Layer==GridLayer).ToArray();
        if(entities.Length!=expected.Count)return false;
        foreach(var entity in entities)
        {
            if(entity is not Polyline p || !p.Visible || p.Closed || p.NumberOfVertices!=2 ||
               p.GetBulgeAt(0)!=0 || Math.Abs(p.Elevation)>1e-7 || (p.Normal-Vector3d.ZAxis).Length>1e-7)return false;
            var layer=(LayerTableRecord)tr.GetObject(p.LayerId,OpenMode.ForRead);
            if(layer.IsOff || layer.IsFrozen || !layer.IsPlottable)return false;
            var a=p.GetPoint2dAt(0);var b=p.GetPoint2dAt(1);
            var index=expected.FindIndex(pair=>
                (a.GetDistanceTo(pair.Item1)<=1e-7 && b.GetDistanceTo(pair.Item2)<=1e-7) ||
                (b.GetDistanceTo(pair.Item1)<=1e-7 && a.GetDistanceTo(pair.Item2)<=1e-7));
            if(index<0)return false;
            expected.RemoveAt(index);
        }
        return expected.Count==0;
    }

    private static void AddModelSpaceSheets(Database db,BlockTableRecord model,LayerTable layers,Transaction tr,JsonElement root,ObjectIdCollection foreground)
    {
        var drafting=root.GetProperty("drafting");
        var endpointLines=drafting.TryGetProperty("endpointAnnotationLines",out var endpointBlock)
            ?endpointBlock.EnumerateArray().Select(v=>v.GetString()!).ToArray():Array.Empty<string>();
        var headerShift=endpointLines.Length==0?0.0:4.0*endpointLines.Length+4.0;
        var length=drafting.GetProperty("actualSectionLengthM").GetDouble();
        var ys=drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
        var low=ys.Min();var high=ys.Max();var relief=Math.Max(1.0,high-low);
        var style=EnsureJapaneseStyle(db,tr);
        var legend=root.GetProperty("polygons").EnumerateArray()
            .GroupBy(row=>row.GetProperty("unitId").GetString(),StringComparer.Ordinal)
            .Select(group=>group.First()).Where(row=>row.GetProperty("legendGroup").GetString()=="Geology").ToArray();
        for(var sheetIndex=0;sheetIndex<RequiredLayouts.Length;sheetIndex++)
        {
            var name=RequiredLayouts[sheetIndex];
            var offset=SheetOffset(length,sheetIndex);
            var layer=EnsureLayer(layers,tr,SheetLayerPrefix+name,Color.FromColorIndex(ColorMethod.ByAci,7),true);
            var title=LayoutTitle(name);
            var disclosure=name=="GEO_EN" ? "SYNTHETIC DATA — NOT FOR INVESTIGATION, DESIGN OR CONSTRUCTION" :
                "疑似データ／調査・設計・施工に使用不可";
            AddText(model,tr,layer,style,title,new Point3d(offset+17,278,0),5.0,TextHorizontalMode.TextLeft,foreground);
            AddText(model,tr,layer,style,$"{drafting.GetProperty("sectionId").GetString()}  LENGTH {length:0.00} m  VERTICAL EXAGGERATION {drafting.GetProperty("verticalExaggeration").GetDouble():0.##}x",new Point3d(offset+17,269,0),3.0,TextHorizontalMode.TextLeft,foreground);
            for(var n=0;n<endpointLines.Length;n++)
                AddText(model,tr,layer,style,endpointLines[n],new Point3d(offset+17,263-4*n,0),2.5,TextHorizontalMode.TextLeft,foreground);
            AddText(model,tr,layer,style,disclosure,new Point3d(offset+17,16,0),2.5,TextHorizontalMode.TextLeft,foreground);
            AddText(model,tr,layer,style,"DATUM: GSI DEM / VERTICAL DATUM UNVERIFIED",new Point3d(offset+403,21,0),2.5,TextHorizontalMode.TextRight,foreground);
            var lowerNote=name=="GEO_EN"?drafting.GetProperty("modelLowerLimitNoteEn").GetString()!:drafting.GetProperty("modelLowerLimitNoteJa").GetString()!;
            var noteLines=WrapSheetText(lowerNote, name=="GEO_EN"?170:85);
            for(var n=0;n<noteLines.Length;n++)
                AddText(model,tr,layer,style,noteLines[n],new Point3d(offset+17,31-n*4,0),2.5,TextHorizontalMode.TextLeft,foreground);
            // Keep the geological explanation in a dedicated right-hand
            // column, aligned with the section.  A long strip below the
            // drawing reads like a software dashboard rather than a
            // conventional geological sheet.
            var legendX=offset+323;
            AddText(model,tr,layer,style,name=="GEO_EN"?"EXPLANATION":"凡例",new Point3d(legendX,256-headerShift,0),3.5,TextHorizontalMode.TextLeft,foreground);
            var legendY=246.0-headerShift;
            for(var index=0;index<legend.Length;index++)
            {
                var row=legend[index];var rgb=row.GetProperty("trueColorRGB").EnumerateArray().Select(v=>v.GetByte()).ToArray();
                var x=legendX;var y=legendY;
                var gray=(byte)Math.Round(.299*rgb[0]+.587*rgb[1]+.114*rgb[2]);
                var swatch=new Solid(new Point3d(x,y,0),new Point3d(x+5,y,0),new Point3d(x,y+3,0),new Point3d(x+5,y+3,0))
                    {LayerId=layer,Color=name=="GEO_MONOCHROME_QA"?Color.FromRgb(gray,gray,gray):Color.FromRgb(rgb[0],rgb[1],rgb[2])};
                model.AppendEntity(swatch);tr.AddNewlyCreatedDBObject(swatch,true);foreground.Add(swatch.ObjectId);
                var label=name=="GEO_EN"?row.GetProperty("displayNameEn").GetString()!:row.GetProperty("displayName").GetString()!;
                var labelLines=WrapSheetText(label,name=="GEO_EN"?40:25);
                for(var n=0;n<labelLines.Length;n++)
                    AddText(model,tr,layer,style,labelLines[n],new Point3d(x+8,y-n*4,0),2.5,TextHorizontalMode.TextLeft,foreground);
                legendY-=Math.Max(7.0,4.0*labelLines.Length+2.0);
                if(legendY<42)throw new InvalidOperationException("LegendExceedsA3Sheet_UseLargerSheetOrSplitExplanation");
            }
            // The explanation is a conventional bounded block.  Restore its
            // own frame without restoring the former full-sheet frame, which
            // crossed the geological viewport as a false vertical contact.
            var legendBottom=legendY;
            var legendFrame=new Polyline();legendFrame.SetDatabaseDefaults();legendFrame.LayerId=layer;
            legendFrame.AddVertexAt(0,new Point2d(offset+320,legendBottom),0,0,0);
            legendFrame.AddVertexAt(1,new Point2d(offset+403,legendBottom),0,0,0);
            legendFrame.AddVertexAt(2,new Point2d(offset+403,263-headerShift),0,0,0);
            legendFrame.AddVertexAt(3,new Point2d(offset+320,263-headerShift),0,0,0);legendFrame.Closed=true;
            model.AppendEntity(legendFrame);tr.AddNewlyCreatedDBObject(legendFrame,true);foreground.Add(legendFrame.ObjectId);
            var rect=drafting.GetProperty("layoutAllocation").GetProperty("viewportRect");
            var left=rect.GetProperty("left").GetDouble();var right=rect.GetProperty("right").GetDouble();
            var bottom=rect.GetProperty("bottom").GetDouble();var top=rect.GetProperty("top").GetDouble();
            var viewHeight=SheetViewHeight(length,relief,right-left,top-bottom);
            var scale=(top-bottom)/viewHeight;
            var gx=(left+right)/2-length*scale/2;var gy=(top+bottom)/2-relief*scale/2;
            foreach(var z in ys)
            {
                AddText(model,tr,layer,style,$"EL {z:0} m",new Point3d(offset+gx-3,gy+(z-low)*scale,0),2.5,TextHorizontalMode.TextRight,foreground);
                AddText(model,tr,layer,style,$"EL {z:0} m",new Point3d(offset+gx+length*scale+3,gy+(z-low)*scale,0),2.5,TextHorizontalMode.TextLeft,foreground);
            }
            foreach(var x in drafting.GetProperty("horizontalTicksM").EnumerateArray().Select(v=>v.GetDouble()))
                AddText(model,tr,layer,style,$"{x:0.##} m",new Point3d(offset+gx+x*scale,gy-6,0),2.5,TextHorizontalMode.TextCenter,foreground);
            AddText(model,tr,layer,style,(endpointLines.Length>0?"A ":"")+SheetDirection(drafting.GetProperty("leftDirection").GetString()!,name),new Point3d(offset+gx,gy+relief*scale+7,0),3,TextHorizontalMode.TextLeft,foreground);
            AddText(model,tr,layer,style,(endpointLines.Length>0?"B ":"")+SheetDirection(drafting.GetProperty("rightDirection").GetString()!,name),new Point3d(offset+gx+length*scale,gy+relief*scale+7,0),3,TextHorizontalMode.TextRight,foreground);
            var frame=new Polyline();frame.LayerId=layer;
            // Inset inside the viewport aperture so its clip boundary cannot
            // remove half (or all) of the native frame line during plotting.
            foreach(var point in new[]{new Point2d(offset+12,12),new Point2d(offset+408,12),new Point2d(offset+408,285),new Point2d(offset+12,285)})
                frame.AddVertexAt(frame.NumberOfVertices,point,0,0,0);
            frame.Closed=true;model.AppendEntity(frame);tr.AddNewlyCreatedDBObject(frame,true);
        }
    }

    private static double SheetOffset(double length,int index)=>Math.Max(1000,length*2)+index*500;
    private static double PaperScale(PlotSettings layout)
    {
        var size=layout.PlotPaperSize;var margins=layout.PlotPaperMargins;
        var width=Math.Max(size.X,size.Y)-margins.MinPoint.X-margins.MaxPoint.X;
        var height=Math.Min(size.X,size.Y)-margins.MinPoint.Y-margins.MaxPoint.Y;
        var scale=Math.Min((width-4)/420.0,(height-4)/297.0);
        if(scale<0.8 || scale>1.01)throw new InvalidOperationException("InsufficientPrintableA3Area");
        return scale;
    }
    private static Point3d PaperPoint(PlotSettings layout,double x,double y)
    {
        var size=layout.PlotPaperSize;var margins=layout.PlotPaperMargins;var scale=PaperScale(layout);
        return new Point3d((Math.Max(size.X,size.Y)-margins.MinPoint.X-margins.MaxPoint.X)/2+(x-210)*scale,
            (Math.Min(size.X,size.Y)-margins.MinPoint.Y-margins.MaxPoint.Y)/2+(y-148.5)*scale,0);
    }
    private static string SheetDirection(string value,string layout)=>layout!="GEO_EN"?value:value switch
    {
        "北"=>"N", "北東"=>"NE", "東"=>"E", "南東"=>"SE",
        "南"=>"S", "南西"=>"SW", "西"=>"W", "北西"=>"NW", _=>value
    };
    private static double SheetViewHeight(double length,double relief,double width,double height)=>
        Math.Max(relief*1.15,length*1.30/(width/height));
    private static string[] WrapSheetText(string value,int columns)
    {
        var lines=new List<string>();var rest=value;
        while(rest.Length>columns)
        {
            var at=rest.LastIndexOf(' ',columns-1,columns);
            if(at<columns/2)at=columns;
            lines.Add(rest[..at].TrimEnd());rest=rest[at..].TrimStart();
        }
        if(rest.Length>0)lines.Add(rest);return lines.ToArray();
    }

    private static ObjectId EnsureJapaneseStyle(Database db,Transaction tr)
    {
        var table=(TextStyleTable)tr.GetObject(db.TextStyleTableId,OpenMode.ForRead);
        if(table.Has("MS_GOTHIC"))return table["MS_GOTHIC"];
        table.UpgradeOpen(); var style=new TextStyleTableRecord{Name="MS_GOTHIC",FileName="msgothic.ttc",Font=new FontDescriptor("ＭＳ ゴシック",false,false,128,49)};
        var id=table.Add(style);tr.AddNewlyCreatedDBObject(style,true);return id;
    }

    private static void AddText(BlockTableRecord model,Transaction tr,ObjectId layer,ObjectId style,string value,Point3d position,double height,TextHorizontalMode mode,ObjectIdCollection foreground)
    {
        var text=new DBText{TextString=value,Height=height,LayerId=layer,TextStyleId=style,Position=position};
        model.AppendEntity(text);tr.AddNewlyCreatedDBObject(text,true);
        if(mode!=TextHorizontalMode.TextLeft){text.HorizontalMode=mode;text.AlignmentPoint=position;text.AdjustAlignment(model.Database);}
        foreground.Add(text.ObjectId);
    }

    private static void CreateLayouts(Database db,JsonElement root)
    {
        var document=Application.DocumentManager.MdiActiveDocument;
        Application.SetSystemVariable("TILEMODE",0);
        document.Editor.SwitchToPaperSpace();
        var drafting=root.GetProperty("drafting");
        var length=drafting.GetProperty("actualSectionLengthM").GetDouble();
        var ys=drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
        var center=new Point2d(length/2,(ys.Min()+ys.Max())/2);
        var viewportRect=drafting.GetProperty("layoutAllocation").GetProperty("viewportRect");
        var viewportLeft=viewportRect.GetProperty("left").GetDouble();
        var viewportRight=viewportRect.GetProperty("right").GetDouble();
        var viewportBottom=viewportRect.GetProperty("bottom").GetDouble();
        var viewportTop=viewportRect.GetProperty("top").GetDouble();
        var viewportWidth=viewportRight-viewportLeft;
        var viewportHeight=viewportTop-viewportBottom;
        var relief=ys.Max()-ys.Min();
        var verticalFit=relief*1.68;
        var horizontalFit=length*1.10/(viewportWidth/viewportHeight);
        var viewHeight=SheetViewHeight(length,relief,viewportWidth,viewportHeight);
        center=new Point2d(length/2,(ys.Min()+ys.Max())/2);
        foreach(var name in RequiredLayouts)
        {
            ObjectId layoutId;
            try{layoutId=LayoutManager.Current.CreateLayout(name);}catch{continue;}
            LayoutManager.Current.CurrentLayout=name;
            document.Editor.SwitchToPaperSpace();
            using var tr=db.TransactionManager.StartTransaction();
            var layout=(Layout)tr.GetObject(layoutId,OpenMode.ForRead);
            layout.UpgradeOpen(); ApplyNamedA3PageSetup(db,tr,layout,name=="GEO_MONOCHROME_QA");
            var sheetScale=PaperScale(layout);
            var sheetLow=PaperPoint(layout,10,10);var sheetHigh=PaperPoint(layout,410,287);
            var plotLow=PaperPoint(layout,viewportLeft,viewportBottom);var plotHigh=PaperPoint(layout,viewportRight,viewportTop);
            var paper=(BlockTableRecord)tr.GetObject(layout.BlockTableRecordId,OpenMode.ForWrite);
            var viewportIdsBeforeMview=paper.Cast<ObjectId>()
                .Where(id=>tr.GetObject(id,OpenMode.ForRead) is Viewport).ToHashSet();
            // Viewport #1 is AutoCAD's paper-space viewport and must remain.
            // Remove only any pre-existing model-space viewports; erasing #1
            // leaves later viewport entities valid in the database but blank.
            foreach(var existingId in paper.Cast<ObjectId>().ToArray())
                if(tr.GetObject(existingId,OpenMode.ForRead) is Viewport existing)
                {
                    if(existing.Number<=1)continue;
                    existing.UpgradeOpen(); existing.Erase();
                }
            var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForRead);
            EnsureLayer(layers,tr,ViewportLayerPrefix+name,Color.FromColorIndex(ColorMethod.ByAci,7),false);
            tr.Commit();
            // Core Console did not register a directly appended Viewport with
            // the graphics system (persisted Number == -1).  MVIEW is the
            // native AutoCAD viewport constructor, so use it only for this
            // entity creation step, then configure all semantics through .NET.
            document.Editor.Command("_.MVIEW",sheetLow,sheetHigh);
            document.Editor.Command("_.MVIEW",plotLow,plotHigh);
            using var activation=db.TransactionManager.StartTransaction();
            var activeLayout=(Layout)activation.GetObject(layoutId,OpenMode.ForRead);
            var activePaper=(BlockTableRecord)activation.GetObject(activeLayout.BlockTableRecordId,OpenMode.ForWrite);
            var createdViews=activePaper.Cast<ObjectId>()
                .Select(id=>activation.GetObject(id,OpenMode.ForRead)).OfType<Viewport>()
                .Where(value=>!viewportIdsBeforeMview.Contains(value.ObjectId)).ToArray();
            var activeLayers=(LayerTable)activation.GetObject(db.LayerTableId,OpenMode.ForRead);
            var persisted=createdViews.OrderBy(value=>Math.Abs(value.Width-viewportWidth*sheetScale)+Math.Abs(value.Height-viewportHeight*sheetScale)).First();
            var sheetViewport=createdViews.OrderBy(value=>Math.Abs(value.Width-400.0*sheetScale)+Math.Abs(value.Height-277.0*sheetScale)).First();
            sheetViewport.UpgradeOpen();
            sheetViewport.LayerId=activeLayers[ViewportLayerPrefix+name];
            sheetViewport.ViewDirection=Vector3d.ZAxis;
            var sheetIndex=Array.IndexOf(RequiredLayouts,name);
            var sheetOffset=SheetOffset(length,sheetIndex);
            sheetViewport.ViewTarget=Point3d.Origin;
            sheetViewport.ViewCenter=new Point2d(sheetOffset+210,148.5);
            sheetViewport.ViewHeight=277;
            sheetViewport.TwistAngle=0;sheetViewport.On=true;sheetViewport.Locked=true;
            var sheetHidden=new ObjectIdCollection();
            foreach(ObjectId layerId in activeLayers)
            {
                var row=(LayerTableRecord)activation.GetObject(layerId,OpenMode.ForRead);
                if(row.Name!=SheetLayerPrefix+name && !row.Name.StartsWith(ViewportLayerPrefix,StringComparison.Ordinal))sheetHidden.Add(layerId);
            }
            if(sheetHidden.Count>0)sheetViewport.FreezeLayersInViewport(sheetHidden.GetEnumerator());
            persisted.UpgradeOpen();
            persisted.LayerId=activeLayers[ViewportLayerPrefix+name];
            persisted.ViewDirection=Vector3d.ZAxis;
            persisted.ViewTarget=Point3d.Origin;
            persisted.ViewCenter=center;
            persisted.ViewHeight=viewHeight;
            persisted.TwistAngle=0;
            persisted.On=true;
            persisted.Locked=true;
            var hiddenSheetLayers=new ObjectIdCollection();
            if(activeLayers.Has(CommonAnnotationLayer))hiddenSheetLayers.Add(activeLayers[CommonAnnotationLayer]);
            foreach(var other in RequiredLayouts)
                if(other!=name && activeLayers.Has(SheetLayerPrefix+other))hiddenSheetLayers.Add(activeLayers[SheetLayerPrefix+other]);
            if(hiddenSheetLayers.Count>0)persisted.FreezeLayersInViewport(hiddenSheetLayers.GetEnumerator());
            if(name=="GEO_TOPOLOGY_QA" || name=="GEO_MONOCHROME_QA")
            {
                var hatchLayers=new ObjectIdCollection();
                foreach(ObjectId layerId in activeLayers)
                {
                    var row=(LayerTableRecord)activation.GetObject(layerId,OpenMode.ForRead);
                    if(row.Name.StartsWith("30_岩相カラー_",StringComparison.Ordinal))hatchLayers.Add(layerId);
                }
                if(hatchLayers.Count>0)persisted.FreezeLayersInViewport(hatchLayers.GetEnumerator());
            }
            var activeOrder=(DrawOrderTable)activation.GetObject(activePaper.DrawOrderTableId,OpenMode.ForWrite);
            activeOrder.MoveToBottom(new ObjectIdCollection{persisted.ObjectId});
            activeOrder.MoveToTop(new ObjectIdCollection{sheetViewport.ObjectId});
            sheetViewport.UpdateDisplay();
            persisted.UpdateDisplay();
            activation.Commit();
        }
    }

    private static string LayoutTitle(string name) => name=="GEO_EN" ? "SYNTHETIC GEOLOGIC CROSS SECTION" :
        name=="GEO_TOPOLOGY_QA" ? "TOPOLOGY QA — HATCH LAYERS HIDDEN" :
        name=="GEO_MONOCHROME_QA" ? "MONOCHROME / LINEWEIGHT QA" : "合成地質断面図";

    private static void ApplyNamedA3PageSetup(Database db,Transaction tr,Layout layout,bool monochrome)
    {
        const string colorSetupName="ADV2_A3_LANDSCAPE_COLOR";
        var dictionary=(DBDictionary)tr.GetObject(db.PlotSettingsDictionaryId,OpenMode.ForRead);
        PlotSettings colorSetup;
        if(dictionary.Contains(colorSetupName))
            colorSetup=(PlotSettings)tr.GetObject(dictionary.GetAt(colorSetupName),OpenMode.ForRead);
        else
        {
            colorSetup=new PlotSettings(layout.ModelType); colorSetup.CopyFrom(layout);
            ConfigureA3PlotSettings(colorSetup,false);
            colorSetup.PlotSettingsName=colorSetupName; colorSetup.AddToPlotSettingsDictionary(db);
            tr.AddNewlyCreatedDBObject(colorSetup,true);
        }
        // All four layouts inherit the exact same A3 coordinate system.  A
        // separate monochrome setup copied from a newly created layout caused
        // AutoCAD to retain a different ScaleToFit state and shrink the sheet.
        layout.CopyFrom(colorSetup);
        // The monochrome QA layout deliberately uses the same A3 page setup.
        // Its viewport freezes colour-fill hatches, leaving native black
        // contact/terrain/grid linework for lineweight inspection.  This avoids
        // a Core Console 2027 monochrome.ctb ScaleToFit corruption.
    }

    private static void ConfigureA3PlotSettings(PlotSettings layout,bool monochrome)
    {
        var validator=PlotSettingsValidator.Current;
        validator.RefreshLists(layout);
        var devices=validator.GetPlotDeviceList().Cast<string>().ToArray();
        var preferredPdfDevices=new[]{
            "DWG To PDF.pc3",
            "AutoCAD PDF (General Documentation).pc3",
            "AutoCAD PDF (High Quality Print).pc3"
        };
        var device=preferredPdfDevices
            .Select(preferred=>devices.FirstOrDefault(value=>value.Equals(preferred,StringComparison.OrdinalIgnoreCase)))
            .FirstOrDefault(value=>value!=null)
            ?? devices.FirstOrDefault(value=>value.EndsWith(".pc3",StringComparison.OrdinalIgnoreCase)
                && value.Contains("PDF",StringComparison.OrdinalIgnoreCase))
            ?? devices.FirstOrDefault(value=>value.Contains("PDF",StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidOperationException("A PDF-capable PC3 device is required. Available: "+string.Join(", ",devices));
        validator.SetPlotConfigurationName(layout,device,null);
        validator.RefreshLists(layout);
        var media=validator.GetCanonicalMediaNameList(layout).Cast<string>().ToArray();
        var medium=media
            // Core Console's Microsoft Print to PDF canonical A3 medium can
            // alternate its reported dimensional alias after a preceding
            // job.  The stable ISO key must win whenever it is available.
            .FirstOrDefault(value=>value.Equals("psk:ISOA3",StringComparison.OrdinalIgnoreCase))
            ?? media.FirstOrDefault(IsLandscapeA3Media)
            ?? throw new InvalidOperationException("An A3 media definition is required for Advanced V2 publication layouts. Device: "+device+"; Available: "+string.Join(", ",media));
        validator.SetCanonicalMediaName(layout,medium);
        validator.SetPlotPaperUnits(layout,PlotPaperUnit.Millimeters);
        validator.SetPlotType(layout,Autodesk.AutoCAD.DatabaseServices.PlotType.Layout);
        // Paper-space origin is the printable lower-left. Both viewports are
        // fitted together into the device-reported printable area, preserving
        // their shared scale and centering without changing model geometry.
        validator.SetUseStandardScale(layout,true);
        validator.SetStdScaleType(layout,StdScaleType.StdScale1To1);
        validator.SetPlotRotation(layout,layout.PlotPaperSize.X<layout.PlotPaperSize.Y?PlotRotation.Degrees090:PlotRotation.Degrees000);
        validator.SetPlotOrigin(layout,new Point2d(0,0));
        Application.DocumentManager.MdiActiveDocument.Editor.WriteMessage($"\nADV2_PAPER={device};{medium};SIZE={layout.PlotPaperSize};MARGINS={layout.PlotPaperMargins};ORIGIN={layout.PlotOrigin};ROTATION={layout.PlotRotation}");
        if(monochrome)
        {
            var sheets=validator.GetPlotStyleSheetList().Cast<string>();
            if(!sheets.Any(value=>value.Equals("monochrome.ctb",StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("monochrome.ctb is required for the monochrome QA layout.");
            validator.SetCurrentStyleSheet(layout,"monochrome.ctb");
        }
    }

    private static bool IsLandscapeA3Media(string value)
    {
        if(!value.Contains("A3",StringComparison.OrdinalIgnoreCase))return false;
        var width=value.IndexOf("420",StringComparison.OrdinalIgnoreCase);
        var height=value.IndexOf("297",StringComparison.OrdinalIgnoreCase);
        return width>=0 && height>width;
    }

    private static ObjectId EnsureLayer(LayerTable table,Transaction tr,string name,Color color,bool plottable)
    { if(table.Has(name))return table[name];table.UpgradeOpen();var row=new LayerTableRecord{Name=name,Color=color,IsPlottable=plottable};var id=table.Add(row);tr.AddNewlyCreatedDBObject(row,true);return id; }
    private static Polyline CreatePolyline(JsonElement vertices,ObjectId layer,bool closed)
    { var p=new Polyline();p.SetDatabaseDefaults();p.LayerId=layer;int i=0;foreach(var v in vertices.EnumerateArray()){var a=v.EnumerateArray().Select(x=>x.GetDouble()).ToArray();p.AddVertexAt(i++,new Point2d(a[0],a[1]),0,0,0);}p.Closed=closed;return p; }
    private static void UpdateExtents(Extents3d e,ref double minX,ref double maxX,ref double minY,ref double maxY)
    { minX=Math.Min(minX,e.MinPoint.X);maxX=Math.Max(maxX,e.MaxPoint.X);minY=Math.Min(minY,e.MinPoint.Y);maxY=Math.Max(maxY,e.MaxPoint.Y); }
    private static bool Intersects(Extents3d a,Extents3d b)
    { return a.MinPoint.X<b.MaxPoint.X && a.MaxPoint.X>b.MinPoint.X && a.MinPoint.Y<b.MaxPoint.Y && a.MaxPoint.Y>b.MinPoint.Y; }
    private static List<string> ExpectedTextFromContract()
    {
        var path=Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT") ?? throw new InvalidOperationException("contract path missing during validation");
        using var json=JsonDocument.Parse(File.ReadAllBytes(path));using var verified=ContractIntegrity.VerifyAndParse(json.RootElement);
        var drafting=verified.RootElement.GetProperty("drafting");var length=drafting.GetProperty("actualSectionLengthM").GetDouble();var values=new List<string>();
        var endpointLines=drafting.TryGetProperty("endpointAnnotationLines",out var block)
            ?block.EnumerateArray().Select(v=>v.GetString()!).ToArray():Array.Empty<string>();
        foreach(var y in drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble())){values.Add($"EL {y:0} m");values.Add($"EL {y:0} m");}
        foreach(var x in drafting.GetProperty("horizontalTicksM").EnumerateArray().Select(v=>v.GetDouble()))values.Add($"{x:0.##} m");
        using var source=JsonDocument.Parse(File.ReadAllBytes(path));using var checkedContract=ContractIntegrity.VerifyAndParse(source.RootElement);
        var polygons=checkedContract.RootElement.GetProperty("polygons").EnumerateArray()
            .GroupBy(row=>row.GetProperty("unitId").GetString(),StringComparer.Ordinal).Select(group=>group.First())
            .Where(row=>row.GetProperty("legendGroup").GetString()=="Geology").ToArray();
        foreach(var name in RequiredLayouts)
        {
            values.Add(LayoutTitle(name));
            values.Add($"{drafting.GetProperty("sectionId").GetString()}  LENGTH {length:0.00} m  VERTICAL EXAGGERATION {drafting.GetProperty("verticalExaggeration").GetDouble():0.##}x");
            values.AddRange(endpointLines);
            values.Add(name=="GEO_EN"?"SYNTHETIC DATA — NOT FOR INVESTIGATION, DESIGN OR CONSTRUCTION":"疑似データ／調査・設計・施工に使用不可");
            values.Add("DATUM: GSI DEM / VERTICAL DATUM UNVERIFIED");
            values.AddRange(WrapSheetText(name=="GEO_EN"?drafting.GetProperty("modelLowerLimitNoteEn").GetString()!:drafting.GetProperty("modelLowerLimitNoteJa").GetString()!,name=="GEO_EN"?170:85));
            // Keep reopen validation tied to the exact model-space sheet
            // heading emitted by AddModelSpaceSheets.  "UNITS" was the old
            // heading and caused an otherwise healthy DWG to fail the text
            // persistence gate after the publication layout was revised.
            values.Add(name=="GEO_EN"?"EXPLANATION":"凡例");
            foreach(var row in polygons)values.AddRange(WrapSheetText(name=="GEO_EN"?row.GetProperty("displayNameEn").GetString()!:row.GetProperty("displayName").GetString()!,name=="GEO_EN"?40:25));
            foreach(var y in drafting.GetProperty("elevationTicksM").EnumerateArray().Select(v=>v.GetDouble())){values.Add($"EL {y:0} m");values.Add($"EL {y:0} m");}
            foreach(var x in drafting.GetProperty("horizontalTicksM").EnumerateArray().Select(v=>v.GetDouble()))values.Add($"{x:0.##} m");
            values.Add((endpointLines.Length>0?"A ":"")+SheetDirection(drafting.GetProperty("leftDirection").GetString()!,name));
            values.Add((endpointLines.Length>0?"B ":"")+SheetDirection(drafting.GetProperty("rightDirection").GetString()!,name));
        }
        return values;
    }

    private static double ExpectedFrameLowerFromContract()
    {
        var path=Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT") ?? throw new InvalidOperationException("contract path missing during validation");
        using var json=JsonDocument.Parse(File.ReadAllBytes(path));using var verified=ContractIntegrity.VerifyAndParse(json.RootElement);
        var drafting=verified.RootElement.GetProperty("drafting");
        if(drafting.GetProperty("modelLowerLimitClass").GetString()!="VariableSyntheticModelBoundary" ||
           drafting.GetProperty("belowModelLimitStatus").GetString()!="SyntheticBasalContinuation")
            throw new InvalidOperationException("unsafe model lower-limit semantics");
        return drafting.GetProperty("drawingFrameLowerM").GetDouble();
    }

    private static (double Left,double Right,double Bottom,double Top) ExpectedViewportRectFromContract()
    {
        var path=Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT") ?? throw new InvalidOperationException("contract path missing during validation");
        using var json=JsonDocument.Parse(File.ReadAllBytes(path));using var verified=ContractIntegrity.VerifyAndParse(json.RootElement);
        var allocation=verified.RootElement.GetProperty("drafting").GetProperty("layoutAllocation");
        if(!allocation.GetProperty("passed").GetBoolean() || allocation.GetProperty("maximumImbalanceRatio").GetDouble()>0.005)
            throw new InvalidOperationException("unsafe paper-space allocation");
        var rect=allocation.GetProperty("viewportRect");
        return (rect.GetProperty("left").GetDouble(),rect.GetProperty("right").GetDouble(),
                rect.GetProperty("bottom").GetDouble(),rect.GetProperty("top").GetDouble());
    }

    private static (double Length,double Low,double High) ReadDraftingFromContract()
    {
        var path=Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT") ?? throw new InvalidOperationException("contract path missing during validation");
        using var json=JsonDocument.Parse(File.ReadAllBytes(path));using var verified=ContractIntegrity.VerifyAndParse(json.RootElement);
        var drafting=verified.RootElement.GetProperty("drafting");
        var ticks=drafting.GetProperty("elevationTicksM").EnumerateArray().Select(value=>value.GetDouble()).ToArray();
        return (drafting.GetProperty("actualSectionLengthM").GetDouble(),ticks.Min(),ticks.Max());
    }

    private static int CountBasalContinuationPolygonsFromContract()
    {
        var path=Environment.GetEnvironmentVariable("GEO3D_EXPORT_CONTRACT") ?? throw new InvalidOperationException("contract path missing during validation");
        using var json=JsonDocument.Parse(File.ReadAllBytes(path));using var verified=ContractIntegrity.VerifyAndParse(json.RootElement);
        return verified.RootElement.GetProperty("polygons").EnumerateArray().Count(row=>
            row.TryGetProperty("materialClassification",out var classification) &&
            classification.GetString()=="SyntheticBasalContinuation" &&
            row.GetProperty("basisType").GetString()=="SyntheticAssumption" &&
            row.GetProperty("continuationOfUnitId").GetString()==row.GetProperty("unitId").GetString());
    }
}
