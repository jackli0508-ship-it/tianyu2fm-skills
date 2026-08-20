---
name: tianyu2fm-fcp-chapter-tool
description: Analyze a TIANYU2FM interview episode from an FCPXML or .fcpxmld bundle, identify genuine topic transitions from the full timed transcript, and create a new importable FCPXML with disabled title blocks spanning each chapter. Use when the user asks for 话题分段、章节标注、chapter blocks、段落标题, or timeline topic labels in Final Cut Pro. Do not use for camera switching or ordinary subtitle generation.
---

# TIANYU2FM FCP Chapter Tool

Create a new Final Cut Pro project whose timeline contains one disabled title block per semantic chapter. Preserve the source export and source media.

## Required outcome

- Read the complete episode transcript in final-timeline order.
- Start a chapter only when a question or turn genuinely opens an independent discussion.
- Write concise Chinese question-form titles that capture the segment's actual core.
- Make every block run from its start to the next chapter start; the last runs to sequence end.
- Put blocks on a dedicated high lane, disabled by default so they label the timeline without appearing in the program.
- Save a standalone `.fcpxml` beside the input. Never overwrite the `.fcpxml` or `.fcpxmld` supplied by the user.

Read [references/topic-segmentation.md](references/topic-segmentation.md) before selecting chapters or writing titles.

## Workflow

1. Resolve `.fcpxmld` to `Info.fcpxml`, then run:

   ```bash
   python3 <skill-dir>/scripts/fcp_chapter_tool.py preflight <input>
   ```

   Stop if XML parsing fails, there is not exactly one project, or the primary storyline cannot be resolved unambiguously.

2. Obtain a full transcript with real timestamps:

   - Prefer an existing transcript/caption export when it matches the submitted edit.
   - If the transcript belongs to the uncut source timeline, require word timestamps and map it through the edit with `extract-transcript` below.
   - If no transcript exists and the project is an identity-timed multicam source followed by a cut-down project, build an aligned source mix:

     ```bash
     python3 <skill-dir>/scripts/build_multicam_mix.py <input> <source-mix.flac> \
       --ffmpeg <absolute-ffmpeg-path>
     ```

     Transcribe the mix in Chinese with word timestamps. On Apple Silicon, `mlx_whisper` with a locally available Whisper model is suitable. Do not install packages globally; use an existing runtime or a disposable virtual environment.

3. If ASR timestamps refer to the source/compound timeline, map only material retained in the final edit:

   ```bash
   python3 <skill-dir>/scripts/fcp_chapter_tool.py extract-transcript \
     <input> <whisper-source.json> <edited-transcript.json> <edited-transcript.txt>
   ```

   The source transcript must use Whisper-style `segments[].words[]` timestamps. Never estimate edit timestamps from transcript length.

4. Read the complete edited transcript. Build a UTF-8 topics JSON list in final-timeline seconds:

   ```json
   [
     {"start": 0.0, "title": "自动饮水机为何不如一碗新鲜水？"},
     {"start": 366.067, "title": "猫爱不爱你，究竟该看哪些信号？"}
   ]
   ```

   Use the first word of the new-topic question as the start. If the edit begins mid-answer, start the first chapter at `0.0` and title the discussion already in progress.

5. Write title blocks:

   ```bash
   python3 <skill-dir>/scripts/fcp_chapter_tool.py annotate \
     <input> <topics.json> <output.fcpxml> \
     --project-name "<original name> - 话题分段" \
     --lane 20
   ```

   The script clones an existing title template, assigns unique text-style IDs, inserts titles in DTD-valid child order, removes the project UID, and disables chapter titles unless `--visible` is explicitly requested.

6. Validate both XML and the installed Final Cut Pro DTD:

   ```bash
   xmllint --noout <output.fcpxml>
   xcrun swift <skill-dir>/scripts/validate_fcpxml.swift <output.fcpxml>
   python3 <skill-dir>/scripts/fcp_chapter_tool.py verify <output.fcpxml> \
     --lane 20 --expected-topics <count>
   ```

## Guardrails

- Do not edit an FCP Library database.
- Do not overwrite or modify the user's source export or media.
- Do not infer topics from waveforms, camera cuts, B-roll markers, or repeated edit notes; they are supporting evidence, not semantic chapters.
- Do not claim exact chapter timing without a transcript carrying real timestamps.
- Keep follow-up questions in the current chapter when they request examples, clarification, evidence, or mechanics of the same issue.
- Treat DTD validation as necessary but not sufficient. Ask the user to inspect chapter boundaries and long connected-title behavior after import.

## Report

Return the output path, project name, chapter count, lane, disabled/visible status, transcript source, and XML/DTD validation results. Mention that the source was preserved.
