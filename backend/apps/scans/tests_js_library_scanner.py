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
