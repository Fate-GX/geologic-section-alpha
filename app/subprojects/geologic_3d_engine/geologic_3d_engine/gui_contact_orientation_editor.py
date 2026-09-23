"""Explicit editor for mapped-contact orientation hypotheses."""
import hashlib
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def _digest(document):
    unsigned={k:v for k,v in document.items() if k!="recordSha256"}
    return hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def update_hypothesis_row(document,index,values):
    """Validate one GUI edit and return a newly hash-bound document."""
    result=json.loads(json.dumps(document,ensure_ascii=False))
    if result.get("schemaVersion")!="ContactOrientationHypothesisTemplate-1.0":
        raise ValueError("走向・傾斜入力雛形ではありません。")
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(result.get("hypotheses",[])):
        raise ValueError("編集対象が不正です。")
    basis=values.get("orientationBasis")
    if basis not in {"NeedsInput","SyntheticAssumption","EvidenceCandidate"}:
        raise ValueError("根拠区分が不正です。")
    row=result["hypotheses"][index]
    if basis=="NeedsInput":
        row.update({"orientationBasis":basis,"trueDipDegrees":None,
            "dipDirectionDegrees":None,"angularUncertaintyDegrees":None,
            "lateralSupportM":None,"basisSourceIds":[],
            "interpretationNote":str(values.get("interpretationNote","")).strip(),
            "subsurfaceContinuationAuthorized":False})
    else:
        numbers={key:values.get(key) for key in ("trueDipDegrees","dipDirectionDegrees",
            "angularUncertaintyDegrees","lateralSupportM")}
        try:numbers={key:float(value) for key,value in numbers.items()}
        except (TypeError,ValueError):raise ValueError("角度・不確実性・適用距離には数値が必要です。")
        if (not 0<=numbers["trueDipDegrees"]<90 or
                not 0<=numbers["dipDirectionDegrees"]<360 or
                not 0<=numbers["angularUncertaintyDegrees"]<=90 or
                numbers["trueDipDegrees"]+numbers["angularUncertaintyDegrees"]>=90 or
                numbers["lateralSupportM"]<=0 or
                not all(math.isfinite(v) for v in numbers.values())):
            raise ValueError("角度・不確実性・適用距離が許容範囲外です。")
        sources=[x.strip() for x in str(values.get("basisSourceIds","")).split(",") if x.strip()]
        if basis=="EvidenceCandidate" and not sources:
            raise ValueError("証拠候補には少なくとも1つの出典IDが必要です。")
        row.update({"orientationBasis":basis,**numbers,"basisSourceIds":sources,
            "interpretationNote":str(values.get("interpretationNote","")).strip(),
            "subsurfaceContinuationAuthorized":False})
    result["recordSha256"]=_digest(result)
    return result


