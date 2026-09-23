"""Single operator entrypoint; reuse the existing regional form and gates."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tempfile

def atomic_write_json(path, payload) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,
                                         prefix=destination.name+".", suffix=".tmp",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def project_root():
    return Path(__file__).resolve().parents[1] / "app"


def load_operator_ui(root):
    advanced=Path(root)/'subprojects/geologic_3d_engine/advanced_v2'
    for path in (advanced,advanced.parent):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    spec=importlib.util.spec_from_file_location('_next_regional_operator_ui',advanced/'gui.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.AdvancedWindow


def run_section(root,request,output,*,pipeline=None):
    # Set only this GUI process's child-launch policy; never import an ARG.
    from run_user_context_native_gate import ensure_interactive_user,windows_process_identity
    ensure_interactive_user(windows_process_identity())
    if pipeline is None:
        from nationwide_pipeline import run_advanced_japan_section
        pipeline=run_advanced_japan_section
    keys=('GEO3D_AUTOCAD_PROFILE_ARG','GEO3D_AUTOCAD_USE_CURRENT_DEFAULT')
    previous={key:os.environ.get(key) for key in keys}
    os.environ.pop(keys[0],None);os.environ[keys[1]]='1'
    try:return pipeline(root,request,output)
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def check_environment(root):
    from frozen_guard import verify_frozen_basic_v1
    root=Path(root)
    freeze=verify_frozen_basic_v1(root)
    required=[root/'tools/AuthoritativeGeoDwg/seed.dxf',
              root/'subprojects/geologic_3d_engine/advanced_v2/native/bin/Release/net10.0-windows/AdvancedV2GeoDwg.dll',
              Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Autodesk/AutoCAD 2027/accoreconsole.exe']
    missing=[str(path) for path in required if not path.is_file()]
    package=root.parent
    package_check=None
    if (package/'PACKAGE_MANIFEST.json').is_file():
        spec=importlib.util.spec_from_file_location('_operator_package_check',package/'tools/check_package.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        package_check=module.verify(package)
    return {'passed':freeze['passed'] and not missing and (package_check is None or package_check['passed']),
            'frozenBasicV1':freeze,'missing':missing,'packageIntegrity':package_check,
            'publicationAuthorized':False}


def launch():
    import tkinter as tk
    from tkinter import filedialog,messagebox,ttk
    root_path=project_root();window=tk.Tk()
    cls=load_operator_ui(root_path)
    package=root_path.parent if root_path.name=='app' else root_path
    ui=cls(window,project_root=root_path,output_directory=package/'results',runner=run_section)
    window.title('Geologic Section Alpha 0.1.0 — 岩相断面DWG')
    menu=tk.Menu(window);window.configure(menu=menu)
    settings=tk.Menu(menu,tearoff=False);menu.add_cascade(label='条件',menu=settings)
    def save_settings():
        if ui.busy:return
        path=filedialog.asksaveasfilename(parent=window,defaultextension='.json',title='入力条件を保存')
        if path:
            atomic_write_json(path,{'schemaVersion':'OperatorSettings-2','routePoints':ui.route_points,'fields':{k:v.get() for k,v in ui.values.items()},
                'contacts':ui.contacts.get(),'density':ui.density.get(),'png':ui.png.get()})
    def load_settings():
        if ui.busy:return
        path=filedialog.askopenfilename(parent=window,filetypes=[('保存した条件','*.json')])
        if not path:return
        try:
            value=json.loads(Path(path).read_text(encoding='utf-8'))
            if value.get('schemaVersion')!='OperatorSettings-2':raise ValueError('地図の二点を保存した入力条件ではありません。地図から再指定してください')
            fields=value['fields']
            if set(fields)!=set(ui.values):raise ValueError('入力項目が一致しません')
            if value.get('routePoints') is None:raise ValueError('保存された二点がありません。地図から指定してください')
            ui.accept_map_route(*value['routePoints'])
            for key,var in ui.values.items():var.set(str(fields[key]))
            ui.contacts.set(value['contacts']);ui.density.set(value['density']);ui.png.set(value['png'])
        except Exception as error:messagebox.showerror('読込失敗',str(error),parent=window)
    settings.add_command(label='入力条件を保存…',command=save_settings)
    settings.add_command(label='入力条件を読み込む…',command=load_settings)
    def checks():
        if ui.busy:return
        ui.set_busy(True);ui.status.set('環境・配布ファイル・凍結版を確認中…')
        results=queue.Queue()
        def worker():
            try:results.put(check_environment(root_path))
            except Exception as error:results.put({'passed':False,'error':str(error)})
        def poll_check():
            try:result=results.get_nowait()
            except queue.Empty:window.after(100,poll_check);return
            ui.set_busy(False)
            ui.status.set('環境確認：正常。図面ごとの検査は生成時に実行します。' if result['passed'] else '環境確認に失敗：詳細を確認してください。')
            if not result['passed']:messagebox.showerror('環境確認',json.dumps(result,ensure_ascii=False,indent=2),parent=window)
        threading.Thread(target=worker,daemon=True).start();window.after(100,poll_check)
    menu.add_command(label='環境・配布ファイルを確認',command=checks)
    def help_window():
        messagebox.showinfo('操作', '地図上で始点Aと終点Bを選び「検証してネイティブDWGを生成」を押してください。\n'
            '細かい条件は「詳細設定」で指定できます。生成後は画面内のボタンからDWG・画像・検査結果を開けます。\n'
            '地域の公開資料に基づく合成仮説です。調査・設計・施工には使用できません。',parent=window)
    menu.add_command(label='使い方',command=help_window)
    window.mainloop()


if __name__=='__main__':launch()
