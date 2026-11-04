# botasaurus-mcp

Free web search and page scraping for **any** MCP client — Claude Desktop, Cursor,
Codex, OpenCode, VS Code/Cline, Continue, or your own agent.

No API keys, no per-search billing. It drives a real headless browser
([Botasaurus](https://github.com/omkarcloud/botasaurus)'s anti-detect driver),
which is what gets past bot walls that reject plain HTTP clients.

Two tools:

| Tool | What it does |
|---|---|
| `search` | Query DuckDuckGo / Bing / Mojeek in a real browser and return `{title, url, snippet}` results. `auto` tries them in order and reports which engine answered. |
| `page` | Open a URL and return its title and readable text, its HTML, or its links; optional CSS `selector`, optional truncation, plus the final URL after redirects. |

## Install

Requires Python 3.9+.

```sh
# from a clone
git clone <this-repo> botasaurus-mcp
cd botasaurus-mcp
python3 -m venv .venv && . .venv/bin/activate
pip install -e .

# or, as a tool on PATH (recommended for teams)
uv tool install .
# or
pipx install .
```

Check it works:

```sh
botasaurus-mcp --selftest "rust programming language"
```

It drives the **Chrome already installed** on the machine over CDP — no browser
download, no chromedriver. The first call prepares a profile, so allow a few
extra seconds; after that a query takes ~2–5 s.

## Register it

The command to point every client at is:

```
botasaurus-mcp
```

If you installed into a venv instead, use the absolute path:
`/path/to/botasaurus-mcp/.venv/bin/botasaurus-mcp`.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "search": { "command": "botasaurus-mcp", "args": [] }
  }
}
```

### Cursor

`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project):

```json
{
  "mcpServers": {
    "search": { "command": "botasaurus-mcp", "args": [] }
  }
}
```

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.search]
command = "botasaurus-mcp"
args = []
```

### OpenCode

`~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "search": {
      "type": "local",
      "command": ["botasaurus-mcp"],
      "environment": { "BOTASAURUS_MCP_HEADLESS": "1" }
    }
  }
}
```

Then `opencode-cli reload` (or restart the app).

### VS Code / Cline / Continue

```json
{
  "mcpServers": {
    "search": {
      "command": "botasaurus-mcp",
      "args": [],
      "env": { "BOTASAURUS_MCP_HEADLESS": "1" }
    }
  }
}
```

### Any other client

Anything that can spawn a stdio MCP server works. The server speaks
newline-delimited JSON-RPC 2.0 and implements `initialize`, `tools/list`,
`tools/call`, `ping`, `shutdown`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BOTASAURUS_MCP_ENGINE` | `auto` | `auto`, `duckduckgo`, `duckduckgo_lite`, `bing`, `mojeek` |
| `BOTASAURUS_MCP_LIMIT` | `10` | Default result count (1–30) |
| `BOTASAURUS_MCP_HEADLESS` | `1` | `0` shows the browser window (useful when debugging a site) |
| `BOTASAURUS_MCP_PROXY` | unset | `http://user:pass@host:port` for egress through a proxy |
| `BOTASAURUS_MCP_PAGE_TIMEOUT` | `45` | Seconds per page load |

Tool arguments override the environment per call (`engine`, `limit`,
`format`, `selector`, `max_chars`).

## Sharing with a team

1. Push this folder to a repo your team can reach.
2. Teammates install once:
   ```sh
   uv tool install git+https://github.com/<org>/botasaurus-mcp
   ```
3. They paste the registration snippet for their client and restart it.

No secrets are involved, so the repo is safe to share. Each machine uses its own
locally installed Chrome.

## How it works

```
client ──stdio JSON-RPC──> botasaurus-mcp ──> Botasaurus Driver (headless Chromium) ──> web
```

Search parses the SERP with BeautifulSoup; `page` extracts text/HTML/links.
stdout is reserved for the protocol — library output is redirected to stderr, so
noise from the browser never corrupts the stream.

## Limits and honest caveats

- **Scraping search engines breaks their terms of service.** Use it for
  engineering work you're allowed to do; keep volume sane or you'll get
  challenged.
- **Some sites still win.** Cloudflare's "Client Challenge" (e.g. pypi.org at
  the time of writing) blocks even an anti-detect browser; `page` returns the
  challenge text, not the content.
- **Engines change markup.** `search` reports `attempts` per engine when nothing
  parses; update the selectors in `_selectors()` when that happens.
- **Not a crawler.** No queue, no robots.txt handling, no rate limiting beyond
  what you build on top. That's deliberate: keep the surface small.
- **Managed machines**: it launches the same Chrome your organisation controls.
  A browser policy that kills Chrome for particular flags (for example
  `--disable-extensions`) will kill this too; check the policy before blaming the
  server.

## License

MIT, same as Botasaurus.
