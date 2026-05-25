from rest_framework import serializers

from apps.reviews.models import PlatformReview


class PlatformReviewSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = PlatformReview
        fields = [
            "id",
            "rating",
            "comment",
            "admin_reply",
            "admin_replied_at",
            "user_display",
            "is_mine",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "admin_reply", "admin_replied_at",
            "user_display", "is_mine", "created_at", "updated_at",
        ]

    def get_user_display(self, obj: PlatformReview) -> str:
        # 對外只顯示姓名（first_name + last_name）；若空才顯示截斷的 email 前綴
        u = obj.user
        full_name = (f"{u.first_name} {u.last_name}").strip()
        if full_name:
            return full_name
        local = (u.email or u.username or "").split("@", 1)[0]
        return local[:32] or "匿名"

    def get_is_mine(self, obj: PlatformReview) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.user_id == request.user.id)

    def validate_rating(self, value: int) -> int:
        if not 1 <= value <= 5:
            raise serializers.ValidationError("rating 必須在 1-5 之間。")
        return value
