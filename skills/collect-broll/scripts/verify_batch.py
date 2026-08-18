#!/usr/bin/env python3
"""Verify downloaded media can be decoded and report obvious fragments."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
PARTIAL_SUFFIXES = {".part", ".ytdl"}
FRAGMENT_RE = re.compile(r"\.f\d+(?:-[^.]*)?\.(?:mp4|webm|m4a)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ffmpeg")
    return parser.parse_args()


def find_ffmpeg(explicit: str | None) -> str:
    if explicit:
        return explicit
    executable = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise SystemExit("ffmpeg not found; pass --ffmpeg or set FFMPEG_BIN") from exc


def inspect(ffmpeg: str, path: Path) -> dict:
    metadata = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    combined = metadata.stderr + metadata.stdout
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", combined)
    dimensions = re.findall(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", combined)
    duration = None
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width = height = None
    if dimensions:
        width, height = map(int, max(dimensions, key=lambda pair: int(pair[0]) * int(pair[1])))

    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0", "-frames:v", "1", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "decode_status": "ok" if decoded.returncode == 0 else "failed",
        "decode_error": decoded.stderr.strip()[-1000:] if decoded.returncode else None,
    }


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    media = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS)
    partials = sorted(
        str(path.resolve())
        for path in root.rglob("*")
        if path.is_file() and (path.suffix.lower() in PARTIAL_SUFFIXES or FRAGMENT_RE.search(path.name))
    )
    records = [inspect(ffmpeg, path) for path in media]
    report = {
        "root": str(root),
        "media_count": len(records),
        "decode_failures": sum(record["decode_status"] != "ok" for record in records),
        "partials": partials,
        "files": records,
    }
    output = args.output or root / "qa-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for record in records:
        print(f"{record['decode_status']}\t{record['width']}x{record['height']}\t{record['duration_seconds']}\t{record['path']}")
    print(f"media={len(records)} failures={report['decode_failures']} partials={len(partials)} report={output}")
    return 1 if not records or report["decode_failures"] or partials else 0


if __name__ == "__main__":
    sys.exit(main())

