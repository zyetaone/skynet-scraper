# Changelog

All notable changes to SkyNet Scraper. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [1.1.0] — 2026-11-06

Bulk fetching for one protected host, learned from a 67,608-page collection run.

### Added
- `bulk` module: `Session`, `fetch`, `fetch_many`. One browser clears the
  challenge, then each page is read with a same-origin request. No render, so
  the cost falls from 2.9 s/page to 0.83 s/page.
- `skynet bulk --urls FILE --out DIR --workers N` writes one HTML file for each
  URL with a stable name and prints a summary.
- `BLOCK_PATTERNS` default list. It removes images, CSS, fonts, video and the
  common analytics hosts.
- Tests for challenge detection and file naming: `tests/test_bulk.py`.

### Changed
- README records what fails against Cloudflare: plain HTTP clients, and copied
  cookies in any client. Clearance is bound to the IP, the user agent and the
  TLS fingerprint.
- The "not a crawler" limit now says what `bulk` does and does not do.

## [1.0.0] — 2026-11-04

First public release.

### Added
- MCP server over stdio with `search` and `page` tools, for any MCP client.
- `skynet` CLI: `search`, `scrape`, `install`, `doctor`.
- `skynet install` registers the server automatically in OpenCode, Claude Desktop, Cursor, VS Code and Codex, skipping apps that are not installed.
- Search across DuckDuckGo, DDG-lite, Bing and Mojeek with `engine: auto` failover and per-engine `attempts` reporting.
- Cloudflare challenge detection with a three-step recovery: caller `fallback` URL (JSON parsed), Wayback snapshot (flagged `archived`), explicit `challenge` field.
- Botasaurus' `bypass_cloudflare` path for ordinary Turnstile challenges.
- Optional proxy (`BOTASAURUS_MCP_PROXY`) and archive toggle (`BOTASAURUS_MCP_ARCHIVE`).
- Offline unit tests for parsing, engine selectors and challenge detection.

### Notes
- Uses the installed Google Chrome over CDP. It needs no browser download and no chromedriver.
- Python 3.9+, macOS and Linux.
