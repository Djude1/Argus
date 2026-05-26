from django.db import models


class ProjectFeature(models.Model):
    """專案介紹頁的特色卡片。"""

    title = models.CharField(max_length=64)
    icon = models.CharField(max_length=16, blank=True, help_text="emoji 或圖示字串")
    description = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.title


class TeamMember(models.Model):
    """團隊頁的成員卡片。"""

    name = models.CharField(max_length=64)
    role = models.CharField(max_length=64, help_text="例如：前端工程師、UX 設計師")
    avatar_emoji = models.CharField(
        max_length=8, blank=True,
        help_text="一個 emoji 當頭像，例如 🧑‍💻、🎨",
    )
    bio = models.TextField(blank=True)
    skills = models.JSONField(
        default=list, blank=True,
        help_text="技能 chip 列表，例如 ['React', 'Django', 'Figma']",
    )
    email = models.EmailField(blank=True)
    github_url = models.URLField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"


class AppRelease(models.Model):
    """APP / PWA 版本資訊（download 頁顯示）。"""

    class Platform(models.TextChoices):
        PWA = "pwa", "PWA（瀏覽器安裝）"
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        DESKTOP = "desktop", "桌面"

    version = models.CharField(max_length=32)
    platform = models.CharField(
        max_length=16, choices=Platform.choices, default=Platform.PWA,
    )
    release_notes = models.TextField(blank=True)
    download_url = models.URLField(
        blank=True,
        help_text="外部下載連結；PWA 留空表示「站內安裝」",
    )
    icon_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    is_latest = models.BooleanField(default=False, help_text="標記為最新版（前台顯示徽章）")
    released_at = models.DateTimeField()

    class Meta:
        ordering = ["-released_at"]

    def __str__(self) -> str:
        return f"{self.platform} v{self.version}"
