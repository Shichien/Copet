#!/usr/bin/env python3
"""Prepare deterministic prompts and manifests for an interactive Codex pet."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw


CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
CHROMA_CANDIDATES = [
    ("magenta", "#FF00FF"),
    ("cyan", "#00FFFF"),
    ("yellow", "#FFFF00"),
    ("blue", "#0000FF"),
    ("orange", "#FF7F00"),
    ("green", "#00FF00"),
]

ANIMATIONS = [
    {
        "id": "feeding",
        "row": 0,
        "frames": 8,
        "durationsMs": [130, 130, 150, 170, 170, 150, 150, 260],
        "loop": False,
        "purpose": "receive food, eat, swallow, and settle",
    },
    {
        "id": "petting",
        "row": 1,
        "frames": 6,
        "durationsMs": [180, 140, 140, 160, 180, 260],
        "loop": True,
        "purpose": "react through the head, ears, face, or body to pointer petting",
    },
    {
        "id": "bathing",
        "row": 2,
        "frames": 8,
        "durationsMs": [140, 140, 160, 180, 180, 150, 150, 260],
        "loop": False,
        "purpose": "wipe clean while fully clothed, shake off, and settle",
    },
    {
        "id": "playing",
        "row": 3,
        "frames": 8,
        "durationsMs": [130, 130, 130, 160, 130, 130, 160, 240],
        "loop": True,
        "purpose": "play using established body language or an identity prop",
    },
    {
        "id": "sleeping",
        "row": 4,
        "frames": 6,
        "durationsMs": [320, 220, 220, 260, 260, 360],
        "loop": True,
        "purpose": "settle into a quiet breathing sleep",
    },
    {
        "id": "waking",
        "row": 5,
        "frames": 4,
        "durationsMs": [220, 180, 180, 300],
        "loop": False,
        "purpose": "wake, stretch, and return near official idle",
    },
    {
        "id": "hungry",
        "row": 6,
        "frames": 6,
        "durationsMs": [220, 160, 160, 180, 220, 300],
        "loop": True,
        "purpose": "ask for food through body language without symbols",
    },
    {
        "id": "dirty",
        "row": 7,
        "frames": 6,
        "durationsMs": [220, 160, 160, 180, 220, 300],
        "loop": True,
        "purpose": "show discomfort and a need for cleaning without symbols",
    },
    {
        "id": "sick",
        "row": 8,
        "frames": 8,
        "durationsMs": [220, 180, 180, 220, 180, 180, 220, 320],
        "loop": True,
        "purpose": "show low health gently without graphic distress",
    },
    {
        "id": "happy",
        "row": 9,
        "frames": 6,
        "durationsMs": [160, 140, 140, 160, 180, 260],
        "loop": True,
        "purpose": "show a calm positive reaction distinct from celebration",
    },
    {
        "id": "celebrate",
        "row": 10,
        "frames": 8,
        "durationsMs": [120, 120, 140, 160, 160, 140, 160, 280],
        "loop": False,
        "purpose": "celebrate a milestone with a clear full-body action",
    },
    {
        "id": "refuse",
        "row": 11,
        "frames": 4,
        "durationsMs": [180, 150, 150, 280],
        "loop": False,
        "purpose": "decline an invalid action with a brief head or body gesture",
    },
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def create_layout_guide(path: Path, frames: int) -> None:
    width = frames * CELL_WIDTH
    image = Image.new("RGB", (width, CELL_HEIGHT), "#F7F7F7")
    draw = ImageDraw.Draw(image)
    for index in range(frames):
        left = index * CELL_WIDTH
        right = left + CELL_WIDTH - 1
        draw.rectangle((left, 0, right, CELL_HEIGHT - 1), outline="#111111", width=2)
        draw.rectangle(
            (left + 18, 16, right - 18, CELL_HEIGHT - 17),
            outline="#2F80ED",
            width=2,
        )
        center_x = left + CELL_WIDTH // 2
        draw.line((center_x, 16, center_x, CELL_HEIGHT - 17), fill="#BBBBBB", width=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def extract_canonical_base(spritesheet: Path, output: Path) -> None:
    with Image.open(spritesheet) as image:
        if image.width != COLUMNS * CELL_WIDTH or image.height < CELL_HEIGHT:
            raise SystemExit(f"unsupported official spritesheet geometry: {image.size}")
        cell = image.convert("RGBA").crop((0, 0, CELL_WIDTH, CELL_HEIGHT))
        if cell.getbbox() is None:
            raise SystemExit("official idle frame 0 is empty")
        output.parent.mkdir(parents=True, exist_ok=True)
        cell.save(output)


def choose_chroma_key(canonical_base: Path) -> dict[str, str | int]:
    with Image.open(canonical_base) as opened:
        image = opened.convert("RGBA")
    opaque = [pixel for pixel in image.get_flattened_data() if pixel[3] > 8]
    if not opaque:
        raise SystemExit("canonical base has no visible pixels")
    threshold_squared = 96 * 96
    scored = []
    for name, hex_value in CHROMA_CANDIDATES:
        red = int(hex_value[1:3], 16)
        green = int(hex_value[3:5], 16)
        blue = int(hex_value[5:7], 16)
        conflicts = sum(
            1
            for pixel_red, pixel_green, pixel_blue, _alpha in opaque
            if (pixel_red - red) ** 2
            + (pixel_green - green) ** 2
            + (pixel_blue - blue) ** 2
            <= threshold_squared
        )
        scored.append((conflicts, name, hex_value))
    conflicts, name, hex_value = min(scored)
    return {"name": name, "hex": hex_value, "conflictingOpaquePixels": conflicts}


def row_prompt(pet_id: str, animation: dict, chroma_key: dict) -> str:
    state = animation["id"]
    prompt_state = "fully-clothed pet cleaning" if state == "bathing" else state
    frames = animation["frames"]
    loop_rule = (
        "The final pose must connect naturally back to the first pose."
        if animation["loop"]
        else "Show a complete beginning, action, and settled ending."
    )
    special = {
        "feeding": (
            "Use one simple opaque food item such as a small cookie or piece of bread. "
            "Keep it touching or held by the pet; never draw a floating inventory item. "
            "Do not draw another character, hand, arm, or body part."
        ),
        "petting": (
            "Do not draw a hand. Show only the pet's physical reaction to pointer petting. "
            "Do not add hearts, flowers, sparkles, motion marks, icons, or symbols outside the pet silhouette."
        ),
        "bathing": (
            "Draw exactly eight distinct poses, not six. Keep the exact canonical uniform fully worn "
            "and keep the umbrella touching or held in every pose. Use one small opaque white cleaning "
            "cloth touching the pet. Keep the umbrella folded and close to the body in the six middle "
            "poses. Do not add foam, droplets, splashes, water marks, motion marks, or particles."
        ),
        "playing": (
            "Use an established identity prop when present; otherwise use body movement without a detached toy. "
            "Keep the umbrella folded and close to the body in the six middle poses."
        ),
        "sleeping": (
            "All six poses must show the pet already asleep in the same seated or curled resting posture, "
            "with closed eyes and only small breathing changes. Do not use a standing pose. Keep the "
            "umbrella folded and touching the pet. No Z letters, sleep symbols, or detached marks."
        ),
        "waking": (
            "Begin from a sleeping pose and finish near the canonical idle pose. "
            "Use a yawn and stretch only; no Z letters, sleep symbols, or detached marks."
        ),
        "hungry": (
            "Use posture and expression only; no food icons, text, plates, speech bubbles, "
            "motion lines, squiggles, or detached marks."
        ),
        "dirty": (
            "Use posture, fur, material, or expression only; no dirt icons, text, or floating marks. "
            "Keep the umbrella folded and close to the body in the four middle poses."
        ),
        "sick": (
            "Keep distress gentle and non-graphic and express it through face and posture only. "
            "Keep the exact canonical clothing and umbrella in every pose. Do not add blankets, cups, "
            "thermometers, steam, breath clouds, scribbles, medical icons, text, effects, or extra items. "
            "Keep the umbrella folded and close to the body in the six middle poses."
        ),
        "happy": "Keep the reaction calmer and smaller than the celebrate animation.",
        "celebrate": (
            "Use a full-body action; no confetti, particles, text, or detached effects. "
            "Keep the umbrella folded and close to the body in the six middle poses."
        ),
        "refuse": "Use a head or body gesture; no crosses, warning icons, text, or speech bubbles.",
    }[state]
    return f"""Create one coherent horizontal interaction animation strip for pet `{pet_id}`.

