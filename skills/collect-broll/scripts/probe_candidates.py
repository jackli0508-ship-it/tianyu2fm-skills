#!/usr/bin/env python3
"""Probe JSONL video candidates with yt-dlp without downloading media."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-height", type=int, default=1080)
    parser.add_argument("--yt-dlp", dest="yt_dlp")
    parser.add_argument("--cookies-from-browser")
    parser.add_argument("--js-runtimes")
    parser.add_argument("--remote-components")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict) or not item.get("url"):
            raise SystemExit(f"{path}:{line_number}: each row must be an object with url")
        items.append(item)
    return items


def selected_video_format(data: dict) -> dict:
    requested = data.get("requested_formats") or []
    for fmt in requested:
        if fmt.get("vcodec") not in (None, "none"):
            return fmt
    return data


def probe(item: dict, args: argparse.Namespace, executable: str) -> dict:
    result = dict(item)
    command = [
        executable,
        "--no-playlist",
        "--simulate",
        "-f",
        f"bv*[height<={args.max_height}]+ba/b[height<={args.max_height}]",
        "--dump-single-json",
    ]
    if args.cookies_from_browser:
        command += ["--cookies-from-browser", args.cookies_from_browser]
    if args.js_runtimes:
        command += ["--js-runtimes", args.js_runtimes]
    if args.remote_components:
        command += ["--remote-components", args.remote_components]
    command.append(str(item["url"]))

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        result["probe_status"] = "failed"
        result["probe_error"] = (completed.stderr or completed.stdout).strip()[-2000:]
        return result

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        result["probe_status"] = "failed"
        result["probe_error"] = f"yt-dlp returned invalid JSON: {exc}"
        return result

    video_format = selected_video_format(data)
    width = video_format.get("width") or data.get("width")
    height = video_format.get("height") or data.get("height")
    result.update(
        {
            "probe_status": "ok",
            "video_id": data.get("id"),
            "title": data.get("title"),
            "uploader": data.get("uploader") or data.get("channel"),
            "duration": data.get("duration"),
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}" if width and height else data.get("resolution"),
            "extractor": data.get("extractor_key") or data.get("extractor"),
            "webpage_url": data.get("webpage_url") or item.get("url"),
            "format_id": data.get("format_id")
            or "+".join(str(part.get("format_id")) for part in data.get("requested_formats", []) if part.get("format_id")),
        }
    )
    result.pop("probe_error", None)
    return result


def main() -> int:
    args = parse_args()
    executable = args.yt_dlp or shutil.which("yt-dlp")
    if not executable:
        raise SystemExit("yt-dlp not found; pass --yt-dlp /absolute/path/to/yt-dlp")

    items = read_jsonl(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failed = 0
    with args.output.open("w", encoding="utf-8") as handle:
        for item in items:
            result = probe(item, args, executable)
            failed += result.get("probe_status") != "ok"
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"{result.get('probe_status')}\t{result.get('category', '')}\t{result.get('title') or result.get('url')}")

    print(f"probed={len(items)} failed={failed} output={args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

