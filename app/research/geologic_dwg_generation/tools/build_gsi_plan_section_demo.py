"""Build a dated, source-aware GSI aerial-photo plan and terrain profile demo."""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ENGINE_PROJECT = Path(__file__).resolve().parents[3] / "subprojects" / "geologic_3d_engine"
if str(ENGINE_PROJECT) not in sys.path:
    sys.path.insert(0, str(ENGINE_PROJECT))

from geologic_3d_engine.section.plan_evidence import (
    PlanEvidenceLayer, PriorityXyzElevationSampler, XyzRasterSampler, build_plan_evidence,
    classify_orthophoto_metadata_point, global_pixel_to_lonlat,
    lonlat_to_global_pixel, sample_geographic_route)
from geologic_3d_engine.section.gsj_surface_geology import sample_route_legends


PHOTO_URL = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"
PHOTO_METADATA_URL = "https://maps.gsi.go.jp/xyz/seamlessphoto_spec/{z}/{x}/{y}.geojson"
PHOTO_METADATA_ZOOM = 11
DEM_SOURCES = (
    ("DEM1A", "dem1a_png", 17), ("DEM5A", "dem5a_png", 15),
    ("DEM5B", "dem5b_png", 15), ("DEM5C", "dem5c_png", 15),
    ("DEM10B", "dem_png", 14),
)
DEM_URL = "https://cyberjapandata.gsi.go.jp/xyz/{name}/{z}/{x}/{y}.png"
GSJ_LEGEND_URL = "https://gbank.gsj.jp/seamless/v2/api/1.3.1/legend.json?point={lat},{lon}&type=level4"


def _ascii_acquisition_label(value):
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月～(\d{1,2})月", value or "")
    if match:
        year, start, end = match.groups()
        return f"{year}-{int(start):02d} to {year}-{int(end):02d}"
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月", value or "")
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    return "see evidence metadata"


def _download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "geologic-3d-engine-research/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            path.write_bytes(response.read())
    return path.read_bytes()


def _decode_dem(data):
    rgb = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=np.int64)
    encoded = rgb[..., 0]*65536 + rgb[..., 1]*256 + rgb[..., 2]
    values = np.where(encoded > 2**23, encoded-2**24, encoded).astype(float)*0.01
    values[encoded == 2**23] = np.nan
    return values