Use the attached canonical idle frame as the exact identity reference and the layout guide only for invisible spacing. Preserve the same face, body proportions, silhouette, palette, materials, markings, clothing, and props.

State: `{prompt_state}`.
Purpose: {animation['purpose']}.
Output exactly {frames} separated, centered, complete full-body poses from left to right. {loop_rule} {special}

Use one flat pure {chroma_key['name']} {chroma_key['hex']} background. Distribute the poses evenly across the full canvas width. Scale the complete pet and every attached prop to fit inside its own invisible equal-width slot. Leave at least 64 pixels of uninterrupted pure background from top to bottom between every two adjacent poses. No silhouette, hair, clothing, prop, effect, or antialiased edge may touch or overlap another pose. Keep a stable baseline. Do not include visible grid lines, labels, interface elements, shadows, scenery, glow, blur, motion streaks, or detached particles. Do not use {chroma_key['hex']} inside the pet.
"""


def behavior_manifest(pet_id: str) -> dict:
    animations = {
        animation["id"]: {
            "atlas": "interaction",
            "row": animation["row"],
            "frames": animation["frames"],
            "durationsMs": animation["durationsMs"],
            "loop": animation["loop"],
            "interruptible": animation["loop"],
        }
        for animation in ANIMATIONS
    }
    return {
        "schemaVersion": 1,
        "petId": pet_id,
        "compatibility": {
            "officialWakeCommand": "/pet",
            "officialManifest": "pet.json",
            "officialAtlas": "spritesheet.webp",
            "currentCodexReadsInteractionFiles": False,
            "requiredRuntimeCapability": "interactive-pet-v1",
        },
        "atlases": {
            "interaction": {
                "path": "interaction-spritesheet.webp",
                "columns": COLUMNS,
                "rows": len(ANIMATIONS),
                "cellWidth": CELL_WIDTH,
                "cellHeight": CELL_HEIGHT,
            }
        },
        "animations": animations,
        "initialState": {
            "hunger": 80,
            "cleanliness": 80,
            "mood": 70,
            "energy": 80,
            "health": 100,
            "growth": 0,
            "coins": 30,
        },
        "initialInventory": {
            "meal": 2,
            "soap": 1,
            "toy": 0,
            "medicine": 1,
        },
        "needs": {
            "range": [0, 100],
            "offlineDecayCapHours": 8,
            "healthSafeFloor": 20,
            "criticalHealthDecayPerHour": -2,
            "decayPerHour": {
                "hunger": -4,
                "cleanliness": -2,
                "mood": -1,
                "energy": -3,
                "health": 0,
            },
        },
        "automaticStates": [
            {"when": {"health": {"lte": 30}}, "animation": "sick", "priority": 100},
            {"when": {"hunger": {"lte": 25}}, "animation": "hungry", "priority": 90},
            {"when": {"cleanliness": {"lte": 25}}, "animation": "dirty", "priority": 80},
            {"when": {"energy": {"lte": 20}}, "animation": "sleeping", "priority": 70},
            {"when": {"mood": {"gte": 85}}, "animation": "happy", "priority": 10},
        ],
        "items": {
            "meal": {"category": "food", "cost": 8},
            "soap": {"category": "care", "cost": 6},
            "toy": {"category": "play", "cost": 12, "consumable": False},
            "medicine": {"category": "health", "cost": 15},
        },
        "actions": {
            "feed": {
                "animation": "feeding",
                "item": "meal",
                "effects": {"hunger": 30, "mood": 4, "growth": 1},
                "cooldownSeconds": 30,
            },
            "pet": {
                "animation": "petting",
                "effects": {"mood": 10, "growth": 1, "coins": 2},
                "cooldownSeconds": 10,
            },
            "bathe": {
                "animation": "bathing",
                "item": "soap",
                "effects": {"cleanliness": 35, "mood": -2, "growth": 1},
                "cooldownSeconds": 60,
            },
            "play": {
                "animation": "playing",
                "item": "toy",
                "effects": {
                    "mood": 18,
                    "energy": -12,
                    "hunger": -6,
                    "growth": 2,
                    "coins": 3,
                },
                "cooldownSeconds": 60,
            },
            "sleep": {
                "animation": "sleeping",
                "completionAnimation": "waking",
                "effects": {"energy": 40, "growth": 1},
                "cooldownSeconds": 120,
            },
            "treat": {
                "animation": "sick",
                "completionAnimation": "happy",
                "item": "medicine",
                "effects": {"health": 35, "mood": -3, "growth": 1},
                "cooldownSeconds": 120,
            },
        },
        "taskEventBindings": {
            "running": {"source": "official", "animation": "running"},
            "needs-input": {"source": "official", "animation": "waiting"},
            "ready": {"source": "official", "animation": "review"},
            "blocked": {"source": "official", "animation": "failed"},
            "milestone": {"source": "interaction", "animation": "celebrate"},
        },
        "transactionPolicy": {
            "applyEffects": "after-animation-completes",
            "interruptedAction": "apply-nothing",
            "clampNeedsToRange": True,
            "randomness": "forbidden",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-pet-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    official_dir = Path(args.official_pet_dir).expanduser().resolve()
    run_dir = Path(args.output_dir).expanduser().resolve()
    manifest_path = official_dir / "pet.json"
    if not manifest_path.is_file():
        raise SystemExit(f"official pet manifest not found: {manifest_path}")
    official_manifest = read_json(manifest_path)
    spritesheet_name = official_manifest.get("spritesheetPath")
    if not isinstance(spritesheet_name, str) or not spritesheet_name:
        raise SystemExit("pet.json has no valid spritesheetPath")
    official_spritesheet = official_dir / spritesheet_name
    if not official_spritesheet.is_file():
        raise SystemExit(f"official pet spritesheet not found: {official_spritesheet}")
    pet_id = official_manifest.get("id")
    if not isinstance(pet_id, str) or not pet_id:
        raise SystemExit("pet.json has no valid id")

    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        raise SystemExit(f"output directory is not empty: {run_dir}; pass --force to reuse it")
    package_dir = run_dir / "package"
    prompts_dir = run_dir / "prompts" / "rows"
    guides_dir = run_dir / "references" / "layout-guides"
    generated_dir = run_dir / "generated"
    decoded_dir = run_dir / "decoded"
    for directory in [
        package_dir,
        prompts_dir,
        guides_dir,
        generated_dir,
        decoded_dir,
        run_dir / "qa",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(manifest_path, package_dir / "pet.json")
    shutil.copy2(official_spritesheet, package_dir / "spritesheet.webp")
    canonical_base = run_dir / "references" / "canonical-base.png"
    extract_canonical_base(official_spritesheet, canonical_base)
    chroma_key = choose_chroma_key(canonical_base)

    jobs = []
    for animation in ANIMATIONS:
        state = animation["id"]
        guide = guides_dir / f"{state}.png"
        create_layout_guide(guide, animation["frames"])
        prompt = prompts_dir / f"{state}.md"
        prompt.write_text(row_prompt(pet_id, animation, chroma_key), encoding="utf-8")
        jobs.append(
            {
                "id": state,
                "kind": "interaction-row-strip",
                "status": "pending",
                "generationMode": "edit",
                "promptFile": str(prompt.relative_to(run_dir)).replace("\\", "/"),
                "inputImages": [
                    {
                        "path": "references/canonical-base.png",
                        "role": "canonical pet identity and official idle reference",
                    },
                    {
                        "path": str(guide.relative_to(run_dir)).replace("\\", "/"),
                        "role": "layout guide only; do not copy visible guide marks",
                    },
                ],
                "rawOutputPath": f"generated/{state}.png",
                "outputPath": f"decoded/{state}.png",
                "postprocess": {
                    "type": "remove-chroma-key",
                    "autoKey": "border",
                    "softMatte": True,
                    "despill": True,
                },
                "frames": animation["frames"],
                "dependsOn": [],
                "generationSkill": "$imagegen",
                "coherentSynthesisRequired": True,
            }
        )

    interaction = behavior_manifest(pet_id)
    write_json(package_dir / "interaction.json", interaction)
    write_json(
        run_dir / "interaction-jobs.json",
        {
            "schemaVersion": 1,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "runDir": str(run_dir),
            "chromaKey": chroma_key["hex"],
            "chromaKeySelection": chroma_key,
            "jobs": jobs,
        },
    )
    write_json(
        run_dir / "interaction-request.json",
        {
            "petId": pet_id,
            "officialPetDir": str(official_dir),
            "runDir": str(run_dir),
            "packageDir": str(package_dir),
            "animationCount": len(ANIMATIONS),
            "chromaKey": chroma_key,
            "compatibilityBoundary": "current Codex reads only pet.json and spritesheet.webp",
        },
    )

    print(
        json.dumps(
            {
                "ok": True,
                "runDir": str(run_dir),
                "packageDir": str(package_dir),
                "jobs": str(run_dir / "interaction-jobs.json"),
                "readyJobs": [animation["id"] for animation in ANIMATIONS],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
