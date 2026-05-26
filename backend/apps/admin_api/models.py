from django.conf import settings
from django.db import models


class AdminAuditLog(models.Model):
    """管理員敏感操作的審計紀錄（only superuser 可查）。

    寫入時機：admin_adjust（補/扣 coin）、reply_review、其他敏感變更。
    寫入透過 `log_admin_action()` helper 集中處理。
    """

    class Action(models.TextChoices):
        COIN_ADJUST = "coin_adjust", "調整點數"
        REVIEW_REPLY = "review_reply", "回覆評論"
        REVIEW_DELETE = "review_delete", "刪除評論"
        USER_TOGGLE_STAFF = "user_toggle_staff", "切換管理員身份"
        OTHER = "other", "其他"

    admin_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_audit_logs",
    )
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs_received",
    )
    target_object_repr = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["admin_actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        actor = self.admin_actor.username if self.admin_actor_id else "(已刪除)"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {actor} {self.get_action_display()}"


def log_admin_action(*, admin_actor, action: str, target_user=None,
                     target_repr: str = "", payload: dict | None = None):
    """寫一筆 admin 操作 audit log。失敗只記 print（不擋業務）。"""
    try:
        return AdminAuditLog.objects.create(
            admin_actor=admin_actor,
            action=action,
            target_user=target_user,
            target_object_repr=target_repr[:255],
            payload=payload or {},
        )
    except Exception:  # noqa: BLE001 — audit 失敗不該阻擋業務操作
        return None
