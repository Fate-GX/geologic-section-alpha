"""Editor and strict backend for diagnostic lithology-unit declarations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


TERM_STATUSES={"Current","Legacy","LocalRelativeUnit","DerivedDisplayLabel","Unverified","Deprecated"}
EVIDENCE_STATUSES={"SyntheticAssumption","EvidenceCandidate"}


def _digest(document):
    unsigned={k:v for k,v in document.items() if k!="recordSha256"}
    return hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def build_unit_declaration_document(orientation_template):
    if orientation_template.get("schemaVersion")!="ContactOrientationHypothesisTemplate-1.0":
        raise ValueError("走向・傾斜入力雛形ではありません。")
    if orientation_template.get("recordSha256")!=_digest(orientation_template):
        raise ValueError("走向・傾斜入力雛形のハッシュが一致しません。")
    contacts=[row["hypothesisId"] for row in orientation_template.get("hypotheses",[])
              if row.get("orientationBasis")!="NeedsInput"]
    result={"schemaVersion":"HypothesisLithologyUnitDeclarations-1.0",
        "orientationTemplateSha256":orientation_template["recordSha256"],
        "availableContactHypothesisIds":contacts,"declarations":[],
        "terminologyBoundary":"Source wording is preserved separately from normalized display terminology",
        "authorizationBoundary":"EditableDiagnosticDeclarations_NoRealRegionAuthorization"}
    result["recordSha256"]=_digest(result);return result


def add_or_update_unit(document,index,values):
    result=json.loads(json.dumps(document,ensure_ascii=False))
    if result.get("schemaVersion")!="HypothesisLithologyUnitDeclarations-1.0" or result.get("recordSha256")!=_digest(result):
        raise ValueError("岩相単元宣言ファイルが不正です。")
    declarations=result.get("declarations");contacts=set(result.get("availableContactHypothesisIds",[]))
    required=("unitId","sourceLabel","sourceYear","sourceAuthority","normalizedLabel",
              "normalizationAuthority","vocabularyVersion","termStatus","normalizationNote",
              "evidenceStatus","topBoundary","bottomBoundary")
    row={key:str(values.get(key,"")).strip() for key in required}
    if any(not row[k] for k in required):raise ValueError("岩相名・用語典拠・上下境界をすべて入力してください。")
    if row["termStatus"] not in TERM_STATUSES:raise ValueError("用語状態が不正です。")
    if row["evidenceStatus"] not in EVIDENCE_STATUSES:raise ValueError("根拠区分が不正です。")
    if row["topBoundary"]!="Terrain" and row["topBoundary"] not in contacts:
        raise ValueError("上面境界が入力済み接触面にありません。")
    if row["bottomBoundary"] not in contacts:raise ValueError("下面境界が入力済み接触面にありません。")
    if row["topBoundary"]==row["bottomBoundary"]:raise ValueError("上面と下面に同じ境界は使えません。")
    if any(x.get("unitId")==row["unitId"] for i,x in enumerate(declarations) if i!=index):
        raise ValueError("岩相単元IDは重複できません。")
    row["topBoundary"]={"type":"Terrain"} if row["topBoundary"]=="Terrain" else {"type":"Contact","hypothesisId":row["topBoundary"]}
    row["bottomBoundary"]={"type":"Contact","hypothesisId":row["bottomBoundary"]}
    row["sectionGeometryAuthorized"]=False
    if index is None:declarations.append(row)
    elif isinstance(index,int) and 0<=index<len(declarations):declarations[index]=row
    else:raise ValueError("編集対象が不正です。")
    result["recordSha256"]=_digest(result);return result


def remove_unit(document,index):
    result=json.loads(json.dumps(document,ensure_ascii=False))
    if result.get("recordSha256")!=_digest(result):raise ValueError("岩相単元宣言のハッシュが一致しません。")
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(result.get("declarations",[])):
        raise ValueError("削除対象が不正です。")
    result["declarations"].pop(index);result["recordSha256"]=_digest(result);return result


class HypothesisUnitEditor:
    fields=(("unitId","単元ID"),("sourceLabel","原典表記"),("sourceYear","原典年"),
        ("sourceAuthority","原典機関"),("normalizedLabel","正規化表示名"),
        ("normalizationAuthority","正規化機関"),("vocabularyVersion","語彙版"),
        ("normalizationNote","正規化注記"))
    def __init__(self,parent,document_path):
        self.path=Path(document_path);self.document=json.loads(self.path.read_text(encoding="utf-8"))
        if self.document.get("recordSha256")!=_digest(self.document):raise ValueError("宣言ファイルのハッシュが一致しません。")
        self.window=tk.Toplevel(parent);self.window.title("岩相単元・用語・上下境界の編集");self.window.geometry("1100x720")
        frame=ttk.Frame(self.window,padding=12);frame.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(frame,columns=("id","source","normalized","top","bottom"),show="headings",height=9)
        for key,label in zip(("id","source","normalized","top","bottom"),("ID","原典表記","正規化名","上面","下面")):
            self.tree.heading(key,text=label);self.tree.column(key,width=180)
        self.tree.pack(fill="x");self.vars={k:tk.StringVar() for k,_ in self.fields}
        form=ttk.Frame(frame);form.pack(fill="x",pady=10)
        for i,(key,label) in enumerate(self.fields):
            ttk.Label(form,text=label).grid(row=i//2,column=(i%2)*2,sticky="w",padx=4,pady=3)
            ttk.Entry(form,textvariable=self.vars[key],width=34).grid(row=i//2,column=(i%2)*2+1,sticky="ew",padx=4,pady=3)
        self.term=tk.StringVar(value="Current");self.evidence=tk.StringVar(value="SyntheticAssumption")
        self.top=tk.StringVar(value="Terrain");self.bottom=tk.StringVar()
        contacts=self.document.get("availableContactHypothesisIds",[])
        for col,(label,var,choices) in enumerate((("用語状態",self.term,sorted(TERM_STATUSES)),("根拠区分",self.evidence,sorted(EVIDENCE_STATUSES)),
                ("上面",self.top,["Terrain"]+contacts),("下面",self.bottom,contacts))):
            ttk.Label(form,text=label).grid(row=5,column=col*2,sticky="w",padx=4,pady=3)
            ttk.Combobox(form,textvariable=var,values=choices,state="readonly",width=27).grid(row=5,column=col*2+1,sticky="w",padx=4,pady=3)
        buttons=ttk.Frame(frame);buttons.pack(fill="x")
        ttk.Button(buttons,text="単元を追加",command=self.add).pack(side="left")
        ttk.Button(buttons,text="選択単元を削除",command=self.remove).pack(side="left",padx=6)
        ttk.Button(buttons,text="別名で保存…",command=self.save_as).pack(side="right")
        self.refresh()
    def values(self):
        result={k:v.get() for k,v in self.vars.items()};result.update(termStatus=self.term.get(),evidenceStatus=self.evidence.get(),topBoundary=self.top.get(),bottomBoundary=self.bottom.get());return result
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.document["declarations"]):
            top=row["topBoundary"].get("hypothesisId","Terrain");bottom=row["bottomBoundary"]["hypothesisId"]
            self.tree.insert("", "end",iid=str(i),values=(row["unitId"],row["sourceLabel"],row["normalizedLabel"],top,bottom))
    def add(self):
        try:self.document=add_or_update_unit(self.document,None,self.values());self.refresh()
        except Exception as error:messagebox.showerror("追加できません",str(error),parent=self.window)
    def remove(self):
        selected=self.tree.selection()
        if selected:
            self.document=remove_unit(self.document,int(selected[0]));self.refresh()
    def save_as(self):
        target=filedialog.asksaveasfilename(parent=self.window,defaultextension=".json",filetypes=[("JSON","*.json")])
        if target:Path(target).write_text(json.dumps(self.document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def create_and_open_unit_editor(parent,orientation_template_path,output_parent):
    source=Path(orientation_template_path);template=json.loads(source.read_text(encoding="utf-8"))
    document=build_unit_declaration_document(template)
    output=Path(output_parent).resolve()/"contact_orientation_hypotheses";output.mkdir(parents=True,exist_ok=True)
    target=output/"hypothesis_lithology_unit_declarations.json"
    target.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return document,target,HypothesisUnitEditor(parent,target)
