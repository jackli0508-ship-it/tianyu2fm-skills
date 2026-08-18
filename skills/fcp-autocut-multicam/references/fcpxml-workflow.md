# FCPXML workflow reference

## Supported input shape

- FCPXML with one project and one top-level `mc-clip`.
- One referenced `<multicam>` resource.
- Two speaker angles containing one isolated audio-only WAV covering the edit
  range.
- One remaining wide/two-shot angle.
- Isolated WAV input readable as mono, 48 kHz, signed 16-bit PCM.

The script can receive a standalone `.fcpxml`, `Info.fcpxml`, or the enclosing
`.fcpxmld` bundle.

## Angle and source mapping

Auto-detection classifies an angle as a speaker angle when a nested
`asset-clip` references an asset with `hasAudio="1"` and without
`hasVideo="1"`. It expects exactly two such angles. It classifies the single
remaining angle as wide.

When the XML has extra angles, use:

```text
--speakers "Speaker A angle" "Speaker B angle" --wide "Two Shot"
```

The isolated WAV time is mapped from multicam time using:

```text
WAV source time = multicam source time - nested audio offset + nested audio start
```

## Reversible audio cleanup

The default reversible mode emits both speaker `mc-source` entries in every
frame-aligned `mc-clip` segment. Each contains an `audio-role-source`.

- Speaking component: `enabled="1"`
- Non-speaking component: `enabled="0"`

This preserves the component and its timing. In Final Cut Pro, expand audio
components to inspect disabled regions and toggle them with `V`.

Without `--preserve-disabled-audio`, inactive speaker sources are omitted from
each segment. That is still non-destructive to source media, but it is less
convenient for component-level restoration.

## Main tuning controls

| Option | Default | Effect |
|---|---:|---|
| `--overlap-margin` | 6.0 dB | Smaller values classify more overlap as one dominant speaker |
| `--audio-preroll` | 0.15 s | Opens a mic before detected speech |
| `--audio-release` | 0.35 s | Holds a mic after detected speech |
| `--feedback-min` | 0.15 s | Minimum short-feedback duration |
| `--feedback-max` | 1.20 s | Maximum short-feedback duration |
| `--reaction-preroll` | 0.25 s | Picture before isolated feedback |
| `--reaction-hold` | 0.75 s | Picture after isolated feedback |
| `--reaction-minimum` | 1.10 s | Minimum isolated reaction shot |
| `--dense-feedback-gap` | 3.00 s | Maximum gap for grouping feedback into wide |
| `--wide-interaction-preroll` | 0.35 s | Wide picture before a dense group |
| `--wide-interaction-hold` | 1.00 s | Wide picture after a dense group |

## Validation and import

Run:

```bash
xmllint --noout <output>
xcrun swift <skill-dir>/scripts/validate_fcpxml.swift <output>
```

The Swift validator loads the DTD matching the root FCPXML version from an
installed Final Cut Pro application.

On import, confirm:

1. A newly named project is created.
2. Total duration matches the source project.
3. Exactly one video angle is active in each interval.
4. Expanded audio components show inactive ranges as disabled, not absent.
5. Pressing `V` can restore a selected disabled audio component.

If component-level disable does not render as expected, obtain a minimal
FCPXML export made after manually disabling one expanded audio component in
Final Cut Pro and compare its `mc-source` and `audio-role-source` representation.
