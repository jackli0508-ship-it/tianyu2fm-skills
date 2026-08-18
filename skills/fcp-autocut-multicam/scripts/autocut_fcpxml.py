#!/usr/bin/env python3
"""Create a first-pass AutoPod-style multicam edit from an FCPXML export.

This proof of concept is intentionally conservative:

* one isolated mono WAV is mapped to each close-up angle;
* the dominant speaker gets the close-up;
* overlapping speech uses the wide angle;
* silence holds the previous picture and disables both microphones;
* the source FCPXML is never modified.

The generated edit uses frame-aligned ``mc-clip`` segments and ``mc-source``
audio/video enable states, which Final Cut Pro can import as normal multicam
edits.
"""

import argparse
import audioop
import copy
import math
import os
import sys
import wave
import xml.etree.ElementTree as ET
from fractions import Fraction
from urllib.parse import unquote, urlparse


def parse_time(value):
    if not value or not value.endswith("s"):
        raise ValueError("Unsupported FCPXML time: {!r}".format(value))
    body = value[:-1]
    if "/" in body:
        numerator, denominator = body.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    return Fraction(body)


def format_time(value):
    value = Fraction(value)
    if value.denominator == 1:
        return "{}s".format(value.numerator)
    return "{}/{}s".format(value.numerator, value.denominator)


def percentile(values, proportion):
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * proportion))
    return ordered[max(0, min(len(ordered) - 1, index))]


def media_path(asset):
    media_rep = asset.find("media-rep")
    if media_rep is None or not media_rep.get("src"):
        raise ValueError("Audio asset has no original-media path")
    parsed = urlparse(media_rep.get("src"))
    if parsed.scheme != "file":
        raise ValueError("Only local file media is supported: {}".format(media_rep.get("src")))
    return unquote(parsed.path)


