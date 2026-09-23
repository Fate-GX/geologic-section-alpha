"""Small GUI and testable backend for the separated basic-section MVP."""
from __future__ import annotations
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .image_preview import export_image

EXAMPLES=Path(__file__).resolve().parents[1]/"examples"
CATALOG=EXAMPLES/"basic_section_regions.json"

def load_basic_section_regions(path=CATALOG):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schemaVersion")!="BasicSectionRegionCatalog-1.0" or not data.get("regions"):
        raise ValueError("基本断面の地域カタログが不正です。")
    result={}
    for row in data["regions"]:
        label=row.get("label");profile=(Path(path).parent/row.get("profile","")).resolve()
        if not label or label in result or not profile.is_file():raise ValueError("地域定義が不正です。")
        result[label]={"profile":profile,"defaults":row["defaults"]}
    return result

def execute_basic_section_preview(output_parent,region_record,*,seed,distance_end,elevation_bottom,
                                  elevation_top,horizontal_tick,vertical_tick,contact_lines):
    target=export_image(output_parent,seed,distance_end=distance_end,elevation_bottom=elevation_bottom,
      elevation_top=elevation_top,horizontal_tick=horizontal_tick,vertical_tick=vertical_tick,
      contact_lines=contact_lines,profile_path=region_record["profile"])
    return target,target.with_name("model.json")

def open_basic_section_window(parent):
    regions=load_basic_section_regions();window=tk.Toplevel(parent);window.title("基本岩相断面 - 分離MVP")
    window.geometry("650x520");frame=ttk.Frame(window,padding=18);frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="地形と岩相を別々に計算する基本断面",font=("Yu Gothic UI",16,"bold")).grid(row=0,column=0,columnspan=2,sticky="w")
    ttk.Label(frame,text="合成仮定・実地下構造ではありません。高度計算モジュールは未使用です。",
              foreground="#8a3b12").grid(row=1,column=0,columnspan=2,sticky="w",pady=(4,14))
    region=tk.StringVar(value=next(iter(regions)));seed=tk.StringVar(value="20260905")
    values={k:tk.StringVar() for k in ("distanceEndM","elevationBottomM","elevationTopM","horizontalTickM","verticalTickM")}
    contacts=tk.StringVar(value="表示する");output=tk.StringVar(value=str(EXAMPLES.parent/"outputs/basic_section_previews"))
    status=tk.StringVar(value="条件を選んでPNGを生成してください。")
    ttk.Label(frame,text="地域プロファイル").grid(row=2,column=0,sticky="w",pady=5)
    combo=ttk.Combobox(frame,textvariable=region,values=list(regions),state="readonly",width=43);combo.grid(row=2,column=1,sticky="ew")
    labels=(("seed","乱数シード"),("distanceEndM","横方向の表示上限 (m)"),("elevationBottomM","標高下端 (m)"),
            ("elevationTopM","標高上端 (m)"),("horizontalTickM","横目盛間隔 (m)"),("verticalTickM","縦目盛間隔 (m)"))
    widgets=[]
    for i,(key,label) in enumerate(labels,3):
        ttk.Label(frame,text=label).grid(row=i,column=0,sticky="w",pady=5)
        variable=seed if key=="seed" else values[key]
        entry=ttk.Entry(frame,textvariable=variable,width=22);entry.grid(row=i,column=1,sticky="w");widgets.append(entry)
    ttk.Label(frame,text="岩相境界線").grid(row=9,column=0,sticky="w",pady=5)
    boundary=ttk.Combobox(frame,textvariable=contacts,values=("表示する","表示しない"),state="readonly",width=20);boundary.grid(row=9,column=1,sticky="w")
    ttk.Label(frame,text="出力先").grid(row=10,column=0,sticky="w",pady=5)
    out=ttk.Entry(frame,textvariable=output);out.grid(row=10,column=1,sticky="ew")
    ttk.Button(frame,text="選択…",command=lambda: output.set(filedialog.askdirectory(parent=window) or output.get())).grid(row=10,column=2,padx=5)
    def apply_defaults(*_):
        for key,value in regions[region.get()]["defaults"].items():values[key].set(str(value))
    combo.bind("<<ComboboxSelected>>",apply_defaults);apply_defaults()
    mailbox=queue.Queue()
    def run():
        try:
            options={k:float(v.get()) for k,v in values.items()};numeric_seed=int(seed.get())
            if str(numeric_seed)!=seed.get().strip():raise ValueError
        except ValueError:
            messagebox.showerror("入力エラー","シードは整数、図面条件は数値で入力してください。",parent=window);return
        button.configure(state="disabled");status.set("地形・岩相を別々に計算し、合成画像を作成中…")
        def worker():
            try:
                result=execute_basic_section_preview(output.get(),regions[region.get()],seed=numeric_seed,
                  distance_end=options["distanceEndM"],elevation_bottom=options["elevationBottomM"],
                  elevation_top=options["elevationTopM"],horizontal_tick=options["horizontalTickM"],
                  vertical_tick=options["verticalTickM"],contact_lines="Show" if contacts.get()=="表示する" else "Hide")
                mailbox.put((True,result))
            except Exception as error:mailbox.put((False,str(error)))
        threading.Thread(target=worker,daemon=True).start()
    def poll():
        try:
            ok,value=mailbox.get_nowait();button.configure(state="normal")
            if ok:status.set(f"生成完了：{value[0]}\nモデル：{value[1]}")
            else:messagebox.showerror("生成できません",value,parent=window);status.set("生成に失敗しました。")
        except queue.Empty:pass
        if window.winfo_exists():window.after(150,poll)
    button=ttk.Button(frame,text="基本断面PNGを生成",command=run);button.grid(row=11,column=1,sticky="e",pady=14)
    ttk.Label(frame,textvariable=status,wraplength=590).grid(row=12,column=0,columnspan=3,sticky="w")
    frame.columnconfigure(1,weight=1);window.after(150,poll)
    return window
