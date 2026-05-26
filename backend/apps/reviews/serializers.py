from rest_framework import serializers

from apps.reviews.models import PlatformReview, ReviewMessage


class ReviewMessageSerializer(serializers.ModelSerializer):
    author_username = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ReviewMessage
        fields = [
            "id", "body", "image", "image_url",
            "is_admin", "author_username", "created_at",
        ]
        read_only_fields = [
            "id", "image_url", "is_admin", "author_username", "created_at",
        ]
        extra_kwargs = {
            "image": {"write_only": True, "required": False, "allow_null": True},
            "body": {"required": False, "allow_blank": True},
        }

    def get_author_username(self, obj: ReviewMessage) -> str:
        if not obj.author_id:
            return "(已刪除)"
        u = obj.author
        full = f"{u.first_name} {u.last_name}".strip()
        return full or u.username

    def get_image_url(self, obj: ReviewMessage):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def validate(self, attrs):
        if not attrs.get("body") and not attrs.get("image"):
            raise serializers.ValidationError("必須至少填寫留言或附上圖片。")
        return attrs


class PlatformReviewSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    messages = ReviewMessageSerializer(many=True, read_only=True)

    class Meta:
        model = PlatformReview
        fields = [
            "id",
            "rating",
            "comment",
            "user_display",
            "is_mine",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "user_display", "is_mine", "messages", "created_at", "updated_at",
        ]

    def get_user_display(self, obj: PlatformReview) -> str:
        u = obj.user
        full = f"{u.first_name} {u.last_name}".strip()
        if full:
            return full
        local = (u.email or u.username or "").split("@", 1)[0]
        return local[:32] or "匿名"

    def get_is_mine(self, obj: PlatformReview) -> bool:
        request = self.context.get("request")
        return bool(
            request and request.user.is_authenticated and obj.user_id == request.user.id
        )

    def validate_rating(self, value: int) -> int:
        if not 1 <= value <= 5:
            raise serializers.ValidationError("rating 必須在 1-5 之間。")
        return value
