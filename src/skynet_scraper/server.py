"""SkyNet Scraper: free web search + page scraping as an MCP server.

Speaks the Model Context Protocol over stdio (newline-delimited JSON-RPC), so any
MCP client can use it: Claude Desktop, Cursor, Codex, OpenCode, VS Code, Cline,
Continue, or your own agent.

No API keys. Searching and fetching are done with a real headless browser
(Botasaurus' anti-detect driver), which is what gets past bot walls that reject
plain HTTP clients.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

__version__ = "1.0.0"

PROTOCOL_VERSION = "2024-11-05"

DEFAULT_ENGINE = os.environ.get("BOTASAURUS_MCP_ENGINE", "auto")
DEFAULT_LIMIT = int(os.environ.get("BOTASAURUS_MCP_LIMIT", "10"))
HEADLESS = os.environ.get("BOTASAURUS_MCP_HEADLESS", "1") not in ("0", "false", "no")
PROXY = os.environ.get("BOTASAURUS_MCP_PROXY") or None
PAGE_TIMEOUT = int(os.environ.get("BOTASAURUS_MCP_PAGE_TIMEOUT", "45"))

TOOLS = [
    {
        "name": "search",
        "description": (
            "Search the web and return ranked results (title, url, snippet). "
            "Uses a real headless browser, so it works where plain HTTP clients are "
            "blocked. Free: no API key, no per-search cost."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "description": f"Results to return (default {DEFAULT_LIMIT}).",
                },
                "engine": {
                    "type": "string",
                    "enum": ["auto", "duckduckgo", "duckduckgo_lite", "bing", "mojeek"],
                    "description": "Search engine; 'auto' tries them in order.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "page",
        "description": (
            "Open a web page in a real browser and return its title and readable text "
            "(optionally its HTML, links, or a CSS-selected block), plus the final URL "
            "after redirects. Use this to read an article, docs page or search result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL to open."},
                "format": {
                    "type": "string",
                    "enum": ["text", "html", "links"],
                    "description": "text (default), html, or links.",
                },
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector; only that block is returned.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 200,
                    "maximum": 200000,
                    "description": "Truncate the result (default 12000).",
                },
                "fallback": {
                    "type": "string",
                    "description": (
                        "Used only if the page serves a bot challenge: an alternative URL to "
                        "fetch instead, typically the site's JSON/API endpoint."
                    ),
                },
            },
            "required": ["url"],
        },
    },
]


# --------------------------------------------------------------------------- #
# browser plumbing
# --------------------------------------------------------------------------- #

_driver = None


def _browser():
    """Lazily import Botasaurus so `--selftest` can report a clean error."""
    from botasaurus.browser import Driver  # noqa: F401

    return Driver


def _open(url: str):
    """Open a URL in the shared headless driver, creating it on first use."""
    global _driver
    Driver = _browser()
    if _driver is None:
        kwargs: dict[str, Any] = {"headless": HEADLESS, "block_images": True}
        if PROXY:
            kwargs["proxy"] = PROXY
        _driver = Driver(**kwargs)
        _driver.get("about:blank")
    try:
        # Botasaurus can clear Cloudflare's challenge (waits for it, clicking the
        # Turnstile checkbox with human-like motion when one appears).
        _driver.get(url, bypass_cloudflare=True, timeout=PAGE_TIMEOUT)
    except TypeError:  # older Driver signature
        _driver.get(url)
    return _driver


def _html(url: str) -> tuple[str, str]:
    driver = _open(url)
    source = getattr(driver, "page_html", None)
    if callable(source):
        source = source()
    if not source:
        inner = getattr(driver, "driver", None)
        source = getattr(inner, "page_source", "") if inner is not None else ""
    current = getattr(driver, "current_url", url)
    if callable(current):
        current = current()
    return source or "", current or url


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _unwrap_ddg(href: str) -> str:
    """DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<url>."""
    if "uddg=" in href:
        try:
            query = parse_qs(urlparse(href).query)
            if "uddg" in query:
                return unquote(query["uddg"][0])
        except Exception:
            pass
    if href.startswith("//"):
        return "https:" + href
    return href


def _selectors(engine: str) -> tuple[str, str, str]:
    """(container, link, snippet) CSS selectors per engine."""
    if engine == "bing":
        return "li.b_algo", "h2 a", "p"
    if engine == "mojeek":
        return "ul.results-standard li", "a.title", "p.s"
    if engine == "duckduckgo_lite":
        return "tr", "a.result-link", "td.result-snippet"
    return "div.result", "a.result__a", "a.result__snippet"


def _search_with(url: str, engine: str, limit: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    html, _ = _html(url)
    soup = BeautifulSoup(html, "lxml")
    container, link_sel, snippet_sel = _selectors(engine)

    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in soup.select(container):
        anchor = node.select_one(link_sel)
        if anchor is None:
            continue
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#")):
            continue
        href = _unwrap_ddg(href)
        if not href.startswith("http") or href in seen:
            continue
        title = _clean(anchor.get_text(" "))
        if not title:
            continue
        snippet_node = node.select_one(snippet_sel)
        results.append(
            {
                "title": title,
                "url": href,
                "snippet": _clean(snippet_node.get_text(" ")) if snippet_node else "",
                "engine": engine,
            }
        )
        seen.add(href)
        if len(results) >= limit:
            break
    return results


ENGINE_URLS = {
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "duckduckgo_lite": "https://lite.duckduckgo.com/lite/?q={q}",
    "bing": "https://www.bing.com/search?q={q}&count={n}",
    "mojeek": "https://www.mojeek.com/search?q={q}",
}


def search(query: str, limit: int = DEFAULT_LIMIT, engine: str = DEFAULT_ENGINE) -> dict[str, Any]:
    limit = max(1, min(int(limit or DEFAULT_LIMIT), 30))
    order = [engine] if engine and engine != "auto" else [
        "duckduckgo", "duckduckgo_lite", "bing", "mojeek",
    ]
    attempts = []
    for name in order:
        template = ENGINE_URLS.get(name)
        if not template:
            continue
        url = template.format(q=quote(query), n=limit)
        try:
            results = _search_with(url, name, limit)
        except Exception as exc:  # engine unreachable / changed markup
            attempts.append({"engine": name, "error": str(exc)[:200]})
            continue
        if results:
            return {"query": query, "engine": name, "count": len(results),
                    "results": results, "attempts": attempts}
        attempts.append({"engine": name, "error": "no results parsed (blocked or markup changed)"})
    return {"query": query, "engine": None, "count": 0, "results": [], "attempts": attempts}


CHALLENGE_MARKERS = (
    "client challenge",
    "just a moment",
    "attention required",
    "checking your browser",
    "cf-challenge",
    "ddos-guard",
    "verify you are human",
)
ARCHIVE_ENABLED = os.environ.get("BOTASAURUS_MCP_ARCHIVE", "1") not in ("0", "false", "no")


def _challenge_reason(title: str, text: str) -> str | None:
    haystack = ((title or "") + " " + (text or "")[:1500]).lower()
    for marker in CHALLENGE_MARKERS:
        if marker in haystack:
            return marker
    return None


def _try_json(url: str) -> tuple[Any, str | None]:
    """Fetch a fallback and parse it as JSON; returns (payload, error)."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=PAGE_TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
        return json.loads(body), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"[:200]


