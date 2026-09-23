"""Experimental profile-driven 2D images, separate from Stage11 acceptance."""
import csv
import hashlib
import json
import math
from pathlib import Path
import uuid

import numpy as np
from .section.shape_preserving import interpolate
from .modeling.terrain_surface_model import build_terrain_surface_model
from .modeling.terrain_lithology_composer import compose_terrain_and_lithology
from .modeling.basic_provider import BasicCorrelatedLithologyProvider
from .modeling.provider_contract import invoke_lithology_provider

ROOT = Path(__file__).resolve().parents[3]
PROFILE = Path(__file__).resolve().parents[1] / "examples/aso_image_profile.json"


def generate_model(seed, profile_path=PROFILE):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
        raise ValueError("シードは0～4294967295の整数です。")
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    source = ROOT / profile["terrainFile"]
    a, b = profile["longitudeRange"]
    samples = []
    with source.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            lon = float(row["Lon"])
            if a-1e-10 <= lon <= b+1e-10:
                x = 6378137 * math.cos(math.radians(profile["latitude"])) * math.radians(lon-a)
                samples.append((x, float(row["Elevation"])))
    samples.sort()
    if len(samples) < 2 or not np.isfinite(samples).all() or np.any(np.diff(np.array(samples)[:,0]) <= 0):
        raise ValueError("地形標本が不正です。")
    x = np.linspace(samples[0][0], samples[-1][0], 241)
    terrain = interpolate(*np.array(samples).T, x)
    lithology_layers = []
    for layer in profile["layers"]:
        mean = layer["base"] + layer["amplitude"]*np.exp(-((x/x[-1]-layer["center"])/layer["width"])**2)
        lithology_layers.append({"unitId":layer["label"],"normalizedLithology":layer["NormalizedLabel"],
          "color":layer["color"],"meanThicknessProfileM":mean.tolist()})
    terrain_model=build_terrain_surface_model(
      [{"stationM":float(a),"elevationM":float(z)} for a,z in zip(x,terrain)],
      source_id=profile["terrainFile"],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
      sampling_method="MonotoneCubicHermite_C1_NoExtrapolation")
    lithology_model=invoke_lithology_provider(BasicCorrelatedLithologyProvider(),x.tolist(),{
      "layers":lithology_layers,"seed":seed,"rangeM":profile["spatialRangeMeters"],"logStd":profile["logStd"]})
    composition=compose_terrain_and_lithology(terrain_model,lithology_model)
    coarse_x=x.copy()
    x=np.unique(np.concatenate((np.linspace(x[0],x[-1],2401),np.array(samples)[:,0])))
    terrain=interpolate(*np.array(samples).T,x)
    rendered_thickness=[np.exp(interpolate(coarse_x,np.log(v["thicknessM"]),x)) for v in composition["layersTopDown"]]
    top=terrain.copy();stack=[]
    for source_layer,thickness in zip(composition["layersTopDown"],rendered_thickness):
        bottom=top-thickness
        stack.append({"top":top.tolist(),"bottom":bottom.tolist(),"thickness":thickness.tolist(),
                      "unitId":source_layer["unitId"]})
        top=bottom
    audit={"passed":all(min(v["thickness"])>0 for v in stack),
           "sharedContacts":all(a["bottom"]==b["top"] for a,b in zip(stack,stack[1:]))}
    if not audit["passed"] or not audit["sharedContacts"]:
        raise ValueError("厚さ・共有境界の検証に失敗しました。")
    return dict(profile=profile, seed=seed, x=x.tolist(), terrain=terrain.tolist(), layers=stack,
                audit=audit, synthetic=True, realRegionAuthorized=False, decision="Experimental",
                terrainSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                profileSha256=hashlib.sha256(Path(profile_path).read_bytes()).hexdigest(),
                terrainSamples=samples, interpolation="MonotoneCubicHermite_C1_NoExtrapolation_LogThickness_SharedContacts",
                terrainModel=terrain_model,lithologyModel=lithology_model,
                compositionArtifactSha256=composition["artifactSha256"],
                moduleSeparation="TerrainIndependentLithology_ExplicitComposition",
                equation="thickness=mean(x)*exp(sigma*W-0.5*sigma^2); independent layers; Cov(W)=exp(-(dx/range)^2)",
                numpyVersion=np.__version__)


