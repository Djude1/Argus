from rest_framework import permissions, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.reviews.models import PlatformReview, ReviewMessage
from apps.reviews.serializers import (
    PlatformReviewSerializer,
    ReviewMessageSerializer,
)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def list_reviews(request):
    """所有平台評論（公開，未登入可看）。"""
    qs = (
        PlatformReview.objects
        .select_related("user")
        .prefetch_related("messages", "messages__author")
        .order_by("-created_at")
    )
    serializer = PlatformReviewSerializer(qs, many=True, context={"request": request})
    return Response({"reviews": serializer.data})


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def my_review(request):
    """我的評論：第一次 POST 建立 rating + 首則 comment；之後一律不可改 rating。"""
    if request.method == "GET":
        review = PlatformReview.objects.filter(user=request.user).first()
        if not review:
            return Response({"detail": "尚未撰寫評論。"}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            PlatformReviewSerializer(review, context={"request": request}).data,
        )

    # POST：只允許「第一次」建立，第二次回 400 引導使用者改走訊息 thread
    existing = PlatformReview.objects.filter(user=request.user).first()
    if existing:
        return Response(
            {"detail": "你已評分過了；如要補充意見請使用留言（messages）。"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PlatformReviewSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    review = PlatformReview.objects.create(
        user=request.user,
        rating=serializer.validated_data["rating"],
        comment=serializer.validated_data.get("comment", ""),
    )
    return Response(
        PlatformReviewSerializer(review, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_message(request, review_id: int):
    """在某則評論下新增訊息（任何登入者皆可，含圖片）。

    若作者是 staff，會自動標記 `is_admin=True`，前端據此區分樣式。
    """
    try:
        review = PlatformReview.objects.get(pk=review_id)
    except PlatformReview.DoesNotExist:
        return Response(
            {"detail": "找不到該評論。"}, status=status.HTTP_404_NOT_FOUND,
        )

    serializer = ReviewMessageSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    message = ReviewMessage.objects.create(
        review=review,
        author=request.user,
        is_admin=request.user.is_staff,
        body=serializer.validated_data.get("body", "").strip(),
        image=serializer.validated_data.get("image"),
    )
    out = ReviewMessageSerializer(message, context={"request": request})
    return Response(out.data, status=status.HTTP_201_CREATED)
