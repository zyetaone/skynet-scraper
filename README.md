# SkyNet Scraper

**Free web search and page scraping for any AI coding agent.** No API keys, no accounts, no configuration.

SkyNet runs a real browser (Botasaurus' anti-detect driver over CDP), which is why it works where plain HTTP clients get a captcha page. It ships as three things from one package: an **MCP server**, a **CLI**, and a **Python module**.

```
agent ──stdio JSON-RPC──> skynet ──CDP──> Chrome ──> web
```

MIT licensed · Python 3.9+ · macOS and Linux · requires Google Chrome

---

## Install

One command, any machine with Python 3.9+ and Chrome:

```sh
uv tool install git+https://github.com/zyetaone/skynet-scraper
```

No `uv`? Use `pipx install git+https://github.com/zyetaone/skynet-scraper`, or `pip install` into a virtualenv.

Then register it in your agent apps — also one command:

```sh
skynet install
```

It writes the right config for every app it finds (OpenCode, Claude Desktop, Cursor, VS Code, Codex), backs up nothing it doesn't have to, and skips apps that aren't installed. Restart the app and you're done.

```sh
skynet doctor
```

```
skynet    1.0.0
python    3.14.10
driver    botasaurus-driver 4.0.101
chrome    found
search test → engine duckduckgo → 2 result(s)
```

---

## Quick start

**As an agent** — ask for anything that needs the web. The agent calls:

| MCP tool | Arguments | Returns |
|---|---|---|
| `search` | `query`, `limit` (1–30), `engine` | ranked `{title, url, snippet}` results |
| `page` | `url`, `format` (`text`/`html`/`links`), `selector`, `max_chars`, `fallback` | title, text, final URL, and a `challenge` flag if the site refused |

**From a shell:**

```sh
skynet search "rust 1.99 release"
skynet search "openspace api" --limit 5 --engine bing
skynet scrape https://doc.rust-lang.org/book/
skynet scrape https://example.com --format links
skynet scrape https://example.com --selector "article" --max-chars 4000
skynet scrape https://challenged.example/ --fallback https://challenged.example/api.json
skynet bulk --urls urls.txt --out pages/ --workers 8
```

Every command prints JSON and exits non-zero when nothing came back, so scripts can branch on it.

**From Python:**

```python
from skynet_scraper import server, bulk

results = server.search("rust release notes", limit=5)
doc = server.page("https://doc.rust-lang.org/book/", format="text", max_chars=4000)

# many pages from one protected host: 0.83 s/page instead of 2.9 s/page
report = bulk.fetch_many(urls, workers=8, out_dir="pages/")
```

---

## Configuration

Everything is optional. There are no keys to obtain.

| Variable | Default | Meaning |
|---|---|---|
| `BOTASAURUS_MCP_ENGINE` | `auto` | `auto`, `duckduckgo`, `duckduckgo_lite`, `bing`, `mojeek` |
| `BOTASAURUS_MCP_LIMIT` | `10` | default number of results (1–30) |
| `BOTASAURUS_MCP_HEADLESS` | `1` | `0` shows the browser window |
| `BOTASAURUS_MCP_PROXY` | unset | `http://user:pass@host:port` |
| `BOTASAURUS_MCP_PAGE_TIMEOUT` | `45` | seconds per page load |
| `BOTASAURUS_MCP_ARCHIVE` | `1` | Wayback fallback for challenged pages |

Tool arguments override the environment per call.

---

## How it works

- **One shared browser.** The first call launches Chrome with a small profile. Later calls reuse it. That is what makes a scrape take a couple of seconds instead of ten.
- **Search** opens the engine's results page in that browser and parses the SERP with BeautifulSoup. `engine: auto` walks DuckDuckGo → DDG-lite → Bing → Mojeek and returns which one answered, plus an `attempts` list when all of them fail.
- **Page** opens the URL, waits for it, and extracts either readable text (scripts/styles stripped), raw HTML, or links. `--selector` narrows to one CSS block.
- **Protocol safety.** stdout carries only JSON-RPC. Library and browser output goes to stderr. The read loop uses `readline()`, not iteration, so clients that keep stdin open don't stall.
- **No daemon.** Nothing runs in the background. Your agent spawns the server on demand.

### When a site serves a challenge

`page` recognises bot-challenge pages (`Client Challenge`, `Just a moment...`, `Attention Required`, `checking your browser`, `verify you are human`, `cf-challenge`, `ddos-guard`) and never passes them off as content. It then, in order:

1. Uses your **`fallback` URL** — JSON is returned parsed (`json`, or `json_text` when larger than `max_chars`), HTML is fetched normally.
2. Serves the closest **Wayback snapshot**, flagged `"archived": true` with a staleness note.
3. Reports `"challenge": "<marker>"` with a hint.

Challenges are mostly IP reputation. The durable fix is `BOTASAURUS_MCP_PROXY`.

### Bulk fetching without a challenge

`page` renders the page, which is correct for one page and slow for 60,000. `bulk` uses a different method. It keeps the browser fingerprint but skips the render.

One browser clears the challenge once. Every later page is then read with a same-origin request inside that page. Cloudflare sees a normal browser request on the same connection, so it keeps answering.

Measured on `archiexpo.com` while collecting 67,608 product pages:

| Method | Time for each page |
|---|---|
| Normal page load | 2.9 s |
| Load with images, CSS and analytics blocked | 1.6 s |
| Same-origin request after one warm-up (`bulk`) | **0.83 s** |

Ten workers finished 67,608 pages in about 3.4 hours, with 0.2% failures.

**What does not work**, so you do not try it:

| Attempt | Result |
|---|---|
| `curl` or `requests` | HTTP 403, challenge page |
| Copy the browser cookies into `requests` | HTTP 403. Clearance is bound to the IP, the user agent and the TLS fingerprint |
| Reuse the same cookies from another tool | HTTP 403, same reason |

**Usage:**

```python
from skynet_scraper import bulk

session = bulk.Session()          # one browser, kept warm
session.warm("https://example.com")
html = session.html("https://example.com/item/1")   # no render
session.close()

# or let the pool do it
report = bulk.fetch_many(urls, workers=8, out_dir="pages/")
```

The pool starts one browser for each worker, warms it on the first URL, then reads the rest. A challenge response triggers a real navigation and a retry. `bulk` writes one file for each URL with a stable name, and returns the byte count and a `blocked` flag for each one.

Keep the worker count moderate. Ten workers are enough for most hosts. More workers raise the chance of a block, and a block costs more time than it saves.

---

## Limitations, stated plainly

- **Search engines' terms of service forbid scraping.** This is a tool for your own engineering work, not a public search API. Keep volume sane or you will be challenged.
- **Cloudflare can still refuse you.** Anti-detect is a moving target, not a guarantee. `fallback` and proxies are the reliable answers.
- **Engine markup changes.** When nothing parses, `search` reports per-engine `attempts`. Fix the selectors in `_selectors()` in `src/skynet_scraper/server.py`.
- **It uses the Chrome already installed.** A machine policy that blocks Chrome kills this too — `skynet doctor` tells you immediately.
- **Bulk is not a crawler.** `bulk` fetches a list of URLs you already have. It has no queue, no scheduler, no `robots.txt` handling and no cross-run deduplication. Add that on top. The API is small on purpose.
- **No JavaScript interaction.** It reads pages. It does not click, fill forms or log in. Use Playwright or the app's own browser tools for that.

---

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Short version:

```sh
git clone https://github.com/zyetaone/skynet-scraper
cd skynet-scraper
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
```

The parsing layer is pure and fully tested offline, so most changes need no browser.

### Where to build next

Good, self-contained places to extend:

- **New search engines** — add a URL template to `ENGINE_URLS` and a selector row to `_selectors()`. Add a fixture test.
- **Richer extraction** — `page` already supports CSS selectors. A `format: "markdown"` would make it agent-friendlier.
- **Challenge strategies** — a proxy pool, cookie reuse, or per-domain fallbacks.
- **MCP resources/prompts** — the server implements tools only. Resources are easy to add.
- **Pagination** — `search` returns one page. The `offset` and `page` arguments are a natural next step.

---

## License

MIT © Binae. See [LICENSE](LICENSE).
