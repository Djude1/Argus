import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import permissions, status, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.billing.services import grant_monthly_bonus_if_needed


class GoogleLoginView(views.APIView):
    """以 Google ID Token 完成登入或註冊（一般使用者唯一的登入方式）。

    首次成功驗證的 Google 帳號會自動建立對應的 User（username=email）。
    管理員仍透過 Django Admin（/admin/）以 username/password 登入，
    本端點不簽發 superuser/staff 權限。
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get("credential")
        if not credential:
            return Response(
                {"credential": "缺少 Google ID Token。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        if not client_id:
            return Response(
                {"config": "伺服器尚未設定 GOOGLE_OAUTH_CLIENT_ID，無法驗證 Google 登入。"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            info = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                client_id,
            )
        except ValueError:
            return Response(
                {"credential": "Google ID Token 無效或已過期。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = info.get("email")
        if not email or not info.get("email_verified"):
            return Response(
                {"credential": "Google 帳號 email 未驗證，無法登入。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": (info.get("given_name") or "")[:150],
                "last_name": (info.get("family_name") or "")[:150],
            },
        )
        # 每次登入：更新最後登入時間 + 本月若未領則自動補發 200 coin
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        grant_monthly_bonus_if_needed(user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )


# ============================================================
# DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING
# 用途：Google Cloud Console 的 Authorized JavaScript origins 設定還沒生效時，
#       讓開發者用 bootstrap superuser 直接拿到 JWT 進入系統。
# 安全：只在 DEBUG=True 時生效；DEBUG=False 時回 404，等同不存在。
# 移除：刪除本 class、accounts/urls.py 的 dev-login path、tests.py 的 DevLoginTests、
#       App.jsx 的「跳過 Google 登入」按鈕區塊。
# ============================================================
class DevLoginView(views.APIView):
    """以 bootstrap superuser 直接簽發 JWT（僅限 DEBUG 模式）。"""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(
                {"detail": "Dev login 僅在 DEBUG=True 時開放，目前已停用。"},
                status=status.HTTP_404_NOT_FOUND,
            )

        username = (
            request.data.get("username")
            or os.environ.get("ARGUS_BOOTSTRAP_SUPERUSER_USERNAME")
            or ""
        ).strip()
        if not username:
            return Response(
                {"detail": "未提供 username 且未設定 ARGUS_BOOTSTRAP_SUPERUSER_USERNAME。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if not user:
            return Response(
                {"detail": f"找不到使用者 {username}。"},
                status=status.HTTP_404_NOT_FOUND,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )
