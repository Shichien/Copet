---
name: hatch-interactive-pet
description: Create, repair, validate, and package a Codex-compatible v2 pet together with a deterministic interaction animation atlas and behavior contract. Use when a user wants a pet that still wakes through /pet while also preparing feeding, petting, bathing, playing, sleeping, needs, items, growth, or task-reactive animations for an interactive pet runtime.
---

# Hatch Interactive Pet

## Goal

Build one dual-format pet package:

- `pet.json` and `spritesheet.webp` remain valid for the current Codex `/pet` command.
- `interaction.json` and `interaction-spritesheet.webp` carry gameplay animations and deterministic behavior for an interaction-capable runtime.

Do not claim that the current Codex client executes the interaction files. It ignores them until a pet runtime is added to the client. Preserve this boundary in every package and user-facing report.

## Required Skills And Runtime

Use the bundled `$hatch-pet` workflow to create or repair the official v2 pet first. Use `$imagegen` for every visual generation job. Never draw or synthesize production pet frames with code.

Before running scripts, call `load_workspace_dependencies` and use its exact Python executable. The scripts require Pillow.

Read these references before starting:

- `references/interaction-animation-rows.md` for the fixed interaction atlas.
- `references/interaction-contract.md` for files, behavior semantics, and compatibility.
- `references/runtime-integration.md` only when planning or implementing client support.

## Workflow

1. Create or select a valid official pet package with `$hatch-pet`.
2. Prepare the interaction run:

```text
python scripts/prepare_interaction_run.py \
  --official-pet-dir <pet-directory> \
  --output-dir <run-directory>
```

3. Inspect `interaction-jobs.json`. Generate every pending row with `$imagegen` in edit mode, attaching every listed input image in order. Write the blue-background result to `rawOutputPath`. Each job produces one coherent horizontal strip and must preserve the canonical pet identity.
4. Run the installed `$imagegen` `remove_chroma_key.py` helper on every raw row with border auto-key sampling, soft matte, and despill. Write the transparent result to `outputPath`. Do not mark a job complete until the processed strip has the exact requested number of separated, unclipped poses and preserves antialiased alpha edges.
5. Compose the fixed interaction atlas:

```text
python scripts/compose_interaction_atlas.py \
  --run-dir <run-directory>
```

6. Validate the complete package:

```text
python scripts/validate_interaction_pack.py \
  --package-dir <run-directory>/package \
  --json-out <run-directory>/qa/validation.json
```

7. Inspect the interaction contact sheet and motion previews when available. Repair a complete failed row, never one final cell.

## Generation Rules

- Generate all twelve interaction rows from the same canonical base.
- Keep each row as one coherent generation so pose identity and timing stay stable.
- Use the generated layout guide only for spacing. Reject visible guide marks.
- Keep the background exactly equal to the run's chroma key.
- Keep effects attached to the pet silhouette. Reject detached icons, text, interface panels, scenery, floor shadows, glow, blur, or particles.
- Make the first and final frames connect naturally for looping states.
- Use the exact frame count and order from the interaction row contract.
- Preserve body scale, baseline, face, materials, palette, markings, and props across official and interaction atlases.
- Treat missing rows, ambiguous pose segmentation, identity drift, clipped poses, or invalid action references as blockers.

## Packaging Boundary

The package intentionally contains two contracts:

```text
pet-package/
  pet.json
  spritesheet.webp
  interaction.json
  interaction-spritesheet.webp
```

The current app reads only the first two files. A modified or future runtime can read all four while keeping `/pet` as the wake and hide command. Do not add extra rows to the official v2 atlas and do not add executable code to `pet.json`.

## Acceptance

- The official package still passes the `$hatch-pet` v2 contract.
- The interaction atlas is exactly `1536x2496`, using `192x208` cells in an 8-column by 12-row grid.
- Every used interaction cell is non-empty and every unused cell is transparent.
- Every animation has one duration per frame.
- Every action and automatic state references an existing animation.
- Gameplay changes are deterministic, capped, and cannot kill the pet while the runtime is offline.
- `validate_interaction_pack.py` exits successfully with no errors.
