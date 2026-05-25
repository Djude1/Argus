from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.reviews.models import PlatformReview


def _make_user(username, **extra):
    defaults = {
        "email": f"{username}@example.com",
        "password": "safe-test-password",
    }
    defaults.update(extra)
    return get_user_model().objects.create_user(username=username, **defaults)


class PlatformReviewModelTests(APITestCase):
    def test_one_review_per_user(self):
        user = _make_user("alice")
        PlatformReview.objects.create(user=user, rating=5, comment="很棒！")
        # OneToOne：再建會 IntegrityError
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlatformReview.objects.create(user=user, rating=4)


class PlatformReviewAPITests(APITestCase):
    def setUp(self):
        self.user = _make_user("bob", first_name="鮑伯", last_name="王")

    def test_create_review_via_post(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("reviews-mine"),
            {"rating": 5, "comment": "Argus 太強了"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        review = PlatformReview.objects.get(user=self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Argus 太強了")

    def test_post_again_updates_existing_review(self):
        self.client.force_authenticate(self.user)
        self.client.post(
            reverse("reviews-mine"),
            {"rating": 3, "comment": "還行"},
            format="json",
        )
        response = self.client.post(
            reverse("reviews-mine"),
            {"rating": 5, "comment": "突然覺得很棒"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PlatformReview.objects.filter(user=self.user).count(), 1)
        review = PlatformReview.objects.get(user=self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "突然覺得很棒")

    def test_rating_must_be_within_range(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("reviews-mine"),
            {"rating": 10, "comment": "破表"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_review_returns_404_when_not_yet_written(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("reviews-mine"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_reviews_is_public(self):
        carol = _make_user("carol")
        PlatformReview.objects.create(user=carol, rating=4, comment="不錯")
        # 不登入也能讀
        response = self.client.get(reverse("reviews-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["reviews"]), 1)
        # is_mine 在未登入時為 False
        self.assertFalse(response.data["reviews"][0]["is_mine"])

    def test_user_display_falls_back_to_email_when_no_name(self):
        dan = _make_user("dan")  # 沒名字
        PlatformReview.objects.create(user=dan, rating=5)
        response = self.client.get(reverse("reviews-list"))
        self.assertEqual(response.data["reviews"][0]["user_display"], "dan")

    def test_is_mine_flag_correct_for_logged_in_user(self):
        self.client.force_authenticate(self.user)
        PlatformReview.objects.create(user=self.user, rating=5)
        response = self.client.get(reverse("reviews-list"))
        self.assertTrue(response.data["reviews"][0]["is_mine"])
