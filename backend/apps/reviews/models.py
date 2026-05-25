from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PlatformReview(models.Model):
    """使用者對整個 Argus 平台的評論（一人一則，可更新）。

    `rating` 為 1-5 星；`comment` 可選；`admin_reply` 與 `admin_replied_at` 由
    管理員在後台填寫，前台公開顯示。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="platform_review",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    admin_reply = models.TextField(blank=True)
    admin_replied_at = models.DateTimeField(null=True, blank=True)
    admin_replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replied_reviews",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rating", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ★{self.rating}"
