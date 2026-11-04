# Changelog

All notable changes to SkyNet Scraper. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

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
- Uses the installed Google Chrome over CDP; no browser download, no chromedriver.
- Python 3.9+, macOS and Linux.
