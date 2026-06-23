"""第三方 JS 庫 CVE scanner（js_library_scanner）單元測試。"""
from django.test import TestCase

from apps.scans.security import js_library_scanner as jls


class TestVersionCompare(TestCase):
    def test_numeric_segments_not_lexical(self):
        # 1.10.0 > 1.9.0（數字比較，非字典序）
        self.assertEqual(jls._compare_versions("1.10.0", "1.9.0"), 1)

    def test_lower_is_negative(self):
        self.assertEqual(jls._compare_versions("1.6.0", "1.6.3"), -1)

    def test_equal_is_zero(self):
        self.assertEqual(jls._compare_versions("1.6.3", "1.6.3"), 0)

    def test_prerelease_below_release(self):
        # 3.0.0-rc1 < 3.0.0（pre-release 視為較低）
        self.assertEqual(jls._compare_versions("3.0.0-rc1", "3.0.0"), -1)


class TestIsVulnerable(TestCase):
    def test_below_only_match(self):
        self.assertTrue(jls._is_vulnerable("1.6.0", {"below": "1.6.3"}))

    def test_below_only_no_match(self):
        self.assertFalse(jls._is_vulnerable("1.7.0", {"below": "1.6.3"}))

    def test_range_atorabove_below(self):
        vuln = {"atOrAbove": "1.0.0", "below": "1.12.0"}
        self.assertTrue(jls._is_vulnerable("1.0.0", vuln))
        self.assertTrue(jls._is_vulnerable("1.5.0", vuln))
        self.assertFalse(jls._is_vulnerable("0.9.0", vuln))
        self.assertFalse(jls._is_vulnerable("1.12.0", vuln))

    def test_no_bounds_never_matches(self):
        self.assertFalse(jls._is_vulnerable("1.0.0", {"severity": "high"}))

    def test_atorbelow_match(self):
        self.assertTrue(jls._is_vulnerable("1.9.9", {"atOrBelow": "2.0.0"}))

    def test_atorbelow_no_match(self):
        self.assertFalse(jls._is_vulnerable("2.0.1", {"atOrBelow": "2.0.0"}))


class TestCollectScripts(TestCase):
    def test_collects_external_src(self):
        pages = [{"html": '<script src="https://cdn.x/jquery-1.6.0.min.js"></script>'}]
        srcs, inline = jls._collect_scripts(pages)
        self.assertEqual(srcs, ["https://cdn.x/jquery-1.6.0.min.js"])
        self.assertEqual(inline, [])

    def test_collects_inline_content(self):
        pages = [{"html": "<script>/*! jQuery v1.6.0 */ var a=1;</script>"}]
        srcs, inline = jls._collect_scripts(pages)
        self.assertEqual(srcs, [])
        self.assertEqual(len(inline), 1)
        self.assertIn("jQuery v1.6.0", inline[0])

    def test_empty_and_missing_html_skipped(self):
        pages = [{"html": ""}, {}, {"html": "<script src='/a.js'></script>"}]
        srcs, inline = jls._collect_scripts(pages)
        self.assertEqual(srcs, ["/a.js"])
        self.assertEqual(inline, [])

    def test_malformed_html_does_not_raise(self):
        pages = [{"html": "<script src=<<>>broken"}]
        srcs, inline = jls._collect_scripts(pages)  # 不應拋例外
        self.assertIsInstance(srcs, list)
