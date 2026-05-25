from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import CoinWallet
from apps.scans.crawler import classify_blocked, compute_min_interval
from apps.scans.models import AuthorizationConsent, Finding, Page, ScanJob
from apps.scans.scanners import (
    PageAnalysisInput,
    analyze_aeo,
    analyze_geo_fast,
    analyze_page,
    analyze_site_signals,
    calculate_scores,
    detect_faq_structure,
    is_admin_path,
    is_binary_resource,
    parse_html_signals,
)


class ScanJobModelTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            email="tester@example.com",
            password="safe-test-password",
        )

    def test_active_scan_requires_extra_authorization(self):
        scan_job = ScanJob(
            user=self.user,
            original_url="https://example.com/",
            normalized_url="https://example.com/",
            origin="https://example.com",
            scan_mode=ScanJob.ScanMode.ACTIVE,
            active_testing_authorized=False,
        )

        with self.assertRaisesMessage(Exception, "主動測試必須先取得額外授權。"):
            scan_job.clean()

    def test_passive_scan_defaults_are_safe(self):
        scan_job = ScanJob.objects.create(
            user=self.user,
            original_url="https://example.com/",
            normalized_url="https://example.com/",
            origin="https://example.com",
        )

        self.assertEqual(scan_job.scan_mode, ScanJob.ScanMode.PASSIVE)
        self.assertEqual(scan_job.max_depth, 3)
        self.assertEqual(scan_job.max_pages, 50)
        self.assertTrue(scan_job.respect_robots)


class StaticScannerTests(APITestCase):
    def test_analyze_page_returns_seo_geo_and_security_findings(self):
        page_input = PageAnalysisInput(
            url="http://example.com/",
            final_url="http://example.com/",
            title="短",
            html="<html><body><h1>主標題</h1><img src='/a.png'><form></form></body></html>",
            headers={},
            element_boxes={"h1": {"x": 1, "y": 2, "width": 3, "height": 4}},
        )

        findings = analyze_page(page_input)
        categories = {finding["category"] for finding in findings}
        titles = {finding["title"] for finding in findings}

        self.assertIn("seo", categories)
        self.assertIn("geo", categories)
        self.assertIn("security", categories)
        self.assertIn("Meta title 長度不理想", titles)
        self.assertIn("缺少 JSON-LD 結構化資料", titles)
        self.assertIn("頁面未使用 HTTPS", titles)

    def test_calculate_scores_returns_top_actions_without_code(self):
        findings = [
            {
                "category": "security",
                "severity": "high",
                "title": "頁面未使用 HTTPS",
                "priority_score": 90,
            },
            {
                "category": "seo",
                "severity": "low",
                "title": "缺少 canonical URL",
                "priority_score": 30,
            },
        ]

        overall_score, category_scores, top_actions = calculate_scores(findings)

        self.assertLess(overall_score, 100)
        self.assertLess(category_scores["security"], category_scores["aeo"])
        self.assertEqual(top_actions[0]["title"], "頁面未使用 HTTPS")


