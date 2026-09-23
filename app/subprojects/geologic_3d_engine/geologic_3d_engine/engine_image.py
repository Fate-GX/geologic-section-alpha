"""Render actual engine B-rep intersections without shape reconstruction."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import secrets
import uuid
from . import gui_backend as loaders
from .fields.stochastic_thickness import (generate_stochastic_thickness, ALGORITHM_VERSION,
    AUTHENTICATION_PURPOSE, UPSTREAM_VALIDATION_KIND, UPSTREAM_VALIDATOR_VERSION)
from .export.authenticated_validation import build_authenticated_validation
from .export.authentication_state import SqliteNonceStore, validate_key_policies
from .export.contract_integrity import build_integrity_envelope
from .stochastic_pipeline import run_stochastic_to_section
from .section.plane_intersection import extract_section

EXAMPLES=Path(__file__).resolve().parents[1]/"examples"


def diagnostics(node, path="pipeline"):
    out=[]
    if isinstance(node,dict):
        if node.get("passed") is False or node.get("errors"):
            out.append({"path":path,"errors":node.get("errors",[])})
        for key,value in node.items():
            if key not in ("errors","section","uncertaintySection"):
                out.extend(diagnostics(value,path+"."+key))
    elif isinstance(node,list):
        for i,value in enumerate(node):out.extend(diagnostics(value,f"{path}[{i}]"))
    return out


def run_engine(folder, seed, section_y=47):
    config=loaders.load_config(EXAMPLES/"stage6_small_config.json")
    files=[("stage3_event_spec.json",loaders.load_event_spec),
           ("stage6_compaction_spec.json",loaders.load_compaction_spec),
           ("stage6_structural_spec.json",loaders.load_structural_spec),
           ("stage6_intrusion_spec.json",loaders.load_intrusion_spec),
           ("stage7_mesh_spec.json",loaders.load_mesh_spec),
           ("stage8_refinement_spec.json",loaders.load_refinement_spec),
           ("stage9_ensemble_spec.json",loaders.load_ensemble_spec)]
    specs=[loader(EXAMPLES/name) for name,loader in files]
    from dataclasses import replace
    section=replace(loaders.load_section_spec(EXAMPLES/"stage10_section_spec.json"),origin=(0.,section_y,0.))
    payload={"contractVersion":"0.8.0-candidate","algorithmVersion":ALGORITHM_VERSION,
      "randomSeed":seed,"grid":{"nx":5,"ny":5,"spacingX":20,"spacingY":20},
      "psdAudit":{"symmetryTolerance":1e-12,"absoluteEigenTolerance":1e-12,"relativeEigenTolerance":1e-12,
                  "toleranceJustification":"Canonical synthetic pipeline numerical test"},"layers":[]}
    for unit,mu in (("OLD_UPPER",4.),("OLD_LOWER",6.)):
        payload["layers"].append({"unitId":unit,"threshold":-3.,"transform":{"kind":"PowerPositivePart","mu":mu,"beta":1.},
          "crossLayerPolicy":"Independent","withinLayerCovariance":{"model":"Gaussian","variance":1.,"ranges":[20.,10.]},
          "parameterEvidenceIds":["SYNTHETIC-TEST-EVIDENCE"]})
    # Local experiment authorization only; never a geological-evidence signature.
    now=dt.datetime.now(dt.timezone.utc)
    stamp=lambda d:d.strftime("%Y-%m-%dT%H:%M:%SZ")
    before,after=stamp(now-dt.timedelta(seconds=1)),stamp(now+dt.timedelta(minutes=4))
    secret=secrets.token_bytes(32)
    envelope=build_integrity_envelope(payload,{"passed":True,"contractVersion":"0.8.0-candidate",
       "validationKind":UPSTREAM_VALIDATION_KIND},UPSTREAM_VALIDATOR_VERSION)
    auth=build_authenticated_validation(envelope,secret=secret,key_id="local-image-experiment",purpose=AUTHENTICATION_PURPOSE,
       issued_at_utc=before,expires_at_utc=after,nonce=secrets.token_hex(16))
    context={"secrets":{"local-image-experiment":secret},"nowUtc":stamp(now),"nonceStore":SqliteNonceStore(folder/"nonces.sqlite3"),
       "policies":validate_key_policies([{"keyId":"local-image-experiment","status":"Active","notBeforeUtc":before,
       "notAfterUtc":after,"purposes":[AUTHENTICATION_PURPOSE]}])}
    generated=generate_stochastic_thickness(dict(payload,authenticatedUpstreamValidation=auth),authentication_context=context)
    pipeline=run_stochastic_to_section(config,generated,[[40]*5 for _ in range(5)],["INTR","FILL"],*specs,section)
    ten=pipeline.get("stageTen",{});eight=ten.get("stageNine",{}).get("stageEight",{})
    cut=ten.get("section")
    diagnostic=False
    if cut is None and eight.get("passed"):
        # Explicit diagnostic extraction, NOT a bypass changing Stage10's status.
        cut=extract_section(eight["adaptiveModel"].refined_brep,section);diagnostic=True
    inputs={name:json.loads((EXAMPLES/name).read_text(encoding="utf-8")) for name in
            ["stage6_small_config.json","stage10_section_spec.json"]+[name for name,_ in files]}
    inputs["stage10_section_spec.json"]["origin"]=[0.,section_y,0.]
    inputs["stochasticRequest"]=payload
    report={"passed":pipeline["passed"],"decision":pipeline["decision"],"seed":seed,
        "region":"CanonicalSynthetic_NotAso","realRegionAuthorized":False,
        "enginePath":"generate_stochastic_thickness -> run_stochastic_to_section -> refined_brep -> extract_section",
        "diagnosticExtraction":diagnostic,"section":cut,"diagnostics":diagnostics(pipeline),
        "sourcePayloadSha256":generated["payloadSha256"],"generatedThickness":generated,"inputs":inputs,
        "authorizationBoundary":"Local synthetic experiment only; no independent geological review",
        "modelSummary":eight.get("modelSummary"),"stage8Passed":eight.get("passed",False)}
    return report


def render(report, target, distance_end, elevation_bottom, elevation_top, horizontal_tick, vertical_tick, contact_lines):
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new("RGB",(1600,1100),"#f6f8fa");draw=ImageDraw.Draw(image)
    font=lambda size:ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc",size)
    draw.text((60,25),"3Dエンジン実出力：合成試験モデル（阿蘇ではありません）",font=font(30),fill="#213645")
    draw.text((60,80),f"{report['decision']} / seed={report['seed']} / 断面 Y={report['inputs']['stage10_section_spec.json']['origin'][1]:g} m / 補間・平滑化なし",font=font(23),fill="#a33320")
    cut=report.get("section")
    if not cut or not cut["validation"]["passed"]:
        draw.text((90,250),"検証済み閉断面なし。地質形状は描画していません。\n詳細はrun.jsonのdiagnosticsを確認してください。",font=font(30),fill="#a33320")
    else:
        scale=min(1000/distance_end,720/(elevation_top-elevation_bottom))
        left,top=130,170;bottom=top+(elevation_top-elevation_bottom)*scale
        point=lambda u,v:(left+u*scale,top+(elevation_top+v)*scale) # v=-Z for this section
        palette={"INTR":"#bf7371","FILL":"#e9c780","OLD_UPPER":"#9bbca9","OLD_LOWER":"#8aa8c6"}
        outlines=[]
        for unit in cut["unitSections"]:
            for polygon in unit["polygons"]:
                pts=[point(*p) for p in polygon["verticesUV"]]
                draw.polygon(pts,fill=palette[unit["unitId"]]);outlines.append(pts)
        if contact_lines=="Show":
            for pts in outlines:draw.line(pts,fill="#34414c",width=2)
        for index,(unit,color) in enumerate(palette.items()):
            draw.rectangle((1200,200+index*65,1230,230+index*65),fill=color)
            draw.text((1240,195+index*65),unit,font=font(22),fill="#213645")
        draw.text((1190,500),"単元IDを表示\n岩相は未同定\n局所座標・単位m\n水平：垂直＝1:1",font=font(21),fill="#213645")
        for i in range(int(distance_end/horizontal_tick)+1):
            x=left+i*horizontal_tick*scale
            draw.text((x,bottom+12),f"{i*horizontal_tick:g}",font=font(20),anchor="mt",fill="#213645")
        for i in range(int((elevation_top-elevation_bottom)/vertical_tick)+1):
            z=elevation_bottom+i*vertical_tick;y=point(0,-z)[1]
            draw.text((left-12,y),f"{z:g}",font=font(20),anchor="rm",fill="#213645")
        draw.text((left,top-40),"Z (m)",font=font(22),fill="#213645")
        draw.text((left+300,bottom+47),"X (m)",font=font(22),fill="#213645")
    note="全体Rejected：Stage8メッシュの診断断面。Stage10受入ではありません。" if not report["passed"] else "Stage10合格／Experimental：実地域認可・DWG保存ではありません。"
    draw.text((60,1000),note+"\n形状は3D B-repの平面交差結果を直接使用。設計使用禁止。",font=font(24),fill="#a33320")
    image.save(target)


def export_image(output_parent, seed, *, distance_end=100, elevation_bottom=-50,elevation_top=50,
                 horizontal_tick=20,vertical_tick=10,contact_lines="Show",section_y=47):
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**32:raise ValueError("シードは32bit非負整数です。")
    values=(distance_end,elevation_bottom,elevation_top,horizontal_tick,vertical_tick,section_y)
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values):raise ValueError("有限数が必要です。")
    if distance_end<100 or elevation_bottom> -50 or elevation_top<50 or not 0<section_y<100:raise ValueError("枠はX0～100、Z-50～50を含め、Yは0～100の内側にしてください。")
    if min(horizontal_tick,vertical_tick)<=0 or distance_end/horizontal_tick>100 or (elevation_top-elevation_bottom)/vertical_tick>100:raise ValueError("目盛は正数・100区間以内です。")
    if contact_lines not in ("Show","Hide"):raise ValueError("不正な境界線設定です。")
    folder=Path(output_parent)/("engine3d_"+uuid.uuid4().hex[:12]);folder.mkdir(parents=True,exist_ok=False)
    report=run_engine(folder,seed,section_y)
    report["drawingSettings"]={"distanceEnd":distance_end,"zBottom":elevation_bottom,"zTop":elevation_top,"contactLines":contact_lines,
       "horizontalTick":horizontal_tick,"verticalTick":vertical_tick}
    (folder/"run.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    target=folder/"section.png"
    render(report,target,distance_end,elevation_bottom,elevation_top,horizontal_tick,vertical_tick,contact_lines)
    return target
