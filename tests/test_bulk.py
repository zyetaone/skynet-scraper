"""Offline tests for the bulk fetcher: challenge detection and file naming.

No browser, no network:

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skynet_scraper import bulk  # noqa: E402


class TestBlocked(unittest.TestCase):
    def test_cloudflare_interstitial_is_blocked(self):
        body = ("<html><head><title>Just a moment...</title></head>"
                "<body>Checking your browser before accessing.</body></html>")
        self.assertTrue(bulk.looks_blocked(body))

    def test_attention_required_is_blocked(self):
        self.assertTrue(bulk.looks_blocked(
            "<html><title>Attention Required! | Cloudflare</title>" + "x" * 900 + "</html>"))

    def test_empty_body_is_blocked(self):
        self.assertTrue(bulk.looks_blocked(""))
        self.assertTrue(bulk.looks_blocked("short"))

    def test_real_page_passes(self):
        body = "<html><head><title>Product</title></head><body>" + "content " * 200 + "</body></html>"
        self.assertFalse(bulk.looks_blocked(body))


class TestSafeName(unittest.TestCase):
    def test_stable_and_flat(self):
        url = "https://www.archiexpo.com/prod/flos/product-9508-2571093.html"
        first = bulk.safe_name(url)
        self.assertEqual(first, bulk.safe_name(url))
        self.assertNotIn("/", first)
        self.assertTrue(first.endswith(".html"))

    def test_different_urls_differ(self):
        a = bulk.safe_name("https://example.com/a")
        b = bulk.safe_name("https://example.com/b")
        self.assertNotEqual(a, b)

    def test_long_url_is_shortened(self):
        name = bulk.safe_name("https://example.com/" + "segment-" * 40)
        self.assertLessEqual(len(name), 100)


class TestFetchManyEdges(unittest.TestCase):
    def test_empty_list_returns_empty(self):
        self.assertEqual(bulk.fetch_many([]), [])

    def test_block_patterns_cover_images_and_analytics(self):
        joined = " ".join(bulk.BLOCK_PATTERNS)
        self.assertIn("*.jpg", joined)
        self.assertIn("*google-analytics*", joined)


class TestSessionDefaults(unittest.TestCase):
    def test_session_is_lazy(self):
        session = bulk.Session(headless=True)
        self.assertIsNone(session._driver)
        self.assertEqual(session.rewarms, 0)
        session.close()


if __name__ == "__main__":
    unittest.main()
