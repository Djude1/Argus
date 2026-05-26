from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PlatformReview(models.Model):
    """使用者對 Argus 平台的評論（一人一則 OneToOne）。

    `rating`：1-5 星。使用者只能在第一次建立時設定；之後想表達補充意見走 `ReviewMessage` thread。
    admin 在回覆時可額外覆寫 `rating`（用 ReviewMessage 的 admin reply endpoint 一次完成）。
    舊版本的 admin_reply / admin_replied_at / admin_replied_by 三欄已拆出為 ReviewMessage。
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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rating", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ★{self.rating}"


class ReviewMessage(models.Model):
    """評論串內的訊息（thread）。

    使用者可發多則，admin 回覆也走這裡，前端依 `is_admin` 區分樣式。
    `image` 可選的問題照片附件，存到 MEDIA_ROOT/review_images/。
    """

    review = models.ForeignKey(
        PlatformReview,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="review_messages",
    )
    is_admin = models.BooleanField(default=False, db_index=True)
    body = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="review_images/", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["review", "created_at"]),
        ]

    def __str__(self) -> str:
        who = self.author.username if self.author_id else "(已刪除)"
        return f"Review#{self.review_id} msg by {who}"
