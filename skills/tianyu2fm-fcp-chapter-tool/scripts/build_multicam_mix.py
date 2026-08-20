#!/usr/bin/env python3
"""Build a timestamp-aligned mono source mix from an identity-timed FCP multicam."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


AUDIO_SUFFIXES = {".wav", ".aif", ".aiff", ".flac", ".m4a", ".mp3", ".aac"}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"error: {message}")


def parse_time(value: str | None) -> Fraction:
    if not value:
        return Fraction(0)
    return Fraction(value.removesuffix("s"))


def resolve_input(path: Path) -> Path:
    if path.is_dir() or path.suffix == ".fcpxmld":
        path = path / "Info.fcpxml"
    if not path.is_file():
        fail(f"input does not exist: {path}")
    return path.resolve()


def one_project(root: ET.Element) -> ET.Element:
    projects = list(root.iter("project"))
    if len(projects) != 1:
        fail(f"expected exactly one project, found {len(projects)}")
    return projects[0]


def most_common_ref(elements: list[ET.Element], tag: str) -> str:
    refs = Counter(
        element.attrib.get("ref")
        for element in elements
        if element.tag == tag and element.attrib.get("ref")
    )
    if not refs:
        fail(f"could not find any {tag} reference")
    ranked = refs.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        fail(f"ambiguous {tag} reference: {ranked[:4]}")
    return ranked[0][0]


def asset_index(root: ET.Element) -> dict[str, dict[str, object]]:
    assets = {}
    for asset in root.findall("./resources/asset"):
        representation = asset.find("media-rep")
        if representation is None or not representation.attrib.get("src", "").startswith("file:"):
            continue
        path = Path(unquote(urlparse(representation.attrib["src"]).path))
        assets[asset.attrib["id"]] = {
            "name": asset.attrib.get("name", path.name),
            "path": path,
        }
    return assets


def identity_multicam_source(root: ET.Element) -> tuple[str, ET.Element, Fraction]:
    project = one_project(root)
    sequence = project.find("sequence")
    spine = sequence.find("spine") if sequence is not None else None
    if sequence is None or spine is None:
        fail("project has no primary spine")
    primary_source = most_common_ref(list(spine), "ref-clip")
    source_media = next(
        (media for media in root.findall("./resources/media") if media.attrib.get("id") == primary_source),
        None,
    )
    if source_media is None or source_media.find("sequence/spine") is None:
        fail(f"primary source {primary_source} is not a compound/media sequence")
    source_sequence = source_media.find("sequence")
    source_spine = source_sequence.find("spine")
    multicam_ref = most_common_ref(list(source_spine), "mc-clip")
    clips = [
        clip
        for clip in source_spine
        if clip.tag == "mc-clip" and clip.attrib.get("ref") == multicam_ref
    ]
    clips.sort(key=lambda clip: parse_time(clip.attrib.get("offset")))
    tolerance = Fraction(1, 3000)
    cursor = Fraction(0)
    for clip in clips:
        offset = parse_time(clip.attrib.get("offset"))
        start = parse_time(clip.attrib.get("start"))
        duration = parse_time(clip.attrib.get("duration"))
        if abs(offset - cursor) > tolerance:
            fail("compound source has gaps or overlapping primary clips; render timeline audio instead")
        if abs(start - offset) > tolerance:
            fail("compound source is cut/reordered rather than identity-timed; render timeline audio instead")
        cursor = offset + duration
    sequence_duration = parse_time(source_sequence.attrib.get("duration"))
    if abs(cursor - sequence_duration) > tolerance:
        fail("multicam clips do not cover the complete compound source duration")
    multicam_media = next(
        (media for media in root.findall("./resources/media") if media.attrib.get("id") == multicam_ref),
        None,
    )
    if multicam_media is None or multicam_media.find("multicam") is None:
        fail(f"referenced media {multicam_ref} is not a multicam")
    return multicam_ref, multicam_media.find("multicam"), sequence_duration


def choose_audio_clip(
    sync_clip: ET.Element, assets: dict[str, dict[str, object]]
) -> tuple[ET.Element, dict[str, object]] | None:
    candidates = []
    for clip in sync_clip.iter("asset-clip"):
        asset = assets.get(clip.attrib.get("ref", ""))
        if not asset:
            continue
        path = asset["path"]
        if path.suffix.lower() not in AUDIO_SUFFIXES:
            continue
        duration = parse_time(clip.attrib.get("duration"))
        cleaned = str(asset["name"]).lower().startswith("c-")
        candidates.append((cleaned, duration, clip, asset))
    if not candidates:
        return None
    _cleaned, _duration, clip, asset = max(candidates, key=lambda item: (item[0], item[1]))
    return clip, asset


def audio_sessions(
    multicam: ET.Element, assets: dict[str, dict[str, object]]
) -> list[dict[str, object]]:
    grouped: dict[Fraction, dict[str, object]] = defaultdict(lambda: {"durations": [], "tracks": []})
    for angle in multicam.findall("mc-angle"):
        angle_name = angle.attrib.get("name", "unnamed")
        for sync_clip in angle.findall("sync-clip"):
            chosen = choose_audio_clip(sync_clip, assets)
            if chosen is None:
                continue
            audio_clip, asset = chosen
            path: Path = asset["path"]
            if not path.is_file():
                fail(f"referenced isolated audio is missing: {path}")
            session_offset = parse_time(sync_clip.attrib.get("offset"))
            session_duration = parse_time(sync_clip.attrib.get("duration"))
            grouped[session_offset]["durations"].append(session_duration)
            grouped[session_offset]["tracks"].append(
                {
                    "angle": angle_name,
                    "path": path,
                    "offset": parse_time(audio_clip.attrib.get("offset")),
                    "start": parse_time(audio_clip.attrib.get("start")),
                    "duration": parse_time(audio_clip.attrib.get("duration")),
                }
            )
    sessions = []
    for offset, data in sorted(grouped.items()):
        durations = data["durations"]
        tracks = data["tracks"]
        if not tracks:
            continue
        sessions.append(
            {
                "offset": offset,
                "duration": max(durations),
                "tracks": tracks,
            }
        )
    if not sessions:
        fail("no isolated audio assets were found inside multicam sync clips")
    return sessions


def build_filter(sessions: list[dict[str, object]]) -> tuple[list[Path], str, list[dict[str, object]]]:
    inputs: list[Path] = []
    filters: list[str] = []
    report_sessions = []
    session_labels = []
    input_index = 0
    for session_index, session in enumerate(sessions):
        track_labels = []
        track_report = []
        for track_index, track in enumerate(session["tracks"]):
            inputs.append(track["path"])
            label = f"s{session_index}t{track_index}"
            delay_ms = max(0, round(float(track["offset"]) * 1000))
            filters.append(
                f"[{input_index}:a]atrim=start={float(track['start']):.6f}:"
                f"duration={float(track['duration']):.6f},asetpts=PTS-STARTPTS,"
                f"adelay={delay_ms},aresample=16000,aformat=sample_fmts=s16:"
                f"channel_layouts=mono[{label}]"
            )
            input_index += 1
            track_labels.append(f"[{label}]")
            track_report.append(
                {
                    "angle": track["angle"],
                    "path": str(track["path"]),
                    "timeline_offset_seconds": float(track["offset"]),
                    "source_start_seconds": float(track["start"]),
                }
            )
        session_label = f"session{session_index}"
        filters.append(
            "".join(track_labels)
            + f"amix=inputs={len(track_labels)}:duration=longest:normalize=0,"
            + f"volume=0.7,alimiter=limit=0.95,atrim=duration={float(session['duration']):.6f}"
            + f"[{session_label}]"
        )
        session_labels.append(f"[{session_label}]")
        report_sessions.append(
            {
                "offset_seconds": float(session["offset"]),
                "duration_seconds": float(session["duration"]),
                "tracks": track_report,
            }
        )
    if len(session_labels) == 1:
        filters.append(f"{session_labels[0]}anull[out]")
    else:
        filters.append("".join(session_labels) + f"concat=n={len(session_labels)}:v=0:a=1[out]")
    return inputs, ";".join(filters), report_sessions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_path = resolve_input(args.input)
    output_path = args.output.expanduser().resolve()
    if output_path.exists() and not args.overwrite:
        fail(f"output already exists (use --overwrite for a generated derivative): {output_path}")
    ffmpeg = str(args.ffmpeg.resolve()) if args.ffmpeg else shutil.which("ffmpeg")
    if not ffmpeg or not Path(ffmpeg).is_file():
        fail("ffmpeg was not found; pass --ffmpeg with an absolute executable path")

    root = ET.parse(input_path).getroot()
    multicam_ref, multicam, source_duration = identity_multicam_source(root)
    assets = asset_index(root)
    sessions = audio_sessions(multicam, assets)
    tolerance = Fraction(1, 30)
    cursor = Fraction(0)
    for session in sessions:
        if abs(session["offset"] - cursor) > tolerance:
            fail("multicam audio sessions are not contiguous from zero")
        cursor = session["offset"] + session["duration"]
    if abs(cursor - source_duration) > Fraction(2):
        fail("multicam audio sessions do not cover the source sequence duration")

    inputs, filter_complex, report_sessions = build_filter(sessions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y" if args.overwrite else "-n", "-v", "warning"]
    for path in inputs:
        command.extend(["-i", str(path)])
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "flac",
            str(output_path),
        ]
    )
    subprocess.run(command, check=True)
    print(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "multicam_ref": multicam_ref,
                "source_duration_seconds": float(source_duration),
                "sessions": report_sessions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
