from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.reviews.models import PlatformReview


def _stars(rating: int) -> str:
    full = "★" * rating
    empty = "☆" * (5 - rating)
    return full + empty


@admin.register(PlatformReview)
class PlatformReviewAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "rating_display",
        "comment_short",
        "admin_reply_short",
        "created_at",
        "updated_at",
    ]
    list_filter = ["rating", "created_at"]
    search_fields = [
        "user__username",
        "user__email",
        "comment",
        "admin_reply",
    ]
    date_hierarchy = "created_at"
    readonly_fields = [
        "user", "rating", "comment",
        "admin_replied_at", "admin_replied_by",
        "created_at", "updated_at",
    ]
    fields = [
        "user",
        "rating",
        "comment",
        "admin_reply",
        "admin_replied_at",
        "admin_replied_by",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        # 評論一律由使用者建立，admin 只能回覆
        return False

    def has_delete_permission(self, request, obj=None):
        # 允許 superuser 刪除惡意評論
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        """若 admin_reply 有變化，自動標記 admin_replied_at 與 admin_replied_by。"""
        if change and "admin_reply" in form.changed_data:
            obj.admin_replied_at = timezone.now()
            obj.admin_replied_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="星等", ordering="rating")
    def rating_display(self, obj: PlatformReview):
        colour = "#f1c40f"
        return format_html(
            '<span style="color:{};font-size:18px;letter-spacing:2px;">{}</span> '
            '<span style="color:#6c757d;">({})</span>',
            colour, _stars(obj.rating), obj.rating,
        )

    @admin.display(description="評論內容")
    def comment_short(self, obj: PlatformReview) -> str:
        text = (obj.comment or "").replace("\n", " ")
        return text[:80] + ("…" if len(text) > 80 else "")

    @admin.display(description="管理員回覆")
    def admin_reply_short(self, obj: PlatformReview):
        if not obj.admin_reply:
            return format_html('<span style="color:#dc3545;">尚未回覆</span>')
        text = obj.admin_reply.replace("\n", " ")
        snippet = text[:60] + ("…" if len(text) > 60 else "")
        return format_html(
            '<span style="color:#198754;">✓</span> {}',
            snippet,
        )
