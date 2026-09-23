"""GUI-only local virtual-environment setup and alpha entrypoint."""
from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

PACKAGE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

def ready():
    try:
        import numpy, PIL, shapely
        return Path(sys.prefix).resolve() == (PACKAGE/'.venv').resolve()
    except ImportError:
        return False

def main():
    if not ready():
        window = tk.Tk()
        window.title('Geologic Section Alpha — 初回セットアップ')
        ttk.Label(window,text='このフォルダ専用のPython環境を作成します。\nNumPy・Pillow・Shapelyをインターネットから導入します。',padding=18).pack()
        status = tk.StringVar(value='既存のPython環境は変更しません。')
        ttk.Label(window,textvariable=status,padding=10).pack()
        messages = queue.Queue()
        def setup():
            button.configure(state='disabled')
            status.set('準備中…')
            def worker():
                try:
                    python = PACKAGE/'.venv/Scripts/python.exe'
                    flags = getattr(subprocess,'CREATE_NO_WINDOW',0)
                    if not python.is_file():
                        subprocess.run([sys.executable,'-m','venv',str(PACKAGE/'.venv')],check=True,capture_output=True,creationflags=flags,timeout=120)
                    subprocess.run([str(python),'-m','pip','install','-r',str(PACKAGE/'requirements.txt')],check=True,capture_output=True,creationflags=flags,timeout=600)
                    messages.put(None)
                except Exception as error:
                    detail = getattr(error,'stderr',b'')
                    messages.put(str(error)+'\n'+(detail.decode('utf-8',errors='replace') if isinstance(detail,bytes) else str(detail)))
            threading.Thread(target=worker,daemon=True).start()
            window.after(150,poll)
        def poll():
            try: error = messages.get_nowait()
            except queue.Empty:
                window.after(150,poll)
                return
            if error:
                status.set('準備に失敗しました。')
                button.configure(state='normal')
                messagebox.showerror('セットアップ',error,parent=window)
            else:
                subprocess.Popen([str(PACKAGE/'.venv/Scripts/pythonw.exe'),'-B',str(Path(__file__).resolve())],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                window.destroy()
        button = ttk.Button(window,text='セットアップ',command=setup)
        button.pack(pady=16)
        window.mainloop()
        return
    from operator_ui import launch
    launch()

if __name__ == '__main__':
    try: main()
    except Exception as error:
        window=tk.Tk();window.withdraw()
        messagebox.showerror('起動できません',str(error),parent=window)
        window.destroy()
