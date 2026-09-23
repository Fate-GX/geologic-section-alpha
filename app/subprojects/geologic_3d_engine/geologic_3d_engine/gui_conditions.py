"""Drawing-frame settings, without extrapolating or rescaling geology."""
from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import shutil
import uuid
from .gui_backend import load_run_bundle, execute_run_bundle

@dataclass(frozen=True)
class GeographicRouteConditions:
    vertices: tuple
    sample_spacing_m: float = 25.0
    terrain_sampling_method: str = "BilinearPixelCentres"

    @classmethod
    def parse(cls, text, sample_spacing_m,
              terrain_sampling_method="BilinearPixelCentres"):
        try:
            spacing = float(sample_spacing_m)
        except (TypeError, ValueError):
            raise ValueError("標高サンプル間隔は数値で入力してください。")
        if not math.isfinite(spacing) or spacing < 1 or spacing > 1000:
            raise ValueError("標高サンプル間隔は1～1000 mにしてください。")
        vertices = []
        for line_number, raw in enumerate(str(text).splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 2:
                raise ValueError(f"測線{line_number}行目は 経度,緯度 の形式にしてください。")
            try:
                lon, lat = map(float, parts)
            except ValueError:
                raise ValueError(f"測線{line_number}行目の経度・緯度は数値で入力してください。")
            if not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -85.05112878 <= lat <= 85.05112878:
                raise ValueError(f"測線{line_number}行目がWeb Mercatorの有効範囲外です。")
            point = (lon, lat)
            if vertices and point == vertices[-1]:
                raise ValueError(f"測線{line_number}行目は直前の点と同一です。")
            vertices.append(point)
        if len(vertices) < 2:
            raise ValueError("測線は異なる2点以上を入力してください。")
        if terrain_sampling_method not in {"NearestPixel", "BilinearPixelCentres"}:
            raise ValueError("地形標高の取得方式を選択してください。")
        return cls(tuple(vertices), spacing, terrain_sampling_method)

@dataclass(frozen=True)
class DrawingConditions:
    x_start: float = 0
    x_end: float = 100
    elevation_bottom: float = -50
    elevation_top: float = 50
    section_y: float = 47
    horizontal_tick: float = 20
    vertical_tick: float = 10

    def validate(self, config):
        if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("条件は有限の数値で入力してください。")
        if self.x_end <= self.x_start or self.elevation_top <= self.elevation_bottom:
            raise ValueError("終点・上端は始点・下端より大きくしてください。")
        if self.horizontal_tick <= 0 or self.vertical_tick <= 0:
            raise ValueError("目盛間隔は0より大きくしてください。")
        if (self.x_end-self.x_start)/self.horizontal_tick > 100 or (self.elevation_top-self.elevation_bottom)/self.vertical_tick > 100:
            raise ValueError("目盛は各方向100区間以内にしてください。")
        lo, hi = config["extent"]["minimum"], config["extent"]["maximum"]
        if not lo[1] < self.section_y < hi[1]:
            raise ValueError(f"断面Yは {lo[1]} ～ {hi[1]} m の内側にしてください。")
        if self.x_start > lo[0] or self.x_end < hi[0] or self.elevation_bottom > lo[2] or self.elevation_top < hi[2]:
            raise ValueError("切り抜き未対応：図面枠にはモデル全体の横幅・標高範囲を含めてください。")
        return self

    def ticks(self):
        def seq(a,b,d): return [a+i*d for i in range(math.floor((b-a)/d)+1)]
        return {"horizontalMeters":seq(self.x_start,self.x_end,self.horizontal_tick),
                "elevationMeters":seq(self.elevation_bottom,self.elevation_top,self.vertical_tick)}

def bundle_details(bundle):
    _, paths = load_run_bundle(bundle)
    config = json.loads(paths["config"].read_text(encoding="utf-8"))
    section = json.loads(paths["sectionSpec"].read_text(encoding="utf-8"))
    if config["coordinateReference"].get("linearUnit") != "m":
        raise ValueError("簡易画面はメートル単位専用です。")
    if section.get("normal") != [0,1,0] or section.get("uDirection") != [1,0,0] or section["origin"][0] != 0 or section["origin"][2] != 0:
        raise ValueError("簡易画面はX方向の鉛直断面専用です。斜め断面は詳細設定で扱います。")
    lo,hi = config["extent"]["minimum"],config["extent"]["maximum"]
    return config, DrawingConditions(lo[0],hi[0],lo[2],hi[2],section["origin"][1],(hi[0]-lo[0])/5,(hi[2]-lo[2])/10)

def execute_conditions(bundle, output_parent, conditions):
    config,_ = bundle_details(bundle)
    conditions.validate(config)
    _,paths = load_run_bundle(bundle)
    if not str(output_parent).strip(): raise ValueError("出力先を選択してください。")
    run = Path(output_parent).resolve() / ("run_"+uuid.uuid4().hex[:12])
    inputs = run / "inputs"
    inputs.mkdir(parents=True,exist_ok=False)
    portable = {"bundleVersion":"1.0","targetStage":"Stage11NeutralContract","inputs":{}}
    for key,path in paths.items():
        name=key+".json"
        shutil.copyfile(path,inputs/name)
        portable["inputs"][key]=name
    section_path=inputs/"sectionSpec.json"
    section=json.loads(section_path.read_text(encoding="utf-8"))
    section.update(origin=[0,conditions.section_y,0],uRange=[conditions.x_start,conditions.x_end],
                   vRange=[-conditions.elevation_top,-conditions.elevation_bottom])
    section_path.write_text(json.dumps(section),encoding="utf-8")
    bundle_path=inputs/"bundle.json"
    bundle_path.write_text(json.dumps(portable),encoding="utf-8")
    settings={"version":"1.0","conditions":asdict(conditions),"ticks":conditions.ticks(),
              "regionalProfileId":config["regionalProfileId"],"modelExtent":config["extent"],
              "synthetic":True,"realRegionAuthorized":False,
              "tickStatus":"PreviewAndSavedSettingsOnly_NativeDwgNotImplemented",
              "rangePolicy":"DrawingFrameOnly_NoGeologyExtrapolation"}
    (run/"drawing_settings.json").write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
    return execute_run_bundle(bundle_path,run/"outputs"),run
