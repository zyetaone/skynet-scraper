"""Offline tests: parsing, engine selection and challenge detection.

No browser, no network, so they run anywhere and fast:

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skynet_scraper.server import (  # noqa: E402
    _challenge_reason,
    _clean,
    _parse_results,
    _selectors,
    _unwrap_ddg,
)

DDG_HTML = """
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">First</a>
  <a class="result__snippet">first snippet</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/b">Second</a>
  <a class="result__snippet">second snippet</a>
</div>
<div class="result">
  <a class="result__a" href="javascript:void(0)">Ignored</a>
</div>
"""

BING_HTML = """
<li class="b_algo"><h2><a href="https://example.com/bing">Bing hit</a></h2><p>bing snippet</p></li>
"""

MOJEEK_HTML = """
<ul class="results-standard">
  <li><a class="title" href="https://example.com/mojeek">Mojeek hit</a><p class="s">mojeek snippet</p></li>
</ul>
"""


class ParsingTests(unittest.TestCase):
    def test_duckduckgo_results_are_unwrapped_and_deduped(self):
        results = _parse_results(DDG_HTML, "duckduckgo", 10)
        self.assertEqual([r["url"] for r in results], ["https://example.com/a", "https://example.com/b"])
        self.assertEqual(results[0]["title"], "First")
        self.assertEqual(results[0]["snippet"], "first snippet")
        self.assertEqual(results[1]["engine"], "duckduckgo")

    def test_limit_is_respected(self):
        self.assertEqual(len(_parse_results(DDG_HTML, "duckduckgo", 1)), 1)

    def test_javascript_links_are_skipped(self):
        urls = [r["url"] for r in _parse_results(DDG_HTML, "duckduckgo", 10)]
        self.assertNotIn("Ignored", " ".join(urls))

    def test_bing_and_mojeek_markup(self):
        bing = _parse_results(BING_HTML, "bing", 5)
        mojeek = _parse_results(MOJEEK_HTML, "mojeek", 5)
        self.assertEqual(bing[0]["url"], "https://example.com/bing")
        self.assertEqual(bing[0]["snippet"], "bing snippet")
        self.assertEqual(mojeek[0]["url"], "https://example.com/mojeek")

    def test_empty_page_yields_nothing(self):
        self.assertEqual(_parse_results("<html><body>no results</body></html>", "duckduckgo", 5), [])


class HelperTests(unittest.TestCase):
    def test_unwrap_duckduckgo_redirect(self):
        self.assertEqual(
            _unwrap_ddg("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx%3Fa%3D1"),
            "https://example.com/x?a=1",
        )
        self.assertEqual(_unwrap_ddg("https://example.com/y"), "https://example.com/y")
        self.assertEqual(_unwrap_ddg("//example.com/z"), "https://example.com/z")

    def test_clean_collapses_whitespace(self):
        self.assertEqual(_clean("  a \n\t b  "), "a b")
        self.assertEqual(_clean(None), "")

    def test_challenge_markers(self):
        self.assertEqual(_challenge_reason("Client Challenge", ""), "client challenge")
        self.assertEqual(_challenge_reason("Just a moment...", ""), "just a moment")
        self.assertEqual(_challenge_reason("Nice page", "please verify you are human"), "verify you are human")
        self.assertIsNone(_challenge_reason("Rust docs", "The Rust Programming Language"))

    def test_selectors_are_defined_for_every_engine(self):
        for engine in ("duckduckgo", "duckduckgo_lite", "bing", "mojeek"):
            container, link, snippet = _selectors(engine)
            self.assertTrue(container and link and snippet, engine)


if __name__ == "__main__":
    unittest.main()