@override_settings(ARGUS_AUTO_QUEUE_SCANS=False)
class ScanJobApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-user",
            email="api@example.com",
            password="safe-test-password",
        )
        # 預先把測試使用者的 coin 加滿，避免 coin 不足干擾建立掃描的行為測試
        CoinWallet.objects.filter(user=self.user).update(balance=10000)
        self.client.force_authenticate(self.user)
        self.url = reverse("scan-list")

    def test_create_scan_requires_authorization_confirmation(self):
        response = self.client.post(
            self.url,
            {
                "url": "https://example.com/",
                "authorization_confirmed": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ScanJob.objects.count(), 0)

    def test_create_scan_records_authorization_consent(self):
        response = self.client.post(
            self.url,
            {
                "url": "example.com",
                "authorization_confirmed": True,
            },
            format="json",
            HTTP_USER_AGENT="ArgusTest/1.0",
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        scan_job = ScanJob.objects.get()
        consent = AuthorizationConsent.objects.get(scan_job=scan_job)
        self.assertEqual(scan_job.normalized_url, "https://example.com/")
        self.assertEqual(scan_job.origin, "https://example.com")
        self.assertEqual(consent.authorized_domain, "example.com")
        self.assertEqual(consent.ip_address, "203.0.113.10")
        self.assertEqual(consent.user_agent, "ArgusTest/1.0")

    def test_create_scan_response_uses_read_model_shape(self):
        response = self.client.post(
            self.url,
            {
                "url": "https://example.com/",
                "authorization_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("status", response.data)
        self.assertIn("normalized_url", response.data)
        self.assertNotIn("authorization_confirmed", response.data)

    def test_obvious_third_party_requires_reconfirmation(self):
        response = self.client.post(
            self.url,
            {
                "url": "https://google.com/",
                "authorization_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("third_party_reconfirmed", response.data)

    def test_active_scan_requires_active_authorization(self):
        response = self.client.post(
            self.url,
            {
                "url": "https://example.com/",
                "authorization_confirmed": True,
                "scan_mode": ScanJob.ScanMode.ACTIVE,
                "active_testing_authorized": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ScanJob.objects.count(), 0)

    def test_active_scan_with_extra_authorization_is_recorded(self):
        response = self.client.post(
            self.url,
            {
                "url": "https://example.com/",
                "authorization_confirmed": True,
                "scan_mode": ScanJob.ScanMode.ACTIVE,
                "active_testing_authorized": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        scan_job = ScanJob.objects.get()
        consent = AuthorizationConsent.objects.get(scan_job=scan_job)
        self.assertEqual(scan_job.scan_mode, ScanJob.ScanMode.ACTIVE)
        self.assertTrue(scan_job.active_testing_authorized)
        self.assertTrue(consent.active_testing_authorized)

    def test_status_endpoint_returns_scan_status(self):
        scan_job = ScanJob.objects.create(
            user=self.user,
            original_url="https://example.com/",
            normalized_url="https://example.com/",
            origin="https://example.com",
        )

        response = self.client.get(reverse("scan-status", args=[scan_job.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ScanJob.Status.QUEUED)


class CrawlerHelperTests(APITestCase):
    def test_compute_min_interval_active_enforces_rps_cap(self):
        # 主動模式 RPS=2，兩次請求至少間隔 0.5 秒
        interval = compute_min_interval("active", active_rps=2, passive_rps=5)
        self.assertEqual(interval, 0.5)

    def test_compute_min_interval_passive_is_faster_than_active(self):
        active = compute_min_interval("active", active_rps=2, passive_rps=5)
        passive = compute_min_interval("passive", active_rps=2, passive_rps=5)
        self.assertLess(passive, active)

    def test_classify_blocked_flags_forbidden_and_rate_limited(self):
        self.assertNotEqual(classify_blocked(401), "")
        self.assertNotEqual(classify_blocked(403), "")
        self.assertNotEqual(classify_blocked(429), "")

    def test_classify_blocked_allows_normal_status(self):
        self.assertEqual(classify_blocked(200), "")
        self.assertEqual(classify_blocked(404), "")
        self.assertEqual(classify_blocked(None), "")


class GeoFastScannerTests(APITestCase):
    def _page_input(self, html: str, html_only: str = "") -> PageAnalysisInput:
        return PageAnalysisInput(
            url="https://example.com/",
            final_url="https://example.com/",
            title="測試頁面",
            html=html,
            headers={},
            element_boxes={},
            html_only=html_only,
        )

    def test_geo_fast_flags_js_dependent_content(self):
        rendered = "<html><body><main>" + "內容文字資料" * 200 + "</main></body></html>"
        raw = "<html><body><div id='root'></div></body></html>"
        page_input = self._page_input(rendered, html_only=raw)
        findings = analyze_geo_fast(page_input, parse_html_signals(rendered))

        self.assertIn("accessible", {finding["impact_area"] for finding in findings})

    def test_geo_fast_skips_accessible_check_for_ssr_page(self):
        html = "<html><body><main>" + "內容文字資料" * 200 + "</main></body></html>"
        page_input = self._page_input(html, html_only=html)
        findings = analyze_geo_fast(page_input, parse_html_signals(html))

        self.assertNotIn("accessible", {finding["impact_area"] for finding in findings})

    def test_geo_fast_flags_missing_semantic_landmark(self):
        html = "<html><body><div>沒有 main 標籤</div></body></html>"
        page_input = self._page_input(html)
        findings = analyze_geo_fast(page_input, parse_html_signals(html))

        self.assertIn("structured", {finding["impact_area"] for finding in findings})

    def test_geo_fast_accepts_semantic_landmark(self):
        html = "<html><body><main>主要內容</main></body></html>"
        page_input = self._page_input(html)
        findings = analyze_geo_fast(page_input, parse_html_signals(html))

        self.assertNotIn("structured", {finding["impact_area"] for finding in findings})

    def test_geo_fast_flags_long_paragraph(self):
        html = f"<html><body><main><p>{'字' * 1500}</p></main></body></html>"
        page_input = self._page_input(html)
        findings = analyze_geo_fast(page_input, parse_html_signals(html))

        self.assertIn("trim", {finding["impact_area"] for finding in findings})

    def test_analyze_site_signals_flags_missing_llms_txt(self):
        findings = analyze_site_signals({"llms_txt_found": False, "blocked_ai_crawlers": []})

        self.assertIn("網站未提供 llms.txt", {finding["title"] for finding in findings})

    def test_analyze_site_signals_flags_blocked_ai_crawlers(self):
        findings = analyze_site_signals(
            {"llms_txt_found": True, "blocked_ai_crawlers": ["GPTBot"]}
        )

        self.assertIn(
            "robots.txt 阻擋了主流 AI 爬蟲",
            {finding["title"] for finding in findings},
        )

    def test_analyze_site_signals_clean_site_has_no_findings(self):
        findings = analyze_site_signals({"llms_txt_found": True, "blocked_ai_crawlers": []})

        self.assertEqual(findings, [])


class ScanAdminTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="root",
            email="root@example.com",
            password="safe-test-password",
        )
        self.client.force_login(self.admin)

    def test_scanjob_changelist_shows_summary(self):
        response = self.client.get("/django-admin/scans/scanjob/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "掃描總覽")

    def test_authorization_consent_admin_is_view_only(self):
        # 授權同意書是法律證據，不允許透過 Admin 新增
        response = self.client.get("/django-admin/scans/authorizationconsent/add/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RerunScanCommandTests(APITestCase):
    def test_rerun_scan_regenerates_findings_from_saved_pages(self):
        user = get_user_model().objects.create_user(
            username="replayer",
            email="replay@example.com",
            password="safe-test-password",
        )
        scan_job = ScanJob.objects.create(
            user=user,
            original_url="https://example.com/",
            normalized_url="https://example.com/",
            origin="https://example.com",
            status=ScanJob.Status.COMPLETED,
        )
        Page.objects.create(
            scan_job=scan_job,
            url="https://example.com/",
            final_url="https://example.com/",
            origin="https://example.com",
            status_code=200,
            title="範例頁",
            html="<html><body><h1>主標題</h1></body></html>",
            html_only_text="<html><body><h1>主標題</h1></body></html>",
            headers={},
            element_boxes={},
        )

        out = StringIO()
        call_command("rerun_scan", scan_job.id, stdout=out)

        self.assertIn("重新掃描", out.getvalue())
        self.assertGreater(Finding.objects.filter(scan_job=scan_job).count(), 0)

    def test_rerun_scan_raises_on_missing_scan_job(self):
        with self.assertRaises(CommandError):
            call_command("rerun_scan", 999999)


class PageTypeRoutingTests(APITestCase):
    """掃描器對 admin 後台與二進位資源的路由判斷：跳過索引面向、保留安全檢查。"""

    def test_is_binary_resource_recognizes_common_downloadables(self):
        self.assertTrue(is_binary_resource("https://example.com/media/app.apk"))
        self.assertTrue(is_binary_resource("https://example.com/files/manual.pdf"))
        self.assertTrue(is_binary_resource("https://example.com/release/build.zip"))
        self.assertTrue(is_binary_resource("https://example.com/assets/logo.png"))

    def test_is_binary_resource_treats_html_pages_as_non_binary(self):
        self.assertFalse(is_binary_resource("https://example.com/"))
        self.assertFalse(is_binary_resource("https://example.com/product/1"))
        self.assertFalse(is_binary_resource("https://example.com/team"))

    def test_is_admin_path_recognizes_common_backend_routes(self):
        self.assertTrue(is_admin_path("https://example.com/admin"))
        self.assertTrue(is_admin_path("https://example.com/admin/login"))
        self.assertTrue(is_admin_path("https://example.com/wp-admin/users.php"))
        self.assertTrue(is_admin_path("https://example.com/dashboard/reports"))

    def test_is_admin_path_skips_frontend_routes(self):
        self.assertFalse(is_admin_path("https://example.com/"))
        self.assertFalse(is_admin_path("https://example.com/administrator-info"))  # 非 admin 前綴
        self.assertFalse(is_admin_path("https://example.com/team"))

    def test_analyze_page_skips_seo_findings_for_admin_login(self):
        # admin/login 缺 H1、缺 description、缺 JSON-LD 都不該被列為 SEO/GEO/AEO 問題
        page_input = PageAnalysisInput(
            url="https://example.com/admin/login",
            final_url="https://example.com/admin/login",
            title="Login",
            html="<html><body><form><input name='user'></form></body></html>",
            headers={},
            element_boxes={},
        )

        findings = analyze_page(page_input)
        categories = {finding["category"] for finding in findings}

        self.assertNotIn("seo", categories)
        self.assertNotIn("aeo", categories)
        self.assertNotIn("geo", categories)

    def test_analyze_page_keeps_security_findings_for_admin_login(self):
        # 後台登入的 CSRF/安全頭部反而更需要被檢查，不可被跳過
        page_input = PageAnalysisInput(
            url="https://example.com/admin/login",
            final_url="https://example.com/admin/login",
            title="Login",
            html="<html><body><form><input name='user'></form></body></html>",
            headers={},
            element_boxes={},
        )

        findings = analyze_page(page_input)
        security_titles = {f["title"] for f in findings if f["category"] == "security"}

        self.assertIn("表單可能缺少 CSRF token", security_titles)

    def test_analyze_page_only_runs_security_for_binary_resource(self):
        # APK 連結沒有 HTML 內容，不該被加上 H1/JSON-LD/FAQPage 等建議
        page_input = PageAnalysisInput(
            url="https://example.com/downloads/app.apk",
            final_url="https://example.com/downloads/app.apk",
            title="",
            html="",
            headers={},
            element_boxes={},
        )

        findings = analyze_page(page_input)
        categories = {finding["category"] for finding in findings}

        self.assertNotIn("seo", categories)
        self.assertNotIn("aeo", categories)
        self.assertNotIn("geo", categories)
        # HSTS/CSP 等安全頭部對檔案下載仍有效益，因此 security 仍會出現
        self.assertIn("security", categories)


class AeoFaqHeuristicTests(APITestCase):
    """FAQPage 建議邏輯：必須真有 FAQ 結構訊號才建議補 Schema，避免機械化誤判。"""

    def _page_input(self, html: str) -> PageAnalysisInput:
        return PageAnalysisInput(
            url="https://example.com/",
            final_url="https://example.com/",
            title="範例頁",
            html=html,
            headers={},
            element_boxes={},
        )

    def test_detect_faq_structure_recognizes_dl(self):
        self.assertTrue(detect_faq_structure("<dl><dt>Q</dt><dd>A</dd></dl>", dl_count=1))

    def test_detect_faq_structure_recognizes_details_tag(self):
        self.assertTrue(detect_faq_structure("<details><summary>Q</summary>A</details>", 0))

    def test_detect_faq_structure_recognizes_faq_class(self):
        self.assertTrue(detect_faq_structure("<section class='faq'>Q&A</section>", 0))

    def test_detect_faq_structure_returns_false_for_plain_content(self):
        self.assertFalse(detect_faq_structure("<p>產品介紹</p>", 0))

    def test_analyze_aeo_does_not_flag_pure_question_tone_without_faq_structure(self):
        # 報告中產品描述常用「能幫你做什麼」「如何使用」等問句，但沒有 FAQ 結構，
        # 此時建議補 FAQPage Schema 是機械化誤判，應改提示「先整理結構」。
        html = (
            "<html><body>"
            "<p>AI 智慧眼鏡能幫你做什麼？我們提供視障導航。</p>"
            "<p>如何使用？戴上即可。</p>"
            "<p>為何選擇我們？因為穩定。</p>"
            "<p>怎麼購買？至產品頁。</p>"
            "</body></html>"
        )
        findings = analyze_aeo(self._page_input(html), parse_html_signals(html))
        titles = {finding["title"] for finding in findings}

        self.assertNotIn("問答內容缺少 FAQPage 或 HowTo 結構化資料", titles)

    def test_analyze_aeo_flags_real_faq_section_without_schema(self):
        # 真正有 FAQ 結構（dl）但沒 Schema 時才該建議補 FAQPage/HowTo
        html = (
            "<html><body>"
            "<dl>"
            "<dt>什麼是視障導航？</dt><dd>用 AI 辨識環境引導視障者。</dd>"
            "<dt>如何配戴？</dt><dd>像一般眼鏡戴上即可。</dd>"
            "<dt>為何選 Argus？</dt><dd>準確度高。</dd>"
            "<dt>怎麼充電？</dt><dd>Type-C 充電。</dd>"
            "</dl>"
            "</body></html>"
        )
        findings = analyze_aeo(self._page_input(html), parse_html_signals(html))
        titles = {finding["title"] for finding in findings}

        self.assertIn("問答內容缺少 FAQPage 或 HowTo 結構化資料", titles)

    def test_analyze_aeo_ignores_low_question_density_text(self):
        # 內文只出現 1-2 個常用字（什麼/如何），不應觸發任何 AEO finding
        html = "<html><body><p>了解產品是什麼，並如何運作。</p></body></html>"
        findings = analyze_aeo(self._page_input(html), parse_html_signals(html))

        self.assertEqual(findings, [])

    def test_analyze_aeo_ignores_question_text_in_html_attributes(self):
        # 問句訊號只計算可見文字；HTML 屬性或 tag 中的字串不該被計入
        html = (
            "<html><body>"
            "<div class='how-to-image' data-tip='如何 什麼 為何 怎麼 ?'>"
            "<p>純粹的內容，不是問答。</p>"
            "</div></body></html>"
        )
        findings = analyze_aeo(self._page_input(html), parse_html_signals(html))

        self.assertEqual(findings, [])
