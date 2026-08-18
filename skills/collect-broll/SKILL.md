---
name: collect-broll
description: Search, visually qualify, download, deduplicate, organize, and verify batches of real online B-roll footage with source records. Use when the user asks to find multiple videos for people, speeches, actions, events, archival footage, news scenes, war or humanitarian scenes, documentary material, podcast inserts, or editing references and save the selected footage locally. Also use when expanding or replacing an existing B-roll batch. Do not use generative video as a fallback.
---

# Collect B-roll

Build a traceable local B-roll package from a multi-scene brief. Search broadly, download only selected clips, inspect actual frames, and finish with the requested count per category.

## Required routing

1. Use `$agent-reach` for internet and platform discovery. Announce the platform/backend before searching.
2. Use `$yt-dlp-direct` for supported online video/audio pages. Always simulate before downloading.
3. Use the in-app browser only to inspect dynamic source pages or verify visible content and provenance.
4. Use FFmpeg through the bundled scripts for deterministic probing, decoding, contact sheets, and duplicate detection.
5. Use `$media-use` only when an existing HyperFrames project needs the downloaded files ingested or cached. Do not use it as the primary public-footage search engine.
6. Never invoke Lovart or another generative-video service in this workflow.

Read [provider-routing.md](references/provider-routing.md) before searching or downloading. Read [selection-rubric.md](references/selection-rubric.md) whenever the request includes subjective visual qualities, people, news, war, archival material, watermarks, or multiple categories. Read [manifest-schema.md](references/manifest-schema.md) before creating a batch manifest.

## Workflow

### 1. Normalize the brief

Extract:

- categories and requested count per category
- target visual, action, mood, people, place, and time period
- preferred and minimum resolution
- duration or aspect-ratio constraints
- exclusions such as watermarks, publishers, graphic content, reenactments, or generated media
- output directory

Use these defaults when the user does not specify them:

- four final clips per category
- overfetch at least three times the final count during discovery
- prefer 1080p and accept 720p; accept lower resolution only for scarce archival footage and disclose it
- MP4 delivery with merged audio/video
- exclude Getty Images and obvious stock-preview watermarks
- avoid graphic gore and visible corpses unless explicitly requested
- never overwrite existing files

Do not ask follow-up questions when these defaults allow safe progress.

### 2. Discover candidates

Use Agent Reach according to the routing reference. Search multiple phrasings and sources. Prefer primary/official footage, public institutions, reputable newsrooms, archives, humanitarian organizations, and original uploaders.

Create a temporary JSONL candidate manifest under `/tmp`, following [manifest-schema.md](references/manifest-schema.md). Record the query and expected visual for every candidate. Do not treat a title as proof that the requested action appears.

### 3. Probe without downloading

Run:

```bash
python3 <SKILL_DIR>/scripts/probe_candidates.py \
  /tmp/broll-candidates.jsonl \
  --output /tmp/broll-probed.jsonl \
  --max-height 1080 \
  --cookies-from-browser chrome \
  --js-runtimes node \
  --remote-components ejs:github
```

Remove failed, duplicate, irrelevant, excessively long, watermarked, or technically poor candidates. Mark only final choices with `"selected": true` and assign an `order` within each category.

### 4. Visually qualify the shortlist

Inspect source thumbnails or visible source-page frames before downloading when possible. For subjective requests, verify facial expression, body language, camera angle, action, and whether the subject remains on screen long enough to edit.

Reject pure narration, static-photo slideshows, reaction videos, commentary about the requested person, misleading thumbnails, and clips whose useful shot is obscured by graphics.

### 5. Download the selected set

Run the batch downloader for yt-dlp-compatible URLs:

```bash
python3 <SKILL_DIR>/scripts/download_batch.py \
  /tmp/broll-probed.jsonl \
  --output-dir "/absolute/delivery/path" \
  --max-height 1080 \
  --cookies-from-browser chrome \
  --js-runtimes node \
  --remote-components ejs:github
```

The downloader requires `selected: true`, creates one folder per category, numbers clips, avoids overwrites, merges to MP4, and writes `sources.jsonl`.

For a verified direct public media URL, download with `curl --fail --location` only after confirming the response is media rather than HTML. Record the original page and direct URL in the source manifest. Do not bypass DRM, paywalls, access controls, or regional restrictions. Do not substitute screen recording.

### 6. Verify and deduplicate

Run all three checks:

```bash
python3 <SKILL_DIR>/scripts/verify_batch.py "/absolute/delivery/path"
python3 <SKILL_DIR>/scripts/deduplicate_media.py "/absolute/delivery/path"
python3 <SKILL_DIR>/scripts/make_contact_sheet.py "/absolute/delivery/path"
```

Open every generated contact sheet with the local image viewer. Inspect early, middle, and late frames. Replace clips that do not visibly satisfy the brief. Never delete suspected duplicates automatically; report or replace them while preserving user files.

### 7. Finish the requested counts

For every category, confirm:

- exact requested number of playable final videos
- no `.part`, `.ytdl`, or unmerged format fragments
- expected subject/action is visible
- resolution exceptions are disclosed
- filenames retain source IDs when available
- `sources.jsonl` contains provenance and rights status

Report the delivery path, per-category counts, total size, notable quality exceptions, and any source that still requires licensing confirmation.

## Boundaries

- Public availability does not imply permission to rebroadcast. Record `rights_status` as `unknown` unless verified from the source.
- Preserve user-created and previously downloaded files. Use new folders or safe numbering.
- Do not download private media without the user's authorization.
- Do not generate replacement footage.
- Do not call a batch complete until actual downloaded frames have been inspected.