def locate_audio_for_angle(angle, assets, analysis_start, analysis_duration):
    candidates = []
    for clip in angle.iter("asset-clip"):
        asset = assets.get(clip.get("ref"))
        if asset is None:
            continue
        if asset.get("hasAudio") == "1" and asset.get("hasVideo") != "1":
            clip_start = parse_time(clip.get("offset", "0s"))
            clip_duration = parse_time(clip.get("duration", "0s"))
            analysis_end = analysis_start + analysis_duration
            clip_end = clip_start + clip_duration
            overlap = max(
                Fraction(0),
                min(analysis_end, clip_end) - max(analysis_start, clip_start),
            )
            if overlap > 0:
                candidates.append((overlap, clip, asset))
    if not candidates:
        raise ValueError(
            "No isolated audio asset covers the edit range in angle {!r}".format(
                angle.get("name")
            )
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, clip, asset = candidates[0]
    # For this test export the isolated WAV is directly synchronized into an
    # angle whose parent starts at zero. Its source-time mapping is:
    # WAV time = multicam time - clip offset + clip start.
    source_delta = parse_time(clip.get("start", "0s")) - parse_time(
        clip.get("offset", "0s")
    )
    return media_path(asset), source_delta


def read_levels(path, start, duration, hop):
    with wave.open(path, "rb") as audio:
        if (
            audio.getnchannels() != 1
            or audio.getframerate() != 48000
            or audio.getsampwidth() != 2
            or audio.getcomptype() != "NONE"
        ):
            raise ValueError(
                "Expected mono 48 kHz 16-bit PCM WAV, got {} ch, {} Hz, {} bytes".format(
                    audio.getnchannels(),
                    audio.getframerate(),
                    audio.getsampwidth(),
                )
            )
        rate = audio.getframerate()
        first_sample = int(round(float(start) * rate))
        if first_sample < 0 or first_sample >= audio.getnframes():
            raise ValueError("Requested analysis start is outside WAV: {}".format(path))
        audio.setpos(first_sample)
        samples_per_hop = int(round(float(hop) * rate))
        hop_count = int(math.ceil(float(duration / hop)))
        levels = []
        for _ in range(hop_count):
            data = audio.readframes(samples_per_hop)
            if not data:
                levels.append(-120.0)
                continue
            rms = audioop.rms(data, 2)
            levels.append(20.0 * math.log10(max(rms, 1) / 32768.0))
        return levels


def expand_mask(mask, before, after):
    result = [False] * len(mask)
    difference = [0] * (len(mask) + 1)
    for index, enabled in enumerate(mask):
        if not enabled:
            continue
        start = max(0, index - before)
        end = min(len(mask), index + after + 1)
        difference[start] += 1
        difference[end] -= 1
    active = 0
    for index in range(len(mask)):
        active += difference[index]
        result[index] = active > 0
    return result


def camera_with_hysteresis(raw_states, hop, wide_name):
    current = wide_name
    output = [current] * len(raw_states)
    candidate = None
    candidate_start = 0

    for index, target in enumerate(raw_states):
        if target is None:
            target = current
        if target == current:
            candidate = None
            output[index] = current
            continue

        if candidate != target:
            candidate = target
            candidate_start = index

        required_seconds = 0.45 if target == wide_name else 0.30
        required_hops = max(1, int(math.ceil(required_seconds / float(hop))))
        if index - candidate_start + 1 >= required_hops:
            current = candidate
            for backfill in range(candidate_start, index + 1):
                output[backfill] = current
            candidate = None
        else:
            output[index] = current

    # Remove very short camera shots to avoid nervous, single-word cutting.
    minimum_hops = max(1, int(math.ceil(0.80 / float(hop))))
    for _ in range(100):
        runs = []
        start = 0
        for index in range(1, len(output) + 1):
            if index == len(output) or output[index] != output[start]:
                runs.append((start, index, output[start]))
                start = index
        short = None
        for run_index, run in enumerate(runs):
            if run[1] - run[0] < minimum_hops:
                short = (run_index, run)
                break
        if short is None or len(runs) == 1:
            break
        run_index, (run_start, run_end, _) = short
        if run_index > 0:
            replacement = runs[run_index - 1][2]
        else:
            replacement = runs[run_index + 1][2]
        for index in range(run_start, run_end):
            output[index] = replacement
    return output


def bridge_false_gaps(mask, maximum_gap):
    result = list(mask)
    index = 0
    while index < len(result):
        if result[index]:
            index += 1
            continue
        end = index
        while end < len(result) and not result[end]:
            end += 1
        if index > 0 and end < len(result) and end - index <= maximum_gap:
            for fill in range(index, end):
                result[fill] = True
        index = end
    return result


def true_runs(mask):
    runs = []
    index = 0
    while index < len(mask):
        if not mask[index]:
            index += 1
            continue
        end = index + 1
        while end < len(mask) and mask[end]:
            end += 1
        runs.append((index, end))
        index = end
    return runs


def remove_short_camera_runs(states, minimum_hops):
    result = list(states)
    for _ in range(100):
        runs = []
        start = 0
        for index in range(1, len(result) + 1):
            if index == len(result) or result[index] != result[start]:
                runs.append((start, index, result[start]))
                start = index
        short = None
        for run_index, run in enumerate(runs):
            if run[1] - run[0] < minimum_hops:
                short = (run_index, run)
                break
        if short is None or len(runs) == 1:
            break
        run_index, (run_start, run_end, _) = short
        if (
            run_index > 0
            and run_index + 1 < len(runs)
            and runs[run_index - 1][2] == runs[run_index + 1][2]
        ):
            replacement = runs[run_index - 1][2]
        elif run_index > 0:
            replacement = runs[run_index - 1][2]
        else:
            replacement = runs[run_index + 1][2]
        for index in range(run_start, run_end):
            result[index] = replacement
    return result


def apply_reaction_editing(cameras, raw_masks, speakers, wide_name, hop, args):
    """Add buffered reaction shots and wide shots for dense backchannels.

    A feedback event is a short speaker-active run that is surrounded by
    activity from the other speaker. That contextual requirement filters out
    most pauses and sentence fragments without requiring speech-to-text.
    """

    feedback_events = []
    bridge_hops = max(1, int(math.ceil(0.10 / float(hop))))
    context_hops = max(1, int(math.ceil(args.feedback_context / float(hop))))
    context_active_hops = max(1, int(math.ceil(0.25 / float(hop))))

    for speaker in speakers:
        other = speakers[1] if speaker == speakers[0] else speakers[0]
        bridged = bridge_false_gaps(raw_masks[speaker], bridge_hops)
        for start, end in true_runs(bridged):
            event_duration = (end - start) * float(hop)
            if event_duration < args.feedback_min or event_duration > args.feedback_max:
                continue
            before = sum(raw_masks[other][max(0, start - context_hops) : start])
            after = sum(raw_masks[other][end : min(len(cameras), end + context_hops)])
            # Requiring the other person on both sides identifies interjected
            # acknowledgements such as "嗯", "对对对", and short laughter.
            if before < context_active_hops or after < context_active_hops:
                continue
            feedback_events.append(
                {
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                }
            )

    feedback_events.sort(key=lambda event: (event["start"], event["end"]))
    groups = []
    current_group = []
    dense_gap_hops = int(math.ceil(args.dense_feedback_gap / float(hop)))
    for event in feedback_events:
        if (
            not current_group
            or event["start"] - current_group[-1]["end"] <= dense_gap_hops
        ):
            current_group.append(event)
        else:
            groups.append(current_group)
            current_group = [event]
    if current_group:
        groups.append(current_group)

    dense_groups = [group for group in groups if len(group) >= 2]
    dense_event_ids = {id(event) for group in dense_groups for event in group}
    result = list(cameras)

    reaction_before = int(math.ceil(args.reaction_preroll / float(hop)))
    reaction_after = int(math.ceil(args.reaction_hold / float(hop)))
    minimum_reaction = int(math.ceil(args.reaction_minimum / float(hop)))
    individual_reactions = 0
    for event in feedback_events:
        if id(event) in dense_event_ids:
            continue
        start = max(0, event["start"] - reaction_before)
        end = min(len(result), event["end"] + reaction_after)
        if end - start < minimum_reaction:
            end = min(len(result), start + minimum_reaction)
            if end - start < minimum_reaction:
                start = max(0, end - minimum_reaction)
        for index in range(start, end):
            result[index] = event["speaker"]
        individual_reactions += 1

    wide_before = int(math.ceil(args.wide_interaction_preroll / float(hop)))
    wide_after = int(math.ceil(args.wide_interaction_hold / float(hop)))
    for group in dense_groups:
        start = max(0, group[0]["start"] - wide_before)
        end = min(len(result), group[-1]["end"] + wide_after)
        for index in range(start, end):
            result[index] = wide_name

    result = remove_short_camera_runs(
        result,
        max(1, int(math.ceil(0.60 / float(hop)))),
    )
    return result, {
        "feedback_events": len(feedback_events),
        "individual_reactions": individual_reactions,
        "dense_groups": len(dense_groups),
        "dense_feedback_events": sum(len(group) for group in dense_groups),
    }


def frame_states(
    duration,
    frame_duration,
    hop,
    camera_states,
    speaker_masks,
):
    frame_count_fraction = duration / frame_duration
    if frame_count_fraction.denominator != 1:
        raise ValueError("Timeline duration is not an exact number of video frames")
    frame_count = frame_count_fraction.numerator
    result = []
    for frame in range(frame_count):
        center = (Fraction(frame, 1) + Fraction(1, 2)) * frame_duration
        hop_index = min(len(camera_states) - 1, int(center / hop))
        active = tuple(
            speaker for speaker, mask in speaker_masks.items() if mask[hop_index]
        )
        result.append((camera_states[hop_index], active))
    return result


def compact_frame_states(states):
    segments = []
    start = 0
    for frame in range(1, len(states) + 1):
        if frame == len(states) or states[frame] != states[start]:
            segments.append((start, frame - start, states[start]))
            start = frame
    return segments


def add_sources(
    clip,
    video_angle,
    active_speakers,
    speaker_angles,
    angle_order,
    role,
    preserve_disabled_audio=False,
):
    active_audio_angles = {speaker_angles[name] for name in active_speakers}
    all_audio_angles = set(speaker_angles.values())
    used_angles = set(active_audio_angles)
    used_angles.add(video_angle)
    if preserve_disabled_audio:
        used_angles.update(all_audio_angles)

    for angle_name in angle_order:
        if angle_name not in used_angles:
            continue
        video_enabled = angle_name == video_angle
        audio_enabled = angle_name in active_audio_angles
        has_audio_component = audio_enabled or (
            preserve_disabled_audio and angle_name in all_audio_angles
        )
        if video_enabled and has_audio_component:
            source_enable = "all"
        elif video_enabled:
            source_enable = "video"
        else:
            source_enable = "audio"
        source = ET.SubElement(
            clip,
            "mc-source",
            {
                "angleID": angle_order[angle_name],
                "srcEnable": source_enable,
            },
        )
        if has_audio_component:
            role_attributes = {"role": role}
            if preserve_disabled_audio:
                # FCPXML's component-level enabled flag is the reversible
                # equivalent of disabling an expanded audio component with V.
                role_attributes["enabled"] = "1" if audio_enabled else "0"
            ET.SubElement(source, "audio-role-source", role_attributes)


def build_edit(args):
    input_path = args.input
    if os.path.isdir(input_path):
        input_path = os.path.join(input_path, "Info.fcpxml")
    tree = ET.parse(input_path)
    root = tree.getroot()
    if root.tag != "fcpxml":
        raise ValueError("Not an FCPXML document")

    resources = root.find("resources")
    if resources is None:
        raise ValueError("FCPXML has no resources")
    assets = {asset.get("id"): asset for asset in resources.findall("asset")}

    project = root.find(".//project")
    if project is None:
        raise ValueError("FCPXML has no project")
    sequence = project.find("sequence")
    if sequence is None:
        raise ValueError("Project has no sequence")
    clips = sequence.findall("./spine/mc-clip")
    if len(clips) != 1:
        raise ValueError("Expected one top-level multicam clip, found {}".format(len(clips)))
    original_clip = clips[0]

    media = resources.find("media[@id='{}']".format(original_clip.get("ref")))
    if media is None:
        raise ValueError("Multicam media resource was not found")
    multicam = media.find("multicam")
    if multicam is None:
        raise ValueError("Referenced media is not a multicam")

    angles = {angle.get("name"): angle for angle in multicam.findall("mc-angle")}
    if args.speakers is None:
        detected_speakers = []
        for angle_name, angle in angles.items():
            for clip in angle.iter("asset-clip"):
                asset = assets.get(clip.get("ref"))
                if (
                    asset is not None
                    and asset.get("hasAudio") == "1"
                    and asset.get("hasVideo") != "1"
                ):
                    detected_speakers.append(angle_name)
                    break
        if len(detected_speakers) != 2:
            raise ValueError(
                "Auto-detection expected exactly two angles with isolated "
                "audio-only assets, found {}: {}. Pass --speakers explicitly.".format(
                    len(detected_speakers),
                    ", ".join(detected_speakers) or "none",
                )
            )
        args.speakers = tuple(detected_speakers)
    if args.wide is None:
        wide_candidates = [name for name in angles if name not in args.speakers]
        if len(wide_candidates) != 1:
            raise ValueError(
                "Auto-detection expected one non-speaker/wide angle, found {}: {}. "
                "Pass --wide explicitly.".format(
                    len(wide_candidates),
                    ", ".join(wide_candidates) or "none",
                )
            )
        args.wide = wide_candidates[0]
    requested = [args.wide] + list(args.speakers)
    missing = [name for name in requested if name not in angles]
    if missing:
        raise ValueError("Missing multicam angle(s): {}".format(", ".join(missing)))

    format_id = sequence.get("format")
    video_format = resources.find("format[@id='{}']".format(format_id))
    if video_format is None or not video_format.get("frameDuration"):
        raise ValueError("Sequence video format has no frameDuration")
    frame_duration = parse_time(video_format.get("frameDuration"))
    duration = parse_time(original_clip.get("duration"))
    source_start = parse_time(original_clip.get("start", "0s"))
    timeline_offset = parse_time(original_clip.get("offset", "0s"))
    hop = Fraction(1, 20)  # 50 ms

    levels = {}
    paths = {}
    gates = {}
    for speaker in args.speakers:
        path, source_delta = locate_audio_for_angle(
            angles[speaker],
            assets,
            source_start,
            duration,
        )
        if not os.path.isfile(path):
            raise ValueError("Missing source audio: {}".format(path))
        paths[speaker] = path
        levels[speaker] = read_levels(
            path,
            source_start + source_delta,
            duration,
            hop,
        )
        # Use the lower quartile as an empirical room/noise reference, while
        # keeping the first test's gate within a sensible speech range.
        gates[speaker] = min(
            -30.0,
            max(-48.0, percentile(levels[speaker], 0.25) + 12.0),
        )

    first, second = args.speakers
    count = min(len(levels[first]), len(levels[second]))
    raw_states = []
    raw_masks = {first: [False] * count, second: [False] * count}
    for index in range(count):
        first_db = levels[first][index]
        second_db = levels[second][index]
        first_on = first_db >= gates[first]
        second_on = second_db >= gates[second]
        if not first_on and not second_on:
            raw_states.append(None)
        elif first_on and not second_on:
            raw_states.append(first)
            raw_masks[first][index] = True
        elif second_on and not first_on:
            raw_states.append(second)
            raw_masks[second][index] = True
        elif abs(first_db - second_db) < args.overlap_margin:
            raw_states.append(args.wide)
            raw_masks[first][index] = True
            raw_masks[second][index] = True
        elif first_db > second_db:
            raw_states.append(first)
            raw_masks[first][index] = True
        else:
            raw_states.append(second)
            raw_masks[second][index] = True

    before = int(math.ceil(args.audio_preroll / float(hop)))
    after = int(math.ceil(args.audio_release / float(hop)))
    speaker_masks = {
        speaker: expand_mask(raw_masks[speaker], before, after)
        for speaker in args.speakers
    }
    cameras = camera_with_hysteresis(raw_states, hop, args.wide)
    reaction_stats = None
    if args.v2_reactions:
        cameras, reaction_stats = apply_reaction_editing(
            cameras,
            raw_masks,
            list(args.speakers),
            args.wide,
            hop,
            args,
        )
    per_frame = frame_states(
        duration,
        frame_duration,
        hop,
        cameras,
        speaker_masks,
    )
    segments = compact_frame_states(per_frame)

    spine = sequence.find("spine")
    insertion_index = list(spine).index(original_clip)
    spine.remove(original_clip)

    angle_order = {
        angle.get("name"): angle.get("angleID") for angle in multicam.findall("mc-angle")
    }
    speaker_angles = {speaker: speaker for speaker in args.speakers}

    elapsed_frames = 0
    for segment_start, segment_frames, state in segments:
        video_angle, active_speakers = state
        clip = copy.deepcopy(original_clip)
        for source in list(clip.findall("mc-source")):
            clip.remove(source)
        relative_start = segment_start * frame_duration
        segment_duration = segment_frames * frame_duration
        clip.set("offset", format_time(timeline_offset + relative_start))
        clip.set("start", format_time(source_start + relative_start))
        clip.set("duration", format_time(segment_duration))
        add_sources(
            clip,
            video_angle,
            active_speakers,
            speaker_angles,
            angle_order,
            args.role,
            args.preserve_disabled_audio,
        )
        spine.insert(insertion_index + elapsed_frames, clip)
        elapsed_frames += 1

    original_name = project.get("name", "Project")
    project.set("name", args.project_name or "{} - AutoCut v1".format(original_name))
    project.attrib.pop("uid", None)
    project.attrib.pop("id", None)
    project.attrib.pop("modDate", None)

    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    xml_bytes = ET.tostring(root, encoding="utf-8")
    with open(args.output, "wb") as output:
        output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        output.write(b"<!DOCTYPE fcpxml>\n")
        output.write(xml_bytes)
        output.write(b"\n")

    camera_switches = sum(
        1 for index in range(1, len(cameras)) if cameras[index] != cameras[index - 1]
    )
    total_seconds = float(duration)
    print("Created: {}".format(args.output))
    print(
        "Project: {} | duration: {:.3f}s | FCPXML segments: {} | camera switches: {}".format(
            project.get("name"), total_seconds, len(segments), camera_switches
        )
    )
    if reaction_stats is not None:
        print(
            "V2 reactions: {} feedback events | {} individual reaction shots | "
            "{} dense groups ({} events) sent to wide".format(
                reaction_stats["feedback_events"],
                reaction_stats["individual_reactions"],
                reaction_stats["dense_groups"],
                reaction_stats["dense_feedback_events"],
            )
        )
    if args.preserve_disabled_audio:
        print(
            "Audio cleanup mode: preserve every speaker component; inactive "
            "components use enabled=0"
        )
    for speaker in args.speakers:
        active_seconds = sum(speaker_masks[speaker]) * float(hop)
        muted_seconds = max(0.0, total_seconds - active_seconds)
        print(
            "{} gate: {:.1f} dBFS | active: {:.1f}s | muted: {:.1f}s ({:.1f}%)".format(
                speaker,
                gates[speaker],
                active_seconds,
                muted_seconds,
                100.0 * muted_seconds / total_seconds,
            )
        )
    print("Audio source paths:")
    for speaker in args.speakers:
        print("  {}: {}".format(speaker, paths[speaker]))


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Source Info.fcpxml or standalone .fcpxml")
    parser.add_argument("output", help="New standalone .fcpxml to create")
    parser.add_argument(
        "--speakers",
        nargs=2,
        default=None,
        metavar=("SPEAKER_1", "SPEAKER_2"),
        help="Two close-up angle names; omit to detect audio-only assets automatically",
    )
    parser.add_argument(
        "--wide",
        default=None,
        help="Wide/two-shot angle name; omit when exactly one non-speaker angle exists",
    )
    parser.add_argument(
        "--overlap-margin",
        type=float,
        default=6.0,
        help="Treat two active mics within this many dB as overlapping speech",
    )
    parser.add_argument(
        "--audio-preroll",
        type=float,
        default=0.15,
        help="Seconds to open a mic before detected speech",
    )
    parser.add_argument(
        "--audio-release",
        type=float,
        default=0.35,
        help="Seconds to keep a mic open after detected speech",
    )
    parser.add_argument(
        "--role",
        default="dialogue.dialogue-1",
        help="FCP audio role used by enabled isolated microphones",
    )
    parser.add_argument(
        "--v2-reactions",
        action="store_true",
        help="Add buffered feedback/reaction shots and density-based wide shots",
    )
    parser.add_argument(
        "--preserve-disabled-audio",
        action="store_true",
        help="Keep inactive audio components in every edit and mark them enabled=0",
    )
    parser.add_argument(
        "--feedback-min",
        type=float,
        default=0.15,
        help="Minimum seconds for a short feedback utterance",
    )
    parser.add_argument(
        "--feedback-max",
        type=float,
        default=1.20,
        help="Maximum seconds for a short feedback utterance",
    )
    parser.add_argument(
        "--feedback-context",
        type=float,
        default=1.50,
        help="Seconds of the other speaker inspected before and after feedback",
    )
    parser.add_argument(
        "--reaction-preroll",
        type=float,
        default=0.25,
        help="Seconds of picture placed before an individual feedback utterance",
    )
    parser.add_argument(
        "--reaction-hold",
        type=float,
        default=0.75,
        help="Seconds to hold an individual reaction shot after the utterance",
    )
    parser.add_argument(
        "--reaction-minimum",
        type=float,
        default=1.10,
        help="Minimum total duration of an individual reaction shot",
    )
    parser.add_argument(
        "--dense-feedback-gap",
        type=float,
        default=3.00,
        help="Maximum gap between feedback events grouped as dense interaction",
    )
    parser.add_argument(
        "--wide-interaction-preroll",
        type=float,
        default=0.35,
        help="Seconds of wide picture before a dense feedback group",
    )
    parser.add_argument(
        "--wide-interaction-hold",
        type=float,
        default=1.00,
        help="Seconds to hold wide picture after a dense feedback group",
    )
    parser.add_argument("--project-name", help="Name of the newly imported project")
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        build_edit(parse_args(sys.argv[1:]))
    except Exception as error:
        print("error: {}".format(error), file=sys.stderr)
        sys.exit(1)
