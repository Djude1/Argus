from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import CoinTransaction
from apps.billing.services import purchase_plan
from apps.reviews.models import PlatformReview
from apps.scans.models import ScanJob


def _make_user(username, *, staff=False, **extra):
    defaults = {
        "email": f"{username}@example.com",
        "password": "safe-test-password",
        "is_staff": staff,
    }
    defaults.update(extra)
    return get_user_model().objects.create_user(username=username, **defaults)


def _make_scan(user, **kwargs):
    return ScanJob.objects.create(
        user=user,
        original_url=kwargs.pop("url", "https://example.com/"),
        normalized_url=kwargs.pop("nurl", "https://example.com/"),
        origin=kwargs.pop("origin", "https://example.com"),
        **kwargs,
    )


class AdminPermissionTests(APITestCase):
    def test_non_staff_user_blocked(self):
        normal = _make_user("normal")
        self.client.force_authenticate(normal)
        for name in ["admin-overview", "admin-users", "admin-transactions"]:
            response = self.client.get(reverse(name))
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN,
                msg=f"endpoint {name} 應該 403 阻擋非 staff",
            )

    def test_anonymous_blocked(self):
        response = self.client.get(reverse("admin-overview"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_user_allowed(self):
        admin = _make_user("admin1", staff=True)
        self.client.force_authenticate(admin)
        response = self.client.get(reverse("admin-overview"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class OverviewTests(APITestCase):
    def setUp(self):
        self.admin = _make_user("admin", staff=True)
        self.client.force_authenticate(self.admin)

    def test_overview_returns_totals_and_recent_lists(self):
        u = _make_user("u1")
        from apps.billing.models import PricingPlan
        plan = PricingPlan.objects.get(code="starter")
        purchase_plan(u, plan)
        _make_scan(u)

        response = self.client.get(reverse("admin-overview"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        totals = response.data["totals"]
        self.assertGreaterEqual(totals["users"], 2)
        self.assertGreaterEqual(totals["scans"], 1)
        self.assertGreaterEqual(totals["revenue_ntd"], 100)
        self.assertIn("recent_purchases", response.data)
        self.assertIn("recent_scans", response.data)


class UsersEndpointTests(APITestCase):
    def setUp(self):
        self.admin = _make_user("admin", staff=True)
        self.client.force_authenticate(self.admin)
        self.alice = _make_user("alice")
        self.bob = _make_user("bob")

    def test_list_users_search_by_email(self):
        response = self.client.get(reverse("admin-users"), {"q": "alice"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [u["username"] for u in response.data["users"]]
        self.assertIn("alice", usernames)
        self.assertNotIn("bob", usernames)

    def test_user_detail_includes_wallet_and_transactions(self):
        response = self.client.get(
            reverse("admin-user-detail", args=[self.alice.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")
        self.assertEqual(response.data["wallet"]["balance"], 200)
        # signal 發放的月贈點交易
        self.assertEqual(len(response.data["recent_transactions"]), 1)

    def test_adjust_coin_adds_and_records_admin_actor(self):
        response = self.client.post(
            reverse("admin-adjust-coin", args=[self.alice.id]),
            {"delta": 500, "note": "退費 #scan1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["wallet_balance"], 700)
        # 確認交易紀錄 admin_actor 為當前 admin
        tx = CoinTransaction.objects.filter(
            wallet__user=self.alice,
            kind=CoinTransaction.Kind.ADMIN_ADJUST,
        ).get()
        self.assertEqual(tx.admin_actor, self.admin)
        self.assertEqual(tx.note, "退費 #scan1")

    def test_adjust_coin_negative_clamped_to_zero(self):
        response = self.client.post(
            reverse("admin-adjust-coin", args=[self.alice.id]),
            {"delta": -500},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 原 200，扣 -500 → 餘額夾到 0
        self.assertEqual(response.data["wallet_balance"], 0)

    def test_adjust_coin_zero_rejected(self):
        response = self.client.post(
            reverse("admin-adjust-coin", args=[self.alice.id]),
            {"delta": 0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TransactionsEndpointTests(APITestCase):
    def setUp(self):
        self.admin = _make_user("admin", staff=True)
        self.client.force_authenticate(self.admin)
        self.user = _make_user("buyer")
        from apps.billing.models import PricingPlan
        purchase_plan(self.user, PricingPlan.objects.get(code="standard"))

    def test_list_all_transactions(self):
        response = self.client.get(reverse("admin-transactions"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kinds = {t["kind"] for t in response.data["transactions"]}
        self.assertIn(CoinTransaction.Kind.PURCHASE, kinds)

    def test_filter_by_kind(self):
        response = self.client.get(
            reverse("admin-transactions"),
            {"kind": CoinTransaction.Kind.PURCHASE},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kinds = {t["kind"] for t in response.data["transactions"]}
        self.assertEqual(kinds, {CoinTransaction.Kind.PURCHASE})


class ReviewsEndpointTests(APITestCase):
    def setUp(self):
        self.admin = _make_user("admin", staff=True)
        self.client.force_authenticate(self.admin)
        self.user = _make_user("reviewer")
        self.review = PlatformReview.objects.create(
            user=self.user, rating=4, comment="不錯",
        )

    def test_list_reviews_marks_pending(self):
        response = self.client.get(reverse("admin-reviews"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_count"], 1)
        self.assertTrue(response.data["reviews"][0]["is_pending"])

    def test_reply_writes_admin_replied_at_and_by(self):
        response = self.client.post(
            reverse("admin-reply-review", args=[self.review.id]),
            {"reply": "謝謝你的回饋！"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.admin_reply, "謝謝你的回饋！")
        self.assertIsNotNone(self.review.admin_replied_at)
        self.assertEqual(self.review.admin_replied_by, self.admin)

    def test_clear_reply_resets_metadata(self):
        # 先回覆，再清空，確認 admin_replied_at/by 一併清除
        self.review.admin_reply = "舊回覆"
        self.review.save()
        response = self.client.post(
            reverse("admin-reply-review", args=[self.review.id]),
            {"reply": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.admin_reply, "")
        self.assertIsNone(self.review.admin_replied_at)
        self.assertIsNone(self.review.admin_replied_by)


@override_settings(ARGUS_AUTO_QUEUE_SCANS=False)
class ScansEndpointTests(APITestCase):
    def setUp(self):
        self.admin = _make_user("admin", staff=True)
        self.client.force_authenticate(self.admin)
        self.user = _make_user("scanner")
        self.scan = _make_scan(self.user, origin="https://abc.com")

    def test_list_scans_returns_username_and_counts(self):
        response = self.client.get(reverse("admin-scans"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["scans"][0]
        self.assertEqual(item["username"], "scanner")
        self.assertEqual(item["origin"], "https://abc.com")
        self.assertIn("findings_count", item)

    def test_list_scans_search_by_origin(self):
        _make_scan(self.user, origin="https://xyz.com")
        response = self.client.get(reverse("admin-scans"), {"q": "xyz"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        origins = [s["origin"] for s in response.data["scans"]]
        self.assertEqual(origins, ["https://xyz.com"])

    def test_scan_detail_returns_warning_summary(self):
        self.scan.warning_summary = {"blocked_urls": ["x"]}
        self.scan.save()
        response = self.client.get(
            reverse("admin-scan-detail", args=[self.scan.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["warning_summary"]["blocked_urls"], ["x"])


class MeEndpointTests(APITestCase):
    def test_me_returns_is_staff_flag(self):
        admin = _make_user("admin", staff=True)
        self.client.force_authenticate(admin)
        response = self.client.get(reverse("admin-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_staff"])

    def test_me_works_for_normal_user(self):
        normal = _make_user("normal")
        self.client.force_authenticate(normal)
        response = self.client.get(reverse("admin-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_staff"])
