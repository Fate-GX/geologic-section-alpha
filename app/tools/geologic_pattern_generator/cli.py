from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine import generate, load_catalog, read_terrain, write_outputs


def main():
    parser = argparse.ArgumentParser(description="Evidence-gated synthetic geologic section pattern generator")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--terrain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).with_name("process_catalog.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = generate(config, read_terrain(args.terrain), load_catalog(args.catalog))
    report = write_outputs(result, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 2)


if __name__ == "__main__":
    main()
