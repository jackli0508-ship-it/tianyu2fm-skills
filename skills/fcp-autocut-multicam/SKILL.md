---
name: fcp-autocut-multicam
description: Turn two-person Final Cut Pro multicam FCPXML exports into AutoPod-style speaker-directed edits with buffered reaction shots, density-based wide shots, and reversible audio cleanup. Use when a user supplies an .fcpxml file or .fcpxmld bundle and asks Codex to cut cameras by active speaker, include backchannel/reaction shots, show a two-shot during dense interaction, or disable a non-speaking microphone without deleting its audio.
---

# FCP Multicam AutoCut

Create a new, importable FCPXML from a two-person multicam project. Preserve the
source export and source media.

## Workflow

1. Resolve the input:
   - For `.fcpxml`, use the file directly.
   - For `.fcpxmld`, use `Info.fcpxml` inside the bundle. The bundled script
     accepts either path.
2. Perform a read-only preflight:
   - Confirm the XML parses.
   - Confirm one project contains one top-level `mc-clip`.
   - List multicam angle names and referenced media paths.
   - Confirm referenced isolated WAV files exist.
3. Choose a new standalone `.fcpxml` output beside the input. Never overwrite
   the source file or bundle.
4. Run `scripts/autocut_fcpxml.py` with absolute paths:

   ```bash
   python3 <skill-dir>/scripts/autocut_fcpxml.py \
     <input.fcpxml-or-fcpxmld> \
     <output-autocut.fcpxml> \
     --v2-reactions \
     --preserve-disabled-audio \
     --project-name "<original name> - AutoCut"
   ```

5. Let the script auto-detect two speaker angles and one wide angle when the
   structure is unambiguous. If detection fails, inspect angle names and rerun:

   ```bash
   python3 <skill-dir>/scripts/autocut_fcpxml.py \
     <input> <output> \
     --speakers "<speaker angle 1>" "<speaker angle 2>" \
     --wide "<wide angle>" \
     --v2-reactions \
     --preserve-disabled-audio \
     --project-name "<new project name>"
   ```

6. Validate both well-formed XML and the installed Final Cut Pro DTD:

   ```bash
   xmllint --noout <output.fcpxml>
   xcrun swift <skill-dir>/scripts/validate_fcpxml.swift <output.fcpxml>
   ```

7. Report the output path, detected angle mapping, camera-switch count,
   reaction/wide-shot count, disabled-audio durations, and validation result.

## Default edit behavior

- Give a close-up to the dominant speaker.
- Detect short feedback only when the other speaker is active immediately
  before and after it.
- Give isolated feedback a reaction shot with 0.25 seconds of picture preroll,
  0.75 seconds of hold, and a 1.10-second minimum shot.
- Group two or more feedback events separated by at most 3 seconds into a wide
  interaction shot.
- Hold the previous camera through silence.
- Add 0.15 seconds of audio preroll and 0.35 seconds of release.
- Keep both isolated audio components in every edit segment. Mark inactive
  components `enabled="0"` so Final Cut Pro can restore them instead of
  omitting them from the XML.
- Remove the project UID and rename the output project so import creates a new
  project rather than overwriting the original.

## Guardrails

- Do not edit an FCP Library database directly.
- Do not overwrite the user-provided XML.
- Do not claim semantic speech recognition: feedback detection is acoustic and
  contextual unless a separate transcript/ASR stage is explicitly added.
- Stop with a clear diagnostic if the project has multiple top-level multicam
  clips, more than two speakers, inaccessible media, or unsupported audio.
- Treat successful DTD validation as necessary but not sufficient; ask the user
  to visually inspect camera choice, word boundaries, and disabled-component
  behavior after importing.

Read [references/fcpxml-workflow.md](references/fcpxml-workflow.md) only when
auto-detection fails, the user requests tuning, or Final Cut Pro imports the
output differently than expected.
