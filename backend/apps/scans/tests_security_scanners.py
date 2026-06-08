"""security/ 被動安全 scanner 套件的單元測試。"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.scans.models import Finding, ScanJob


def _make_scan():
    """建立測試用 ScanJob（含必填 user / normalized_url / origin）。"""
    user = get_user_model().objects.create_user(
        username=f"user_{uuid.uuid4().hex[:8]}",
        password="testpass123",
    )
    return ScanJob.objects.create(
        user=user,
        original_url="https://example.com/",
        normalized_url="https://example.com/",
        origin="https://example.com",
    )


class TestFindingOwaspFields(TestCase):
    def test_finding_has_owasp_and_cwe_fields(self):
        scan = _make_scan()
        finding = Finding.objects.create(
            scan_job=scan,
            category="security",
            severity="medium",
            title="t",
            description="d",
            remediation="r",
            ai_handoff_prompt="p",
            owasp_category="A05",
            cwe_id="CWE-200",
        )
        finding.refresh_from_db()
        self.assertEqual(finding.owasp_category, "A05")
        self.assertEqual(finding.cwe_id, "CWE-200")


from apps.scans.security import ssl_scanner


class TestSslScanner(TestCase):
    def test_cert_expiry_high_when_within_30_days(self):
        import ssl as _ssl, time
        not_after = _ssl.cert_time_to_seconds  # noqa: F841 — 確認 API 存在
        future = time.strftime("%b %d %H:%M:%S %Y GMT", time.gmtime(time.time() + 20 * 86400))
        findings = ssl_scanner._eval_cert_expiry(future)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["rule_id"], "ssl-cert-expiring")

    def test_cert_expiry_critical_when_expired(self):
        import time
        past = time.strftime("%b %d %H:%M:%S %Y GMT", time.gmtime(time.time() - 86400))
        findings = ssl_scanner._eval_cert_expiry(past)
        self.assertEqual(findings[0]["severity"], "critical")
        self.assertEqual(findings[0]["rule_id"], "ssl-cert-expired")

    def test_cert_expiry_none_when_far(self):
        import time
        far = time.strftime("%b %d %H:%M:%S %Y GMT", time.gmtime(time.time() + 365 * 86400))
        self.assertEqual(ssl_scanner._eval_cert_expiry(far), [])

    def test_protocol_old_tls_is_high(self):
        findings = ssl_scanner._eval_protocol("TLSv1")
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["rule_id"], "ssl-weak-protocol")

    def test_protocol_modern_tls_empty(self):
        self.assertEqual(ssl_scanner._eval_protocol("TLSv1.3"), [])

    def test_cipher_weak_is_high(self):
        findings = ssl_scanner._eval_cipher("ECDHE-RSA-RC4-SHA")
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["rule_id"], "ssl-weak-cipher")

    def test_cipher_strong_empty(self):
        self.assertEqual(ssl_scanner._eval_cipher("ECDHE-RSA-AES128-GCM-SHA256"), [])

    def test_analyze_ssl_empty_host_returns_empty(self):
        self.assertEqual(ssl_scanner.analyze_ssl(""), [])

    def test_analyze_ssl_connection_error_returns_empty(self):
        self.assertEqual(ssl_scanner.analyze_ssl("invalid.invalid", port=443), [])

    def test_verify_error_expired_is_critical(self):
        findings = ssl_scanner._eval_cert_verify_error("certificate has expired")
        self.assertEqual(findings[0]["severity"], "critical")
        self.assertEqual(findings[0]["rule_id"], "ssl-cert-expired")

    def test_verify_error_self_signed_is_medium(self):
        findings = ssl_scanner._eval_cert_verify_error("self signed certificate")
        self.assertEqual(findings[0]["severity"], "medium")
        self.assertEqual(findings[0]["rule_id"], "ssl-self-signed")

    def test_verify_error_unknown_returns_empty(self):
        self.assertEqual(ssl_scanner._eval_cert_verify_error("some other error"), [])


from apps.scans.security import cookie_scanner


class TestCookieScanner(TestCase):
    def test_missing_secure_on_https_is_medium(self):
        headers = {"set-cookie": "sid=abc; Path=/; HttpOnly"}
        findings = cookie_scanner.analyze_cookies(headers, "https://example.com")
        rules = {f["rule_id"]: f for f in findings}
        self.assertIn("cookie-no-secure", rules)
        self.assertEqual(rules["cookie-no-secure"]["severity"], "medium")

    def test_missing_httponly_is_low(self):
        headers = {"set-cookie": "sid=abc; Path=/; Secure"}
        findings = cookie_scanner.analyze_cookies(headers, "https://example.com")
        rules = {f["rule_id"]: f for f in findings}
        self.assertEqual(rules["cookie-no-httponly"]["severity"], "low")

    def test_samesite_none_without_secure_is_medium(self):
        headers = {"set-cookie": "sid=abc; SameSite=None"}
        findings = cookie_scanner.analyze_cookies(headers, "https://example.com")
        rules = {f["rule_id"] for f in findings}
        self.assertIn("cookie-samesite-none", rules)

    def test_secure_httponly_strict_no_findings(self):
        headers = {"set-cookie": "sid=abc; Secure; HttpOnly; SameSite=Strict"}
        self.assertEqual(cookie_scanner.analyze_cookies(headers, "https://example.com"), [])

    def test_no_set_cookie_returns_empty(self):
        self.assertEqual(cookie_scanner.analyze_cookies({}, "https://example.com"), [])

    def test_multiple_cookies_split_by_newline(self):
        headers = {"set-cookie": "a=1; HttpOnly\nb=2; Secure"}
        findings = cookie_scanner.analyze_cookies(headers, "https://example.com")
        self.assertGreaterEqual(len(findings), 2)

    def test_bad_input_returns_empty(self):
        self.assertEqual(cookie_scanner.analyze_cookies(None, "https://example.com"), [])


from apps.scans.security import header_scanner


class TestHeaderScanner(TestCase):
    def _page(self, headers):
        return [{"headers": headers, "final_url": "https://example.com", "url": "https://example.com"}]

    def test_server_version_leak_is_low(self):
        findings = header_scanner.analyze_headers(self._page({"server": "Apache/2.4.49"}))
        rules = {f["rule_id"]: f for f in findings}
        self.assertEqual(rules["header-server-version"]["severity"], "low")

    def test_x_powered_by_is_low(self):
        findings = header_scanner.analyze_headers(self._page({"x-powered-by": "PHP/7.4.3"}))
        self.assertIn("header-x-powered-by", {f["rule_id"] for f in findings})

    def test_cors_wildcard_is_medium(self):
        findings = header_scanner.analyze_headers(self._page({"access-control-allow-origin": "*"}))
        rules = {f["rule_id"]: f for f in findings}
        self.assertEqual(rules["header-cors-wildcard"]["severity"], "medium")

    def test_cors_wildcard_with_credentials_is_high(self):
        findings = header_scanner.analyze_headers(self._page({
            "access-control-allow-origin": "*",
            "access-control-allow-credentials": "true",
        }))
        rules = {f["rule_id"]: f for f in findings}
        self.assertEqual(rules["header-cors-credentials"]["severity"], "high")

    def test_csp_unsafe_inline_is_medium(self):
        findings = header_scanner.analyze_headers(self._page({
            "content-security-policy": "default-src 'self'; script-src 'unsafe-inline'",
        }))
        self.assertIn("header-csp-unsafe", {f["rule_id"] for f in findings})

    def test_clean_headers_no_findings(self):
        findings = header_scanner.analyze_headers(self._page({"server": "cloudflare"}))
        self.assertEqual(findings, [])

    def test_no_pages_returns_empty(self):
        self.assertEqual(header_scanner.analyze_headers([]), [])

    def test_bad_input_returns_empty(self):
        self.assertEqual(header_scanner.analyze_headers(None), [])
