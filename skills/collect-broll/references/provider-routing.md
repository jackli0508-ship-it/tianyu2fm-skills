# Provider routing

Choose the discovery and download path independently. A source can be discoverable but not downloadable.

| Source | Discovery | Download | Notes |
|---|---|---|---|
| YouTube | Agent Reach video route / yt-dlp search | yt-dlp-direct | Simulate first; use browser cookies and JS runtime only when needed. |
| Generic supported video page | Agent Reach web search, browser verification | yt-dlp-direct | Confirm extractor and selected format before downloading. |
| Official direct media file | Agent Reach or browser | `curl --fail --location` | Verify media content type and retain the source page URL. |
| Newsroom or archive page | Agent Reach web search, browser | yt-dlp when supported; otherwise source-only record | Prefer original uploader and archive provenance. Do not assume reuse rights. |
| X, Reddit, Xiaohongshu, or another social platform | Agent Reach active backend | yt-dlp only after a direct URL passes simulation | Run `agent-reach doctor --json` for multi-backend platforms. Authentication may be required. |
| Bilibili | Agent Reach `bili-cli` / OpenCLI route | Follow the current Agent Reach Bilibili instructions | Do not default to yt-dlp; current platform controls may return 412. |
| HyperFrames project media | Existing local files or an already verified public URL | media-use ingest/cache after download | media-use is not the primary general B-roll search or download route. |
| DRM, paywalled, private, or blocked stream | Source-page verification only | Do not download | Report the blocker. Do not screen-record or bypass controls. |

## Search order

1. Search official channels, public institutions, archives, government or military public-affairs sources, international organizations, and original uploaders.
2. Search reputable newsrooms and wire-service uploads.
3. Search social platforms when the requested scene is unlikely to exist in institutional sources.
4. Use mirrors only when provenance can be traced and the original is unavailable.

Search at least three phrasings per category when results are weak. Include action verbs, location, event, date, shot type, and source organization in queries.

## Download fallback chain

1. Run yt-dlp simulation and inspect title, uploader, duration, extractor, and resolution.
2. Retry with authorized browser cookies when authentication is the only blocker.
3. Enable the required JavaScript runtime for YouTube when needed.
4. Use a verified public direct-media URL when the source provides one.
5. If unsupported, retain the source URL and mark `download_status: unsupported`.

Never use a generative-video provider as a fallback.

