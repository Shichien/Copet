#!/usr/bin/env python3
"""Validate an official-plus-interaction Codex pet package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


OFFICIAL_ANIMATIONS = {
    "idle",
    "running-right",
    "running-left",
    "waving",
    "jumping",
    "failed",
    "waiting",
    "running",
    "review",
}


def read_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        errors.append(f"missing file: {path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"invalid JSON in {path.name}: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return value


def validate_official(
    package_dir: Path,
    official: dict,
    errors: list[str],
) -> None:
    if not official:
        return
    pet_id = official.get("id")
    if not isinstance(pet_id, str) or not pet_id.strip():
        errors.append("pet.json id must be a non-empty string")
    sprite_path = official.get("spritesheetPath")
    if not isinstance(sprite_path, str) or not sprite_path:
        errors.append("pet.json spritesheetPath must be a non-empty string")
        return
    atlas_path = package_dir / sprite_path
    if not atlas_path.is_file():
        errors.append(f"official spritesheet is missing: {sprite_path}")
        return
    try:
        with Image.open(atlas_path) as image:
            expected_height = 2288 if official.get("spriteVersionNumber") == 2 else 1872
            if image.size != (1536, expected_height):
                errors.append(
                    f"official spritesheet has size {image.size}, expected (1536, {expected_height})"
                )
    except OSError as error:
        errors.append(f"cannot read official spritesheet: {error}")


def validate_interaction(
    package_dir: Path,
    official: dict,
    interaction: dict,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not interaction:
        return
    if interaction.get("schemaVersion") != 1:
        errors.append("interaction.json schemaVersion must be 1")
    if official and interaction.get("petId") != official.get("id"):
        errors.append("interaction petId must match pet.json id")

    compatibility = interaction.get("compatibility")
    if not isinstance(compatibility, dict):
        errors.append("interaction compatibility must be an object")
        compatibility = {}
    else:
        if compatibility.get("officialWakeCommand") != "/pet":
            errors.append("compatibility officialWakeCommand must be /pet")
        if compatibility.get("currentCodexReadsInteractionFiles") is not False:
            errors.append(
                "compatibility must explicitly state that current Codex ignores interaction files"
            )

    atlases = interaction.get("atlases")
    if not isinstance(atlases, dict) or not isinstance(atlases.get("interaction"), dict):
        errors.append("interaction atlas contract is missing")
        return
    atlas_contract = atlases["interaction"]
    required_geometry = {
        "columns": 8,
        "rows": 12,
        "cellWidth": 192,
        "cellHeight": 208,
    }
    for key, expected in required_geometry.items():
        if atlas_contract.get(key) != expected:
            errors.append(f"interaction atlas {key} must be {expected}")
    atlas_name = atlas_contract.get("path")
    if not isinstance(atlas_name, str) or not atlas_name:
        errors.append("interaction atlas path must be a non-empty string")
        return
    atlas_path = package_dir / atlas_name
    if not atlas_path.is_file():
        errors.append(f"interaction atlas is missing: {atlas_name}")
        return

    animations = interaction.get("animations")
    if not isinstance(animations, dict) or not animations:
        errors.append("animations must be a non-empty object")
        return
    rows_seen: set[int] = set()
    try:
        with Image.open(atlas_path) as opened:
            atlas = opened.convert("RGBA")
    except OSError as error:
        errors.append(f"cannot read interaction atlas: {error}")
        return
    expected_size = (
        required_geometry["columns"] * required_geometry["cellWidth"],
        required_geometry["rows"] * required_geometry["cellHeight"],
    )
    if atlas.size != expected_size:
        errors.append(f"interaction atlas has size {atlas.size}, expected {expected_size}")
        return

    for animation_id, animation in animations.items():
        if not isinstance(animation, dict):
            errors.append(f"animation {animation_id} must be an object")
            continue
        row = animation.get("row")
        frames = animation.get("frames")
        durations = animation.get("durationsMs")
        if not isinstance(row, int) or row < 0 or row >= 12:
            errors.append(f"animation {animation_id} has invalid row")
            continue
        if row in rows_seen:
            errors.append(f"multiple animations use row {row}")
        rows_seen.add(row)
        if not isinstance(frames, int) or frames < 1 or frames > 8:
            errors.append(f"animation {animation_id} has invalid frame count")
            continue
        if not isinstance(durations, list) or len(durations) != frames:
            errors.append(f"animation {animation_id} must have one duration per frame")
        elif any(not isinstance(value, int) or value <= 0 for value in durations):
            errors.append(f"animation {animation_id} durations must be positive integers")
        for column in range(8):
            left = column * 192
            top = row * 208
            cell = atlas.crop((left, top, left + 192, top + 208))
            occupied = cell.getchannel("A").getbbox() is not None
            if column < frames and not occupied:
                errors.append(f"animation {animation_id} frame {column} is empty")
            if column >= frames and occupied:
                errors.append(f"animation {animation_id} unused cell {column} is not transparent")
    if rows_seen != set(range(12)):
        errors.append("interaction animations must occupy every row from 0 through 11 exactly once")

    animation_ids = set(animations)
    items = interaction.get("items")
    if not isinstance(items, dict):
        errors.append("items must be an object")
        items = {}
    initial_inventory = interaction.get("initialInventory")
    if not isinstance(initial_inventory, dict):
        errors.append("initialInventory must be an object")
    else:
        for item, count in initial_inventory.items():
            if item not in items:
                errors.append(f"initialInventory references unknown item {item}")
            if not isinstance(count, int) or count < 0:
                errors.append(f"initialInventory {item} must be a non-negative integer")
    actions = interaction.get("actions")
    if not isinstance(actions, dict) or not actions:
        errors.append("actions must be a non-empty object")
        actions = {}
    for action_id, action in actions.items():
        if not isinstance(action, dict):
            errors.append(f"action {action_id} must be an object")
            continue
        animation = action.get("animation")
        if animation not in animation_ids:
            errors.append(f"action {action_id} references unknown animation {animation}")
        completion = action.get("completionAnimation")
        if completion is not None and completion not in animation_ids:
            errors.append(
                f"action {action_id} references unknown completion animation {completion}"
            )
        item = action.get("item")
        if item is not None and item not in items:
            errors.append(f"action {action_id} references unknown item {item}")
        effects = action.get("effects")
        if not isinstance(effects, dict) or not effects:
            errors.append(f"action {action_id} must declare deterministic effects")

    automatic_states = interaction.get("automaticStates")
    if not isinstance(automatic_states, list):
        errors.append("automaticStates must be an array")
    else:
        for index, state in enumerate(automatic_states):
            if not isinstance(state, dict) or state.get("animation") not in animation_ids:
                errors.append(f"automatic state {index} references an unknown animation")

    event_bindings = interaction.get("taskEventBindings")
    if not isinstance(event_bindings, dict):
        errors.append("taskEventBindings must be an object")
    else:
        for event, binding in event_bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"task event {event} binding must be an object")
                continue
            source = binding.get("source")
            target = binding.get("animation")
            if source == "official" and target not in OFFICIAL_ANIMATIONS:
                errors.append(f"task event {event} references unknown official animation {target}")
            elif source == "interaction" and target not in animation_ids:
                errors.append(
                    f"task event {event} references unknown interaction animation {target}"
                )
            elif source not in {"official", "interaction"}:
                errors.append(f"task event {event} has invalid source {source}")

    needs = interaction.get("needs")
    if not isinstance(needs, dict):
        errors.append("needs must be an object")
    else:
        if needs.get("range") != [0, 100]:
            errors.append("needs range must be [0, 100]")
        offline_cap = needs.get("offlineDecayCapHours")
        if not isinstance(offline_cap, int) or offline_cap < 0 or offline_cap > 24:
            errors.append("offlineDecayCapHours must be an integer from 0 through 24")
        safe_floor = needs.get("healthSafeFloor")
        if not isinstance(safe_floor, int) or safe_floor < 1:
            errors.append("healthSafeFloor must prevent death from offline decay")
        critical_health_decay = needs.get("criticalHealthDecayPerHour")
        if not isinstance(critical_health_decay, (int, float)) or critical_health_decay > 0:
            errors.append("criticalHealthDecayPerHour must be a non-positive number")

    transaction = interaction.get("transactionPolicy")
    if not isinstance(transaction, dict):
        errors.append("transactionPolicy must be an object")
    else:
        if transaction.get("randomness") != "forbidden":
            errors.append("transactionPolicy must forbid hidden randomness")
        if transaction.get("interruptedAction") != "apply-nothing":
            errors.append("interrupted actions must apply no cost or reward")

    if compatibility.get("requiredRuntimeCapability") == "interactive-pet-v1":
        warnings.append(
            "Current Codex will wake the official pet through /pet but will ignore interaction.json and interaction-spritesheet.webp."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    official = read_json(package_dir / "pet.json", errors)
    interaction = read_json(package_dir / "interaction.json", errors)
    validate_official(package_dir, official, errors)
    validate_interaction(package_dir, official, interaction, errors, warnings)
    result = {
        "ok": not errors,
        "packageDir": str(package_dir),
        "errors": errors,
        "warnings": warnings,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.json_out:
        output = Path(args.json_out).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
