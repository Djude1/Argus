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