class CachedGsi:
    def __init__(self, root):
        self.root = Path(root)
        self.used_photo = {}
        self.used_dem = {}
        self.used_photo_metadata = {}

    def photo(self, z, x, y):
        path = self.root / "seamlessphoto" / str(z) / str(x) / f"{y}.jpg"
        data = _download(PHOTO_URL.format(z=z, x=x, y=y), path)
        self.used_photo[str(path)] = hashlib.sha256(data).hexdigest()
        return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))

    def elevation(self, lon, lat):
        for source, name, zoom in DEM_SOURCES:
            gx, gy = lonlat_to_global_pixel(lon, lat, zoom)
            px, py = int(gx), int(gy)
            path = self.root / name / str(zoom) / str(px//256) / f"{py//256}.png"
            missing = path.with_suffix(".missing")
            if missing.exists():
                continue
            try:
                data = _download(DEM_URL.format(name=name, z=zoom, x=px//256, y=py//256), path)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    missing.parent.mkdir(parents=True, exist_ok=True)
                    missing.write_text("HTTP 404\n", encoding="ascii")
                    continue
                raise
            self.used_dem[str(path)] = hashlib.sha256(data).hexdigest()
            value = _decode_dem(data)[py % 256, px % 256]
            if math.isfinite(float(value)):
                return float(value), source
        return None, None

    def elevation_tile(self, source, name, zoom, z, x, y):
        if z != zoom:
            raise ValueError("DEM sampler zoom mismatch")
        path = self.root / name / str(z) / str(x) / f"{y}.png"
        missing = path.with_suffix(".missing")
        if missing.exists():
            return None
        try:
            data = _download(DEM_URL.format(name=name, z=z, x=x, y=y), path)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                missing.parent.mkdir(parents=True, exist_ok=True)
                missing.write_text("HTTP 404\n", encoding="ascii")
                return None
            raise
        self.used_dem[str(path)] = hashlib.sha256(data).hexdigest()
        return _decode_dem(data)

    def photo_metadata(self, longitude, latitude):
        gx, gy = lonlat_to_global_pixel(longitude, latitude, PHOTO_METADATA_ZOOM)
        tx, ty = int(gx)//256, int(gy)//256
        path = self.root / "seamlessphoto_spec" / str(PHOTO_METADATA_ZOOM) / str(tx) / f"{ty}.geojson"
        data = _download(PHOTO_METADATA_URL.format(z=PHOTO_METADATA_ZOOM, x=tx, y=ty), path)
        self.used_photo_metadata[str(path)] = hashlib.sha256(data).hexdigest()
        return json.loads(data.decode("utf-8")), {"z":PHOTO_METADATA_ZOOM,"x":tx,"y":ty}


def run(project_root, route=None, sample_spacing_m=25.0, output_directory=None,
        terrain_sampling_method="BilinearPixelCentres", cache_directory=None):
    root = Path(project_root)
    output = Path(output_directory) if output_directory else root / "outputs" / "gsi_plan_section_cycle1_20260904"
    cache = CachedGsi(Path(cache_directory) if cache_directory else output / "tiles")
    zoom = 15
    route = route or [[131.036, 32.878], [131.044, 32.887], [131.052, 32.880], [131.057, 32.889]]
    margin = 0.0015
    bounds = (min(p[0] for p in route)-margin, min(p[1] for p in route)-margin,
              max(p[0] for p in route)+margin, max(p[1] for p in route)+margin)
    left, top = lonlat_to_global_pixel(bounds[0], bounds[3], zoom)
    right, bottom = lonlat_to_global_pixel(bounds[2], bounds[1], zoom)
    tx0, ty0, tx1, ty1 = int(left)//256, int(top)//256, int(right)//256, int(bottom)//256
    mosaic = Image.new("RGB", ((tx1-tx0+1)*256, (ty1-ty0+1)*256))
    for ty in range(ty0, ty1+1):
        for tx in range(tx0, tx1+1):
            mosaic.paste(Image.fromarray(cache.photo(zoom, tx, ty)), ((tx-tx0)*256, (ty-ty0)*256))
    photo_tile_metadata = []
    for ty in range(ty0, ty1+1):
        for tx in range(tx0, tx1+1):
            samples = []
            for fx, fy in ((0.5,0.5),(0.001,0.001),(0.999,0.001),(0.001,0.999),(0.999,0.999)):
                lon, lat = global_pixel_to_lonlat((tx+fx)*256, (ty+fy)*256, zoom)
                metadata, metadata_tile = cache.photo_metadata(lon, lat)
                samples.append(classify_orthophoto_metadata_point(metadata, lon, lat))
            identities = {(row.get("dataSource"), row.get("acquisitionDateOrRange"))
                          for row in samples if row["status"] == "ExactPolygonMatch"}
            status = "FivePointConsistentMetadata" if len(identities) == 1 and all(
                row["status"] == "ExactPolygonMatch" for row in samples) else "MixedOrIncompleteTileMetadata"
            photo_tile_metadata.append({"photoTile":{"z":zoom,"x":tx,"y":ty},
                "metadataTile":metadata_tile, "status":status,
                "sampleClassifications":samples,
                "interpretationRole":"VisibleSurfaceContext"})
    crop_box = (int(left-tx0*256), int(top-ty0*256),
                int(math.ceil(right-tx0*256)), int(math.ceil(bottom-ty0*256)))
    plan = mosaic.crop(crop_box)

    priority_sources = []
    for source, name, source_zoom in DEM_SOURCES:
        priority_sources.append((source, XyzRasterSampler(
            source_zoom, "Elevation",
            lambda z, x, y, source=source, name=name, source_zoom=source_zoom:
                cache.elevation_tile(source, name, source_zoom, z, x, y))))
    query_sampler = PriorityXyzElevationSampler(priority_sources)
    skeleton = sample_geographic_route(
        route, sample_spacing_m, query_sampler,
        sampling_method=terrain_sampling_method)
    source_by_station = []
    for row in skeleton:
        row["demSource"] = row["elevationSourceId"]
        source_by_station.append(row["demSource"])

    draw = ImageDraw.Draw(plan)
    def plan_xy(lon, lat):
        gx, gy = lonlat_to_global_pixel(lon, lat, zoom)
        return int(gx-left), int(gy-top)
    route_pixels = [plan_xy(*point) for point in route]
    draw.line(route_pixels, fill=(255, 40, 20), width=4)
    for index, point in enumerate(route_pixels):
        draw.ellipse((point[0]-5, point[1]-5, point[0]+5, point[1]+5), fill=(255,255,0))
        draw.text((point[0]+7, point[1]-7), chr(65+index), fill=(0,0,0))
    metadata_pairs = sorted({(row.get("dataSource"), row.get("acquisitionDateOrRange"))
        for tile in photo_tile_metadata for row in tile["sampleClassifications"]
        if row["status"] == "ExactPolygonMatch"})
    metadata_label = " / ".join(f"GSI aerial acquisition: {_ascii_acquisition_label(date)}"
                                for _source, date in metadata_pairs)
    if metadata_label:
        draw.rectangle((3, 3, min(plan.width-3, 12+len(metadata_label)*7), 25),
                       fill=(255, 255, 255), outline=(0, 0, 0))
        draw.text((8, 7), metadata_label, fill=(0, 0, 0))

    width, profile_height = plan.width, 260
    canvas = Image.new("RGB", (width, plan.height+profile_height), "white")
    canvas.paste(plan, (0,0))
    pd = ImageDraw.Draw(canvas)
    valid = [row for row in skeleton if row["elevationM"] is not None]
    zmin, zmax = min(r["elevationM"] for r in valid), max(r["elevationM"] for r in valid)
    margin = 45
    profile_points = []
    for row in valid:
        x = margin + (width-2*margin)*row["stationM"]/valid[-1]["stationM"]
        y = plan.height+profile_height-margin-(profile_height-2*margin)*(row["elevationM"]-zmin)/max(zmax-zmin,1)
        profile_points.append((int(x), int(y)))
    pd.line(profile_points, fill=(35,70,40), width=3)
    route_label = f"A-{chr(64 + len(route))}"
    pd.text((10, plan.height+8),
            f"GSI DEM terrain profile / {terrain_sampling_method} / arbitrary bent route {route_label}",
            fill=(0,0,0))
    pd.text((10, plan.height+28), f"Elevation {zmin:.1f}-{zmax:.1f} m; subsurface lithology NOT inferred", fill=(150,0,0))
    image_path = output / "current_aerial_and_arbitrary_terrain_profile.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(image_path)

    photo_digest = hashlib.sha256("".join(cache.used_photo[k] for k in
                                          sorted(cache.used_photo)).encode()).hexdigest()
    dem_digest = hashlib.sha256("".join(cache.used_dem[k] for k in
                                        sorted(cache.used_dem)).encode()).hexdigest()
    verified_dates = sorted({row["sampleClassifications"][0]["acquisitionDateOrRange"]
        for row in photo_tile_metadata if row["status"] == "FivePointConsistentMetadata"})
    photo_date = ", ".join(verified_dates) if verified_dates else "per-tile metadata unresolved"
    layers = [
        PlanEvidenceLayer("GSI-CURRENT-AERIAL", "Orthophoto", "GSI-AERIAL-SEAMLESS",
            PHOTO_URL, "JGD2011/WebMercator", photo_date,
            photo_digest, "VisibleSurfaceContext"),
        PlanEvidenceLayer("GSI-DEM", "DEM", "GSI-ELEVATION-TILE",
            DEM_URL, "JGD2011/WebMercator", f"retrieved {date.today().isoformat()}",
            dem_digest, "TerrainElevation")]
    # Query mapped surface units at a coarser, explicit spacing. A transition
    # is bracketed between queries rather than claimed at an exact position.
    geology_profile = skeleton[::5]
    if geology_profile[-1] is not skeleton[-1]:
        geology_profile.append(skeleton[-1])
    geology_bytes = []
    def query_gsj(latitude, longitude):
        url = GSJ_LEGEND_URL.format(lat=f"{latitude:.8f}", lon=f"{longitude:.8f}")
        request = urllib.request.Request(url, headers={"User-Agent":"geologic-3d-engine-research/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        geology_bytes.append(data)
        return json.loads(data.decode("utf-8"))
    geology = sample_route_legends(geology_profile, query_gsj, "2026-05-10",
                                   allow_color_metadata_mismatch=True)
    geology_digest = hashlib.sha256(b"".join(geology_bytes)).hexdigest()
    layers.append(PlanEvidenceLayer("GSJ-SURFACE-GEOLOGY", "SurfaceGeology",
        "GSJ-SEAMLESS-V2-API", GSJ_LEGEND_URL, "JGD2011/WebMercator",
        f"map edition 2026-05-10; retrieved {date.today().isoformat()}", geology_digest,
        "MappedSurfaceUnit"))
    bundle = build_plan_evidence(layers, route, skeleton)
    bundle["tileSha256"] = {"orthophoto": cache.used_photo, "dem": cache.used_dem}
    bundle["orthophotoMetadata"] = {"canonicalUrl":PHOTO_METADATA_URL,
        "metadataTileSha256":cache.used_photo_metadata, "photoTiles":photo_tile_metadata,
        "classificationMethod":"TileCenterAndFourInsetCorners",
        "inferenceBoundary":"AcquisitionProvenanceOnly_NoSubsurfaceAuthorization"}
    bundle["visualization"] = str(image_path)
    bundle["aerialMetadataStatus"] = ("AllPhotoTilesFivePointConsistent" if all(
        row["status"] == "FivePointConsistentMetadata" for row in photo_tile_metadata)
        else "MixedOrIncompletePerTileMetadata")
    bundle["surfaceGeology"] = geology
    bundle["terrainSampling"] = {
        "method": terrain_sampling_method,
        "sourcePolicy": "FirstCompletePriorityLayer_NoCrossSourcePixelMixing",
        "accuracyBoundary": "ResamplingDoesNotIncreaseNativeDemAccuracyOrResolution",
        "cacheDirectory": str(cache.root)}
    (output / "plan_evidence_bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"image":str(image_path), "samples":len(skeleton),
                      "valid":len(valid), "demSources":sorted(set(source_by_station)),
                      "authorizationState":bundle["authorizationState"]}, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GSI plan and arbitrary terrain-profile preview")
    parser.add_argument("--route-json", help="JSON array of [longitude, latitude] vertices")
    parser.add_argument("--spacing-m", type=float, default=25.0)
    parser.add_argument("--output")
    parser.add_argument("--terrain-sampling", choices=("NearestPixel", "BilinearPixelCentres"),
                        default="BilinearPixelCentres")
    parser.add_argument("--cache", help="Optional existing GSI tile cache directory")
    args = parser.parse_args()
    selected_route = json.loads(args.route_json) if args.route_json else None
    run(Path(__file__).resolve().parents[3], selected_route, args.spacing_m, args.output,
        args.terrain_sampling, args.cache)
