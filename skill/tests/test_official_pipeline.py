from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
PREPARE = SCRIPTS / "prepare_pet_run.py"
PACKAGE = SCRIPTS / "package_official_pet.py"
ROWS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OfficialPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_dir = self.root / "official-run"
        self.package_dir = self.root / "package"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def prepare_run(self) -> None:
        completed = self.run_script(
            PREPARE,
            "--pet-name",
            "Test Pet",
            "--description",
            "A reusable official pipeline fixture.",
            "--pet-notes",
            "A compact blue mascot with one white forehead mark.",
            "--output-dir",
            str(self.run_dir),
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def write_valid_atlas(self) -> Path:
        final_dir = self.run_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        atlas = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for row, frame_count in enumerate(ROWS):
            for column in range(frame_count):
                left = column * 192 + 48
                top = row * 208 + 44
                draw.rounded_rectangle(
                    (left, top, left + 95, top + 119),
                    radius=18,
                    fill=(30 + row * 12, 100 + column * 8, 190, 255),
                )
        output = final_dir / "spritesheet.webp"
        atlas.save(output, format="WEBP", lossless=True, quality=100, method=6, exact=True)
        return output

    def test_prepare_creates_complete_official_job_contract(self) -> None:
        self.prepare_run()
        request = json.loads((self.run_dir / "pet_request.json").read_text(encoding="utf-8"))
        jobs = json.loads((self.run_dir / "imagegen-jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(request["pet_id"], "test-pet")
        self.assertEqual(len(request["rows"]), 9)
        self.assertEqual(len(jobs["jobs"]), 10)
        self.assertEqual(jobs["jobs"][0]["id"], "base")
        self.assertEqual({job["generation_skill"] for job in jobs["jobs"]}, {"$imagegen"})
        for guide in request["layout_guides"]:
            self.assertTrue((self.run_dir / guide["path"]).is_file())

    def test_package_validates_and_copies_the_official_pet(self) -> None:
        self.prepare_run()
        atlas = self.write_valid_atlas()
        completed = self.run_script(
            PACKAGE,
            "--run-dir",
            str(self.run_dir),
            "--output-dir",
            str(self.package_dir),
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        manifest = json.loads((self.package_dir / "pet.json").read_text(encoding="utf-8"))
        validation = json.loads(
            (self.run_dir / "final" / "validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["id"], "test-pet")
        self.assertEqual(manifest["spritesheetPath"], "spritesheet.webp")
        self.assertTrue(validation["ok"])
        self.assertEqual(sha256(atlas), sha256(self.package_dir / "spritesheet.webp"))

    def test_package_rejects_an_invalid_official_atlas(self) -> None:
        self.prepare_run()
        final_dir = self.run_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (192, 208), (0, 0, 0, 0)).save(
            final_dir / "spritesheet.webp", format="WEBP", lossless=True
        )
        completed = self.run_script(
            PACKAGE,
            "--run-dir",
            str(self.run_dir),
            "--output-dir",
            str(self.package_dir),
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("official atlas validation failed", completed.stderr)
        self.assertFalse(self.package_dir.exists())


class SkillBundleTest(unittest.TestCase):
    def test_skill_is_self_contained_for_official_pet_creation(self) -> None:
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("$hatch-pet", skill_text)
        for relative_path in [
            "LICENSE.txt",
            "references/animation-rows.md",
            "references/codex-pet-contract.md",
            "references/qa-rubric.md",
            "scripts/prepare_pet_run.py",
            "scripts/extract_strip_frames.py",
            "scripts/inspect_frames.py",
            "scripts/compose_atlas.py",
            "scripts/validate_atlas.py",
            "scripts/make_contact_sheet.py",
            "scripts/render_animation_previews.py",
            "scripts/package_official_pet.py",
            "assets/runtime/build-interactive-codex.ps1",
            "assets/runtime/install-interactive-codex.ps1",
            "assets/runtime/launch-interactive-codex.ps1",
            "assets/runtime/interactive-pet-loader.cjs",
            "assets/runtime/interactive-pet-runtime.js",
            "assets/runtime/interactive-pet-store.cjs",
            "assets/pet/package/pet.json",
            "assets/pet/package/spritesheet.webp",
            "assets/pet/package/interaction.json",
            "assets/pet/package/interaction-spritesheet.webp",
        ]:
            self.assertTrue((SKILL_DIR / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
