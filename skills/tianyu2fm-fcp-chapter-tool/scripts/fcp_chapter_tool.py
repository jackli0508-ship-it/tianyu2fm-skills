#!/usr/bin/env python3
"""Preflight, transcript mapping, chapter annotation, and verification for FCPXML."""

from __future__ import annotations

import argparse
import copy
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


MARKER_AND_LATER_TAGS = {
    "marker",
    "chapter-marker",
    "rating",
    "keyword",
    "analysis-marker",
    "hidden-clip-marker",
    "audio-role-source",
    "filter-video",
    "filter-video-mask",
    "filter-audio",
    "metadata",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"error: {message}")


def resolve_input(path: Path) -> Path:
    if path.is_dir() or path.suffix == ".fcpxmld":
        path = path / "Info.fcpxml"
    if not path.is_file():
        fail(f"FCPXML input does not exist: {path}")
    return path.resolve()


def load_xml(path: Path) -> tuple[Path, ET.ElementTree]:
    resolved = resolve_input(path)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        return resolved, ET.parse(resolved, parser=parser)
    except ET.ParseError as exc:
        fail(f"XML parsing failed: {exc}")


def parse_time(value: str | None) -> Fraction:
    if not value:
        return Fraction(0)
    try:
        return Fraction(value.removesuffix("s"))
    except (ValueError, ZeroDivisionError) as exc:
        fail(f"invalid FCPXML time value {value!r}: {exc}")


