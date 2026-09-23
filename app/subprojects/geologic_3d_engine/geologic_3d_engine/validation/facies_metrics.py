"""Descriptive statistics on categorical Cartesian volumes, not geology approval.

No external geological solver is imported. Arrays are ZYX; spacing is XYZ.
Empirical semivariance follows the project's experimental_semivariance definition.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def _component_sizes(occupied):
    remaining = occupied.copy()
    sizes = []
    nz, ny, nx = remaining.shape
    for flat in np.flatnonzero(occupied):
        z, y, x = np.unravel_index(flat, remaining.shape)
        if not remaining[z, y, x]:
            continue
        remaining[z, y, x] = False
        pending = [(z, y, x)]
        size = 0
        while pending:
            a, b, c = pending.pop()
            size += 1
            for p, q, r in ((a-1,b,c),(a+1,b,c),(a,b-1,c),
                            (a,b+1,c),(a,b,c-1),(a,b,c+1)):
                if 0 <= p < nz and 0 <= q < ny and 0 <= r < nx and remaining[p,q,r]:
                    remaining[p,q,r] = False
                    pending.append((p,q,r))
        sizes.append(size)
    return sorted(sizes, reverse=True)


def describe_facies(labels_zyx, spacing_xyz, *, valid_mask=None, max_lag=4,
                    length_unit="m"):
    labels = np.asarray(labels_zyx)
    if labels.ndim != 3 or not labels.size or labels.size > 2_000_000:
        raise ValueError("Expected nonempty 3D labels, at most 2000000 cells")
    if labels.dtype.kind not in "iuf" or not np.isfinite(labels).all():
        raise ValueError("Labels must be finite numeric integer IDs")
    if not np.equal(labels, np.floor(labels)).all():
        raise ValueError("Fractional category IDs are invalid")
    spacing = np.asarray(spacing_xyz)
    if (spacing.shape != (3,) or spacing.dtype.kind not in "iuf"
            or not np.isfinite(spacing).all() or np.any(spacing <= 0)):
        raise ValueError("Spacing must contain three finite positive lengths in XYZ order")
    if type(max_lag) is not int or not 1 <= max_lag <= 64:
        raise ValueError("max_lag must be an integer in [1,64]")
    if length_unit not in ("m", "km", "mm"):
        raise ValueError("Unsupported length unit; no implicit conversion")
    mask = np.ones(labels.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    if mask.dtype != np.dtype(bool) or mask.shape != labels.shape:
        raise ValueError("Mask must be Boolean and exactly match ZYX shape")
    count = int(mask.sum())
    if not count:
        raise ValueError("No valid cells")
    categories = np.unique(labels[mask])
    if len(categories) > 64:
        raise ValueError("At most 64 categories are supported")
    result = {"schemaVersion":"1.0", "status":"DescriptiveOnly",
              "algorithmBasisType":"ProjectEmpiricalStatisticDefinition",
              "equationReference":"FACIES-METRICS-001",
              "shapeZYX":list(labels.shape), "spacingXYZ":spacing.tolist(),
              "lengthUnit":length_unit, "validCellCount":count,
              "excludedCellCount":int(labels.size-count), "connectivity":6,
              "realRegionAuthorized":False, "categories":[],
              "limitations":["No fitted range or model identification",
                             "Masked finite-domain statistics; no periodic wrapping",
                             "One realization is not an ensemble uncertainty estimate",
                             "Connectivity is voxel-scale, not mesh manifoldness"]}
    for category in categories:
        indicator = labels == category
        occupied = indicator & mask
        cells = int(occupied.sum())
        sizes = _component_sizes(occupied)
        record = {"id":int(category), "cellCount":cells, "fraction":cells/count,
                  "componentCount":len(sizes), "componentSizesDescending":sizes,
                  "largestComponentFraction":sizes[0]/cells, "directional":{}}
        for axis_name, axis, step in (("X",2,spacing[0]),("Y",1,spacing[1]),("Z",0,spacing[2])):
            rows = []
            for lag in range(1,max_lag+1):
                pairs = mismatches = 0
                if lag < labels.shape[axis]:
                    left = [slice(None)]*3
                    right = [slice(None)]*3
                    left[axis] = slice(None,-lag)
                    right[axis] = slice(lag,None)
                    left, right = tuple(left), tuple(right)
                    valid_pairs = mask[left] & mask[right]
                    pairs = int(valid_pairs.sum())
                    mismatches = int(((indicator[left] != indicator[right]) & valid_pairs).sum())
                rows.append({"lagCells":lag, "distance":float(lag*step),
                             "pairCount":pairs, "mismatchCount":mismatches,
                             "indicatorSemivariance":mismatches/(2*pairs) if pairs else None})
            record["directional"][axis_name] = rows
        result["categories"].append(record)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--key", required=True)
    parser.add_argument("--order", choices=("XYZ","ZYX"), required=True)
    parser.add_argument("--spacing", nargs=3, type=float, required=True)
    parser.add_argument("--mask-key", help="Boolean array in the same axis order as labels")
    parser.add_argument("--exclude", nargs="*", type=int, default=[])
    parser.add_argument("--lag", type=int, default=4)
    parser.add_argument("--unit", choices=("m","km","mm"), default="m")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    with np.load(args.input, allow_pickle=False) as data:
        labels = data[args.key]
        mask = data[args.mask_key] if args.mask_key else np.ones(labels.shape,dtype=bool)
        if mask.dtype != bool or mask.shape != labels.shape:
            raise ValueError("Invalid source mask")
        mask = mask & ~np.isin(labels,args.exclude)
        if args.order == "XYZ":
            labels, mask = labels.transpose(2,1,0), mask.transpose(2,1,0)
        report = describe_facies(labels,args.spacing,valid_mask=mask,max_lag=args.lag,length_unit=args.unit)
    report["input"] = {"file":args.input.name,"sha256":digest,"key":args.key,
                       "arrayOrder":args.order,"maskKey":args.mask_key,"excludedIds":args.exclude}
    with args.output.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(f"FACIES_METRICS=OK;VALID_CELLS={report['validCellCount']};REAL_REGION_AUTHORIZED=false")


if __name__ == "__main__":
    main()
