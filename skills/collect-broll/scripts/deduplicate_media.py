#!/usr/bin/env python3
"""Report exact and visually similar media without deleting files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threshold", type=int, default=6, help="Maximum dHash Hamming distance")
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


def duration_seconds(ffmpeg: str, path: Path) -> float:
    completed = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", completed.stderr + completed.stdout)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def visual_dhash(ffmpeg: str, path: Path) -> int | None:
    seek = max(0.0, duration_seconds(ffmpeg, path) * 0.5)
    command = [
        ffmpeg,
        "-v",
        "error",
        "-ss",
        f"{seek:.3f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        "scale=17:16,format=gray",
        "-f",
        "rawvideo",
        "-",
    ]
    completed = subprocess.run(command, capture_output=True)
    if completed.returncode or len(completed.stdout) < 17 * 16:
        return None
    pixels = completed.stdout[: 17 * 16]
    bits = 0
    for row in range(16):
        for column in range(16):
            left = pixels[row * 17 + column]
            right = pixels[row * 17 + column + 1]
            bits = (bits << 1) | int(left > right)
    return bits


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS)
    exact_index: defaultdict[str, list[str]] = defaultdict(list)
    visual: list[tuple[Path, int]] = []
    visual_failures: list[str] = []

    for path in paths:
        exact_index[file_sha256(path)].append(str(path.resolve()))
        value = visual_dhash(ffmpeg, path)
        if value is None:
            visual_failures.append(str(path.resolve()))
        else:
            visual.append((path, value))

    exact_groups = [group for group in exact_index.values() if len(group) > 1]
    near_pairs = []
    for index, (left_path, left_hash) in enumerate(visual):
        for right_path, right_hash in visual[index + 1 :]:
            distance = bin(left_hash ^ right_hash).count("1")
            if distance <= args.threshold:
                near_pairs.append(
                    {"left": str(left_path.resolve()), "right": str(right_path.resolve()), "distance": distance}
                )

    report = {
        "root": str(root),
        "media_count": len(paths),
        "threshold": args.threshold,
        "exact_duplicate_groups": exact_groups,
        "visual_near_duplicate_pairs": near_pairs,
        "visual_hash_failures": visual_failures,
    }
    output = args.output or root / "dedupe-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"media={len(paths)} exact_groups={len(exact_groups)} near_pairs={len(near_pairs)} report={output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
