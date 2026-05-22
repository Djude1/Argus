from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.scans.crawler import classify_blocked, compute_min_interval
from apps.scans.models import AuthorizationConsent, Finding, Page, ScanJob, UserScanQuota
from apps.scans.scanners import (
    PageAnalysisInput,
    analyze_geo_fast,
    analyze_page,
    analyze_site_signals,
    calculate_scores,
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
        response = self.client.get("/admin/scans/scanjob/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "掃描總覽")

    def test_authorization_consent_admin_is_view_only(self):
        # 授權同意書是法律證據，不允許透過 Admin 新增
        response = self.client.get("/admin/scans/authorizationconsent/add/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(ARGUS_AUTO_QUEUE_SCANS=False)
class UserScanQuotaTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="quota-user",
            email="quota@example.com",
            password="safe-test-password",
        )
        self.client.force_authenticate(self.user)
        self.url = reverse("scan-list")

    def test_quota_auto_created_with_default_limit(self):
        response = self.client.post(
            self.url,
            {"url": "https://example.com/", "authorization_confirmed": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        quota = UserScanQuota.objects.get(user=self.user)
        self.assertEqual(quota.monthly_limit, 20)

    def test_quota_blocks_when_exhausted(self):
        UserScanQuota.objects.create(user=self.user, monthly_limit=1)
        first = self.client.post(
            self.url,
            {"url": "https://example.com/", "authorization_confirmed": True},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            self.url,
            {"url": "https://example.com/foo", "authorization_confirmed": True},
            format="json",
        )

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quota", second.data)

    def test_has_quota_remaining_with_no_scans(self):
        quota = UserScanQuota.objects.create(user=self.user, monthly_limit=5)

        self.assertTrue(quota.has_quota_remaining())
        self.assertEqual(quota.consumed_this_month(), 0)


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