def export_image(output_parent, seed, *, distance_end=2200, elevation_bottom=650,
                 elevation_top=1400, horizontal_tick=500, vertical_tick=100, contact_lines="Show",
                 profile_path=PROFILE):
    if contact_lines not in ("Show","Hide"):
        raise ValueError("岩相境界線はShowまたはHideです。")
    settings = dict(distance_end=distance_end,elevation_bottom=elevation_bottom,
                    elevation_top=elevation_top,horizontal_tick=horizontal_tick,vertical_tick=vertical_tick)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in settings.values()):
        raise ValueError("図面条件は有限の数値にしてください。")
    if distance_end <= 0 or elevation_top <= elevation_bottom or min(horizontal_tick,vertical_tick) <= 0:
        raise ValueError("範囲・目盛は正の間隔が必要です。")
    if distance_end/horizontal_tick > 100 or (elevation_top-elevation_bottom)/vertical_tick > 100:
        raise ValueError("目盛は各軸100区間以内にしてください。")
    model = generate_model(seed,profile_path)
    if distance_end < model["x"][-1] or elevation_top < max(model["terrain"]) or elevation_bottom >= min(model["layers"][-1]["bottom"]):
        raise ValueError("図面枠は測線全体と全境界を含めてください（横2200m・標高650～1400mを推奨）。")
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path("C:/Windows/Fonts/meiryo.ttc")
    def font(size):
        return ImageFont.truetype(str(font_path),size) if font_path.exists() else ImageFont.load_default()
    image=Image.new("RGB",(1800,1000),"#f6f8fa");draw=ImageDraw.Draw(image)
    scale=min(1560/distance_end,570/(elevation_top-elevation_bottom))
    left,top=140,175
    right=left+distance_end*scale;bottom=top+(elevation_top-elevation_bottom)*scale
    def point(x,z):return (left+x*scale,top+(elevation_top-z)*scale)
    draw.rectangle((left,top,right,bottom),fill="white",outline="#74808b",width=2)
    x = model["x"]; p = model["profile"]
    for data, layer in zip(model["layers"],p["layers"]):
        upper=[point(a,b) for a,b in zip(x,data["top"])]
        lower=[point(a,b) for a,b in zip(x,data["bottom"])]
        draw.polygon(upper+lower[::-1],fill=layer["color"])
    lower=[point(a,b) for a,b in zip(x,model["layers"][-1]["bottom"])]
    draw.polygon(lower+[point(x[-1],elevation_bottom),point(x[0],elevation_bottom)],fill=p["basement"]["color"])
    if contact_lines == "Show":
        for data in model["layers"]:
            draw.line([point(a,b) for a,b in zip(x,data["bottom"])],fill="#574f46",width=2)
    draw.line([point(a,b) for a,b in zip(x,model["terrain"])],fill="#202830",width=3)
    for value in np.arange(0,distance_end+1e-8,horizontal_tick):
        px,_=point(value,elevation_bottom);draw.line((px,bottom,px,bottom+8),fill="#485766",width=2)
        draw.text((px,bottom+14),f"{value:g}",font=font(22),anchor="mt",fill="#263441")
    for value in np.arange(elevation_bottom,elevation_top+1e-8,vertical_tick):
        _,py=point(0,value);draw.line((left-8,py,left,py),fill="#485766",width=2)
        draw.text((left-15,py),f"{value:g}",font=font(22),anchor="rm",fill="#263441")
    draw.text((left,top-35),"標高 (m)",font=font(22),fill="#263441")
    draw.text(((left+right)/2,bottom+52),"測線西端からの距離 (m)",font=font(23),anchor="mt",fill="#263441")
    draw.text((90,30),p["title"]+" ｜ ランダム合成断面",font=font(36),fill="#203649")
    draw.text((90,88),f"Experimental / seed={seed} / 水平・垂直 1:1 / 地下厚さは未較正・実地質の再現ではありません",font=font(23),fill="#885333")
    for i,layer in enumerate(p["layers"]+[p["basement"]]):
        lx=140+(i%2)*740;ly=825+(i//2)*40
        draw.rectangle((lx,ly,lx+27,ly+24),fill=layer["color"])
        draw.text((lx+40,ly-3),layer["label"],font=font(23),fill="#263441")
    draw.text((90,925),"設計使用禁止 · 地形外は外挿なし · 地表地質適合・3D・DWG未検証\nGSI標高標本／GSJ阿蘇火山地質図（1985）。出典・条件・数値配列は隣接JSONに保存。",font=font(21),fill="#5a6270")
    folder = Path(output_parent)/("image_"+uuid.uuid4().hex[:12]);folder.mkdir(parents=True,exist_ok=False)
    model["drawingSettings"] = settings
    model["drawingSettings"]["contactLines"] = contact_lines
    (folder/"model.json").write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    target = folder/"section.png";image.save(target)
    return target
