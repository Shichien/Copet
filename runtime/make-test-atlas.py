#!/usr/bin/env python3
"""Build a visibly functional test atlas from an official Codex pet atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


SOURCE_ROWS = {
    "feeding": (0, 6),
    "petting": (3, 4),
    "bathing": (4, 5),
    "playing": (7, 6),
    "sleeping": (6, 6),
    "waking": (3, 4),
    "hungry": (6, 6),
    "dirty": (5, 8),
    "sick": (5, 8),
    "happy": (3, 4),
    "celebrate": (4, 5),
    "refuse": (5, 4),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True)
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    interaction = json.loads((package_dir / "interaction.json").read_text(encoding="utf-8"))
    official = json.loads((package_dir / "pet.json").read_text(encoding="utf-8"))
    atlas_contract = interaction["atlases"]["interaction"]
    cell_width = atlas_contract["cellWidth"]
    cell_height = atlas_contract["cellHeight"]
    columns = atlas_contract["columns"]
    rows = atlas_contract["rows"]

    with Image.open(package_dir / official["spritesheetPath"]) as opened:
        source = opened.convert("RGBA")
    if source.width != columns * cell_width:
        raise SystemExit(f"official atlas width {source.width} does not match {columns * cell_width}")

    atlas = Image.new("RGBA", (columns * cell_width, rows * cell_height), (0, 0, 0, 0))
    mappings = {}
    for animation_name, animation in interaction["animations"].items():
        source_row, source_frames = SOURCE_ROWS[animation_name]
        if (source_row + 1) * cell_height > source.height:
            raise SystemExit(f"official atlas has no row {source_row} for {animation_name}")
        target_row = animation["row"]
        frame_count = animation["frames"]
        used_columns = []
        for target_column in range(frame_count):
            source_column = target_column % source_frames
            cell = source.crop(
                (
                    source_column * cell_width,
                    source_row * cell_height,
                    (source_column + 1) * cell_width,
                    (source_row + 1) * cell_height,
                )
            )
            atlas.alpha_composite(cell, (target_column * cell_width, target_row * cell_height))
            used_columns.append(source_column)
        mappings[animation_name] = {
            "targetRow": target_row,
            "sourceOfficialRow": source_row,
            "sourceColumns": used_columns,
        }

    output = package_dir / atlas_contract["path"]
    atlas.save(output, format="WEBP", lossless=True, method=6)
    report_path = package_dir.parent / "qa" / "test-atlas.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "temporaryTestAsset": True,
                "purpose": "runtime integration testing only; replace with generated interaction rows",
                "output": str(output),
                "size": [atlas.width, atlas.height],
                "mappings": mappings,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "output": str(output), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()
