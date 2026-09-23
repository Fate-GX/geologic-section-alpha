"""Simple Japanese region/drawing conditions editor."""
from dataclasses import asdict
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from .gui_conditions import DrawingConditions, GeographicRouteConditions, bundle_details, execute_conditions

EXAMPLES=Path(__file__).resolve().parents[1]/"examples"
FIELDS=(("x_start","横方向の始点"),("x_end","横方向の終点"),
        ("elevation_bottom","標高の下端"),("elevation_top","標高の上端"),
        ("section_y","断面位置 Y"),("horizontal_tick","横目盛の間隔"),("vertical_tick","縦目盛の間隔"))

class ConditionsWindow:
    def __init__(self,root):
        self.root=root;self.busy=False;self.messages=queue.Queue()
        records=json.loads((EXAMPLES/"gui_regions.json").read_text(encoding="utf-8"))["regions"]
        self.regions={r["label"]:EXAMPLES/r["bundle"] for r in records}
        self.region=tk.StringVar(value=next(iter(self.regions)))
        self.output=tk.StringVar(value=str(EXAMPLES.parent/"outputs/gui_runs"))
        self.status=tk.StringVar(value="地域・モデルを選び、条件を確認してください。")
        self.info=tk.StringVar();self.values={key:tk.StringVar() for key,_ in FIELDS}
        self.route_text=tk.StringVar(value="131.036,32.878\n131.044,32.887\n131.052,32.880\n131.057,32.889")
        self.route_spacing=tk.StringVar(value="25")
        self.terrain_sampling=tk.StringVar(value="双一次（推奨）")
        self.borehole_path=tk.StringVar();self.borehole_offset=tk.StringVar(value="100")
        self.borehole_context_offset=tk.StringVar(value="5000")
        self.mapped_point_path=tk.StringVar();self.mapped_point_offset=tk.StringVar(value="500")
        self.mapped_linework_path=tk.StringVar()
        self.last_kunijiban_plan=None;self.last_kunijiban_index=None;self.last_kunijiban_collection=None
        root.title("地質断面モデル — 条件設定");root.geometry("880x900");root.minsize(800,800)
        body=ttk.Frame(root,padding=18);body.pack(fill="both",expand=True)
        ttk.Label(body,text="地質断面の条件設定",font=("Yu Gothic UI",18,"bold")).pack(anchor="w")
        ttk.Label(body,text="疑似地質モデル・設計用途不可 ｜ 任意測線：ネイティブDWG＋確認PNG").pack(anchor="w",pady=(4,12))
        from .gui_image import open_image_window
        ttk.Button(body,text="3Dエンジンの生成結果をPNGで確認…",command=lambda:open_image_window(root)).pack(anchor="w",pady=(0,8))
        from .gui_basic_section import open_basic_section_window
        ttk.Button(body,text="地形・岩相を分離した基本断面PNG…",
                   command=lambda:open_basic_section_window(root)).pack(anchor="w",pady=(0,8))
        regionbox=ttk.LabelFrame(body,text="1  地域・モデル",padding=10);regionbox.pack(fill="x")
        self.combo=ttk.Combobox(regionbox,textvariable=self.region,values=list(self.regions),state="readonly",width=60)
        self.combo.pack(side="left",fill="x",expand=True)
        self.combo.bind("<<ComboboxSelected>>",lambda e:self.select_region())
        self.import_button=ttk.Button(regionbox,text="地域設定を読み込む…",command=self.import_bundle)
        self.import_button.pack(side="right",padx=(8,0))
        ttk.Label(body,textvariable=self.info,wraplength=810).pack(anchor="w",pady=8)
        settings=ttk.LabelFrame(body,text="2  図面範囲と目盛（単位：m）",padding=10);settings.pack(fill="x")
        self.controls=[self.import_button]
        for i,(key,label) in enumerate(FIELDS):
            row,col=divmod(i,2)
            ttk.Label(settings,text=label).grid(row=row,column=col*2,sticky="w",padx=6,pady=5)
            entry=ttk.Entry(settings,textvariable=self.values[key],width=18)
            entry.grid(row=row,column=col*2+1,padx=(6,35),pady=5);self.controls.append(entry)
        ttk.Label(body,text="標高はモデル基準面からの高さ（例：下端 −50m）。図面枠の拡大で地質は延長されません。",wraplength=810).pack(anchor="w",pady=5)
        routebox=ttk.LabelFrame(body,text="3  現況平面図・任意測線プレビュー",padding=10);routebox.pack(fill="x",pady=5)
        ttk.Label(routebox,text="測線頂点（1行に 経度,緯度。2点以上）").grid(row=0,column=0,sticky="w")
        route_entry=tk.Text(routebox,height=4,width=58)
        route_entry.insert("1.0",self.route_text.get());route_entry.grid(row=1,column=0,rowspan=2,sticky="ew",padx=(0,10));self.route_entry=route_entry;self.controls.append(route_entry)
        terrain_controls=ttk.Frame(routebox);terrain_controls.grid(row=0,column=1,rowspan=3,sticky="nw")
        ttk.Label(terrain_controls,text="標高サンプル間隔 (m)").pack(anchor="w")
        spacing_entry=ttk.Entry(terrain_controls,textvariable=self.route_spacing,width=12);spacing_entry.pack(anchor="w",pady=(2,7));self.controls.append(spacing_entry)
        ttk.Label(terrain_controls,text="DEM標高の取得方式").pack(anchor="w")
        sampling_combo=ttk.Combobox(terrain_controls,textvariable=self.terrain_sampling,
            values=("双一次（推奨）","最近傍（比較用）"),state="readonly",width=18)
        sampling_combo.pack(anchor="w",pady=(2,0));self.controls.append(sampling_combo)
        ttk.Label(routebox,text="地質点証拠JSON（任意）").grid(row=3,column=0,sticky="w",pady=(7,0))
        mapped_entry=ttk.Entry(routebox,textvariable=self.mapped_point_path);mapped_entry.grid(row=4,column=0,sticky="ew",padx=(0,10));self.controls.append(mapped_entry)
        mapped_browse=ttk.Button(routebox,text="JSONを選択…",command=self.choose_mapped_points);mapped_browse.grid(row=4,column=1,sticky="w");self.controls.append(mapped_browse)
        ttk.Label(routebox,text="記号表示の最大離隔 (m)").grid(row=5,column=0,sticky="w",pady=(7,0))
        mapped_offset=ttk.Entry(routebox,textvariable=self.mapped_point_offset,width=12);mapped_offset.grid(row=5,column=1,sticky="w",pady=(7,0));self.controls.append(mapped_offset)
        ttk.Label(routebox,text="地質境界・断層線JSON（任意）").grid(row=6,column=0,sticky="w",pady=(7,0))
        line_entry=ttk.Entry(routebox,textvariable=self.mapped_linework_path);line_entry.grid(row=7,column=0,sticky="ew",padx=(0,10));self.controls.append(line_entry)
        line_browse=ttk.Button(routebox,text="JSONを選択…",command=self.choose_mapped_linework);line_browse.grid(row=7,column=1,sticky="w");self.controls.append(line_browse)
        plan_button=ttk.Button(routebox,text="航空写真＋地形縦断を生成",command=self.run_plan_preview);plan_button.grid(row=8,column=0,sticky="w",pady=(8,0));self.controls.append(plan_button)
        arbitrary_button=ttk.Button(routebox,text="この任意測線のDWG＋確認PNG",command=self.run_arbitrary_basic_section)
        arbitrary_button.grid(row=8,column=1,sticky="e",pady=(8,0));self.controls.append(arbitrary_button)
        readiness_button=ttk.Button(routebox,text="この測線で生成できる範囲を確認…",command=self.run_route_readiness);readiness_button.grid(row=9,column=0,columnspan=2,sticky="e",pady=(6,0));self.controls.append(readiness_button)
        kuni_button=ttk.Button(routebox,text="KuniJiban周辺ボーリング候補を検索…",command=self.run_kunijiban_search);kuni_button.grid(row=10,column=0,columnspan=2,sticky="e",pady=(6,0));self.controls.append(kuni_button)
        ttk.Label(routebox,text="地形・地表地質・地質点の証拠表示です。航空写真やDEMだけから地下岩相は推定しません。",foreground="#8a3b12").grid(row=11,column=0,columnspan=2,sticky="w")
        routebox.columnconfigure(0,weight=1)
        borebox=ttk.LabelFrame(body,text="4  公開ボーリング証拠（任意）",padding=10);borebox.pack(fill="x",pady=5)
        bore_entry=ttk.Entry(borebox,textvariable=self.borehole_path);bore_entry.grid(row=0,column=0,sticky="ew");self.controls.append(bore_entry)
        browse=ttk.Button(borebox,text="JSONを選択…",command=self.choose_boreholes);browse.grid(row=0,column=1,padx=6);self.controls.append(browse)
        xml_import=ttk.Button(borebox,text="BED0500 XMLを正規化…",command=self.run_bed0500_import);xml_import.grid(row=1,column=0,sticky="w",pady=(7,0));self.controls.append(xml_import)
        kuni_capture=ttk.Button(borebox,text="KuniJiban候補IDの公式XMLを取得…",command=self.run_kunijiban_record_capture);kuni_capture.grid(row=1,column=1,sticky="e",pady=(7,0));self.controls.append(kuni_capture)
        transform_button=ttk.Button(borebox,text="座標変換証拠を適用…",command=self.run_borehole_transform);transform_button.grid(row=9,column=0,sticky="w",pady=(7,0));self.controls.append(transform_button)
        ranking_button=ttk.Button(borebox,text="候補の距離・位置品質を比較…",command=self.run_kunijiban_ranking);ranking_button.grid(row=9,column=1,sticky="e",pady=(7,0));self.controls.append(ranking_button)
        ttk.Label(borebox,text="地域参考として表示する範囲 (m)").grid(row=10,column=0,sticky="w",pady=(7,0))
        context_combo=ttk.Combobox(borebox,textvariable=self.borehole_context_offset,
            values=("500","1000","2000","5000"),state="readonly",width=12)
        context_combo.grid(row=10,column=1,sticky="w",pady=(7,0));self.controls.append(context_combo)
        role_button=ttk.Button(borebox,text="元測線で拘束／地域参考／範囲外を分類",
            command=self.run_borehole_route_role)
        role_button.grid(row=11,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(role_button)
        context_render=ttk.Button(borebox,text="地域参考孔の位置・柱状概要PNG…",
            command=self.run_regional_borehole_context)
        context_render.grid(row=12,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(context_render)
        orientation_template=ttk.Button(borebox,text="地表境界ごとの走向・傾斜入力雛形…",
            command=self.run_contact_orientation_template)
        orientation_template.grid(row=13,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(orientation_template)
        orientation_preview=ttk.Button(borebox,text="入力済み走向・傾斜の診断断面PNG…",
            command=self.run_contact_hypothesis_preview)
        orientation_preview.grid(row=14,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(orientation_preview)
        unit_editor=ttk.Button(borebox,text="岩相単元・共通表記・上下境界を編集…",
            command=self.run_hypothesis_unit_editor)
        unit_editor.grid(row=15,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(unit_editor)
        structure_bind=ttk.Button(borebox,text="構造観測を地質境界へ明示的に割り当て…",
            command=self.run_contact_structural_binding)
        structure_bind.grid(row=16,column=0,columnspan=2,sticky="e",pady=(7,0));self.controls.append(structure_bind)
        ttk.Label(borebox,text="測線からの最大離隔 (m)").grid(row=2,column=0,sticky="w",pady=(7,0))
        offset=ttk.Entry(borebox,textvariable=self.borehole_offset,width=12);offset.grid(row=2,column=1,sticky="w",pady=(7,0));self.controls.append(offset)
        project=ttk.Button(borebox,text="測線へ投影して証拠JSONを作成",command=self.run_borehole_intake);project.grid(row=3,column=0,columnspan=2,sticky="e",pady=(8,0));self.controls.append(project)
        correlate=ttk.Button(borebox,text="投影済みJSONから地層相関を編集…",command=self.open_correlation);correlate.grid(row=3,column=0,sticky="w",pady=(8,0));self.controls.append(correlate)
        section_button=ttk.Button(borebox,text="レビュー済み相関から断面PNG…",command=self.run_reviewed_section);section_button.grid(row=4,column=1,sticky="e",pady=(8,0));self.controls.append(section_button)
        structure_button=ttk.Button(borebox,text="走向・傾斜JSONを測線へ投影…",command=self.run_structural_intake);structure_button.grid(row=4,column=0,sticky="w",pady=(8,0));self.controls.append(structure_button)
        linework_button=ttk.Button(borebox,text="地質図線・断層線を測線と交差…",command=self.run_linework_intake);linework_button.grid(row=5,column=0,sticky="w",pady=(8,0));self.controls.append(linework_button)
        route_candidate=ttk.Button(borebox,text="この孔を通る代替測線を比較…",command=self.propose_evidence_route);route_candidate.grid(row=5,column=1,sticky="e",pady=(8,0));self.controls.append(route_candidate)
        gsj_refine=ttk.Button(borebox,text="GSJ地表遷移区間を精密化…",command=self.run_gsj_refinement);gsj_refine.grid(row=5,column=1,sticky="e",pady=(8,0));self.controls.append(gsj_refine)
        gsj_button=ttk.Button(borebox,text="GSJレビューを接触点へ変換…",command=self.run_gsj_transition_review);gsj_button.grid(row=6,column=1,sticky="e",pady=(8,0));self.controls.append(gsj_button)
        mapped_template=ttk.Button(borebox,text="GSJ正確境界の相関レビュー雛形…",command=self.create_mapped_contact_review);mapped_template.grid(row=7,column=0,sticky="w",pady=(8,0));self.controls.append(mapped_template)
        mapped_execute=ttk.Button(borebox,text="レビュー済み正確境界を変換…",command=self.run_mapped_contact_review);mapped_execute.grid(row=7,column=1,sticky="e",pady=(8,0));self.controls.append(mapped_execute)
        ttk.Label(borebox,text="孔間の地層相関は自動実行しません。観測柱状図と境界位置だけを保存します。",foreground="#8a3b12").grid(row=8,column=0,columnspan=2,sticky="w")
        borebox.columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(body,height=180,bg="#f5f7fa",highlightthickness=0);self.canvas.pack(fill="x",pady=5)
        self.canvas.bind("<Configure>",lambda e:self.preview())
        outbox=ttk.LabelFrame(body,text="5  出力先",padding=10);outbox.pack(fill="x",pady=6)
        entry=ttk.Entry(outbox,textvariable=self.output);entry.pack(side="left",fill="x",expand=True);self.controls.append(entry)
        button=ttk.Button(outbox,text="選択…",command=self.choose_output);button.pack(side="right",padx=(8,0));self.controls.append(button)
        actions=ttk.Frame(body);actions.pack(fill="x",pady=8)
        button=ttk.Button(actions,text="条件を確認・プレビュー",command=lambda:self.preview(True));button.pack(side="left");self.controls.append(button)
        button=ttk.Button(actions,text="検証して中立データを生成",command=self.run);button.pack(side="right");self.controls.append(button)
        self.progress=ttk.Progressbar(body,mode="indeterminate");self.progress.pack(fill="x")
        ttk.Label(body,textvariable=self.status,wraplength=810).pack(anchor="w",pady=6)
        root.protocol("WM_DELETE_WINDOW",self.close)
        self.select_region();root.after(150,self.poll)

    def conditions(self):
        try:c=DrawingConditions(**{k:float(v.get()) for k,v in self.values.items()})
        except ValueError:raise ValueError("全ての条件に数値を入力してください。")
        return c.validate(self.config)

    def select_region(self):
        try:
            self.config,defaults=bundle_details(self.regions[self.region.get()])
            for k,v in asdict(defaults).items():self.values[k].set(str(v))
            lo,hi=self.config["extent"]["minimum"],self.config["extent"]["maximum"]
            self.info.set(f"モデル：X {lo[0]}～{hi[0]}m ／ Y {lo[1]}～{hi[1]}m ／ 標高 {lo[2]}～{hi[2]}m\n地域ID：{self.config['regionalProfileId']}（実地域としての認可はありません）")
            self.preview()
        except Exception as error:self.status.set(str(error))

    def import_bundle(self):
        path=filedialog.askopenfilename(title="地域の実行バンドルJSON",filetypes=[("Run bundle","*.json")])
        if not path:return
        try:
            config,_=bundle_details(path)
            label=f"{config['regionalProfileId']}（読込・未認可）"
            self.regions[label]=Path(path);self.combo.configure(values=list(self.regions));self.region.set(label);self.select_region()
        except Exception as error:messagebox.showerror("読込できません",str(error),parent=self.root)

    def choose_output(self):
        folder=filedialog.askdirectory()
        if folder:self.output.set(folder)

    def choose_boreholes(self):
        path=filedialog.askopenfilename(title="正規化ボーリングJSON",filetypes=[("JSON","*.json")])
        if path:self.borehole_path.set(path)

    def choose_mapped_points(self):
        path=filedialog.askopenfilename(title="ハッシュ検証済み地質点証拠JSON",filetypes=[("JSON","*.json")])
        if path:self.mapped_point_path.set(path)

    def choose_mapped_linework(self):
        path=filedialog.askopenfilename(title="ハッシュ検証済み地質境界・断層線JSON",filetypes=[("JSON","*.json")])
        if path:self.mapped_linework_path.set(path)

    def propose_evidence_route(self):
        source=self.borehole_path.get().strip() or filedialog.askopenfilename(
            title="1孔だけを含む正規化ボーリングJSON",filetypes=[("JSON","*.json")])
        if not source:return
        try:
            from .gui_evidence_route import execute_evidence_route_candidate
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),
                                                   self.route_spacing.get())
            result,target=execute_evidence_route_candidate(route,source,self.output.get())
            blockers=", ".join(result["eligibilityBlockers"]) or "なし"
            message=(f"元測線：{result['originalLengthM']:.0f} m\n"
                     f"候補測線：{result['candidateLengthM']:.0f} m\n"
                     f"追加距離：{result['additionalLengthM']:.0f} m\n"
                     f"経路位相：{result['routeTopologyStatus']}\n"
                     f"証拠採用の阻害条件：{blockers}\n\n"
                     "候補を測線入力欄へ反映しますか？\n"
                     "反映しても証拠の検証状態は変わりません。")
            if messagebox.askyesno("代替測線候補",message,parent=self.root):
                text="\n".join(f"{lon:.10f},{lat:.10f}" for lon,lat in result["candidateRouteLonLat"])
                self.route_entry.delete("1.0","end");self.route_entry.insert("1.0",text)
                self.status.set(f"代替測線候補を入力欄へ反映しました。証拠採用状態は変更していません。\n記録：{target}")
            else:self.status.set(f"元の測線を維持しました。比較記録：{target}")
        except Exception as error:messagebox.showerror("代替測線を作成できません",str(error),parent=self.root)

    def run_bed0500_import(self):
        source=filedialog.askopenfilename(title="BED0500 XML",filetypes=[("BED XML","*.xml"),("All files","*")])
        if not source:return
        crs=simpledialog.askstring("水平座標系","XMLメタデータで確認した水平CRS（例：JGD2011）",parent=self.root)
        if not crs:return
        datum=simpledialog.askstring("標高基準","XML・調査資料で確認した鉛直基準（例：TokyoPeil）",parent=self.root)
        if not datum:return
        source_id=simpledialog.askstring("出典ID","この孔に一意な出典ID",parent=self.root)
        if not source_id:return
        source_url=simpledialog.askstring("出典URL","原XMLまたは公式公開ページのURL",parent=self.root)
        if not source_url:return
        try:
            from .gui_bed0500_import import execute_bed0500_import
            result,target=execute_bed0500_import(source,self.output.get(),horizontal_crs=crs,
                vertical_datum=datum,source_id=source_id,source_url=source_url)
            self.borehole_path.set(str(target))
            self.status.set(f"BED0500 XMLを未検証証拠として正規化しました：{result['recordCount']}孔。\n地質相関への採用には別レビューが必要です。\nJSON：{target}")
        except Exception as error:messagebox.showerror("BED0500 XMLを変換できません",str(error),parent=self.root)

    def open_correlation(self):
        path=filedialog.askopenfilename(title="投影済みボーリングJSON",filetypes=[("JSON","*.json")])
        if not path:return
        try:
            from .gui_correlation_editor import open_correlation_editor
            open_correlation_editor(self.root,path)
        except Exception as error:messagebox.showerror("相関画面を開けません",str(error),parent=self.root)

    def run_reviewed_section(self):
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        intake=filedialog.askopenfilename(title="投影済みボーリングJSON",filetypes=[("JSON","*.json")])
        if not intake:return
        review=filedialog.askopenfilename(title="レビュー済み相関JSON",filetypes=[("JSON","*.json")])
        if not review:return
        structural=None
        if messagebox.askyesno("構造観測","走向・傾斜の投影結果を使って断面を監査しますか？",parent=self.root):
            structural=filedialog.askopenfilename(title="投影済み構造観測JSON",filetypes=[("JSON","*.json")])
            if not structural:return
        linework=None
        if messagebox.askyesno("地質図線","地質接触線・断層線の交差結果を使いますか？",parent=self.root):
            linework=filedialog.askopenfilename(title="測線との地質図線交差JSON",filetypes=[("JSON","*.json")])
            if not linework:return
        fault_evidence=None
        if linework and messagebox.askyesno("断層変位","鉛直落差の証拠JSONを適用しますか？",parent=self.root):
            fault_evidence=filedialog.askopenfilename(title="断層鉛直落差証拠JSON",filetypes=[("JSON","*.json")])
            if not fault_evidence:return
        erosion_fill=None
        if messagebox.askyesno("不整合イベント","侵食面＋若い充填層の証拠JSONを適用しますか？",parent=self.root):
            erosion_fill=filedialog.askopenfilename(title="侵食・充填イベント証拠JSON",filetypes=[("JSON","*.json")])
            if not erosion_fill:return
        qualitative=None
        if messagebox.askyesno("定性的層序","出典結合済みの新旧関係・不整合関係を事前監査しますか？",parent=self.root):
            qualitative=filedialog.askopenfilename(title="定性的層序制約JSON",filetypes=[("JSON","*.json")])
            if not qualitative:return
        try:
            from .gui_reproducible_section import execute_selected_section_inputs
            artifacts={"plan":plan,"boreholeIntake":intake,"correlationReview":review,
              "structuralObservations":structural,"mappedLinework":linework,
              "faultEvidence":fault_evidence,"erosionFill":erosion_fill,
              "qualitativeStratigraphy":qualitative}
            manifest,run,bundle=execute_selected_section_inputs(self.output.get(),artifacts)
            self.status.set(f"再現可能な解釈断面を実行しました：{manifest['decision']}（実地域認可なし）\n実行：{run}\n入力バンドル：{bundle}")
        except Exception as error:messagebox.showerror("断面を生成できません",str(error),parent=self.root)

    def run_structural_intake(self):
        source=filedialog.askopenfilename(title="走向・傾斜観測JSON",filetypes=[("JSON","*.json")])
        if not source:return
        try:
            from .section.borehole_section_intake import validate_projection_offset
            from .gui_structural_intake import execute_structural_intake
            method=("BilinearPixelCentres" if self.terrain_sampling.get()=="双一次（推奨）"
                    else "NearestPixel")
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),
                                                   self.route_spacing.get(),method)
            maximum=validate_projection_offset(self.borehole_offset.get())
            result,target=execute_structural_intake(source,self.output.get(),route,maximum)
            self.status.set(f"構造観測投影完了：採用 {result['projectedCount']}点／離隔外 {result['rejectedCount']}点。\n証拠：{target}")
        except Exception as error:messagebox.showerror("構造観測を投影できません",str(error),parent=self.root)

    def run_linework_intake(self):
        source=filedialog.askopenfilename(title="地質接触線・断層線JSON",filetypes=[("JSON","*.json")])
        if not source:return
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        try:
            from .gui_linework_intake import execute_linework_intake
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),self.route_spacing.get())
            result,target=execute_linework_intake(source,plan,self.output.get(),route)
            self.status.set(f"地質図線交差完了：点交差 {len(result['events'])}件／曖昧重複 {len(result['ambiguities'])}件。\n証拠：{target}")
        except Exception as error:messagebox.showerror("地質図線を処理できません",str(error),parent=self.root)

    def run_gsj_transition_review(self):
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        review=filedialog.askopenfilename(title="レビュー済みGSJ地表遷移JSON",filetypes=[("JSON","*.json")])
        if not review:return
        try:
            from .gui_gsj_transition import execute_gsj_transition_review
            result,target=execute_gsj_transition_review(plan,review,self.output.get())
            self.status.set(f"GSJ地表遷移を接触監査へ変換しました：{len(result['events'])}件。\n位置は点照会間の区間不確実性を保持します。\n証拠：{target}")
        except Exception as error:messagebox.showerror("GSJ遷移を変換できません",str(error),parent=self.root)

    def create_mapped_contact_review(self):
        adjacency=filedialog.askopenfilename(title="GSJ境界両側単元JSON",filetypes=[("JSON","*.json")])
        if not adjacency:return
        correlation=filedialog.askopenfilename(title="レビュー済みボーリング相関JSON",filetypes=[("JSON","*.json")])
        if not correlation:return
        try:
            from .gui_mapped_contact_review import create_mapped_contact_review_template
            result,target=create_mapped_contact_review_template(adjacency,correlation,self.output.get())
            self.status.set(f"正確な地表境界 {len(result['candidates'])}件のレビュー雛形を作成しました。\n自動相関は未実施です。\n雛形：{target}")
        except Exception as error:messagebox.showerror("境界レビュー雛形を作成できません",str(error),parent=self.root)

    def run_mapped_contact_review(self):
        adjacency=filedialog.askopenfilename(title="GSJ境界両側単元JSON",filetypes=[("JSON","*.json")])
        if not adjacency:return
        correlation=filedialog.askopenfilename(title="レビュー済みボーリング相関JSON",filetypes=[("JSON","*.json")])
        if not correlation:return
        review=filedialog.askopenfilename(title="レビュー済み正確境界相関JSON",filetypes=[("JSON","*.json")])
        if not review:return
        try:
            from .gui_mapped_contact_review import execute_mapped_contact_review
            result,target=execute_mapped_contact_review(adjacency,correlation,review,self.output.get())
            self.status.set(f"正確な地表境界を断面接触へ変換しました：採用 {result['review']['usedCount']}件／除外 {result['review']['excludedCount']}件。\n地下への継続は未認可です。\n証拠：{target}")
        except Exception as error:messagebox.showerror("境界レビューを変換できません",str(error),parent=self.root)

    def run_gsj_refinement(self):
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        index=simpledialog.askinteger("遷移番号","精密化するGSJ遷移番号（最初は0）",parent=self.root,minvalue=0)
        if index is None:return
        width=simpledialog.askfloat("目標幅","残す境界区間の最大幅 (m)",parent=self.root,
                                    minvalue=1.0,initialvalue=10.0)
        if width is None:return
        self.set_busy(True);self.status.set("GSJ公式APIへ追加照会し、境界区間を精密化中…")
        def worker():
            try:
                from .gui_gsj_refinement import execute_gsj_refinement
                value=execute_gsj_refinement(plan,index,width,self.output.get())
                self.messages.put(("gsj_refinement",tuple(str(v) if isinstance(v,Path) else v for v in value)))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_borehole_transform(self):
        source=self.last_kunijiban_collection
        if not source:
            source=filedialog.askopenfilename(title="1孔ボーリングコレクション",filetypes=[("JSON","*.json")])
            if not source:return
        transform=filedialog.askopenfilename(title="ハッシュ結合済み座標変換証拠",filetypes=[("JSON","*.json")])
        if not transform:return
        output=self.output.get()
        if not output.strip():
            messagebox.showerror("出力先","出力先を選択してください。",parent=self.root);return
        self.set_busy(True);self.status.set("座標変換証拠のハッシュと対象孔を検証中…")
        def worker():
            try:
                from .gui_borehole_transform import execute_borehole_geographic_transform
                result,target=execute_borehole_geographic_transform(source,transform,output)
                self.messages.put(("borehole_transform",(result,str(target))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def preview(self,notify=False):
        self.canvas.delete("all")
        try:
            c=self.conditions();left,right,top,bottom=65,max(self.canvas.winfo_width(),700)-25,25,145
            def x(v):return left+(v-c.x_start)/(c.x_end-c.x_start)*(right-left)
            def y(v):return bottom-(v-c.elevation_bottom)/(c.elevation_top-c.elevation_bottom)*(bottom-top)
            lo,hi=self.config["extent"]["minimum"],self.config["extent"]["maximum"]
            self.canvas.create_rectangle(left,top,right,bottom,fill="white",outline="#8190a0")
            self.canvas.create_rectangle(x(lo[0]),y(hi[2]),x(hi[0]),y(lo[2]),fill="#d5e5ec",outline="#50859a")
            for v in c.ticks()["horizontalMeters"]:self.canvas.create_line(x(v),bottom,x(v),bottom+4)
            for v in c.ticks()["elevationMeters"]:self.canvas.create_line(left-4,y(v),left,y(v))
            for v in (c.x_start,c.x_end):self.canvas.create_text(x(v),bottom+15,text=f"{v:g} m")
            for v in (c.elevation_bottom,c.elevation_top):self.canvas.create_text(left-8,y(v),anchor="e",text=f"{v:g}")
            self.canvas.create_text((left+right)/2,85,text="青：モデル範囲 ／ 白：余白（外挿なし）\n目盛はプレビュー・設定保存のみ。地層形状のプレビューではありません。",fill="#284452")
            if notify:self.status.set(f"条件OK：幅 {c.x_end-c.x_start:g}m・高さ {c.elevation_top-c.elevation_bottom:g}m。目盛 横{c.horizontal_tick:g}m／縦{c.vertical_tick:g}m")
        except Exception as error:
            self.canvas.create_text(15,30,anchor="w",text=str(error),fill="#a32d2d")
            if notify:self.status.set(str(error))

    def set_busy(self,value):
        self.busy=value
        for widget in self.controls:widget.configure(state="disabled" if value else "normal")
        self.combo.configure(state="disabled" if value else "readonly")
        self.progress.start(15) if value else self.progress.stop()

    def run(self):
        try:
            conditions=self.conditions();bundle=str(self.regions[self.region.get()]);output=self.output.get()
            if not output.strip():raise ValueError("出力先を選択してください。")
        except Exception as error:
            messagebox.showerror("条件を確認してください",str(error),parent=self.root);return
        self.set_busy(True);self.status.set("Stage1～11を検証・計算中…")
        def worker():
            try:self.messages.put(("result",execute_conditions(bundle,output,conditions)))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_plan_preview(self):
        try:
            from .section.borehole_section_intake import validate_projection_offset
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),self.route_spacing.get())
            output=self.output.get()
            if not output.strip():raise ValueError("出力先を選択してください。")
            mapped=self.mapped_point_path.get().strip() or None
            linework=self.mapped_linework_path.get().strip() or None
            maximum=validate_projection_offset(self.mapped_point_offset.get())
        except Exception as error:
            messagebox.showerror("測線を確認してください",str(error),parent=self.root);return
        self.set_busy(True);self.status.set("国土地理院・地質調査総合センターの公開データを取得中…")
        def worker():
            try:
                from .gui_plan_preview import execute_plan_preview
                root=Path(__file__).resolve().parents[3]
                image,evidence,template=execute_plan_preview(root,output,route,mapped,maximum,linework)
                self.messages.put(("plan",(str(image),str(evidence),str(template))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_arbitrary_basic_section(self):
        try:
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),self.route_spacing.get())
            output=self.output.get()
            if not output.strip():raise ValueError("出力先を選択してください。")
            seed=simpledialog.askinteger("乱数シード","基本岩相の乱数シード",parent=self.root,
                                         initialvalue=20260905,minvalue=0,maxvalue=2**32-1)
            if seed is None:return
            contacts="Show" if messagebox.askyesno("岩相境界線","岩相境界線を表示しますか？",parent=self.root) else "Hide"
        except Exception as error:
            messagebox.showerror("測線を確認してください",str(error),parent=self.root);return
        self.set_busy(True);self.status.set("任意測線を計算し、ネイティブDWGを生成・再オープン検証中…")
        def worker():
            try:
                from .gui_arbitrary_basic_section import execute_arbitrary_basic_section
                project_root=Path(__file__).resolve().parents[3]
                result=execute_arbitrary_basic_section(project_root,output,route,seed=seed,contact_lines=contacts)
                self.messages.put(("arbitrary_basic",tuple(map(str,result))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_route_readiness(self):
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        borehole=None
        if messagebox.askyesno("ボーリング証拠","投影済みボーリング証拠も含めますか？",parent=self.root):
            borehole=filedialog.askopenfilename(title="投影済みボーリングJSON",filetypes=[("JSON","*.json")])
            if not borehole:return
        correlation=None
        if borehole and messagebox.askyesno("地層相関","レビュー済みボーリング相関も検証しますか？",parent=self.root):
            correlation=filedialog.askopenfilename(title="レビュー済み地層相関JSON",filetypes=[("JSON","*.json")])
            if not correlation:return
        structural=None
        if messagebox.askyesno("構造観測","投影済み走向・傾斜証拠も含めますか？",parent=self.root):
            structural=filedialog.askopenfilename(title="投影済み構造観測JSON",filetypes=[("JSON","*.json")])
            if not structural:return
        crossings=None
        if messagebox.askyesno("正確な地表境界","地質境界両側判定JSONも含めますか？",parent=self.root):
            crossings=filedialog.askopenfilename(title="地質境界両側判定JSON",filetypes=[("JSON","*.json")])
            if not crossings:return
        output=self.output.get()
        if not output.strip():
            messagebox.showerror("出力先","出力先を選択してください。",parent=self.root);return
        self.set_busy(True);self.status.set("測線の証拠充足度を検証中…")
        def worker():
            try:
                from .gui_route_readiness import (execute_route_readiness,
                                                   execute_route_evidence_workspace)
                result,target=execute_route_readiness(plan,output,borehole,
                    structural_observations_path=structural,
                    mapped_crossings_path=crossings,
                    correlation_review_path=correlation)
                _,workspace=execute_route_evidence_workspace(
                    plan,output,borehole,structural)
                self.messages.put(("readiness",(result,str(target),str(workspace))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_kunijiban_search(self):
        plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
        if not plan:return
        output=self.output.get()
        if not output.strip():
            messagebox.showerror("出力先","出力先を選択してください。",parent=self.root);return
        self.set_busy(True);self.status.set("KuniJiban公式ビューアから測線周辺候補を検索中…")
        self.last_kunijiban_plan=plan
        def worker():
            try:
                from .gui_kunijiban_candidates import execute_kunijiban_candidate_search
                result,target=execute_kunijiban_candidate_search(plan,output)
                self.messages.put(("kunijiban",(result,str(target))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_kunijiban_ranking(self):
        index=self.last_kunijiban_index
        if not index:
            index=filedialog.askopenfilename(title="KuniJiban候補一覧JSON",filetypes=[("JSON","*.json")])
            if not index:return
        output=self.output.get()
        if not output.strip():
            messagebox.showerror("出力先","出力先を選択してください。",parent=self.root);return
        self.last_kunijiban_index=index
        self.set_busy(True);self.status.set("候補XMLの版・距離・取得方法・読取精度を比較中…")
        def worker():
            try:
                from .gui_kunijiban_ranking import execute_kunijiban_candidate_ranking
                result,target=execute_kunijiban_candidate_ranking(index,output)
                self.messages.put(("kunijiban_ranked",(result,str(target))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def _show_kunijiban_table(self,result,target):
        from .gui_kunijiban_ranking import candidate_table_rows
        rows=candidate_table_rows(result)
        dialog=tk.Toplevel(self.root);dialog.title("KuniJiban候補比較（地下断面には未採用）")
        dialog.geometry("1000x520");dialog.transient(self.root)
        ttk.Label(dialog,text="距離・取得方法・宣言精度を分離表示します。順位や選択は地質学的採用を意味しません。",
                  foreground="#8a3b12").pack(anchor="w",padx=10,pady=8)
        columns=("id","distance","name","dtd","method","resolution","crs","depth","label")
        tree=ttk.Treeview(dialog,columns=columns,show="headings",height=18)
        headings=("ID","測線離隔m","孔名","DTD","取得方法","秒精度","測地系","深度m","提供表示")
        widths=(75,90,150,55,165,75,90,70,100)
        for key,label,width in zip(columns,headings,widths):
            tree.heading(key,text=label);tree.column(key,width=width,anchor="center")
        for row in rows:
            tree.insert("", "end", iid=str(row["providerRecordId"]), values=(
                row["providerRecordId"],f'{row["distanceM"]:.1f}',row["boreholeName"],
                row["dtdVersion"],row["coordinateMethod"],
                "-" if row["resolutionArcSeconds"] is None else row["resolutionArcSeconds"],
                row["horizontalCrs"],f'{row["totalDepthM"]:.1f}',row["providerApprovalLabel"] or "-"))
        tree.pack(fill="both",expand=True,padx=10)
        def capture_selected():
            selected=tree.selection()
            if len(selected)!=1:
                messagebox.showerror("候補選択","1孔を選択してください。",parent=dialog);return
            identifier=int(selected[0]);dialog.destroy();self.run_kunijiban_record_capture(identifier)
        ttk.Button(dialog,text="選択した公式XMLを取得",command=capture_selected).pack(anchor="e",padx=10,pady=10)
        self.status.set(f"候補 {len(rows)}孔の比較表を作成しました。全件、地下形状には未採用です。\n順位表：{target}")

    def run_kunijiban_record_capture(self,record_id=None):
        plan=self.last_kunijiban_plan
        index=self.last_kunijiban_index
        if not plan:
            plan=filedialog.askopenfilename(title="平面・地形証拠JSON",filetypes=[("JSON","*.json")])
            if not plan:return
        if not index:
            index=filedialog.askopenfilename(title="KuniJiban候補一覧JSON",filetypes=[("JSON","*.json")])
            if not index:return
        if record_id is None:
            record_id=simpledialog.askinteger("KuniJiban候補","取得するprovider record ID",parent=self.root,minvalue=1)
        if record_id is None:return
        output=self.output.get()
        if not output.strip():
            messagebox.showerror("出力先","出力先を選択してください。",parent=self.root);return
        self.set_busy(True);self.status.set("KuniJiban公式XMLを取得し、未検証候補として正規化中…")
        def worker():
            try:
                from .gui_kunijiban_record import execute_kunijiban_record_capture
                result,xml_path,json_path,collection_path=execute_kunijiban_record_capture(
                    plan,index,record_id,output)
                self.messages.put(("kunijiban_record",(result,str(xml_path),str(json_path),str(collection_path))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_borehole_intake(self):
        try:
            from .section.borehole_section_intake import validate_projection_offset
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),self.route_spacing.get())
            source=self.borehole_path.get();output=self.output.get()
            if not source.strip():raise ValueError("ボーリングJSONを選択してください。")
            if not output.strip():raise ValueError("出力先を選択してください。")
            maximum=validate_projection_offset(self.borehole_offset.get())
        except Exception as error:
            messagebox.showerror("ボーリング条件を確認してください",str(error),parent=self.root);return
        self.set_busy(True);self.status.set("ボーリング証拠を検証し、測線へ投影中…")
        def worker():
            try:
                from .gui_borehole_intake import execute_borehole_intake
                result,target,template=execute_borehole_intake(source,output,route,maximum)
                self.messages.put(("borehole",(result,str(target),str(template))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_borehole_route_role(self):
        try:
            from .section.borehole_section_intake import validate_projection_offset
            route=GeographicRouteConditions.parse(self.route_entry.get("1.0","end"),self.route_spacing.get())
            source=self.borehole_path.get();output=self.output.get()
            if not source.strip():raise ValueError("ボーリングJSONを選択してください。")
            if not output.strip():raise ValueError("出力先を選択してください。")
            constraint=validate_projection_offset(self.borehole_offset.get())
            context=validate_projection_offset(self.borehole_context_offset.get())
            if context<constraint:raise ValueError("地域参考範囲は断面拘束範囲以上にしてください。")
        except Exception as error:
            messagebox.showerror("ボーリング役割条件を確認してください",str(error),parent=self.root);return
        self.set_busy(True);self.status.set("元測線を維持したまま、ボーリングの利用可能範囲を分類中…")
        def worker():
            try:
                from .gui_borehole_route_role import execute_borehole_route_role
                result,target=execute_borehole_route_role(source,route,constraint,context,output)
                self.messages.put(("borehole_role",(result,str(target))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_regional_borehole_context(self):
        plan=filedialog.askopenfilename(title="元測線のplan_evidence_bundle.json",
            filetypes=[("Plan evidence","*.json")])
        if not plan:return
        roles=filedialog.askopenfilename(title="ボーリング役割分類JSON",
            filetypes=[("Borehole roles","*.json")])
        if not roles:return
        source=self.borehole_path.get().strip()
        if not source:
            messagebox.showerror("入力不足","正規化ボーリングJSONを先に選択してください。",parent=self.root);return
        self.set_busy(True);self.status.set("地域参考孔を断面拘束せず、位置・柱状概要を描画中…")
        def worker():
            try:
                from .gui_regional_borehole_context import execute_regional_borehole_context
                result,image,report,combined,evidence=execute_regional_borehole_context(
                    plan,roles,source,self.output.get())
                self.messages.put(("borehole_context",(result,str(image),str(report),
                                                        str(combined) if combined else None,
                                                        str(evidence))))
            except Exception as error:self.messages.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def run_contact_orientation_template(self):
        source=filedialog.askopenfilename(title="測線と地質境界線の交点JSON",
            filetypes=[("Linework intersections","*.json")])
        if not source:return
        try:
            from .gui_contact_orientation_hypothesis import execute_contact_orientation_template
            result,target=execute_contact_orientation_template(source,self.output.get())
            self.status.set(f"地質境界 {len(result['hypotheses'])}点の走向・傾斜入力雛形を作成しました。未入力状態では地下線を生成しません。\n雛形：{target}")
            from .gui_contact_orientation_editor import open_contact_orientation_editor
            open_contact_orientation_editor(self.root,target)
        except Exception as error:
            messagebox.showerror("入力雛形を作成できません",str(error),parent=self.root)

    def run_contact_hypothesis_preview(self):
        plan=filedialog.askopenfilename(title="交点作成時に使ったplan_evidence_bundle.json",filetypes=[("Plan evidence","*.json")])
        if not plan:return
        intersections=filedialog.askopenfilename(title="測線と地質境界線の交点JSON",filetypes=[("Linework intersections","*.json")])
        if not intersections:return
        template=filedialog.askopenfilename(title="編集済み走向・傾斜入力JSON",filetypes=[("Orientation hypotheses","*.json")])
        if not template:return
        declarations=filedialog.askopenfilename(title="岩相単元宣言JSON（未作成ならキャンセルして診断線のみ）",
            filetypes=[("Lithology unit declarations","*.json")])
        try:
            from .gui_contact_hypothesis_preview import execute_contact_hypothesis_preview
            report,image,*_=execute_contact_hypothesis_preview(plan,intersections,template,self.output.get(),declarations or None)
            self.status.set(f"診断断面を生成しました（実地域断面として未認可）。\n入力済み境界：{report['evaluatedContactCount']}／診断岩相単元：{report['diagnosticLithologyUnitCount']}\n画像：{image}")
        except Exception as error:
            messagebox.showerror("診断断面を生成できません",str(error),parent=self.root)

    def run_hypothesis_unit_editor(self):
        template=filedialog.askopenfilename(title="編集済み走向・傾斜入力JSON",filetypes=[("Orientation hypotheses","*.json")])
        if not template:return
        try:
            from .gui_hypothesis_unit_editor import create_and_open_unit_editor
            document,target,_=create_and_open_unit_editor(self.root,template,self.output.get())
            self.status.set(f"岩相単元宣言を作成しました。入力済み境界候補：{len(document['availableContactHypothesisIds'])}\n原典表記と正規化名は別々に保存されます。\n宣言：{target}")
        except Exception as error:messagebox.showerror("岩相単元編集を開始できません",str(error),parent=self.root)

    def run_contact_structural_binding(self):
        plan=filedialog.askopenfilename(title="測線plan evidence",filetypes=[("JSON","*.json")])
        if not plan:return
        intersections=filedialog.askopenfilename(title="地質境界交点",filetypes=[("JSON","*.json")])
        if not intersections:return
        template=filedialog.askopenfilename(title="走向・傾斜入力雛形",filetypes=[("JSON","*.json")])
        if not template:return
        projected=filedialog.askopenfilename(title="投影済み構造観測",filetypes=[("JSON","*.json")])
        if not projected:return
        limit=simpledialog.askfloat("測線方向の適用距離","境界交点と構造観測の測線方向最大距離 (m)",initialvalue=500,minvalue=0,parent=self.root)
        if limit is None:return
        try:
            from .gui_contact_structural_binding import execute_contact_structural_binding
            proposals,path,_=execute_contact_structural_binding(plan,intersections,template,projected,self.output.get(),limit,False)
            count=proposals["uniqueCandidateCount"]
            accept=count>0 and messagebox.askyesno("候補の移送",f"明示的な地質境界対応を持つ一意候補が {count} 件あります。\nEvidenceCandidateとして入力雛形へ移送しますか？\n（実地域認可にはなりません）",parent=self.root)
            accepted_path=None
            if accept:
                proposals,path,accepted_path=execute_contact_structural_binding(plan,intersections,template,projected,self.output.get(),limit,True)
            self.status.set(f"構造観測の境界対応候補：{count}件\n候補記録：{path}"+(f"\n移送済み雛形：{accepted_path}" if accepted_path else ""))
        except Exception as error:messagebox.showerror("構造観測を割り当てできません",str(error),parent=self.root)

    def poll(self):
        try:
            kind,value=self.messages.get_nowait();self.set_busy(False)
            if kind=="error":
                self.status.set("実行エラー："+value);messagebox.showerror("生成できません",value,parent=self.root)
            elif kind=="result":
                result,folder=value
                self.status.set(("生成完了（中立JSON・DWG未生成）" if result["passed"] else "検証で拒否。成功成果物は発行していません。")+f"\n保存先：{folder}")
            elif kind=="plan":
                image,evidence,template=value
                self.status.set(f"現況平面図・地形縦断を生成しました（地下岩相は未認可）。\n画像：{image}\n証拠：{evidence}\n地表遷移レビュー雛形：{template}")
            elif kind=="arbitrary_basic":
                image,model,evidence,contract,dwg,report=value
                self.status.set(f"任意測線のネイティブDWGを生成し、再オープン検証しました（地下は合成仮定・実地域認可なし）。\nDWG：{dwg}\n検証：{report}\n確認画像：{image}\nモデル：{model}\n契約：{contract}\n公開データ証拠：{evidence}")
            elif kind=="gsj_refinement":
                result,artifact,refined,template=value
                bracket=result["refinedBracket"]
                if bracket:
                    self.status.set(f"GSJ地表遷移を幅 {bracket['upperStationM']-bracket['lowerStationM']:.3f}mまで精密化しました（地下境界ではありません）。\n証拠：{artifact}\n精密化plan：{refined}\nレビュー雛形：{template}")
                else:self.status.set(f"精密化停止：{result['refinementStatus']}。曖昧結果はレビューへ昇格しません。\n監査証拠：{artifact}")
            elif kind=="readiness":
                result,target,workspace=value
                if result["sectionGeometryAuthorized"]:
                    message="レビュー済み証拠拘束断面を生成できます。"
                else:
                    message="地下形状は未認可です。地形・地表地質または合成仮説としてのみ生成できます。"
                preview=str(Path(workspace).with_name("route_evidence_section.png"))
                self.status.set(f"{message}\n不足：{', '.join(result['blockingReasons']) or 'なし'}\n判定記録：{target}\n測線証拠ワークスペース：{workspace}\n統合断面プレビュー：{preview}")
            elif kind=="kunijiban":
                result,target=value
                self.last_kunijiban_index=target
                nearest=(result["candidates"][0]["projectionDistanceM"]
                         if result["candidates"] else None)
                distance=(f"最短離隔 {nearest:.1f} m" if nearest is not None else "候補なし")
                self.status.set(f"KuniJiban候補 {result['candidateCount']}孔（{distance}）。全件未検証候補で、地下形状には未採用です。\n候補一覧：{target}")
            elif kind=="kunijiban_ranked":
                result,target=value
                self._show_kunijiban_table(result,target)
            elif kind=="kunijiban_record":
                result,xml_path,json_path,collection_path=value
                screen=result["routeScreening"]
                self.last_kunijiban_collection=collection_path
                self.status.set(f"公式XMLを保存し、{len(result['intervals'])}区間を未検証候補として正規化しました。\n測線離隔：約{screen['projectionDistanceM']:.1f}m。座標変換証拠の適用前なので投影入力には未設定です。\nXML：{xml_path}\n候補JSON：{json_path}\n未変換コレクション：{collection_path}")
            elif kind=="borehole_transform":
                result,target=value
                self.borehole_path.set(target)
                status=("標高拘束可能" if result["sectionConstraintAuthorized"] else
                        "個別孔口標高精度が未検証のため拘束不可")
                self.status.set(f"座標変換証拠を適用しました（{status}）。\n測線投影入力：{target}")
            elif kind=="borehole_role":
                result,target=value
                self.status.set(f"元測線を変更せず分類しました：拘束候補 {result['directConstraintCandidateCount']}孔／地域参考 {result['regionalContextCount']}孔／範囲外 {result['outsideContextCount']}孔。\n地域参考孔の接触面は断面へ投影しません。\n記録：{target}")
            elif kind=="borehole_context":
                result,image,report,combined,evidence=value
                integrated=f"\n平面図統合画像：{combined}" if combined else "\n平面図画像が隣接せず、単独画像のみ生成しました。"
                self.status.set(f"地域参考孔 {result['regionalContextBoreholeCount']}孔の位置・柱状概要を生成しました。断面接触線は0本です。\n画像：{image}{integrated}\n統合証拠：{evidence}\n境界記録：{report}")
            else:
                result,target,template=value
                self.status.set(f"ボーリング投影完了：採用 {result['projectedCount']}孔／離隔外 {result['rejectedByOffsetCount']}孔。\n孔間相関は未実施・地下境界面は未認可。\n証拠：{target}\n相関レビュー雛形：{template}")
        except queue.Empty:pass
        self.root.after(150,self.poll)

    def close(self):
        if self.busy:messagebox.showinfo("処理中","計算完了後に閉じてください。",parent=self.root)
        else:self.root.destroy()

def main():
    root=tk.Tk();ConditionsWindow(root);root.mainloop()

if __name__=="__main__":main()
