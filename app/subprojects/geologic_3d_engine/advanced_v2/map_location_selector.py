"""Nonblocking GSI map, bounded tile cache, and ordered endpoint selection."""
from __future__ import annotations
import io
import math
import queue
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from PIL import Image
from route_request import (endpoint_geometry, destination, validate_endpoint,
                           MIN_SECTION_LENGTH_M, MAX_SECTION_LENGTH_M, SECTION_LENGTH_LABEL)

TILE_SIZE = 256
MIN_ZOOM, MAX_ZOOM = 5, 16
TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png"
DEM_SOURCES = (("DEM1A","dem1a_png",17),("DEM5A","dem5a_png",15),
               ("DEM5B","dem5b_png",15),("DEM5C","dem5c_png",15),
               ("DEM10B","dem_png",14))
DEM_URL = "https://cyberjapandata.gsi.go.jp/xyz/{name}/{z}/{x}/{y}.png"
USER_AGENT = "geologic-3d-engine-research/1.0"


def lonlat_to_global_pixel(longitude: float, latitude: float, zoom: int):
    if not (-180 <= longitude <= 180 and -85.05112878 <= latitude <= 85.05112878):
        raise ValueError("coordinate is outside Web Mercator")
    scale = TILE_SIZE * (2 ** zoom)
    x = (longitude + 180.0) / 360.0 * scale
    latitude_radians = math.radians(latitude)
    y = (1.0 - math.asinh(math.tan(latitude_radians)) / math.pi) * 0.5 * scale
    return x, y


def global_pixel_to_lonlat(x: float, y: float, zoom: int):
    scale = TILE_SIZE * (2 ** zoom)
    longitude = x / scale * 360.0 - 180.0
    mercator = math.pi * (1.0 - 2.0 * y / scale)
    latitude = math.degrees(math.atan(math.sinh(mercator)))
    return longitude, latitude


def selection_candidate(points, target, point):
    """Validate before mutating selection, using the generation request's limits."""
    validate_endpoint(point)
    candidate=list(points)
    if not candidate:candidate.append(point)
    elif target=="A":candidate[0]=point
    elif len(candidate)==1:candidate.append(point)
    else:candidate[1]=point
    if len(candidate)==2:endpoint_geometry(*candidate)
    return candidate


def distance_ring_pixels(anchor, radius_m, zoom):
    """Equal ground-distance ring, projected to the map (not a screen-radius guess)."""
    return [lonlat_to_global_pixel(*destination(*anchor,bearing,radius_m),zoom)
            for bearing in range(0,361,2)]


def _decode_dem_pixel(data: bytes, pixel_x: int, pixel_y: int) -> float | None:
    rgb=np.asarray(Image.open(io.BytesIO(data)).convert("RGB"),dtype=np.int64)
    red,green,blue=(int(v) for v in rgb[pixel_y,pixel_x])
    encoded=red*65536+green*256+blue
    if encoded==2**23:return None
    signed=encoded-2**24 if encoded>2**23 else encoded
    return signed*0.01


