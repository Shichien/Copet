#!/usr/bin/env python3
"""Generate pending interaction rows through an OpenAI-compatible Image API."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from PIL import Image


@dataclass(frozen=True)
class PreparedJob:
    job_id: str
    prompt: str
    input_paths: tuple[Path, ...]
    output_path: Path
    output_relative: str


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_inside(root: Path, relative_path: object, label: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"{label} must be a non-empty relative path")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} escapes the run directory: {relative_path}") from error
    return candidate


def decode_image_response(
    response: object,
    downloader: Callable[[str], bytes],
) -> tuple[bytes, str]:
    data = getattr(response, "data", None)
    if not isinstance(data, list) or len(data) != 1:
        raise ValueError("Image API response must contain exactly one image")
    item = data[0]
    encoded = getattr(item, "b64_json", None)
    if isinstance(encoded, str) and encoded:
        try:
            return base64.b64decode(encoded, validate=True), "b64_json"
        except ValueError as error:
            raise ValueError("Image API returned invalid Base64 image data") from error
    url = getattr(item, "url", None)
    if isinstance(url, str) and url:
        return downloader(url), "url"
    raise ValueError("Image API response contains neither b64_json nor url")


def secure_image_url(url: str, upgrade_http_host: str | None = None) -> str:
    parsed = urlsplit(url)
    if parsed.scheme == "http" and parsed.hostname == upgrade_http_host:
        return parsed._replace(scheme="https").geturl()
    if parsed.scheme == "https" and parsed.netloc:
        return url
    scheme = parsed.scheme or "missing"
    host = parsed.hostname or "missing"
    raise ValueError(f"Image API returned unsupported URL scheme: {scheme} (host: {host})")


def download_image(url: str, upgrade_http_host: str | None = None) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme == "data":
        try:
            header, encoded = url.split(",", 1)
        except ValueError as error:
            raise ValueError("Image API returned a malformed data URL") from error
        allowed_headers = {
            "data:image/jpeg;base64",
            "data:image/png;base64",
            "data:image/webp;base64",
        }
        if header.lower() not in allowed_headers:
            raise ValueError("Image API returned an unsupported data URL media type")
        try:
            return base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise ValueError("Image API returned invalid Base64 data URL content") from error
    safe_url = secure_image_url(url, upgrade_http_host)
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Copet/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def normalize_png(data: bytes, expected_size: tuple[int, int]) -> bytes:
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            if opened.size != expected_size:
                raise ValueError(
                    f"generated image has size {opened.size}, expected {expected_size}"
                )
            image = opened.convert("RGBA")
    except (OSError, SyntaxError) as error:
        raise ValueError("Image API returned invalid image bytes") from error
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise ValueError("--size must use WIDTHxHEIGHT")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as error:
        raise ValueError("--size must use integer dimensions") from error
    if width <= 0 or height <= 0:
        raise ValueError("--size dimensions must be positive")
    return width, height


def prepare_jobs(
    run_dir: Path,
    manifest: dict,
    selected_ids: set[str],
) -> list[PreparedJob]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("interaction-jobs.json has no jobs array")
    known_ids = {job.get("id") for job in jobs if isinstance(job, dict)}
    missing_ids = selected_ids - known_ids
    if missing_ids:
        raise ValueError(f"unknown job ids: {', '.join(sorted(missing_ids))}")

    prepared: list[PreparedJob] = []
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("interaction job must be an object")
        job_id = job.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("interaction job has no valid id")
        if selected_ids and job_id not in selected_ids:
            continue
        if not selected_ids and job.get("status") != "pending":
            continue
        if job.get("generationMode") != "edit":
            raise ValueError(f"{job_id}: only edit generationMode is supported")

        prompt_path = resolve_inside(run_dir, job.get("promptFile"), f"{job_id}.promptFile")
        if not prompt_path.is_file():
            raise ValueError(f"{job_id}: prompt file not found: {prompt_path}")
        input_images = job.get("inputImages")
        if not isinstance(input_images, list) or not input_images:
            raise ValueError(f"{job_id}: inputImages must be a non-empty array")
        input_paths = []
        for index, image in enumerate(input_images):
            if not isinstance(image, dict):
                raise ValueError(f"{job_id}: input image {index} must be an object")
            input_path = resolve_inside(
                run_dir,
                image.get("path"),
                f"{job_id}.inputImages[{index}].path",
            )
            if not input_path.is_file():
                raise ValueError(f"{job_id}: input image not found: {input_path}")
            input_paths.append(input_path)
        output_relative = job.get("rawOutputPath")
        output_path = resolve_inside(
            run_dir,
            output_relative,
            f"{job_id}.rawOutputPath",
        )
        prepared.append(
            PreparedJob(
                job_id=job_id,
                prompt=prompt_path.read_text(encoding="utf-8"),
                input_paths=tuple(input_paths),
                output_path=output_path,
                output_relative=output_relative,
            )
        )
    return prepared


def generate_job(
    job: PreparedJob,
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    size: str,
    quality: str,
    expected_size: tuple[int, int],
    request_base64: bool,
) -> dict:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError("The openai Python package is required") from error

    client_options = {"api_key": api_key}
    if base_url:
        client_options["base_url"] = base_url
    client = OpenAI(**client_options)
    started = time.monotonic()
    with ExitStack() as stack:
        images = [stack.enter_context(path.open("rb")) for path in job.input_paths]
        request_options = {
            "model": model,
            "prompt": job.prompt,
            "image": images,
            "size": size,
            "quality": quality,
            "output_format": "png",
        }
        if request_base64:
            request_options["extra_body"] = {"response_format": "b64_json"}
        response = client.images.edit(
            **request_options,
        )
    upgrade_http_host = urlsplit(base_url).hostname if base_url else None
    image_bytes, response_kind = decode_image_response(
        response,
        lambda url: download_image(url, upgrade_http_host),
    )
    normalized = normalize_png(image_bytes, expected_size)
    write_atomic(job.output_path, normalized)
    return {
        "id": job.job_id,
        "output": job.output_relative,
        "responseKind": response_kind,
        "sha256": hashlib.sha256(normalized).hexdigest(),
        "bytes": len(normalized),
        "elapsedSeconds": round(time.monotonic() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--job", action="append", default=[])
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--size", default="1536x1024")
    parser.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="high")
    parser.add_argument("--base-url")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--request-base64", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.concurrency < 1 or args.concurrency > 8:
        raise SystemExit("--concurrency must be between 1 and 8")
    try:
        expected_size = parse_size(args.size)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")

    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "interaction-jobs.json"
    if not manifest_path.is_file():
        raise SystemExit(f"interaction jobs manifest not found: {manifest_path}")
    try:
        jobs = prepare_jobs(run_dir, read_json(manifest_path), set(args.job))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not jobs:
        raise SystemExit("no matching pending interaction jobs")

    skipped = []
    runnable = []
    for job in jobs:
        if job.output_path.exists() and not args.force:
            try:
                with Image.open(job.output_path) as opened:
                    if opened.size != expected_size:
                        raise ValueError(
                            f"{job.output_path} has size {opened.size}, expected {expected_size}"
                        )
                    opened.verify()
            except (OSError, SyntaxError, ValueError) as error:
                raise SystemExit(f"existing output is invalid: {error}") from error
            skipped.append({"id": job.job_id, "output": job.output_relative})
        else:
            runnable.append(job)

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=min(args.concurrency, len(runnable) or 1)) as executor:
        future_jobs = {
            executor.submit(
                generate_job,
                job,
                api_key=api_key,
                base_url=base_url,
                model=args.model,
                size=args.size,
                quality=args.quality,
                expected_size=expected_size,
                request_base64=args.request_base64,
            ): job
            for job in runnable
        }
        for future in as_completed(future_jobs):
            job = future_jobs[future]
            try:
                results.append(future.result())
            except Exception as error:
                errors.append({"id": job.job_id, "error": str(error)})

    report = {
        "ok": not errors,
        "model": args.model,
        "size": args.size,
        "quality": args.quality,
        "generated": sorted(results, key=lambda value: value["id"]),
        "skipped": sorted(skipped, key=lambda value: value["id"]),
        "errors": sorted(errors, key=lambda value: value["id"]),
    }
    qa_path = run_dir / "qa" / "generation.json"
    write_atomic(qa_path, (json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