class ContactOrientationEditor:
    def __init__(self,parent,template_path):
        self.path=Path(template_path);self.document=json.loads(self.path.read_text(encoding="utf-8"))
        if self.document.get("recordSha256")!=_digest(self.document):raise ValueError("入力雛形のハッシュが一致しません。")
        self.window=tk.Toplevel(parent);self.window.title("地質境界の走向・傾斜入力")
        self.window.geometry("1120x690")
        body=ttk.Frame(self.window,padding=14);body.pack(fill="both",expand=True)
        ttk.Label(body,text="地表境界ごとの地下延長条件",font=("Yu Gothic UI",13,"bold")).pack(anchor="w")
        ttk.Label(body,text="未入力行は地下線を生成しません。合成仮定と証拠候補を区別してください。",
                  foreground="#8a3b12").pack(anchor="w",pady=(2,8))
        columns=("station","elevation","segment","basis","dip","direction","uncertainty","support")
        self.tree=ttk.Treeview(body,columns=columns,show="tree headings",height=12)
        self.tree.heading("#0",text="境界ID");self.tree.column("#0",width=250)
        for key,label,width in (("station","測線m",80),("elevation","地表標高m",85),
            ("segment","区間",50),("basis","根拠区分",145),("dip","真傾斜°",70),
            ("direction","傾斜方向°",75),("uncertainty","±角度°",65),("support","適用距離m",80)):
            self.tree.heading(key,text=label);self.tree.column(key,width=width,anchor="center")
        self.tree.pack(fill="both",expand=True);self.tree.bind("<<TreeviewSelect>>",lambda _:self.load_selected())
        form=ttk.LabelFrame(body,text="選択行を編集",padding=8);form.pack(fill="x",pady=8)
        self.vars={key:tk.StringVar() for key in ("basis","dip","direction","uncertainty","support","sources","note")}
        ttk.Label(form,text="根拠").grid(row=0,column=0,sticky="w")
        ttk.Combobox(form,textvariable=self.vars["basis"],state="readonly",width=20,
            values=("NeedsInput","SyntheticAssumption","EvidenceCandidate")).grid(row=0,column=1,padx=4)
        for col,(key,label,width) in enumerate((("dip","真傾斜°",9),("direction","傾斜方向°",10),
                ("uncertainty","±角度°",9),("support","適用距離m",10)),start=2):
            ttk.Label(form,text=label).grid(row=0,column=col*2-2,sticky="e")
            ttk.Entry(form,textvariable=self.vars[key],width=width).grid(row=0,column=col*2-1,padx=4)
        ttk.Label(form,text="出典ID（カンマ区切り）").grid(row=1,column=0,sticky="w",pady=(7,0))
        ttk.Entry(form,textvariable=self.vars["sources"],width=45).grid(row=1,column=1,columnspan=3,sticky="ew",pady=(7,0))
        ttk.Label(form,text="解釈メモ").grid(row=1,column=4,sticky="e",pady=(7,0))
        ttk.Entry(form,textvariable=self.vars["note"],width=42).grid(row=1,column=5,columnspan=3,sticky="ew",pady=(7,0))
        ttk.Button(form,text="選択行へ適用",command=self.apply).grid(row=2,column=6,pady=(8,0))
        ttk.Button(form,text="別名で保存…",command=self.save).grid(row=2,column=7,pady=(8,0))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index,row in enumerate(self.document["hypotheses"]):
            show=lambda key:"" if row.get(key) is None else str(row[key])
            self.tree.insert("","end",iid=str(index),text=row["featureId"],values=(
                f"{row['anchorStationM']:.2f}",f"{row['anchorElevationM']:.2f}",row.get("routeSegmentIndex",""),
                row["orientationBasis"],show("trueDipDegrees"),show("dipDirectionDegrees"),
                show("angularUncertaintyDegrees"),show("lateralSupportM")))

    def load_selected(self):
        selected=self.tree.selection()
        if not selected:return
        row=self.document["hypotheses"][int(selected[0])]
        mapping={"basis":"orientationBasis","dip":"trueDipDegrees","direction":"dipDirectionDegrees",
                 "uncertainty":"angularUncertaintyDegrees","support":"lateralSupportM","note":"interpretationNote"}
        for target,source in mapping.items():self.vars[target].set("" if row.get(source) is None else str(row[source]))
        self.vars["sources"].set(", ".join(row.get("basisSourceIds",[])))

    def apply(self):
        selected=self.tree.selection()
        if not selected:return messagebox.showerror("選択不足","編集する境界を選択してください。",parent=self.window)
        values={"orientationBasis":self.vars["basis"].get(),"trueDipDegrees":self.vars["dip"].get(),
            "dipDirectionDegrees":self.vars["direction"].get(),"angularUncertaintyDegrees":self.vars["uncertainty"].get(),
            "lateralSupportM":self.vars["support"].get(),"basisSourceIds":self.vars["sources"].get(),
            "interpretationNote":self.vars["note"].get()}
        try:self.document=update_hypothesis_row(self.document,int(selected[0]),values);self.refresh()
        except Exception as error:messagebox.showerror("適用できません",str(error),parent=self.window)

    def save(self):
        path=filedialog.asksaveasfilename(parent=self.window,title="走向・傾斜候補JSON",defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:
            Path(path).write_text(json.dumps(self.document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            messagebox.showinfo("保存しました",path,parent=self.window)


def open_contact_orientation_editor(parent,template_path):
    return ContactOrientationEditor(parent,template_path)
