#!/usr/bin/env python3
"""Normalize generated interaction strips and compose the interaction atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid chroma key: {value}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def foreground_mask(
    image: Image.Image,
    chroma: tuple[int, int, int],
    threshold: int,
) -> tuple[Image.Image, list[int], str]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_minimum, _ = alpha.getextrema()
    if alpha_minimum < 255:
        column_counts = [0] * rgba.width
        for index, value in enumerate(alpha.get_flattened_data()):
            if value > 8:
                column_counts[index % rgba.width] += 1
        return alpha, column_counts, "alpha"

    pixels = list(rgba.get_flattened_data())
    mask_data = bytearray(len(pixels))
    column_counts = [0] * rgba.width
    threshold_squared = threshold * threshold
    for index, (red, green, blue, alpha) in enumerate(pixels):
        distance = (
            (red - chroma[0]) * (red - chroma[0])
            + (green - chroma[1]) * (green - chroma[1])
            + (blue - chroma[2]) * (blue - chroma[2])
        )
        if alpha > 8 and distance > threshold_squared:
            mask_data[index] = 255
            column_counts[index % rgba.width] += 1
    mask = Image.frombytes("L", rgba.size, bytes(mask_data))
    return mask, column_counts, "chroma-key"


def active_runs(column_counts: list[int], max_gap: int = 3) -> list[tuple[int, int]]:
    active = [index for index, count in enumerate(column_counts) if count >= 2]
    if not active:
        return []
    runs: list[tuple[int, int]] = []
    start = previous = active[0]
    for current in active[1:]:
        if current - previous > max_gap + 1:
            runs.append((start, previous + 1))
            start = current
        previous = current
    runs.append((start, previous + 1))
    return runs


def crop_pose(
    image: Image.Image,
    mask: Image.Image,
    x_range: tuple[int, int],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    left, right = x_range
    local_mask = mask.crop((left, 0, right, image.height))
    bbox = local_mask.getbbox()
    if bbox is None:
        raise ValueError("pose segment is empty")
    global_bbox = (left + bbox[0], bbox[1], left + bbox[2], bbox[3])
    pose = image.convert("RGBA").crop(global_bbox)
    pose_mask = mask.crop(global_bbox)
    pose.putalpha(pose_mask)
    return pose, global_bbox


def extract_poses(
    source: Path,
    expected_frames: int,
    chroma: tuple[int, int, int],
    threshold: int,
) -> tuple[list[Image.Image], list[dict], str]:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    mask, column_counts, mask_source = foreground_mask(image, chroma, threshold)
    runs = active_runs(column_counts)
    candidates: list[tuple[Image.Image, tuple[int, int, int, int]]] = []
    for run in runs:
        pose, bbox = crop_pose(image, mask, run)
        opaque_pixels = sum(
            1 for value in pose.getchannel("A").get_flattened_data() if value > 0
        )
        if pose.width >= 3 and pose.height >= 3 and opaque_pixels >= 64:
            candidates.append((pose, bbox))
    if len(candidates) != expected_frames:
        raise ValueError(
            f"{source.name}: expected {expected_frames} separated poses, found {len(candidates)}"
        )
    poses = [candidate[0] for candidate in candidates]
    report = [
        {
            "sourceBbox": list(candidate[1]),
            "sourceWidth": candidate[0].width,
            "sourceHeight": candidate[0].height,
        }
        for candidate in candidates
    ]
    return poses, report, mask_source


def normalize_poses(
    poses: list[Image.Image],
    cell_width: int,
    cell_height: int,
    margin_x: int = 18,
    margin_y: int = 16,
) -> tuple[list[Image.Image], float]:
    maximum_width = max(pose.width for pose in poses)
    maximum_height = max(pose.height for pose in poses)
    scale = min(
        (cell_width - 2 * margin_x) / maximum_width,
        (cell_height - 2 * margin_y) / maximum_height,
    )
    normalized = []
    for pose in poses:
        width = max(1, round(pose.width * scale))
        height = max(1, round(pose.height * scale))
        resized = pose.resize((width, height), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (cell_width, cell_height), (0, 0, 0, 0))
        x = (cell_width - width) // 2
        y = cell_height - margin_y - height
        cell.alpha_composite(resized, (x, y))
        normalized.append(cell)
    return normalized, scale


def make_contact_sheet(atlas: Image.Image, output: Path, scale: int = 1) -> None:
    if scale <= 1:
        preview = atlas
    else:
        preview = atlas.resize(
            (atlas.width * scale, atlas.height * scale), Image.Resampling.NEAREST
        )
    backdrop = Image.new("RGBA", preview.size, (32, 36, 42, 255))
    backdrop.alpha_composite(preview)
    output.parent.mkdir(parents=True, exist_ok=True)
    backdrop.convert("RGB").save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chroma-threshold", type=int, default=96)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    jobs_manifest = read_json(run_dir / "interaction-jobs.json")
    interaction = read_json(run_dir / "package" / "interaction.json")
    atlas_contract = interaction["atlases"]["interaction"]
    columns = int(atlas_contract["columns"])
    rows = int(atlas_contract["rows"])
    cell_width = int(atlas_contract["cellWidth"])
    cell_height = int(atlas_contract["cellHeight"])
    chroma = parse_hex_color(jobs_manifest["chromaKey"])
    atlas = Image.new(
        "RGBA", (columns * cell_width, rows * cell_height), (0, 0, 0, 0)
    )

    jobs = {job["id"]: job for job in jobs_manifest["jobs"]}
    animation_reports = {}
    for animation_id, animation in sorted(
        interaction["animations"].items(), key=lambda item: item[1]["row"]
    ):
        job = jobs.get(animation_id)
        if job is None:
            raise SystemExit(f"missing interaction job: {animation_id}")
        source = run_dir / job["outputPath"]
        if not source.is_file():
            raise SystemExit(f"missing generated row: {source}")
        try:
            poses, pose_reports, mask_source = extract_poses(
                source,
                int(animation["frames"]),
                chroma,
                args.chroma_threshold,
            )
            normalized, scale = normalize_poses(poses, cell_width, cell_height)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        row = int(animation["row"])
        for column, cell in enumerate(normalized):
            atlas.alpha_composite(cell, (column * cell_width, row * cell_height))
        animation_reports[animation_id] = {
            "row": row,
            "frames": len(normalized),
            "sharedScale": scale,
            "maskSource": mask_source,
            "poses": pose_reports,
        }

    output_path = run_dir / "package" / atlas_contract["path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output_path, format="WEBP", lossless=True, method=6)
    qa_dir = run_dir / "qa"
    make_contact_sheet(atlas, qa_dir / "interaction-contact-sheet.png")
    report = {
        "ok": True,
        "atlas": str(output_path),
        "width": atlas.width,
        "height": atlas.height,
        "cellWidth": cell_width,
        "cellHeight": cell_height,
        "chromaKey": jobs_manifest["chromaKey"],
        "animations": animation_reports,
    }
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "composition.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
