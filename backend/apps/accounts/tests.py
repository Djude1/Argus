from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


@override_settings(GOOGLE_OAUTH_CLIENT_ID="fake-client-id")
class GoogleLoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("google-login")

    @patch("apps.accounts.views.id_token.verify_oauth2_token")
    def test_google_login_creates_new_user(self, mock_verify):
        mock_verify.return_value = {
            "email": "new@example.com",
            "email_verified": True,
            "given_name": "New",
            "family_name": "User",
        }

        response = self.client.post(self.url, {"credential": "fake-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = get_user_model().objects.get(username="new@example.com")
        self.assertEqual(user.email, "new@example.com")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    @patch("apps.accounts.views.id_token.verify_oauth2_token")
    def test_google_login_reuses_existing_user(self, mock_verify):
        get_user_model().objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
        )
        mock_verify.return_value = {
            "email": "existing@example.com",
            "email_verified": True,
        }

        response = self.client.post(self.url, {"credential": "fake-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            get_user_model().objects.filter(username="existing@example.com").count(),
            1,
        )

    @patch("apps.accounts.views.id_token.verify_oauth2_token")
    def test_google_login_rejects_unverified_email(self, mock_verify):
        mock_verify.return_value = {
            "email": "unverified@example.com",
            "email_verified": False,
        }

        response = self.client.post(self.url, {"credential": "fake-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            get_user_model().objects.filter(username="unverified@example.com").exists()
        )

    @patch("apps.accounts.views.id_token.verify_oauth2_token")
    def test_google_login_rejects_invalid_token(self, mock_verify):
        mock_verify.side_effect = ValueError("Token expired")

        response = self.client.post(self.url, {"credential": "bad-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_google_login_requires_credential(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GoogleLoginConfigTests(APITestCase):
    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_returns_503_when_client_id_missing(self):
        response = self.client.post(
            reverse("google-login"),
            {"credential": "any"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING
class DevLoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("dev-login")
        self.user = get_user_model().objects.create_user(
            username="dev-user",
            email="dev@example.com",
            password="ignored-by-dev-login",
        )

    @override_settings(DEBUG=True)
    def test_dev_login_returns_jwt_in_debug_mode(self):
        response = self.client.post(self.url, {"username": "dev-user"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    @override_settings(DEBUG=False)
    def test_dev_login_disabled_when_debug_is_false(self):
        response = self.client.post(self.url, {"username": "dev-user"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=True)
    def test_dev_login_rejects_nonexistent_user(self):
        response = self.client.post(self.url, {"username": "does-not-exist"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=True)
    def test_dev_login_falls_back_to_bootstrap_username_from_env(self):
        # 未傳 username 時讀環境變數，常見情境是前端直接 POST 空 body
        with self.settings():
            import os as _os

            _os.environ["ARGUS_BOOTSTRAP_SUPERUSER_USERNAME"] = "dev-user"
            try:
                response = self.client.post(self.url, {}, format="json")
            finally:
                _os.environ.pop("ARGUS_BOOTSTRAP_SUPERUSER_USERNAME", None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
