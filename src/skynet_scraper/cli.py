"""SkyNet Scraper command line.

    skynet                 MCP server on stdio (what coding agents run)
    skynet search "query"  print results
    skynet scrape <url>    print a page's text
    skynet bulk            fetch many pages from one protected host
    skynet install         register the MCP server in every agent app found
    skynet doctor          check the install

No configuration is required for any of it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any

from . import server

DESKTOP_CLIENTS = {
    # name: (config path, json path inside it, entry shape)
    "claude_desktop": (
        "~/Library/Application Support/Claude/claude_desktop_config.json",
        ("mcpServers", "skynet"),
        "claude",
    ),
    "cursor": ("~/.cursor/mcp.json", ("mcpServers", "skynet"), "claude"),
    "opencode": ("~/.config/opencode/opencode.json", ("mcp", "skynet"), "opencode"),
    "vscode": ("~/Library/Application Support/Code/User/mcp.json", ("servers", "skynet"), "claude"),
}


def _exe() -> str:
    """The command an MCP client should run."""
    found = shutil.which("skynet")
    if found:
        return found
    return os.path.abspath(sys.argv[0])


def _entry(exe: str, shape: str) -> dict[str, Any]:
    if shape == "opencode":
        return {"type": "local", "command": [exe], "environment": {"BOTASAURUS_MCP_HEADLESS": "1"}}
    return {"command": exe, "args": [], "env": {"BOTASAURUS_MCP_HEADLESS": "1"}}


def _merge_json(path: str, keys: tuple[str, str], entry: dict[str, Any]) -> str:
    path = os.path.expanduser(path)
    data: dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path) as handle:
                data = json.load(handle) or {}
        except Exception:
            backup = path + ".bak"
            shutil.copy(path, backup)
            data = {}
    container = data.setdefault(keys[0], {})
    if not isinstance(container, dict):
        container = {}
        data[keys[0]] = container
    existed = keys[1] in container
    container[keys[1]] = entry
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    return "updated" if existed else "added"


def _codex_config() -> str | None:
    path = os.path.expanduser("~/.codex/config.toml")
    if not os.path.isdir(os.path.dirname(path)):
        return None
    text = ""
    if os.path.exists(path):
        with open(path) as handle:
            text = handle.read()
    if "[mcp_servers.skynet]" in text:
        return "already registered"
    block = f'\n[mcp_servers.skynet]\ncommand = "{_exe()}"\nargs = []\n'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        handle.write(block)
    return "added"


def install(argv: list[str]) -> int:
    exe = _exe()
    print(f"SkyNet Scraper at {exe}\n")
    touched = 0

    for name, (path, keys, shape) in DESKTOP_CLIENTS.items():
        expanded = os.path.expanduser(path)
        parent = os.path.dirname(expanded)
        # only touch apps that are actually installed
        if name == "claude_desktop" and not os.path.isdir(
            os.path.expanduser("~/Library/Application Support/Claude")
        ):
            continue
        if name == "vscode" and not os.path.isdir(os.path.expanduser("~/Library/Application Support/Code")):
            continue
        if name == "cursor" and not os.path.isdir(os.path.expanduser("~/.cursor")):
            continue
        if name == "opencode" and not os.path.isdir(os.path.expanduser("~/.config/opencode")):
            continue
        state = _merge_json(path, keys, _entry(exe, shape))
        print(f"  {name:16} {state:16} {path}")
        touched += 1

    codex = _codex_config()
    if codex:
        print(f"  {'codex':16} {codex:16} ~/.codex/config.toml")
        touched += 1

    if not touched:
        print("  no agent apps found; register this command by hand:")
        print(json.dumps({"mcpServers": {"skynet": _entry(exe, "claude")}}, indent=2))

    print("\nRestart the app(s) above. Then ask your agent to search or scrape")
    print("anything; no keys, no accounts, no further setup.")
    return 0


def doctor(_: list[str]) -> int:
    exe = _exe()
    print(f"skynet    {server.__version__}  ({exe})")
    print(f"python    {sys.version.split()[0]}  ({sys.executable})")
    try:
        from importlib.metadata import PackageNotFoundError, version

        from botasaurus_driver.driver import Driver  # noqa: F401

        try:
            driver_version = version("botasaurus-driver")
        except PackageNotFoundError:
            driver_version = "installed"
        print(f"driver    botasaurus-driver {driver_version}")
    except Exception as exc:
        print(f"driver    MISSING: {exc}")
        return 1

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    print(f"chrome    {'found' if os.path.exists(chrome) else 'NOT FOUND at ' + chrome}")
    print(f"engine    {server.DEFAULT_ENGINE}   headless: {server.HEADLESS}   archive fallback: {server.ARCHIVE_ENABLED}")
    print("\nsearch test")
    data = server.search("rust release notes", limit=2)
    print(f"  engine {data['engine']} -> {data['count']} result(s)")
    if data["count"]:
        print("  ", data["results"][0]["title"][:70])
    return 0 if data["count"] else 2


def cli_search(argv: list[str]) -> int:
    if not argv:
        print("usage: skynet search <query> [--limit N] [--engine auto|bing|duckduckgo|mojeek]", file=sys.stderr)
        return 2
    limit, engine, query = 10, server.DEFAULT_ENGINE, []
    i = 0
    while i < len(argv):
        if argv[i] == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1]); i += 2
        elif argv[i] == "--engine" and i + 1 < len(argv):
            engine = argv[i + 1]; i += 2
        else:
            query.append(argv[i]); i += 1
    data = server.search(" ".join(query), limit, engine)
    print(json.dumps(data, indent=1, ensure_ascii=False))
    return 0 if data["count"] else 2


def cli_scrape(argv: list[str]) -> int:
    if not argv:
        print("usage: skynet scrape <url> [--format text|html|links] [--selector CSS] [--max-chars N] [--fallback URL]",
              file=sys.stderr)
        return 2
    url, fmt, selector, max_chars, fallback = None, "text", None, 12000, None
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag in ("--format", "--selector", "--max-chars", "--fallback") and i + 1 < len(argv):
            value = argv[i + 1]
            if flag == "--format":
                fmt = value
            elif flag == "--selector":
                selector = value
            elif flag == "--max-chars":
                max_chars = int(value)
            else:
                fallback = value
            i += 2
        else:
            url = url or flag
            i += 1
    if not url:
        print("usage: skynet scrape <url>", file=sys.stderr)
        return 2
    data = server.page(url, fmt, selector, max_chars, fallback)
    print(json.dumps(data, indent=1, ensure_ascii=False))
    return 0 if not data.get("error") else 1


def cli_bulk(argv: list[str]) -> int:
    """Fetch many pages from one host, with Cloudflare handled."""
    from . import bulk

    if not argv:
        print("usage: skynet bulk --urls FILE [--out DIR] [--workers N] "
              "[--delay A B] [--limit N]", file=sys.stderr)
        return 2

    urls: list[str] = []
    out_dir = None
    workers = 4
    delay = (0.05, 0.25)
    limit = 0
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag == "--urls" and i + 1 < len(argv):
            with open(os.path.expanduser(argv[i + 1])) as handle:
                urls.extend(line.strip() for line in handle if line.strip())
            i += 2
        elif flag == "--out" and i + 1 < len(argv):
            out_dir = argv[i + 1]; i += 2
        elif flag == "--workers" and i + 1 < len(argv):
            workers = int(argv[i + 1]); i += 2
        elif flag == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1]); i += 2
        elif flag == "--delay" and i + 2 < len(argv):
            delay = (float(argv[i + 1]), float(argv[i + 2])); i += 3
        elif flag.startswith("-"):
            print(f"unknown flag: {flag}", file=sys.stderr); return 2
        else:
            urls.append(flag); i += 1

    if limit:
        urls = urls[:limit]
    if not urls:
        print("no urls given", file=sys.stderr)
        return 2

    started = time.time()
    seen = {"n": 0}

    def progress(message: dict[str, Any]) -> None:
        seen["n"] += 1
        if seen["n"] % 25 == 0:
            rate = seen["n"] / max(time.time() - started, 1e-9)
            print(f"  {seen['n']}/{len(urls)} {rate:.1f}/s", file=sys.stderr, flush=True)

    results = bulk.fetch_many(urls, workers=workers, out_dir=out_dir,
                             delay=delay, progress=progress)
    blocked = sum(1 for item in results if item["blocked"])
    summary = {
        "urls": len(urls),
        "fetched": len(results),
        "blocked": blocked,
        "bytes": sum(item["bytes"] for item in results),
        "out": out_dir,
        "seconds": round(time.time() - started, 1),
    }
    print(json.dumps(summary, indent=1))
    return 0 if len(results) == len(urls) and not blocked else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return server.main([])          # MCP on stdio: what agents spawn
    command, rest = argv[0], argv[1:]
    if command in ("mcp", "serve"):
        return server.main(rest)
    if command == "search":
        return cli_search(rest)
    if command == "scrape":
        return cli_scrape(rest)
    if command == "bulk":
        return cli_bulk(rest)
    if command == "install":
        return install(rest)
    if command == "doctor":
        return doctor(rest)
    if command in ("-V", "--version", "version"):
        print(server.__version__)
        return 0
    if command in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    print(f"unknown command: {command}\n\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
