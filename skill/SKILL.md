---
name: hatch-interactive-pet
description: Create, repair, validate, package, and install a Codex-compatible pet that keeps the native /pet command and adds deterministic feeding, petting, bathing, playing, sleeping, needs, inventory, growth, and task-reactive animations. Use for a new custom Codex pet, an official 8x9 pet atlas, an interactive 8x12 extension atlas, or a reusable Copet package and local runtime installation.
---

# Hatch Interactive Pet

## Goal

Build one four-file pet package:

```text
package/
  pet.json
  spritesheet.webp
  interaction.json
  interaction-spritesheet.webp
```

Keep `pet.json` and `spritesheet.webp` valid for the native `/pet` command. Add gameplay only through the two interaction files and the Copet runtime. The unmodified Codex client ignores the interaction files.

This skill extends OpenAI's Apache-2.0 `hatch-pet` workflow. Copet adds the interaction atlas, deterministic care contract, compatible Image API executor, package installer, and local runtime integration. The upstream deterministic scripts and references are bundled here, so never require a separately installed hatch-pet skill.

## Required Resources

Use the installed `$imagegen` skill for visual generation. Use Python with Pillow for deterministic image processing. Never synthesize production pet poses with drawing code, geometric transforms, or repeated tiles.

Read these references before a full run:

- `references/codex-pet-contract.md` and `references/animation-rows.md` for the official atlas.
- `references/qa-rubric.md` for official visual acceptance.
- `references/interaction-contract.md` and `references/interaction-animation-rows.md` for care behavior and the extension atlas.
- `references/runtime-integration.md` only when building or installing the local client runtime.

## Workflow

### 1. Prepare The Official Pet

Create the official run from text and optional references:

```text
python scripts/prepare_pet_run.py \
  --pet-name <name> \
  --description <one-sentence-description> \
  --reference <absolute-reference-path> \
  --pet-notes <stable-identity-description> \
  --style-preset auto \
  --output-dir <official-run-dir>
```

Inspect `imagegen-jobs.json`. Complete `base` first, then the nine official animation rows. For every row, attach every image listed in `input_images`, including its layout guide and canonical base. Copy the selected image to `output_path` before marking the job complete. Generate `running-left` normally unless mirroring the approved `running-right` row preserves identity, markings, props, lighting, direction, and temporal order; use `derive_running_left_from_running_right.py` only for that approved case.

Use one coherent generated strip per row. Reject identity drift, wrong frame counts, copied guide marks, visible chroma background, clipping, slot overlap, detached effects, shadows, motion trails, or a static loop.

### 2. Assemble And Validate The Official Atlas

After every official job is complete, run:

```text
python scripts/extract_strip_frames.py \
  --decoded-dir <official-run-dir>/decoded \
  --output-dir <official-run-dir>/frames \
  --states all \
  --method auto

python scripts/inspect_frames.py \
  --frames-root <official-run-dir>/frames \
  --json-out <official-run-dir>/qa/review.json \
  --require-components

python scripts/compose_atlas.py \
  --frames-root <official-run-dir>/frames \
  --output <official-run-dir>/final/spritesheet.png \
  --webp-output <official-run-dir>/final/spritesheet.webp

python scripts/validate_atlas.py \
  <official-run-dir>/final/spritesheet.webp \
  --json-out <official-run-dir>/final/validation.json

python scripts/make_contact_sheet.py \
  <official-run-dir>/final/spritesheet.webp \
  --output <official-run-dir>/qa/contact-sheet.png

python scripts/render_animation_previews.py \
  --frames-root <official-run-dir>/frames \
  --output-dir <official-run-dir>/qa/previews
```

Inspect the contact sheet and every motion preview. Use `stable-slots` only when the source strips are sound and component extraction alone causes scale or baseline popping. Package the accepted official pet:

```text
python scripts/package_official_pet.py \
  --run-dir <official-run-dir> \
  --output-dir <official-package-dir>
```

### 3. Prepare The Interaction Extension

Use the validated official package as the only identity source:

```text
python scripts/prepare_interaction_run.py \
  --official-pet-dir <official-package-dir> \
  --output-dir <interaction-run-dir>
```

This copies the official package, extracts its first idle frame as the canonical reference, chooses a non-conflicting chroma key, writes twelve fixed row prompts, and creates `interaction.json` plus `interaction-jobs.json`.

### 4. Generate Interaction Rows

For the normal path, use `$imagegen` in edit mode for every pending job. Attach all images listed in `inputImages` in order and write the chroma-key result to `rawOutputPath`.

When the user explicitly selects an OpenAI-compatible Image API, set `OPENAI_API_KEY` only in the process environment and run:

```text
python scripts/generate_interaction_rows.py \
  --run-dir <interaction-run-dir> \
  --base-url <compatible-v1-base-url> \
  --model gpt-image-2
```

Never put an API key in a command argument, manifest, repository file, report, or response. The executor reads prompts and paths only from `interaction-jobs.json`, validates exact dimensions, accepts Base64, HTTPS URL, or data-URL image responses, and writes outputs atomically.

Remove the chroma background from each raw row with the installed imagegen helper:

```text
python <CODEX_HOME>/skills/.system/imagegen/scripts/remove_chroma_key.py \
  --input <raw-output-path> \
  --out <output-path> \
  --auto-key border \
  --soft-matte \
  --transparent-threshold 12 \
  --opaque-threshold 220 \
  --despill
```

Do not mark a row complete until the transparent strip contains the exact number of separated, unclipped poses with preserved antialiased edges.

### 5. Assemble And Validate The Interactive Package

Run:

```text
python scripts/compose_interaction_atlas.py --run-dir <interaction-run-dir>

python scripts/validate_interaction_pack.py \
  --package-dir <interaction-run-dir>/package \
  --json-out <interaction-run-dir>/qa/validation.json
```

Inspect the interaction atlas and at least one in-motion frame from every direct action. Repair a failed row as a whole; never patch a final atlas cell or hide a failed row behind a fallback.

### 6. Install The Local Runtime

When operating inside the Copet repository, build the version-checked local Codex copy, install the complete generated package, and launch it:

```text
assets/runtime/build-interactive-codex.ps1
assets/runtime/install-interactive-codex.ps1 -PetPackagePath <interaction-run-dir>/package
assets/runtime/launch-interactive-codex.ps1 -IsolatedProfile
```

Use `/pet` to wake, hide, and wake the pet again. Verify every care button, transaction timing, cooldown, refusal, state persistence after restart, and overlay layout before accepting the run. Never distribute OpenAI application binaries or bypass runtime version and hash checks.

## Rules

- Keep all official geometry fixed at 8 columns, 9 rows, and `192x208` cells.
- Keep all interaction geometry fixed at 8 columns, 12 rows, and `192x208` cells.
- Generate every production row from the same canonical identity.
- Apply item costs and state effects only after the declared action animation completes.
- Keep needs, offline decay, rewards, purchases, and cooldowns deterministic and bounded by `interaction.json`.
- Keep `/pet` as the only wake and hide command. Do not register a second command or send it through a model prompt.
- Treat missing rows, invalid action references, identity drift, clipped poses, visible key color, transparent RGB residue, and unreviewed motion as blockers.

## Acceptance

- The official atlas is exactly `1536x1872`; used cells are non-empty and unused cells are transparent.
- The interaction atlas is exactly `1536x2496`; every declared row and duration is valid.
- Both deterministic validators exit successfully.
- Contact sheets and motion previews pass visual review.
- The complete package contains all four required files with matching pet ids.
- A real `/pet` cycle loads the interaction runtime, performs care actions, persists state, and restores it after restart.