def page(url: str, format: str = "text", selector: str | None = None,
         max_chars: int = 12000, fallback: str | None = None) -> dict[str, Any]:
    from bs4 import BeautifulSoup

    html, final_url = _html(url)
    soup = BeautifulSoup(html, "lxml")
    title = _clean(soup.title.get_text(" ")) if soup.title else ""

    reason = _challenge_reason(title, html)
    archived_from = None

    if reason and fallback:
        payload, error = _try_json(fallback)
        if payload is not None:
            text = json.dumps(payload, ensure_ascii=False, indent=1)
            fits = len(text) <= max_chars
            result: dict[str, Any] = {
                "url": url,
                "final_url": fallback,
                "title": title,
                "format": "json",
                "challenge": None,
                "fallback_used": fallback,
                "truncated": not fits,
                "note": "the HTML page served a bot challenge; returned the fallback API response instead",
            }
            if fits:
                result["json"] = payload
            else:
                result["json_text"] = text[:max_chars]
            return result

    if reason:
        target = fallback
        if not target and ARCHIVE_ENABLED:
            target = f"https://web.archive.org/web/2026/{url}"
            archived_from = url
        if target:
            try:
                html, _ = _html(target)
                final_url = target
                soup = BeautifulSoup(html, "lxml")
                title = _clean(soup.title.get_text(" ")) if soup.title else ""
                reason2 = _challenge_reason(title, html)
                if reason2:
                    reason, archived_from = reason2, None
                else:
                    reason = None
            except Exception as exc:
                return {"url": url, "final_url": final_url, "title": title,
                        "challenge": reason, "error": str(exc)[:200]}

    if selector:
        node = soup.select_one(selector)
        if node is None:
            return {"url": url, "final_url": final_url, "title": title,
                    "error": f"selector matched nothing: {selector}"}
        soup = node

    if format == "html":
        body = str(soup)
    elif format == "links":
        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = _unwrap_ddg(a["href"].strip())
            if not href.startswith("http") or href in seen:
                continue
            links.append({"url": href, "text": _clean(a.get_text(" "))[:200]})
            seen.add(href)
            if len(links) >= 500:
                break
        return {"url": url, "final_url": final_url, "title": title,
                "format": "links", "links": links, "count": len(links)}
    else:
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        body = soup.get_text("\n")
        body = "\n".join(line.strip() for line in body.splitlines() if line.strip())

    truncated = len(body) > max_chars
    result: dict[str, Any] = {
        "url": url,
        "final_url": final_url,
        "title": title,
        "format": format,
        "truncated": truncated,
        "text" if format != "html" else "html": body[:max_chars],
    }
    if reason:
        result["challenge"] = reason
        result["hint"] = (
            "The site served a bot challenge. Pass fallback=<the site's API or a mirror URL>, "
            "or set BOTASAURUS_MCP_PROXY to a proxy this site does not challenge."
        )
    if archived_from:
        result["archived"] = True
        result["archived_from"] = archived_from
        result["note"] = "the live page was challenged; served the closest Wayback snapshot (may be stale)"
    return result


