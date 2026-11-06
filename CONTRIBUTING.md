# Contributing to SkyNet Scraper

Thanks for helping. This document is everything you need to change the code with confidence.

## Set up

Requires Python 3.9+ and Google Chrome.

```sh
git clone https://github.com/zyetaone/skynet-scraper
cd skynet-scraper
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Check that it works end to end:

```sh
python -m unittest discover -s tests -v   # offline, ~40 ms, no browser
skynet doctor                              # online, launches Chrome and searches once
```

## Layout

```
src/skynet_scraper/
  server.py    MCP server, search/page implementations, parsing
  bulk.py      many pages from one host: warm session, same-origin fetch
  cli.py       the `skynet` command: install, doctor, search, scrape, bulk
tests/
  test_parsing.py   pure tests: parsing, engine selectors, challenge detection
  test_bulk.py      pure tests: challenge detection, file naming, empty input
```

`server.py` has no CLI concerns and `cli.py` has no protocol concerns. Keep it that way: anything reusable belongs in `server.py`.

## Making a change

1. **Parsing and helpers** are pure functions with no browser. Add a test in `tests/test_parsing.py` first — the HTML fixtures there are small strings.
2. **A single page** goes through `_html(url)` in `server.py`. **Many pages from one host** go through `bulk.Session`, which keeps one browser warm and skips the render. Do not open a browser anywhere else.
3. Run `python -m unittest discover -s tests -v` before opening a pull request.
4. If you touch the protocol loop, test it by hand:
   ```sh
   printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | skynet
   ```
   stdout must contain exactly one JSON line and nothing else.

## Adding a search engine

Two edits, one test:

```python
# server.py
ENGINE_URLS["mysite"] = "https://mysite.example/search?q={q}"

def _selectors(engine):
    if engine == "mysite":
        return "li.hit", "a.hit-title", "p.hit-snippet"
```

Add `"mysite"` to the `engine` enum in both tool schemas (`TOOLS` in `server.py`), and add a fixture test that feeds a small HTML string to `_parse_results`. Never fetch the live site in tests.

## Style

- Standard library first. The only runtime dependencies are Botasaurus, BeautifulSoup and lxml.
- Type hints on public functions. Put `from __future__ import annotations` at the top.
- No prints on stdout in `server.py` — stdout is the protocol.
- Errors are values: return `{"error": ...}` or set `isError`. Do not raise into the client.

## Pull requests

- One topic per PR, with the reason in the description.
- Say what you ran: the unit tests, `skynet doctor`, and one real scrape if the change touches fetching.
- Note behaviour changes for agents (new arguments, changed return fields) — they are API.

## Releasing

1. Bump `version` in `pyproject.toml` and `__version__` in `server.py`.
2. Add a CHANGELOG entry.
3. Tag: `git tag v1.x.y && git push --tags`.
