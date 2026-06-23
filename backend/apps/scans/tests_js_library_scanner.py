"""第三方 JS 庫 CVE scanner（js_library_scanner）單元測試。"""
import pathlib

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

    def test_mixed_external_and_inline_in_same_page(self):
        html = (
            '<script src="https://cdn.x/a.js"></script>'
            "<script>/*! lib v2.0 */ var b=2;</script>"
        )
        srcs, inline = jls._collect_scripts([{"html": html}])
        self.assertEqual(srcs, ["https://cdn.x/a.js"])
        self.assertEqual(len(inline), 1)
        self.assertIn("lib v2.0", inline[0])

    def test_malformed_html_does_not_raise(self):
        pages = [{"html": "<script src=<<>>broken"}]
        srcs, inline = jls._collect_scripts(pages)  # 不應拋例外
        self.assertIsInstance(srcs, list)
        self.assertIsInstance(inline, list)


class TestDetectVersion(TestCase):
    _EXTRACTORS = {
        "uri": ["/(§§version§§)/jquery(.min)?.js"],
        "filename": ["jquery-(§§version§§)(.min)?.js"],
        "filecontent": ["/\\*! jQuery v(§§version§§)"],
    }

    def test_filename_extractor_captures_version(self):
        ver, src = jls._detect_version(
            self._EXTRACTORS, ["https://cdn.x/jquery-1.6.0.min.js"], []
        )
        self.assertEqual(ver, "1.6.0")
        self.assertEqual(src, "https://cdn.x/jquery-1.6.0.min.js")

    def test_chained_suffix_stripped_to_core(self):
        # jquery-1.6.0.bundle.min.js → 版本核心應為 1.6.0（丟棄連鎖後綴）
        ver, _ = jls._detect_version(
            self._EXTRACTORS, ["https://cdn.x/jquery-1.6.0.bundle.min.js"], []
        )
        self.assertEqual(ver, "1.6.0")

    def test_uri_extractor_captures_version(self):
        ver, src = jls._detect_version(
            self._EXTRACTORS, ["https://cdnjs/ajax/libs/jquery/3.4.1/jquery.min.js"], []
        )
        self.assertEqual(ver, "3.4.1")

    def test_filecontent_extractor_marks_inline(self):
        ver, src = jls._detect_version(
            self._EXTRACTORS, [], ["/*! jQuery v1.6.0 */"]
        )
        self.assertEqual(ver, "1.6.0")
        self.assertEqual(src, "inline")

    def test_no_match_returns_none(self):
        ver, src = jls._detect_version(self._EXTRACTORS, ["https://cdn.x/react.min.js"], [])
        self.assertIsNone(ver)
        self.assertIsNone(src)

    def test_load_db_missing_file_returns_empty(self):
        # 暫時指向不存在的路徑，確認 silent-fail（清掉 lru_cache）
        orig = jls._DB_PATH
        jls._load_db.cache_clear()
        jls._DB_PATH = pathlib.Path("/nonexistent/jsrepository.json")
        try:
            self.assertEqual(jls._load_db(), {})
        finally:
            jls._DB_PATH = orig
            jls._load_db.cache_clear()
