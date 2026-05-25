from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.reviews.models import PlatformReview
from apps.reviews.serializers import PlatformReviewSerializer


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def list_reviews(request):
    """所有平台評論（公開）。未登入也可看；is_mine 在未登入時固定為 false。"""
    qs = PlatformReview.objects.select_related("user").order_by("-created_at")
    serializer = PlatformReviewSerializer(qs, many=True, context={"request": request})
    return Response({"reviews": serializer.data})


@api_view(["GET", "POST", "PUT"])
@permission_classes([permissions.IsAuthenticated])
def my_review(request):
    """取得 / 建立 / 更新「我」對平台的評論（一人一則）。

    GET：回傳自己的評論（沒有則 404）。
    POST 或 PUT：upsert（已存在則更新，不重新建立）。
    """
    if request.method == "GET":
        review = PlatformReview.objects.filter(user=request.user).first()
        if not review:
            return Response({"detail": "尚未撰寫評論。"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlatformReviewSerializer(review, context={"request": request}).data)

    # upsert
    serializer = PlatformReviewSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    review, created = PlatformReview.objects.update_or_create(
        user=request.user,
        defaults={
            "rating": serializer.validated_data["rating"],
            "comment": serializer.validated_data.get("comment", ""),
        },
    )
    out = PlatformReviewSerializer(review, context={"request": request})
    return Response(
        out.data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
