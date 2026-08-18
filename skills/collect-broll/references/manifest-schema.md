# Batch manifest schema

Use newline-delimited JSON. Keep temporary candidate manifests under `/tmp`; write the final `sources.jsonl` inside the delivery directory.

## Candidate input

One object per source URL:

```json
{"category":"Trump strong speech","url":"https://example.com/video","selected":true,"order":1,"query":"Trump stern podium warning","expected_visual":"medium shot, speaking with visible hand gestures","source_page":"https://example.com/video","rights_status":"unknown","notes":""}
```

Required before download:

- `category`: destination category and folder name
- `url`: URL to probe or download
- `selected`: set to `true` only for final choices

Recommended:

- `order`: one-based order within the category
- `query`: discovery query
- `expected_visual`: what must be visible during visual QA
- `source_page`: original public page when `url` is a direct media URL
- `rights_status`: `unknown`, `verified-reusable`, `permission-required`, or `restricted`
- `notes`: concise selection or licensing note

## Probe fields

`probe_candidates.py` adds:

- `probe_status`
- `video_id`
- `title`
- `uploader`
- `duration`
- `width`, `height`, and `resolution`
- `extractor`
- `webpage_url`
- `format_id`
- `probe_error` when probing fails

## Download fields

`download_batch.py` writes `sources.jsonl` and adds:

- `download_status`: `downloaded`, `existing`, `skipped`, or `failed`
- `local_files`
- `download_error` when downloading fails

Never store browser cookies, authorization headers, passwords, or temporary signed URLs in the manifest.