# --------------------------------------------------------------------------- #
# MCP over stdio
# --------------------------------------------------------------------------- #

def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, result: dict[str, Any]) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "search":
        data = search(
            args.get("query", ""),
            args.get("limit", DEFAULT_LIMIT),
            args.get("engine", DEFAULT_ENGINE),
        )
    elif name == "page":
        data = page(
            args.get("url", ""),
            args.get("format", "text"),
            args.get("selector"),
            int(args.get("max_chars", 12000)),
            args.get("fallback"),
        )
    else:
        raise ValueError(f"unknown tool: {name}")
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=1)}],
        "isError": bool(data.get("error")) or (name == "search" and data.get("count") == 0),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--version" in argv:
        print(__version__)
        return 0
    if "--selftest" in argv:
        return _selftest(argv)
    if "--help" in argv or "-h" in argv:
        print(
            "skynet %s\n\n"
            "MCP server over stdio: free web search + page scraping.\n\n"
            "Usage: skynet [mcp]            MCP server on stdio\n"
            "       skynet search <query>   \n"
            "       skynet scrape <url>     \n"
            "       skynet install          register in your agent apps\n"
            "       skynet doctor           check the install\n\n"
            "Environment:\n"
            "  BOTASAURUS_MCP_ENGINE        auto|duckduckgo|duckduckgo_lite|bing|mojeek\n"
            "  BOTASAURUS_MCP_LIMIT         default result count (10)\n"
            "  BOTASAURUS_MCP_HEADLESS      1 (default) or 0 to watch the browser\n"
            "  BOTASAURUS_MCP_PROXY         optional http proxy\n"
            "  BOTASAURUS_MCP_PAGE_TIMEOUT  seconds per page (45)\n"
            % __version__
        )
        return 0

    # stdout belongs to the protocol: anything the libraries print must not
    # corrupt it, so give the real stdout to a private handle and send prints
    # (ours and theirs) to stderr.
    protocol_out = os.fdopen(os.dup(1), "w", encoding="utf-8")
    sys.stdout = sys.stderr
    globals()["_protocol_out"] = protocol_out

    def send(payload: dict[str, Any]) -> None:
        protocol_out.write(json.dumps(payload, ensure_ascii=False) + "\n")
        protocol_out.flush()

    globals()["_send"] = send
    globals()["_result"] = lambda rid, result: send({"jsonrpc": "2.0", "id": rid, "result": result})
    globals()["_error"] = lambda rid, code, msg: send(
        {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}
    )

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            requested = params.get("protocolVersion") or PROTOCOL_VERSION
            result = {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "botasaurus-mcp", "version": __version__},
            }
            if request_id is not None:
                result_ = result
                send({"jsonrpc": "2.0", "id": request_id, "result": result_})
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            if request_id is not None:
                send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "tools/list":
            if request_id is not None:
                send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            try:
                payload = _call_tool(name, arguments)
                send({"jsonrpc": "2.0", "id": request_id, "result": payload})
            except Exception as exc:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                            "isError": True,
                        },
                    }
                )
        elif request_id is not None and method and method.startswith("resources/"):
            send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601,
                  "message": f"unsupported method: {method}"}})
        elif request_id is not None and method == "shutdown":
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
            break
        # any other notification: ignore

    global _driver
    try:
        if _driver is not None:
            _driver.close()
    except Exception:
        pass
    return 0


def _selftest(argv: list[str]) -> int:
    query = argv[argv.index("--selftest") + 1] if len(argv) > argv.index("--selftest") + 1 else "rust programming language"
    print(f"engine order: {DEFAULT_ENGINE} | headless: {HEADLESS}", file=sys.stderr)
    data = search(query, 5)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    if data["count"]:
        first = data["results"][0]["url"]
        doc = page(first, max_chars=400)
        print("\n--- first result ---")
        print(json.dumps(doc, indent=2, ensure_ascii=False)[:1200])
    return 0 if data["count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