def query_gsi_elevation(longitude: float, latitude: float, timeout: float = 15.0) -> float:
    """Read the same prioritized GSI DEM tiles used by the generation path."""
    for _source,name,zoom in DEM_SOURCES:
        global_x,global_y=lonlat_to_global_pixel(longitude,latitude,zoom)
        pixel_x,pixel_y=int(global_x),int(global_y)
        url=DEM_URL.format(name=name,z=zoom,x=pixel_x//TILE_SIZE,y=pixel_y//TILE_SIZE)
        request=urllib.request.Request(url,headers={"User-Agent":USER_AGENT})
        try:
            with urllib.request.urlopen(request,timeout=timeout) as response:data=response.read()
        except urllib.error.HTTPError as error:
            if error.code==404:continue
            raise
        value=_decode_dem_pixel(data,pixel_x%TILE_SIZE,pixel_y%TILE_SIZE)
        if value is not None and math.isfinite(value):return float(value)
    raise ValueError("選択地点ではGSI DEM標高を取得できません。陸地を選択してください。")


_TILE_CACHE = OrderedDict()


class TileLoader:
    """Only fetch/decode on workers. All state and Tk access stay on the UI thread."""
    def __init__(self, fetch, *, cache=None, capacity=128, workers=4):
        self.fetch=fetch;self.cache=_TILE_CACHE if cache is None else cache
        self.capacity=capacity;self.workers=workers;self.wanted=[];self.pending={}
        self.failed={};self.closed=False;self.done=queue.Queue()
        self.pool=ThreadPoolExecutor(max_workers=workers,thread_name_prefix="map-tiles")

    def set_view(self, keys):
        self.wanted=list(dict.fromkeys(keys))
        self.failed={key:expiry for key,expiry in self.failed.items() if expiry>time.monotonic()}
        for key,future in list(self.pending.items()):
            if key not in self.wanted:future.cancel()
        self._pump()

    def _pump(self):
        if self.closed:return
        for key in self.wanted:
            if len(self.pending)>=self.workers:break
            if key in self.cache or key in self.pending:continue
            if self.failed.get(key,0)>time.monotonic():continue
            future=self.pool.submit(self.fetch,key);self.pending[key]=future
            future.add_done_callback(lambda f,k=key:self.done.put((k,f)))

    def drain(self):
        changed=False
        while True:
            try:key,future=self.done.get_nowait()
            except queue.Empty:break
            self.pending.pop(key,None)
            if self.closed or future.cancelled():continue
            try:self.cache[key]=future.result()
            except Exception:self.failed[key]=time.monotonic()+20;changed=True;continue
            self.cache.move_to_end(key)
            while len(self.cache)>self.capacity:self.cache.popitem(last=False)
            changed=True
        self._pump();return changed

    def get(self,key):
        value=self.cache.get(key)
        if value is not None:self.cache.move_to_end(key)
        return value

    def close(self):
        self.closed=True;self.wanted=[]
        self.pool.shutdown(wait=False,cancel_futures=True)


def fetch_map_tile(key):
    z,x,y=key
    request=urllib.request.Request(TILE_URL.format(z=z,x=x,y=y),headers={"User-Agent":USER_AGENT})
    with urllib.request.urlopen(request,timeout=6) as response:data=response.read()
    # Reject malformed/non-tile responses before the Tk thread sees them.
    with Image.open(io.BytesIO(data)) as source:
        if source.size!=(TILE_SIZE,TILE_SIZE):raise ValueError("invalid map tile size")
        source.load()
    return data


class GsiRouteSelector(tk.Toplevel):
    WIDTH, HEIGHT = 768, 560

    def __init__(self,parent,longitude,latitude,on_accept,*,points=None,fetch_tile=fetch_map_tile):
        super().__init__(parent);self.title("地理院地図 — 始点A・終点Bを指定")
        self.resizable(False,False);self.transient(parent);self.grab_set()
        self.center=[float(longitude),float(latitude)];self.zoom=10
        self.points=list(points or []);self.target=tk.StringVar(value="B" if len(self.points)==1 else "A")
        self.on_accept=on_accept;self._images=[];self._drag=None;self._closed=False
        self._render_id=None;self._poll_id=None;self._positions=[];self._accepting=False
        self.loader=TileLoader(fetch_tile);self.accept_results=queue.Queue()
        ttk.Label(self,text="始点A → 終点Bの順にクリック。ドラッグで移動、ホイールで拡大縮小。断面の左端=A、右端=Bです。",
                  wraplength=self.WIDTH).pack(anchor="w",padx=10,pady=(10,5))
        controls=ttk.Frame(self);controls.pack(fill="x",padx=10,pady=4)
        for label in ("A","B"):
            ttk.Radiobutton(controls,text=label+"を指定",variable=self.target,value=label,
                            command=self._target_changed).pack(side="left")
        ttk.Button(controls,text="二点をクリア",command=self._clear).pack(side="left",padx=6)
        ttk.Button(controls,text="A/B入替",command=self._swap).pack(side="left")
        self.range_button=ttk.Button(controls,text="範囲全体",command=self._fit_range,state="disabled")
        self.range_button.pack(side="left",padx=6)
        ttk.Button(controls,text="＋",command=lambda:self._zoom(1)).pack(side="right")
        ttk.Button(controls,text="－",command=lambda:self._zoom(-1)).pack(side="right")
        self.range_status=tk.StringVar(value=f"二点間の距離：{SECTION_LENGTH_LABEL}（陸地を選択。資料不足時は生成不可）")
        ttk.Label(self,textvariable=self.range_status,wraplength=self.WIDTH).pack(anchor="w",padx=10,pady=(0,4))
        self.canvas=tk.Canvas(self,width=self.WIDTH,height=self.HEIGHT,bg="#d8e5ed",highlightthickness=1)
        self.canvas.pack(padx=10);self.status=tk.StringVar(value="始点Aを選択してください")
        bar=ttk.Frame(self);bar.pack(fill="x",padx=10,pady=8)
        ttk.Label(bar,textvariable=self.status).pack(side="left")
        self.accept_button=ttk.Button(bar,text="この二点で確定",command=self._accept,state="disabled")
        self.accept_button.pack(side="right")
        ttk.Button(bar,text="キャンセル",command=self.destroy).pack(side="right",padx=8)
        self.canvas.bind("<ButtonPress-1>",self._press);self.canvas.bind("<B1-Motion>",self._motion)
        self.canvas.bind("<ButtonRelease-1>",self._release);self.canvas.bind("<MouseWheel>",self._wheel)
        ttk.Label(self,text="出典：国土地理院（地理院タイル）。地点選択は測量ではありません。").pack(anchor="w",padx=10)
        self.protocol("WM_DELETE_WINDOW",self.destroy)
        self._update_status()
        self._schedule_render(1)
        self._poll_id=self.after(40,self._poll)

    def _schedule_render(self,delay=90):
        if self._render_id:self.after_cancel(self._render_id)
        self._render_id=self.after(delay,self._render)

    def _render(self):
        self._render_id=None
        if self._closed:return
        center_x,center_y=lonlat_to_global_pixel(*self.center,self.zoom)
        left,top=center_x-self.WIDTH/2,center_y-self.HEIGHT/2
        first_x,last_x=math.floor(left/TILE_SIZE),math.floor((left+self.WIDTH)/TILE_SIZE)
        first_y,last_y=math.floor(top/TILE_SIZE),math.floor((top+self.HEIGHT)/TILE_SIZE)
        tile_count=2**self.zoom
        self._positions=[((self.zoom,tile_x%tile_count,tile_y),tile_x*TILE_SIZE-left,tile_y*TILE_SIZE-top)
            for tile_y in range(first_y,last_y+1) if 0<=tile_y<tile_count
            for tile_x in range(first_x,last_x+1)]
        ordered=sorted(self._positions,key=lambda p:(p[1]+128-self.WIDTH/2)**2+(p[2]+128-self.HEIGHT/2)**2)
        self.loader.set_view([p[0] for p in ordered]);self._draw_tiles()

    def _draw_tiles(self):
        self.canvas.delete("all");self._images=[]
        for key,x,y in self._positions:
            data=self.loader.get(key)
            if data is not None:
                image=tk.PhotoImage(master=self,data=data);self._images.append(image)
                self.canvas.create_image(x,y,image=image,anchor="nw",tags="map")
            else:
                self.canvas.create_rectangle(x,y,x+256,y+256,outline="#bbb",tags="map")
                self.canvas.create_text(x+128,y+128,text="取得失敗（移動で再試行）" if key in self.loader.failed else "読込中…",tags="map")
        self._draw_points()

    def _draw_points(self):
        self.canvas.delete("selection")
        gx,gy=lonlat_to_global_pixel(*self.center,self.zoom)
        anchor=self._range_anchor()
        self.range_button.configure(state="normal" if anchor else "disabled")
        if anchor:
            index,point=anchor
            for radius,color,tag in ((MAX_SECTION_LENGTH_M,"#1667b1","maximum_range"),
                                     (MIN_SECTION_LENGTH_M,"#ba5100","minimum_range")):
                ring=distance_ring_pixels(point,radius,self.zoom)
                coords=[v for x,y in ring for v in (x-gx+self.WIDTH/2,y-gy+self.HEIGHT/2)]
                self.canvas.create_polygon(*coords,fill="" if radius==MAX_SECTION_LENGTH_M else color,
                                           stipple="gray12",outline="",
                                           tags=("map","selection",tag+"_fill"))
                self.canvas.create_line(*coords,fill="white",width=6,
                                        tags=("map","selection",tag+"_halo"))
                self.canvas.create_line(*coords,fill=color,width=3,
                                        tags=("map","selection",tag))
            self.range_status.set(f"{'AB'[index]}中心の青円：上限{MAX_SECTION_LENGTH_M:g} m。橙円内：{MIN_SECTION_LENGTH_M:g} m未満は不可。全体表示は「範囲全体」。資料不足時は生成不可。")
        else:self.range_status.set(f"二点間の距離：{SECTION_LENGTH_LABEL}（陸地を選択。資料不足時は生成不可）")
        pixels=[(x-gx+self.WIDTH/2,y-gy+self.HEIGHT/2) for x,y in
                (lonlat_to_global_pixel(*p,self.zoom) for p in self.points)]
        if len(pixels)==2:self.canvas.create_line(*pixels[0],*pixels[1],fill="#b50020",width=3,tags=("map","selection"))
        for index,(x,y) in enumerate(pixels):
            self.canvas.create_oval(x-6,y-6,x+6,y+6,fill="white",outline="#b50020",width=2,tags=("map","selection"))
            self.canvas.create_text(x+10,y-12,text="AB"[index],fill="#b50020",font=("Arial",14,"bold"),tags=("map","selection"))

    def _range_anchor(self):
        if not self.points:return None
        index=1 if len(self.points)==2 and self.target.get()=="A" else 0
        return index,self.points[index]

    def _target_changed(self):
        self._draw_points()

    def _fit_range(self):
        anchor=self._range_anchor()
        if not anchor:return
        self._drag=None;self.center=list(anchor[1])
        for zoom in range(MAX_ZOOM,MIN_ZOOM-1,-1):
            gx,gy=lonlat_to_global_pixel(*self.center,zoom)
            ring=distance_ring_pixels(self.center,MAX_SECTION_LENGTH_M,zoom)
            if all(abs(x-gx)<=self.WIDTH/2-24 and abs(y-gy)<=self.HEIGHT/2-24 for x,y in ring):break
        self.zoom=zoom;self._schedule_render(1)

    def _poll(self):
        if self._closed:return
        if self.loader.drain() and not self._drag and self._render_id is None:self._draw_tiles()
        try:ok,result=self.accept_results.get_nowait()
        except queue.Empty:pass
        else:
            self._accepting=False
            if ok:
                self.on_accept(tuple(self.points[0]),tuple(self.points[1]),result);self.destroy();return
            self._update_status();messagebox.showerror("地点確認に失敗",str(result),parent=self)
        self._poll_id=self.after(40,self._poll)

    def _update_status(self):
        valid=False
        if len(self.points)==2:
            try:
                _,length,bearing=endpoint_geometry(*self.points)
                self.status.set(f"A → B：{length:.2f} m ／ 方位角 {bearing:.1f}°");valid=True
            except ValueError as error:self.status.set(str(error))
        else:self.status.set(f"終点Bを選択（Aから{SECTION_LENGTH_LABEL}）" if self.points else "始点Aを選択してください")
        self.accept_button.configure(state="normal" if valid and not self._accepting else "disabled")

    def _clear(self):
        if self._accepting:return
        self.points=[];self.target.set("A");self._draw_points();self._update_status()

    def _swap(self):
        if self._accepting:return
        if len(self.points)==2:
            self.points.reverse();self._target_changed();self._update_status()

    def _press(self,event):self._drag=(event.x,event.y,self.center[:],False,event.x,event.y)
    def _motion(self,event):
        if not self._drag:return
        x0,y0,origin,_,last_x,last_y=self._drag
        if abs(event.x-x0)+abs(event.y-y0)>4:
            self._drag=(x0,y0,origin,True,event.x,event.y)
            gx,gy=lonlat_to_global_pixel(*origin,self.zoom)
            self.center=list(global_pixel_to_lonlat(gx-(event.x-x0),max(1,min(256*2**self.zoom-1,gy-(event.y-y0))),self.zoom))
            self.center[0]=(self.center[0]+180)%360-180
            self.canvas.move("map",event.x-last_x,event.y-last_y)
    def _release(self,event):
        if not self._drag:return
        x0,y0,origin,moved,*_=self._drag;self._drag=None
        if moved:self._schedule_render(1);return
        if self._accepting:return
        if self._render_id:
            self.after_cancel(self._render_id);self._render()
        gx,gy=lonlat_to_global_pixel(*self.center,self.zoom)
        point=global_pixel_to_lonlat(gx+event.x-self.WIDTH/2,gy+event.y-self.HEIGHT/2,self.zoom)
        try:candidate=selection_candidate(self.points,self.target.get(),point)
        except ValueError as error:
            self.status.set("選択範囲外："+str(error));return
        changed_start=self.target.get()=="A"
        self.points=candidate
        if changed_start:self.target.set("B")
        self._draw_points();self._update_status()
    def _wheel(self,event):
        if event.delta:self._zoom(1 if event.delta>0 else -1)
    def _zoom(self,delta):
        self._drag=None
        self.zoom=max(MIN_ZOOM,min(MAX_ZOOM,self.zoom+delta));self._schedule_render()
    def _accept(self):
        if self._accepting:return
        try:endpoint_geometry(*self.points)
        except (ValueError,TypeError):self._update_status();return
        self._accepting=True;self.accept_button.configure(state="disabled");self.status.set("二点のDEMを確認中…（地図操作は継続できます）")
        points=tuple(self.points)
        def worker():
            try:self.accept_results.put((True,tuple(query_gsi_elevation(*p,timeout=5) for p in points)))
            except Exception as error:self.accept_results.put((False,str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def destroy(self):
        if not self._closed:
            self._closed=True
            for timer in (self._render_id,self._poll_id):
                if timer:self.after_cancel(timer)
            self.loader.close()
        super().destroy()


def open_gsi_route_selector(parent,longitude,latitude,on_accept,*,points=None):
    return GsiRouteSelector(parent,longitude,latitude,on_accept,points=points)
