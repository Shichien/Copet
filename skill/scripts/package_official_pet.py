#!/usr/bin/env python3
"""Validate and package one completed official Codex pet run."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


PET_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def read_object(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"required file is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"pet_request.json {field} must be a non-empty string")
    return value.strip()


def atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(destination: Path, value: object) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def default_package_dir(pet_id: str) -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return root / "pets" / pet_id


def validate_atlas(script_dir: Path, atlas: Path, report: Path) -> None:
    command = [
        sys.executable,
        str(script_dir / "validate_atlas.py"),
        str(atlas),
        "--json-out",
        str(report),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stdout.strip() or completed.stderr.strip()
        raise SystemExit(f"official atlas validation failed:\n{detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request = read_object(run_dir / "pet_request.json")
    pet_id = require_text(request.get("pet_id"), "pet_id")
    if not PET_ID_PATTERN.fullmatch(pet_id):
        raise SystemExit("pet_request.json pet_id is not a safe pet folder name")
    display_name = require_text(request.get("display_name"), "display_name")
    description = require_text(request.get("description"), "description")

    atlas = run_dir / "final" / "spritesheet.webp"
    if not atlas.is_file():
        raise SystemExit(f"completed official atlas is missing: {atlas}")
    validation_report = run_dir / "final" / "validation.json"
    validation_report.parent.mkdir(parents=True, exist_ok=True)
    validate_atlas(Path(__file__).resolve().parent, atlas, validation_report)

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_package_dir(pet_id).resolve()
    )
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        raise SystemExit(f"{output_dir} already contains files; pass --force to replace the package")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": pet_id,
        "displayName": display_name,
        "description": description,
        "spritesheetPath": "spritesheet.webp",
    }
    atomic_copy(atlas, output_dir / "spritesheet.webp")
    atomic_write_json(output_dir / "pet.json", manifest)

    print(
        json.dumps(
            {
                "ok": True,
                "petId": pet_id,
                "packageDir": str(output_dir),
                "manifest": str(output_dir / "pet.json"),
                "spritesheet": str(output_dir / "spritesheet.webp"),
                "validation": str(validation_report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
