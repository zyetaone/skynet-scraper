# SkyNet Scraper

Free web search and page scraping for **any** AI coding agent — as an MCP server,
a CLI, or a Python import. No API keys, no accounts, no configuration.

It drives a real browser (Botasaurus' anti-detect driver over CDP), which is what
gets past the bot walls that reject plain HTTP clients. DuckDuckGo answers `curl`
with a captcha page; SkyNet gets results.

## Install (one command)

```sh
uv tool install git+https://github.com/cosmiclab-dev/skynet-scraper
```

No `uv`? `pipx install git+https://github.com/cosmiclab-dev/skynet-scraper`
(or `pip install` into a venv). Requires Python 3.9+ and Google Chrome.

## Register it in your agents (one command)

```sh
skynet install
```

It writes the right config for every agent app it finds — OpenCode, Claude
Desktop, Cursor, VS Code, Codex — and skips the ones that aren't installed.
Nothing to copy, nothing to edit. Restart the app and you're done.

```sh
skynet doctor      # verify: driver, Chrome, a live search
```

## Use it

**From an agent** (MCP tools):

| Tool | Returns |
|---|---|
| `search` | ranked `{title, url, snippet}` from DuckDuckGo / DDG-lite / Bing / Mojeek; `engine: auto` tries them in order and says which answered |
| `page` | a URL's title and readable text, its HTML, or its links; optional CSS `selector`, `max_chars`, `fallback` URL |

**From a shell:**

```sh
skynet search "rust 1.99 release"
skynet scrape https://doc.rust-lang.org/book/
skynet scrape https://pypi.org/project/requests/ --format links
skynet scrape https://site-that-challenges.example/ --fallback https://site-that-challenges.example/api.json
```

Both print JSON. Exit code is non-zero when nothing came back, so scripts can
branch on it.

**From Python:**

```python
from skynet_scraper import server
server.search("rust release notes", limit=5)
server.page("https://example.com", format="text", max_chars=4000)
```

## When a site serves a challenge

`page` recognises bot-challenge pages (`Client Challenge`, `Just a moment...`,
`Attention Required`, `checking your browser`, `verify you are human`,
`cf-challenge`, `ddos-guard`) and never passes them off as content. Then:

1. **Your `fallback` URL wins.** JSON responses come back parsed (`json`, or
   `json_text` when larger than `max_chars`); HTML is fetched normally.
2. **Otherwise the closest Wayback snapshot** is served, flagged
   `"archived": true` with a note that it may be stale
   (`BOTASAURUS_MCP_ARCHIVE=0` disables this).
3. **Otherwise it reports** `"challenge": "<marker>"` plus a hint.

Challenges are mostly IP reputation. For heavy use, pass a proxy:
`BOTASAURUS_MCP_PROXY=http://user:pass@host:port`.

## Configuration

All optional; there are no keys.

| Variable | Default | Meaning |
|---|---|---|
| `BOTASAURUS_MCP_ENGINE` | `auto` | `auto`, `duckduckgo`, `duckduckgo_lite`, `bing`, `mojeek` |
| `BOTASAURUS_MCP_LIMIT` | `10` | default results (1–30) |
| `BOTASAURUS_MCP_HEADLESS` | `1` | `0` shows the browser window |
| `BOTASAURUS_MCP_PROXY` | unset | `http://user:pass@host:port` |
| `BOTASAURUS_MCP_PAGE_TIMEOUT` | `45` | seconds per page |
| `BOTASAURUS_MCP_ARCHIVE` | `1` | Wayback fallback on/off |

## How it works

```
agent ──stdio JSON-RPC──> skynet ──CDP──> Chrome ──> web
```

- stdio is reserved for the protocol; library output is redirected to stderr, so
  browser noise can never corrupt the stream.
- the read loop uses `readline()`, not iteration, so clients that keep stdin open
  don't stall.
- one browser instance is reused across calls; results are parsed with
  BeautifulSoup.

## Limits, stated plainly

- Scraping search engines breaks their terms of service. Keep volume sane.
- Cloudflare's "Client Challenge" can still refuse you; use `fallback` or a proxy.
- Search engines change markup. When nothing parses, `search` reports per-engine
  `attempts`; the selectors live in `_selectors()` in
  `src/skynet_scraper/server.py`.
- It launches the Chrome your machine already has, so an organisation browser
  policy that kills Chrome will kill this too.
- Not a crawler: no queue, no robots.txt handling. Add that where you need it.

## License

MIT.
