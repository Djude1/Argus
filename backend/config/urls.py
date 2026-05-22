from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

FRONTEND_DIST = settings.BASE_DIR.parent / "frontend" / "dist"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.scans.urls")),
    # 由 Django 直接服務 Vite build 出的靜態 assets，讓 runserver 模式不必另開 npm dev
    re_path(
        r"^assets/(?P<path>.*)$",
        serve,
        {"document_root": FRONTEND_DIST / "assets"},
    ),
    # SPA fallback：其他路徑都回傳 index.html，由 React Router 處理
    # （Docker 模式由 nginx 處理 SPA fallback，此路由在容器內為惰性 fallback）
    re_path(
        r"^(?!admin/|api/|static/|media/).*$",
        TemplateView.as_view(template_name="index.html"),
    ),
]
