from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
PREPARE = SKILL_DIR / "scripts" / "prepare_interaction_run.py"
COMPOSE = SKILL_DIR / "scripts" / "compose_interaction_atlas.py"
VALIDATE = SKILL_DIR / "scripts" / "validate_interaction_pack.py"


class InteractionPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.official = self.root / "official"
        self.run_dir = self.root / "run"
        self.official.mkdir()
        official_atlas = Image.new("RGBA", (1536, 2288), (0, 0, 0, 0))
        draw = ImageDraw.Draw(official_atlas)
        draw.rounded_rectangle((55, 40, 137, 190), radius=20, fill=(30, 150, 220, 255))
        official_atlas.save(self.official / "spritesheet.webp", format="WEBP", lossless=True)
        (self.official / "pet.json").write_text(
            json.dumps(
                {
                    "id": "test-pet",
                    "displayName": "Test Pet",
                    "description": "A pipeline fixture.",
                    "spriteVersionNumber": 2,
                    "spritesheetPath": "spritesheet.webp",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def prepare_and_compose(self, transparent: bool = False) -> None:
        prepared = self.run_script(
            PREPARE,
            "--official-pet-dir",
            str(self.official),
            "--output-dir",
            str(self.run_dir),
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        jobs = json.loads((self.run_dir / "interaction-jobs.json").read_text(encoding="utf-8"))
        chroma_hex = jobs["chromaKey"].lstrip("#")
        chroma = tuple(int(chroma_hex[index : index + 2], 16) for index in (0, 2, 4))
        for row_index, job in enumerate(jobs["jobs"]):
            self.assertEqual(job["generationMode"], "edit")
            self.assertEqual(job["rawOutputPath"], f"generated/{job['id']}.png")
            self.assertEqual(job["postprocess"]["type"], "remove-chroma-key")
            frames = job["frames"]
            background = (0, 0, 0, 0) if transparent else (*chroma, 255)
            strip = Image.new("RGBA", (frames * 120, 190), background)
            draw = ImageDraw.Draw(strip)
            for frame in range(frames):
                left = frame * 120 + 24
                height = 110 + ((frame + row_index) % 3) * 8
                if transparent:
                    draw.rounded_rectangle(
                        (left - 1, 169 - height, left + 73, 171),
                        radius=15,
                        fill=(30 + row_index * 10, 100 + frame * 8, 180, 96),
                    )
                draw.rounded_rectangle(
                    (left, 170 - height, left + 72, 170),
                    radius=14,
                    fill=(30 + row_index * 10, 100 + frame * 8, 180, 255),
                )
            output = self.run_dir / job["outputPath"]
            output.parent.mkdir(parents=True, exist_ok=True)
            strip.save(output)
        composed = self.run_script(COMPOSE, "--run-dir", str(self.run_dir))
        self.assertEqual(composed.returncode, 0, composed.stderr)

    def test_preprocessed_alpha_edges_are_preserved(self) -> None:
        self.prepare_and_compose(transparent=True)
        report = json.loads(
            (self.run_dir / "qa" / "composition.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {animation["maskSource"] for animation in report["animations"].values()},
            {"alpha"},
        )
        with Image.open(self.run_dir / "package" / "interaction-spritesheet.webp") as opened:
            alpha_values = set(opened.convert("RGBA").getchannel("A").get_flattened_data())
        self.assertTrue(any(0 < value < 255 for value in alpha_values))

    def test_end_to_end_package_is_valid(self) -> None:
        self.prepare_and_compose()
        jobs = json.loads(
            (self.run_dir / "interaction-jobs.json").read_text(encoding="utf-8")
        )
        self.assertEqual({job["status"] for job in jobs["jobs"]}, {"complete"})
        validation_path = self.run_dir / "qa" / "validation.json"
        validated = self.run_script(
            VALIDATE,
            "--package-dir",
            str(self.run_dir / "package"),
            "--json-out",
            str(validation_path),
        )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        report = json.loads(validation_path.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["warnings"]), 1)
        with Image.open(self.run_dir / "package" / "interaction-spritesheet.webp") as atlas:
            self.assertEqual(atlas.size, (1536, 2496))

    def test_unknown_action_animation_is_rejected(self) -> None:
        self.prepare_and_compose()
        manifest_path = self.run_dir / "package" / "interaction.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["actions"]["feed"]["animation"] = "missing-animation"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        validated = self.run_script(
            VALIDATE,
            "--package-dir",
            str(self.run_dir / "package"),
        )
        self.assertEqual(validated.returncode, 1)
        self.assertIn("unknown animation missing-animation", validated.stdout)


if __name__ == "__main__":
    unittest.main()
