"""Small explicit borehole-correlation editor; no automatic label matching."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .section.borehole_correlation import create_correlation_review


class CorrelationEditor:
    def __init__(self,parent,intake_path):
        self.path=Path(intake_path);self.intake=json.loads(self.path.read_text(encoding="utf-8"))
        self.units=[];self.used=set();self.rows={}
        self.window=tk.Toplevel(parent);self.window.title("ボーリング地層相関レビュー");self.window.geometry("980x680")
        body=ttk.Frame(self.window,padding=14);body.pack(fill="both",expand=True)
        ttk.Label(body,text="同じ地層と判断した区間を3孔以上から選択し、下位層から追加してください。",font=("Yu Gothic UI",12,"bold")).pack(anchor="w")
        ttk.Label(body,text="岩相名の一致だけでは相関しません。選択そのものが解釈記録になります。",foreground="#8a3b12").pack(anchor="w",pady=(2,8))
        self.tree=ttk.Treeview(body,columns=("station","offset","index","source","normalized","top","bottom"),show="tree headings",selectmode="extended",height=15)
        self.tree.heading("#0",text="ボーリングID")
        for key,label,width in (("station","測線m",75),("offset","離隔m",75),("index","区間",50),("source","原記載",130),("normalized","正規化岩相",150),("top","上端標高",80),("bottom","下端標高",80)):
            self.tree.heading(key,text=label);self.tree.column(key,width=width,anchor="center")
        self.tree.column("#0",width=120);self.tree.pack(fill="both",expand=True)
        for hole in self.intake.get("boreholes",[]):
            if hole.get("projectionState")!="Projected":continue
            for interval in hole["intervals"]:
                key=(hole["boreholeId"],interval["intervalIndex"]);iid=f"{len(self.rows)}"
                self.rows[iid]=(key,interval)
                self.tree.insert("", "end",iid=iid,text=hole["boreholeId"],values=(f"{hole['stationM']:.1f}",f"{hole['projectionDistanceM']:.1f}",interval["intervalIndex"],interval["sourceLabel"],interval["normalizedLithology"],f"{interval['topElevationM']:.2f}",f"{interval['bottomElevationM']:.2f}"))
        form=ttk.Frame(body);form.pack(fill="x",pady=8)
        self.unit_id=tk.StringVar();self.lithology=tk.StringVar()
        ttk.Label(form,text="単元ID").pack(side="left");ttk.Entry(form,textvariable=self.unit_id,width=18).pack(side="left",padx=5)
        ttk.Label(form,text="正規化岩相").pack(side="left");ttk.Entry(form,textvariable=self.lithology,width=22).pack(side="left",padx=5)
        ttk.Button(form,text="選択区間を次の上位単元として追加",command=self.add_unit).pack(side="right")
        self.unit_list=tk.Listbox(body,height=5);self.unit_list.pack(fill="x")
        meta=ttk.Frame(body);meta.pack(fill="x",pady=8)
        self.correlation_id=tk.StringVar(value="CORRELATION-001");self.reviewer=tk.StringVar()
        ttk.Label(meta,text="相関ID").grid(row=0,column=0);ttk.Entry(meta,textvariable=self.correlation_id,width=24).grid(row=0,column=1,padx=5)
        ttk.Label(meta,text="レビュー担当者").grid(row=0,column=2);ttk.Entry(meta,textvariable=self.reviewer,width=28).grid(row=0,column=3,padx=5)
        ttk.Button(meta,text="レビューJSONを保存…",command=self.save).grid(row=0,column=4,padx=(20,0))

    def add_unit(self):
        try:
            selected=list(self.tree.selection())
            if len(selected)<3:raise ValueError("異なる3孔以上の区間を選択してください。")
            unit_id=self.unit_id.get().strip();lithology=self.lithology.get().strip()
            if not unit_id or not lithology:raise ValueError("単元IDと正規化岩相を入力してください。")
            chosen=[self.rows[i] for i in selected]
            keys=[row[0] for row in chosen]
            if len({k[0] for k in keys})!=len(keys):raise ValueError("同じ単元には1孔から1区間だけ選択できます。")
            if any(k in self.used for k in keys):raise ValueError("既に別単元へ登録された区間があります。")
            if any(row[1]["normalizedLithology"]!=lithology for row in chosen):raise ValueError("入力した正規化岩相と選択区間が一致しません。")
            unit={"unitId":unit_id,"normalizedLithology":lithology,
                  "members":[{"boreholeId":k[0],"intervalIndex":k[1]} for k in keys]}
            self.units.append(unit);self.used.update(keys)
            self.unit_list.insert("end",f"{len(self.units)}（下→上） {unit_id} / {lithology} / {len(keys)}孔")
            self.unit_id.set("");self.lithology.set("")
        except Exception as error:messagebox.showerror("追加できません",str(error),parent=self.window)

    def save(self):
        try:review=create_correlation_review(self.intake,self.correlation_id.get(),self.reviewer.get(),self.units)
        except Exception as error:messagebox.showerror("保存できません",str(error),parent=self.window);return
        path=filedialog.asksaveasfilename(parent=self.window,title="相関レビューJSON",defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:
            Path(path).write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8")
            messagebox.showinfo("保存しました",path,parent=self.window)


def open_correlation_editor(parent,intake_path):
    return CorrelationEditor(parent,intake_path)
