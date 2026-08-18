#!/usr/bin/env python3
"""Create early/middle/late FFmpeg contact sheets for downloaded media."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--rows-per-sheet", type=int, default=12)
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


def extract_frame(ffmpeg: str, source: Path, seek: float, target: Path) -> bool:
    command = [
        ffmpeg,
        "-v",
        "error",
        "-ss",
        f"{max(0.0, seek):.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2",
        "-y",
        str(target),
    ]
    return subprocess.run(command, capture_output=True).returncode == 0


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    if args.rows_per_sheet < 1 or args.rows_per_sheet > 20:
        raise SystemExit("--rows-per-sheet must be between 1 and 20")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    output_dir = (args.output_dir or root / "_contact-sheets").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS and output_dir not in path.parents)
    if not paths:
        raise SystemExit(f"no media files found under {root}")

    index_lines = ["sheet\trow\tfile\tearly_seconds\tmiddle_seconds\tlate_seconds"]
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="collect-broll-contact-") as temporary:
        temp_root = Path(temporary)
        for chunk_start in range(0, len(paths), args.rows_per_sheet):
            chunk = paths[chunk_start : chunk_start + args.rows_per_sheet]
            sheet_number = chunk_start // args.rows_per_sheet + 1
            chunk_dir = temp_root / f"sheet-{sheet_number:02d}"
            chunk_dir.mkdir()
            extracted = 0
            for row, path in enumerate(chunk, 1):
                duration = duration_seconds(ffmpeg, path)
                points = [duration * 0.1, duration * 0.5, duration * 0.9]
                if duration <= 0:
                    points = [0.0, 0.0, 0.0]
                row_ok = True
                for position, seek in enumerate(points, 1):
                    frame = chunk_dir / f"{row:03d}-{position}.jpg"
                    row_ok &= extract_frame(ffmpeg, path, seek, frame)
                    extracted += frame.exists()
                if not row_ok:
                    failures.append(str(path.resolve()))
                index_lines.append(
                    f"contact-sheet-{sheet_number:02d}.jpg\t{row}\t{path.resolve()}\t{points[0]:.3f}\t{points[1]:.3f}\t{points[2]:.3f}"
                )

            if extracted != len(chunk) * 3:
                continue
            target = output_dir / f"contact-sheet-{sheet_number:02d}.jpg"
            tile_filter = f"tile=3x{len(chunk)}"
            command = [
                ffmpeg,
                "-v",
                "error",
                "-framerate",
                "1",
                "-pattern_type",
                "glob",
                "-i",
                str(chunk_dir / "*.jpg"),
                "-vf",
                tile_filter,
                "-frames:v",
                "1",
                "-y",
                str(target),
            ]
            if subprocess.run(command, capture_output=True).returncode != 0:
                failures.extend(str(path.resolve()) for path in chunk)

    index_path = output_dir / "contact-sheet-index.tsv"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    sheets = sorted(output_dir.glob("contact-sheet-*.jpg"))
    for sheet in sheets:
        print(sheet)
    print(f"media={len(paths)} sheets={len(sheets)} failures={len(set(failures))} index={index_path}")
    return 1 if failures or not sheets else 0


if __name__ == "__main__":
    sys.exit(main())

