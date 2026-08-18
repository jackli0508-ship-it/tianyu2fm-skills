#!/usr/bin/env python3
"""Download selected JSONL B-roll candidates with yt-dlp."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--max-height", type=int, default=1080)
    parser.add_argument("--yt-dlp", dest="yt_dlp")
    parser.add_argument("--ffmpeg-location")
    parser.add_argument("--cookies-from-browser")
    parser.add_argument("--js-runtimes")
    parser.add_argument("--remote-components")
    parser.add_argument("--all", action="store_true", help="Download every row, not only selected=true")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict) or not item.get("url") or not item.get("category"):
            raise SystemExit(f"{path}:{line_number}: category and url are required")
        rows.append(item)
    return rows


def safe_folder(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")
    return cleaned or "uncategorized"


def find_downloads(folder: Path, video_id: str | None) -> list[str]:
    if not video_id:
        return []
    marker = f"[{video_id}]"
    return [str(path.resolve()) for path in sorted(folder.iterdir()) if path.is_file() and marker in path.name]


def main() -> int:
    args = parse_args()
    executable = args.yt_dlp or shutil.which("yt-dlp")
    if not executable:
        raise SystemExit("yt-dlp not found; pass --yt-dlp /absolute/path/to/yt-dlp")

    rows = read_jsonl(args.manifest)
    selected = [row for row in rows if args.all or row.get("selected") is True]
    if not selected:
        raise SystemExit("no rows selected; set selected=true or pass --all")

    counters: defaultdict[str, int] = defaultdict(int)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report or args.output_dir / "sources.jsonl"
    reports: list[dict] = []
    failed = 0

    for item in selected:
        category = safe_folder(str(item["category"]))
        counters[category] += 1
        order = int(item.get("order") or counters[category])
        folder = args.output_dir / category
        folder.mkdir(parents=True, exist_ok=True)
        video_id = item.get("video_id")
        existing = find_downloads(folder, video_id)
        result = dict(item)
        if existing:
            result.update({"download_status": "existing", "local_files": existing})
            reports.append(result)
            print(f"existing\t{category}\t{existing[0]}")
            continue

        command = [
            executable,
            "--no-playlist",
            "--no-overwrites",
            "--no-post-overwrites",
            "-f",
            f"bv*[height<={args.max_height}]+ba/b[height<={args.max_height}]",
            "--merge-output-format",
            "mp4",
            "-P",
            str(folder),
            "-o",
            f"{order:02d} - %(title)s [%(id)s].%(ext)s",
        ]
        if args.ffmpeg_location:
            command += ["--ffmpeg-location", args.ffmpeg_location]
        if args.cookies_from_browser:
            command += ["--cookies-from-browser", args.cookies_from_browser]
        if args.js_runtimes:
            command += ["--js-runtimes", args.js_runtimes]
        if args.remote_components:
            command += ["--remote-components", args.remote_components]
        command.append(str(item["url"]))

        completed = subprocess.run(command, text=True)
        if completed.returncode != 0:
            failed += 1
            result.update({"download_status": "failed", "download_error": f"yt-dlp exit code {completed.returncode}", "local_files": []})
            print(f"failed\t{category}\t{item['url']}", file=sys.stderr)
        else:
            files = find_downloads(folder, video_id)
            result.update({"download_status": "downloaded", "local_files": files})
            result.pop("download_error", None)
            print(f"downloaded\t{category}\t{files[0] if files else item['url']}")
        reports.append(result)

    with report_path.open("w", encoding="utf-8") as handle:
        for result in reports:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"selected={len(selected)} failed={failed} report={report_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