def fcpx_time(value: Fraction) -> str:
    value = value.limit_denominator(720_000)
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def clock(value: float) -> str:
    milliseconds = round(value * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def one_project(root: ET.Element) -> ET.Element:
    projects = list(root.iter("project"))
    if len(projects) != 1:
        fail(f"expected exactly one project, found {len(projects)}")
    return projects[0]


def project_sequence(root: ET.Element) -> ET.Element:
    sequence = one_project(root).find("sequence")
    if sequence is None:
        fail("project has no sequence")
    return sequence


def project_spine(root: ET.Element) -> ET.Element:
    spine = project_sequence(root).find("spine")
    if spine is None:
        fail("project sequence has no spine")
    return spine


def main_source_ref(root: ET.Element, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    counts = Counter(
        child.attrib["ref"]
        for child in project_spine(root)
        if child.tag == "ref-clip" and "ref" in child.attrib
    )
    if not counts:
        fail("project spine contains no referenced source clips")
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        fail(f"primary source reference is ambiguous: {ranked[:4]}; pass --source-ref")
    return ranked[0][0]


def edit_map(
    root: ET.Element, source_ref: str | None = None
) -> list[tuple[Fraction, Fraction, Fraction, ET.Element]]:
    source_ref = main_source_ref(root, source_ref)
    mappings = []
    for clip in project_spine(root):
        if clip.tag != "ref-clip" or clip.attrib.get("ref") != source_ref:
            continue
        source_start = parse_time(clip.attrib.get("start"))
        duration = parse_time(clip.attrib.get("duration"))
        project_start = parse_time(clip.attrib.get("offset"))
        if duration <= 0:
            continue
        mappings.append((source_start, source_start + duration, project_start, clip))
    if not mappings:
        fail(f"no project ref-clips point to primary source {source_ref}")
    return mappings


def map_source_time_all(
    value: float,
    mappings: list[tuple[Fraction, Fraction, Fraction, ET.Element]],
) -> list[tuple[float, ET.Element]]:
    point = Fraction(str(value))
    matches = []
    for source_start, source_end, project_start, clip in mappings:
        if source_start <= point < source_end:
            matches.append((float(project_start + point - source_start), clip))
    return sorted(matches, key=lambda item: item[0])


def media_paths(root: ET.Element) -> list[dict[str, object]]:
    paths = []
    for asset in root.findall("./resources/asset"):
        representation = asset.find("media-rep")
        if representation is None or not representation.attrib.get("src", "").startswith("file:"):
            continue
        path = Path(unquote(urlparse(representation.attrib["src"]).path))
        paths.append(
            {
                "id": asset.attrib.get("id"),
                "name": asset.attrib.get("name"),
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return paths


def command_preflight(args: argparse.Namespace) -> None:
    resolved, tree = load_xml(args.input)
    root = tree.getroot()
    project = one_project(root)
    sequence = project_sequence(root)
    source_ref = main_source_ref(root, args.source_ref)
    source_counts = Counter(
        child.attrib.get("ref")
        for child in project_spine(root)
        if child.tag == "ref-clip"
    )
    title_effects = {
        effect.attrib.get("id"): effect.attrib.get("name")
        for effect in root.findall("./resources/effect")
        if effect.attrib.get("id")
    }
    report = {
        "input": str(resolved),
        "fcpxml_version": root.attrib.get("version"),
        "project_name": project.attrib.get("name"),
        "sequence_duration_seconds": float(parse_time(sequence.attrib.get("duration"))),
        "primary_source_ref": source_ref,
        "project_ref_clip_counts": dict(source_counts),
        "captions": sum(1 for _ in root.iter("caption")),
        "titles": sum(1 for _ in root.iter("title")),
        "title_effects": title_effects,
        "media": media_paths(root),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def command_extract_transcript(args: argparse.Namespace) -> None:
    _resolved, tree = load_xml(args.input)
    mappings = edit_map(tree.getroot(), args.source_ref)
    try:
        transcript = json.loads(args.transcript_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not read transcript JSON: {exc}")

    mapped_segments = []
    word_count = 0
    for segment in transcript.get("segments", []):
        source_words = segment.get("words") or []
        if not source_words:
            continue
        mapped_words = []
        for word in source_words:
            if not {"start", "end", "word"}.issubset(word):
                continue
            start = float(word["start"])
            end = float(word["end"])
            midpoint = (start + end) / 2
            half_duration = max(0.0, (end - start) / 2)
            for project_midpoint, _clip in map_source_time_all(midpoint, mappings):
                mapped_words.append(
                    {
                        "start": max(0.0, project_midpoint - half_duration),
                        "end": project_midpoint + half_duration,
                        "word": word["word"],
                        "source_start": start,
                        "source_end": end,
                    }
                )
                word_count += 1
        mapped_words.sort(key=lambda item: item["start"])
        if mapped_words:
            mapped_segments.append(
                {
                    "start": mapped_words[0]["start"],
                    "end": mapped_words[-1]["end"],
                    "text": "".join(str(word["word"]) for word in mapped_words).strip(),
                    "words": mapped_words,
                }
            )
    if not mapped_segments:
        fail("no word-timestamped transcript material mapped into the final project")
    mapped_segments.sort(key=lambda item: item["start"])

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps({"segments": mapped_segments}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    paragraphs: list[str] = []
    current_minute: int | None = None
    current_text: list[str] = []
    for segment in mapped_segments:
        minute = int(segment["start"] // 60)
        if current_minute is None:
            current_minute = minute
        if minute != current_minute:
            paragraphs.append(f"[{clock(current_minute * 60)}] " + "".join(current_text))
            current_minute = minute
            current_text = []
        current_text.append(segment["text"])
    if current_minute is not None:
        paragraphs.append(f"[{clock(current_minute * 60)}] " + "".join(current_text))
    args.output_text.parent.mkdir(parents=True, exist_ok=True)
    args.output_text.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "segments": len(mapped_segments),
                "mapped_words": word_count,
                "output_json": str(args.output_json.resolve()),
                "output_text": str(args.output_text.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def choose_title_template(root: ET.Element, explicit_ref: str | None) -> ET.Element:
    titles = list(root.iter("title"))
    if explicit_ref:
        candidates = [title for title in titles if title.attrib.get("ref") == explicit_ref]
        if not candidates:
            fail(f"no title uses requested template ref {explicit_ref}")
        return candidates[0]
    if not titles:
        fail("project has no existing title to clone; add a basic/custom title or pass an export containing one")
    refs = Counter(title.attrib.get("ref") for title in titles if title.attrib.get("ref"))
    if not refs:
        fail("existing titles have no effect reference")
    preferred_names = {"basic title", "basic", "custom", "自定", "自定义"}
    effects = {
        effect.attrib.get("id"): effect.attrib.get("name", "").lower()
        for effect in root.findall("./resources/effect")
    }
    preferred = [ref for ref in refs if effects.get(ref, "") in preferred_names]
    chosen = max(preferred or list(refs), key=lambda ref: refs[ref])
    return next(title for title in titles if title.attrib.get("ref") == chosen)


def set_title_text(title: ET.Element, text: str, topic_index: int) -> None:
    title.attrib["name"] = text
    title.attrib.pop("start", None)
    title.attrib.pop("role", None)
    style_ids: dict[str, str] = {}
    for style_index, style_def in enumerate(title.iter("text-style-def"), start=1):
        old = style_def.attrib.get("id", f"style-{style_index}")
        new = f"topic-{topic_index:02d}-style-{style_index:02d}"
        style_ids[old] = new
        style_def.attrib["id"] = new
        for style in style_def.iter("text-style"):
            style.attrib.update(
                {
                    "font": "PingFang SC",
                    "fontFace": "Semibold",
                    "fontColor": "0.2 0.95 1 1",
                    "bold": "1",
                }
            )
    for text_style in title.iter("text-style"):
        if text_style.attrib.get("ref") in style_ids:
            text_style.attrib["ref"] = style_ids[text_style.attrib["ref"]]
        text_style.text = text


def insert_connected_child(anchor: ET.Element, child: ET.Element) -> None:
    insert_at = next(
        (
            index
            for index, existing in enumerate(anchor)
            if existing.tag in MARKER_AND_LATER_TAGS
        ),
        len(anchor),
    )
    anchor.insert(insert_at, child)


def anchor_for_time(root: ET.Element, start: Fraction) -> ET.Element:
    for child in project_spine(root):
        clip_start = parse_time(child.attrib.get("offset"))
        duration = parse_time(child.attrib.get("duration"))
        if clip_start <= start < clip_start + duration:
            return child
    fail(f"no primary storyline element covers chapter start {float(start):.3f}s")


def command_annotate(args: argparse.Namespace) -> None:
    input_path, tree = load_xml(args.input)
    output_path = args.output.expanduser().resolve()
    if output_path == input_path:
        fail("refusing to overwrite the source FCPXML")
    if input_path.parent.suffix == ".fcpxmld" and output_path.parent == input_path.parent:
        fail("output must be a standalone .fcpxml outside the source .fcpxmld bundle")
    if output_path.suffix != ".fcpxml":
        fail("output filename must end in .fcpxml")

    root = tree.getroot()
    project = one_project(root)
    sequence = project_sequence(root)
    sequence_duration = parse_time(sequence.attrib.get("duration"))
    template = choose_title_template(root, args.template_ref)

    try:
        topics = json.loads(args.topics_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not read topics JSON: {exc}")
    if not isinstance(topics, list) or not topics:
        fail("topics JSON must be a non-empty list")
    try:
        topics = sorted(topics, key=lambda item: float(item["start"]))
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"each topic needs numeric start and string title fields: {exc}")
    if float(topics[0]["start"]) != 0.0:
        fail("first chapter must start at 0.0 seconds")

    project.attrib.pop("uid", None)
    project.attrib["name"] = args.project_name or f"{project.attrib.get('name', 'Project')} - 话题分段"

    for index, topic in enumerate(topics, start=1):
        title_text = str(topic.get("title", "")).strip()
        if not title_text:
            fail(f"topic {index} has an empty title")
        start = Fraction(str(topic["start"]))
        if "end" in topic:
            end = Fraction(str(topic["end"]))
        elif index < len(topics):
            end = Fraction(str(topics[index]["start"]))
        else:
            end = sequence_duration
        if start < 0 or end <= start or end > sequence_duration:
            fail(f"topic {index} has invalid range {float(start):.3f}–{float(end):.3f}")

        title = copy.deepcopy(template)
        title.attrib.update(
            {
                "lane": str(args.lane),
                "offset": fcpx_time(start),
                "duration": fcpx_time(end - start),
            }
        )
        if args.visible:
            title.attrib.pop("enabled", None)
        else:
            title.attrib["enabled"] = "0"
        set_title_text(title, title_text, index)
        insert_connected_child(anchor_for_time(root, start), title)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="    ")
    xml_body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + xml_body + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_path),
                "project_name": project.attrib["name"],
                "topics": len(topics),
                "lane": args.lane,
                "visible": args.visible,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_verify(args: argparse.Namespace) -> None:
    resolved, tree = load_xml(args.input)
    root = tree.getroot()
    sequence_duration = parse_time(project_sequence(root).attrib.get("duration"))
    titles = [
        title
        for title in root.iter("title")
        if title.attrib.get("lane") == str(args.lane)
    ]
    titles.sort(key=lambda title: parse_time(title.attrib.get("offset")))
    errors = []
    if args.expected_topics is not None and len(titles) != args.expected_topics:
        errors.append(f"expected {args.expected_topics} chapter titles, found {len(titles)}")
    if not titles:
        errors.append(f"no titles found on lane {args.lane}")
    else:
        if parse_time(titles[0].attrib.get("offset")) != 0:
            errors.append("first chapter title does not start at 0")
        for current, following in zip(titles, titles[1:]):
            current_end = parse_time(current.attrib.get("offset")) + parse_time(
                current.attrib.get("duration")
            )
            following_start = parse_time(following.attrib.get("offset"))
            if current_end != following_start:
                errors.append(
                    f"chapter gap/overlap between {current.attrib.get('name')!r} and "
                    f"{following.attrib.get('name')!r}"
                )
        last_end = parse_time(titles[-1].attrib.get("offset")) + parse_time(
            titles[-1].attrib.get("duration")
        )
        if last_end != sequence_duration:
            errors.append("last chapter title does not end at sequence duration")
    style_ids = [item.attrib.get("id") for item in root.iter("text-style-def")]
    if len(style_ids) != len(set(style_ids)):
        errors.append("text-style-def IDs are not globally unique")
    report = {
        "input": str(resolved),
        "project_name": one_project(root).attrib.get("name"),
        "chapter_titles": len(titles),
        "lane": args.lane,
        "all_disabled": bool(titles) and all(title.attrib.get("enabled") == "0" for title in titles),
        "continuous_coverage": not any("gap/overlap" in error or "does not" in error for error in errors),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("input", type=Path)
    preflight.add_argument("--source-ref")
    preflight.set_defaults(func=command_preflight)

    extract = subparsers.add_parser("extract-transcript")
    extract.add_argument("input", type=Path)
    extract.add_argument("transcript_json", type=Path)
    extract.add_argument("output_json", type=Path)
    extract.add_argument("output_text", type=Path)
    extract.add_argument("--source-ref")
    extract.set_defaults(func=command_extract_transcript)

    annotate = subparsers.add_parser("annotate")
    annotate.add_argument("input", type=Path)
    annotate.add_argument("topics_json", type=Path)
    annotate.add_argument("output", type=Path)
    annotate.add_argument("--project-name")
    annotate.add_argument("--lane", type=int, default=20)
    annotate.add_argument("--template-ref")
    annotate.add_argument("--visible", action="store_true")
    annotate.set_defaults(func=command_annotate)

    verify = subparsers.add_parser("verify")
    verify.add_argument("input", type=Path)
    verify.add_argument("--lane", type=int, default=20)
    verify.add_argument("--expected-topics", type=int)
    verify.set_defaults(func=command_verify)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
