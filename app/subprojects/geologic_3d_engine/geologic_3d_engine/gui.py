"""Minimal desktop launcher; all calculations remain in gui_backend."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk

from .gui_backend import execute_run_bundle


def legacy_main():
    root=tk.Tk();root.title("Geologic 3D Engine — Synthetic Stage 11")
    bundle=tk.StringVar();output=tk.StringVar();status=tk.StringVar(value="Ready")
    ttk.Label(root,text="Synthetic geological hypothesis / 疑似地質モデル").grid(
        row=0,column=0,columnspan=3,padx=8,pady=8)
    _row(root,1,"Run bundle",bundle,lambda:bundle.set(filedialog.askopenfilename(filetypes=[("JSON","*.json")])))
    _row(root,2,"Output folder",output,lambda:output.set(filedialog.askdirectory()))
    button=ttk.Button(root,text="Validate and generate neutral contract")
    button.grid(row=3,column=0,columnspan=3,pady=8)
    ttk.Label(root,textvariable=status).grid(row=4,column=0,columnspan=3,pady=8)
    def run():
        button.state(["disabled"]);status.set("Running validation stages 1–11…")
        def worker():
            try:
                result=execute_run_bundle(bundle.get(),output.get())
                root.after(0,lambda:_finish(button,status,result))
            except Exception as error:
                root.after(0,lambda e=error:_fail(button,status,e))
        threading.Thread(target=worker,daemon=True).start()
    button.configure(command=run);root.mainloop()


def _row(root,row,label,variable,command):
    ttk.Label(root,text=label).grid(row=row,column=0,sticky="w",padx=8,pady=4)
    ttk.Entry(root,textvariable=variable,width=72).grid(row=row,column=1,padx=8,pady=4)
    ttk.Button(root,text="Browse…",command=command).grid(row=row,column=2,padx=8,pady=4)


def _finish(button,status,result):
    button.state(["!disabled"]);status.set("Completed" if result["passed"] else "Rejected")
    messagebox.showinfo("Result",f"Decision: {result['decision']}")


def _fail(button,status,error):
    button.state(["!disabled"]);status.set("Input or execution error")
    messagebox.showerror("Error",str(error))


from .gui_editor import main

if __name__=="__main__":main()
