"""Small image-only launcher. All Tk access stays on the UI thread."""
import os
from pathlib import Path
import queue
import secrets
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .engine_image import export_image


def open_image_window(parent):
    window = tk.Toplevel(parent);window.title("3Dエンジン・断面PNG");window.geometry("760x680")
    frame = ttk.Frame(window,padding=20);frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="3Dエンジンの実出力を画像で確認",font=("Yu Gothic UI",17,"bold")).pack(anchor="w")
    ttk.Label(frame,text="合成試験地域：100×100×100m。阿蘇の3D入力は未接続です。\n確率的厚さ→地質イベント→B-rep→断面。全体拒否時は診断画像として明示します。",wraplength=700).pack(anchor="w",pady=10)
    grid=ttk.Frame(frame);grid.pack(fill="x")
    fields=[("seed","乱数シード",1234),("distance_end","横方向の終点 (m)",100),
            ("elevation_bottom","Zの下端 (m)",-50),("elevation_top","Zの上端 (m)",50),
            ("horizontal_tick","横目盛の間隔 (m)",20),("vertical_tick","縦目盛の間隔 (m)",10),
            ("section_y","断面位置 Y (m)",47)]
    values={};controls=[]
    for i,(key,label,default) in enumerate(fields):
        values[key]=tk.StringVar(value=str(default));ttk.Label(grid,text=label).grid(row=i,column=0,sticky="w",pady=5)
        entry=ttk.Entry(grid,textvariable=values[key],width=25);entry.grid(row=i,column=1,padx=16);controls.append(entry)
    random_button=ttk.Button(grid,text="別の乱数にする",command=lambda:values["seed"].set(str(secrets.randbelow(2**32))))
    random_button.grid(row=0,column=2);controls.append(random_button)
    contacts=tk.StringVar(value="表示する")
    ttk.Label(grid,text="岩相境界線").grid(row=7,column=0,sticky="w",pady=8)
    contact_combo=ttk.Combobox(grid,textvariable=contacts,values=["表示する","表示しない"],state="readonly",width=23)
    contact_combo.grid(row=7,column=1,padx=16)
    output=tk.StringVar(value=str(Path(__file__).resolve().parents[1]/"outputs/image_previews"))
    ttk.Label(frame,text="保存先（毎回新しいフォルダ）").pack(anchor="w",pady=(12,3))
    entry=ttk.Entry(frame,textvariable=output);entry.pack(fill="x");controls.append(entry)
    def browse():
        folder=filedialog.askdirectory(parent=window)
        if folder:output.set(folder)
    button=ttk.Button(frame,text="保存先を選択",command=browse);button.pack(anchor="w");controls.append(button)
    status=tk.StringVar(value="PNGと再現用JSONを保存します。同じシード・条件で同じモデルになります。")
    mailbox=queue.Queue();state={"busy":False,"image":None}
    def run():
        try:
            seed=int(values["seed"].get());settings={k:float(v.get()) for k,v in values.items() if k!="seed"}
            folder=output.get().strip()
            settings["contact_lines"]="Show" if contacts.get()=="表示する" else "Hide"
            if not folder:raise ValueError("保存先を選択してください。")
        except ValueError as error:messagebox.showerror("条件エラー",str(error),parent=window);return
        state["busy"]=True;state["image"]=None;show.configure(state="disabled")
        for control in controls:control.configure(state="disabled")
        contact_combo.configure(state="disabled")
        status.set("3D生成・Stage1～10検証・断面抽出中…")
        def work():
            try:mailbox.put((True,export_image(folder,seed,**settings)))
            except Exception as error:mailbox.put((False,str(error)))
        threading.Thread(target=work,daemon=True).start()
    button=ttk.Button(frame,text="ランダム断面PNGを生成",command=run);button.pack(anchor="e",pady=8);controls.append(button)
    show=ttk.Button(frame,text="保存した画像を開く",state="disabled",command=lambda:os.startfile(str(state["image"])))
    show.pack(anchor="e")
    ttk.Label(frame,textvariable=status,wraplength=665).pack(anchor="w",pady=8)
    def poll():
        try:
            success,result=mailbox.get_nowait();state["busy"]=False
            for control in controls:control.configure(state="normal")
            contact_combo.configure(state="readonly")
            if success:
                import json
                report=json.loads(result.with_name("run.json").read_text(encoding="utf-8"))
                state["image"]=result;show.configure(state="normal");status.set("保存完了："+report["decision"]+"（判定・診断は画像とrun.json参照）\n"+str(result))
            else:status.set("生成失敗："+result)
        except queue.Empty:pass
        window.after(150,poll)
    def close():
        if state["busy"]:messagebox.showinfo("処理中","完了後に閉じてください。",parent=window)
        else:window.destroy()
    window.protocol("WM_DELETE_WINDOW",close);window.after(150,poll)
    return window
