from __future__ import annotations

import base64
import importlib.util
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_interaction_rows.py"
SPEC = importlib.util.spec_from_file_location("generate_interaction_rows", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def png_bytes(size: tuple[int, int] = (16, 16)) -> bytes:
    image = Image.new("RGB", size, "#0000ff")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class GenerateInteractionRowsTest(unittest.TestCase):
    def test_decodes_base64_response(self) -> None:
        expected = png_bytes()
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(expected).decode("ascii"), url=None)]
        )
        actual, response_kind = MODULE.decode_image_response(
            response,
            lambda _url: self.fail("downloader must not be called"),
        )
        self.assertEqual(actual, expected)
        self.assertEqual(response_kind, "b64_json")

    def test_downloads_url_response(self) -> None:
        expected = png_bytes()
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=None, url="https://example.test/image.png")]
        )
        actual, response_kind = MODULE.decode_image_response(
            response,
            lambda url: expected if url == "https://example.test/image.png" else b"",
        )
        self.assertEqual(actual, expected)
        self.assertEqual(response_kind, "url")

    def test_decodes_image_data_url(self) -> None:
        expected = png_bytes()
        encoded = base64.b64encode(expected).decode("ascii")
        actual = MODULE.download_image(f"data:image/png;base64,{encoded}")
        self.assertEqual(actual, expected)

    def test_rejects_plain_http_image_url(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            r"unsupported URL scheme: http \(host: example\.test\)",
        ):
            MODULE.download_image("http://example.test/image.png")

    def test_upgrades_http_only_for_the_api_host(self) -> None:
        self.assertEqual(
            MODULE.secure_image_url(
                "http://api.example.test/image.png",
                "api.example.test",
            ),
            "https://api.example.test/image.png",
        )
        with self.assertRaisesRegex(
            ValueError,
            r"unsupported URL scheme: http \(host: cdn\.example\.test\)",
        ):
            MODULE.secure_image_url(
                "http://cdn.example.test/image.png",
                "api.example.test",
            )

    def test_rejects_paths_outside_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError, "escapes the run directory"):
                MODULE.resolve_inside(root, "../outside.png", "output")

    def test_normalizes_image_and_enforces_size(self) -> None:
        data = png_bytes((32, 16))
        normalized = MODULE.normalize_png(data, (32, 16))
        with Image.open(BytesIO(normalized)) as opened:
            self.assertEqual(opened.format, "PNG")
            self.assertEqual(opened.mode, "RGBA")
        with self.assertRaisesRegex(ValueError, "expected"):
            MODULE.normalize_png(data, (16, 16))


if __name__ == "__main__":
    unittest.main()
