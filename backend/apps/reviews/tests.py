from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.reviews.models import PlatformReview, ReviewMessage


def _make_user(username, **extra):
    defaults = {
        "email": f"{username}@example.com",
        "password": "safe-test-password",
    }
    defaults.update(extra)
    return get_user_model().objects.create_user(username=username, **defaults)


def _png_bytes():
    """產生 1x1 PNG bytes，給 ImageField 測試用。"""
    img = Image.new("RGB", (1, 1), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class PlatformReviewModelTests(APITestCase):
    def test_one_review_per_user(self):
        user = _make_user("alice")
        PlatformReview.objects.create(user=user, rating=5, comment="很棒！")
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

    def test_second_post_rejected_with_400(self):
        """使用者只能評分一次；第二次 POST 回 400，引導改用 messages 補充。"""
        self.client.force_authenticate(self.user)
        self.client.post(
            reverse("reviews-mine"), {"rating": 3, "comment": "還行"}, format="json",
        )
        response = self.client.post(
            reverse("reviews-mine"), {"rating": 5, "comment": "改主意"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # rating 不變
        review = PlatformReview.objects.get(user=self.user)
        self.assertEqual(review.rating, 3)

    def test_rating_must_be_within_range(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("reviews-mine"), {"rating": 10, "comment": "破表"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_review_returns_404_when_not_yet_written(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("reviews-mine"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_reviews_is_public(self):
        carol = _make_user("carol")
        PlatformReview.objects.create(user=carol, rating=4, comment="不錯")
        response = self.client.get(reverse("reviews-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["reviews"]), 1)
        self.assertFalse(response.data["reviews"][0]["is_mine"])

    def test_is_mine_flag_correct_for_logged_in_user(self):
        self.client.force_authenticate(self.user)
        PlatformReview.objects.create(user=self.user, rating=5)
        response = self.client.get(reverse("reviews-list"))
        self.assertTrue(response.data["reviews"][0]["is_mine"])


class ReviewMessageTests(APITestCase):
    def setUp(self):
        self.user = _make_user("eve")
        self.review = PlatformReview.objects.create(user=self.user, rating=4)
        self.client.force_authenticate(self.user)
        self.url = reverse("reviews-create-message", args=[self.review.id])

    def test_user_can_post_multiple_messages(self):
        for i in range(3):
            response = self.client.post(
                self.url, {"body": f"留言 {i}"}, format="multipart",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.review.messages.count(), 3)

    def test_message_requires_body_or_image(self):
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_can_attach_image(self):
        image = SimpleUploadedFile(
            "issue.png", _png_bytes(), content_type="image/png",
        )
        response = self.client.post(
            self.url,
            {"body": "我遇到這個畫面", "image": image},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        msg = ReviewMessage.objects.get()
        self.assertTrue(msg.image.name.startswith("review_images/"))
        self.assertTrue(response.data["image_url"])

    def test_staff_author_marked_is_admin(self):
        admin = _make_user("admin1", is_staff=True)
        self.client.force_authenticate(admin)
        response = self.client.post(
            self.url, {"body": "官方回覆"}, format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_admin"])

    def test_messages_appear_in_review_list(self):
        ReviewMessage.objects.create(
            review=self.review, author=self.user, body="補充", is_admin=False,
        )
        response = self.client.get(reverse("reviews-list"))
        self.assertEqual(len(response.data["reviews"][0]["messages"]), 1)
