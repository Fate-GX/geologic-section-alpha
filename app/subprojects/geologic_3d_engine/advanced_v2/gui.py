"""Progressive-disclosure GUI for Advanced V2 native-DWG generation."""
from __future__ import annotations
import os,queue,sys,threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from nationwide_pipeline import run_advanced_japan_section
from map_location_selector import open_gsi_route_selector
from route_request import AdvancedJapanSectionRequest
from gui_progressive_disclosure import DisclosureState,audit_information_architecture
GUI_INFORMATION_ARCHITECTURE=audit_information_architecture()

class AdvancedWindow:
    def __init__(self,root,*,project_root=None,output_directory=None,runner=None):
        self.root=root;self.busy=False;self.mailbox=queue.Queue();self.disclosure=DisclosureState();self.project_root=HERE.parents[2]
        if project_root is not None:self.project_root=Path(project_root).resolve()
        self.runner=runner or run_advanced_japan_section;self.result_paths={}
        root.title("高度拡張 v2 — 日本任意地点・合成地質断面DWG");root.geometry("800x720");root.minsize(720,600)
        shell=tk.Canvas(root,highlightthickness=0);bar=ttk.Scrollbar(root,orient="vertical",command=shell.yview)
        shell.configure(yscrollcommand=bar.set);bar.pack(side="right",fill="y");shell.pack(side="left",fill="both",expand=True)
        frame=ttk.Frame(shell,padding=18);window=shell.create_window((0,0),window=frame,anchor="nw")
        frame.bind("<Configure>",lambda e:shell.configure(scrollregion=shell.bbox("all")))
        shell.bind("<Configure>",lambda e:shell.itemconfigure(window,width=e.width))
        shell.bind_all("<MouseWheel>",lambda e:shell.yview_scroll(int(-e.delta/120),"units"))
        ttk.Label(frame,text="高度拡張 v2：証拠を区別する地質断面DWG",font=("Yu Gothic UI",17,"bold")).pack(anchor="w")
        ttk.Label(frame,text="基本版とは分離。地下は証拠拘束または明示した合成仮説で、設計利用不可。",foreground="#8a3b12",wraplength=750).pack(anchor="w",pady=(4,14))
        self.values={"spacing":tk.StringVar(value="10"),"seed":tk.StringVar(value="20260908")}
        self.route_points=None;self.controls=[]
        location=ttk.LabelFrame(frame,text="1  地域と測線",padding=10);location.pack(fill="x",pady=4)
        self.location_note=tk.StringVar(value="地図上で始点A・終点Bを指定してください。代表点からは生成しません。")
        self.endpoint_text=tk.StringVar(value="A：未指定\nB：未指定")
        self.map_button=ttk.Button(location,text="地図で始点A・終点Bを指定…",command=self.choose_on_map)
        self.map_button.grid(row=0,column=0,sticky="w",pady=5);self.controls.append(self.map_button)
        ttk.Label(location,textvariable=self.endpoint_text).grid(row=1,column=0,sticky="w",pady=6)
        ttk.Label(location,textvariable=self.location_note,wraplength=700,foreground="#38556b").grid(row=2,column=0,sticky="w")
        toggle=ttk.Frame(frame);toggle.pack(fill="x",pady=4)
        self.toggle_button=ttk.Button(toggle,text=self.disclosure.button_text,command=self.toggle_advanced);self.toggle_button.pack(side="left");self.controls.append(self.toggle_button)
        self.advanced_help=tk.StringVar(value=self.disclosure.help_text);ttk.Label(toggle,textvariable=self.advanced_help).pack(side="left",padx=10);root.bind("<Alt-d>",lambda e:self.toggle_advanced())
        self.advanced_host=ttk.Frame(frame);self.advanced_host.pack(fill="x")
        self.advanced=ttk.LabelFrame(self.advanced_host,text="詳細：計算・図面設定",padding=10)
        self.contacts=tk.StringVar(value="表示する");self.density=tk.StringVar(value="標準");self.png=tk.BooleanVar(value=True)
        for row,(key,label) in enumerate((("spacing","DEM標本間隔 (m)"),("seed","乱数シード"))):
            ttk.Label(self.advanced,text=label).grid(row=row,column=0,sticky="w",pady=5)
            entry=ttk.Entry(self.advanced,textvariable=self.values[key]);entry.grid(row=row,column=1,sticky="ew");self.controls.append(entry)
        ttk.Label(self.advanced,text="岩相区分線").grid(row=2,column=0,sticky="w",pady=5)
        self.contact_box=ttk.Combobox(self.advanced,textvariable=self.contacts,values=("表示する","表示しない"),state="readonly");self.contact_box.grid(row=2,column=1,sticky="ew");self.controls.append(self.contact_box)
        ttk.Label(self.advanced,text="図面目盛の密度").grid(row=3,column=0,sticky="w",pady=5)
        self.density_box=ttk.Combobox(self.advanced,textvariable=self.density,values=("簡潔","標準","詳細"),state="readonly");self.density_box.grid(row=3,column=1,sticky="ew");self.controls.append(self.density_box)
        png_box=ttk.Checkbutton(self.advanced,text="PNGを副成果物として保持",variable=self.png);png_box.grid(row=4,column=1,sticky="w",pady=5);self.controls.append(png_box);self.advanced.columnconfigure(1,weight=1)
        output_box=ttk.LabelFrame(frame,text="2  出力と生成",padding=10);output_box.pack(fill="x",pady=4)
        self.output=tk.StringVar(value=str(output_directory or self.project_root/"research/geologic_dwg_generation/outputs/advanced_v2_runs"))
        ttk.Label(output_box,text="実行記録の保存先").grid(row=0,column=0,sticky="w")
        out=ttk.Entry(output_box,textvariable=self.output);out.grid(row=0,column=1,sticky="ew",padx=6);self.controls.append(out)
        browse=ttk.Button(output_box,text="選択…",command=lambda:self.output.set(filedialog.askdirectory(parent=root) or self.output.get()));browse.grid(row=0,column=2);self.controls.append(browse)
        self.run_button=ttk.Button(output_box,text="検証してネイティブDWGを生成",command=self.run);self.run_button.grid(row=1,column=1,sticky="e",pady=(12,0));self.controls.append(self.run_button);output_box.columnconfigure(1,weight=1)
        self.progress=ttk.Progressbar(frame,mode="indeterminate");self.progress.pack(fill="x",pady=(10,2))
        self.status=tk.StringVar(value="準備完了：条件を確認して生成してください。");ttk.Label(frame,textvariable=self.status,wraplength=750).pack(anchor="w",pady=6)
        result_bar=ttk.Frame(frame);result_bar.pack(fill="x",pady=6)
        self.result_buttons={}
        for kind,label in (("dwg","DWGを開く"),("preview","画像を開く"),("report","検査結果を開く"),("folder","保存先を開く")):
            button=ttk.Button(result_bar,text=label,state="disabled",command=lambda k=kind:self.open_result(k))
            button.pack(side="left",padx=3);self.result_buttons[kind]=button
        self.map_button.focus_set();root.after(150,self.poll)
    def accept_map_route(self,start,end,elevations=None):
        request=AdvancedJapanSectionRequest.from_endpoints(start,end)
        self.route_points=(tuple(start),tuple(end))
        self.endpoint_text.set("\n".join(f"{label}：緯度 {point[1]:.8f}° ／ 経度 {point[0]:.8f}°" for label,point in zip("AB",self.route_points)))
        self.location_note.set(f"A → B：{request.length_m:.2f} m ／ 方位角 {request.azimuth_degrees:.2f}°（北=0°）。図面左=A、右=B。")
    def choose_on_map(self):
        if self.busy:return
        center=(138.0,36.0) # Initial map viewport only; never a generated route.
        if self.route_points:
            request=AdvancedJapanSectionRequest.from_endpoints(*self.route_points)
            center=(request.center_longitude,request.center_latitude)
        open_gsi_route_selector(self.root,*center,self.accept_map_route,points=self.route_points)
    def toggle_advanced(self):
        if self.busy:return
        self.disclosure=self.disclosure.toggled();self.toggle_button.configure(text=self.disclosure.button_text);self.advanced_help.set(self.disclosure.help_text)
        self.advanced.pack(fill="x",pady=4) if self.disclosure.expanded else self.advanced.pack_forget()
    def set_busy(self,busy):
        self.busy=busy
        for widget in self.controls:
            if busy:
                try:widget._prior_state=str(widget.cget("state"))
                except tk.TclError:widget._prior_state="normal"
                widget.configure(state="disabled")
            else:widget.configure(state=getattr(widget,"_prior_state","normal"))
        self.progress.start(14) if busy else self.progress.stop()
    def run(self):
        try:
            if not self.route_points:raise ValueError("地図で始点A・終点Bの二点を指定してください")
            request=AdvancedJapanSectionRequest.from_endpoints(*self.route_points,
                sample_spacing_m=float(self.values["spacing"].get()),seed=int(self.values["seed"].get()),
                contact_lines="Show" if self.contacts.get()=="表示する" else "Hide",png_preview=bool(self.png.get()),
                drafting_density={"簡潔":"Compact","標準":"Standard","詳細":"Detailed"}[self.density.get()])
            if not self.output.get().strip():raise ValueError("保存先を入力してください")
        except Exception as error:messagebox.showerror("入力条件",str(error),parent=self.root);return
        destination=self.output.get();self.result_paths={}
        for button in self.result_buttons.values():button.configure(state="disabled")
        self.set_busy(True);self.status.set("処理中：公開データ取得→地質区判定→合成→規格監査→DWG再オープン検証")
        def worker():
            try:self.mailbox.put((True,self.runner(self.project_root,request,destination)))
            except Exception as error:self.mailbox.put((False,str(error)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            ok,result=self.mailbox.get_nowait();self.set_busy(False)
            if not ok:self.status.set("失敗：成果物を承認していません。");messagebox.showerror("生成失敗",result,parent=self.root)
            elif not result.get("passed"):
                self.status.set("拒否：地質区または検証ゲートを通過できません。\n"+str(result.get("reason")))
                if result.get("refusalPath"):self.result_paths={"report":result["refusalPath"],"folder":str(Path(result["refusalPath"]).parent)}
            else:
                dwg=next(v["path"] for v in result["artifacts"] if v["path"].lower().endswith(".dwg"));self.status.set(f"成功：ネイティブDWG生成・再オープン検証完了。\nDWG：{dwg}\n記録：{result['manifestPath']}")
                self.result_paths={"dwg":dwg,"report":result["manifestPath"],"folder":str(Path(result["manifestPath"]).parent)}
                preview=next((v["path"] for v in result["artifacts"] if v["path"].endswith("section_preview.png")),None)
                if preview:self.result_paths["preview"]=preview
            for kind,button in self.result_buttons.items():button.configure(state="normal" if kind in self.result_paths else "disabled")
        except queue.Empty:pass
        self.root.after(150,self.poll)
    def open_result(self,kind):
        path=self.result_paths.get(kind)
        if path and Path(path).exists():os.startfile(path)
def main():
    root=tk.Tk();AdvancedWindow(root);root.mainloop()
if __name__=="__main__":main()
