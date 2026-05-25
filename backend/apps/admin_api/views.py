"""Argus React 後台用的 API。

所有 endpoint 都要求 `IsAdminUser`（is_staff=True），與 Django Admin 權限一致。
端點故意設計成扁平的，避免暴露技術細節（AgentSession/Page/Finding 等）。
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.admin_api.serializers import (
    AdjustCoinSerializer,
    AdminCoinTransactionSerializer,
    AdminReplyReviewSerializer,
    AdminReviewSerializer,
    AdminScanJobSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
)
from apps.billing.models import CoinTransaction, CoinWallet
from apps.billing.services import admin_adjust
from apps.reviews.models import PlatformReview
from apps.scans.models import ScanJob

PAGE_SIZE = 25


def _paginate(request, queryset):
    """簡單 offset/limit 分頁；回傳 (items_slice, page, total_pages, total_count)。"""
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        page = 1
    total = queryset.count()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    return queryset[start:start + PAGE_SIZE], page, total_pages, total


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def overview(request):
    """後台首頁概覽：核心統計 + 最新活動。"""
    user_model = get_user_model()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = user_model.objects.count()
    total_wallets = CoinWallet.objects.count()
    total_balance = CoinWallet.objects.aggregate(s=Sum("balance"))["s"] or 0
    total_revenue = CoinWallet.objects.aggregate(s=Sum("total_purchased_ntd"))["s"] or 0
    total_scans = ScanJob.objects.count()
    scans_this_month = ScanJob.objects.filter(created_at__gte=month_start).count()
    pending_reviews = PlatformReview.objects.filter(admin_reply="").count()
    total_reviews = PlatformReview.objects.count()
    avg_rating = None
    if total_reviews:
        agg = PlatformReview.objects.aggregate(s=Sum("rating"))
        avg_rating = round(agg["s"] / total_reviews, 2)

    recent_purchases = (
        CoinTransaction.objects
        .filter(kind=CoinTransaction.Kind.PURCHASE)
        .select_related("wallet__user", "plan")
        .order_by("-created_at")[:5]
    )
    recent_scans = (
        ScanJob.objects.select_related("user").order_by("-created_at")[:5]
        .annotate(findings_count=Count("findings"), pages_count=Count("pages"))
    )

    return Response({
        "totals": {
            "users": total_users,
            "wallets": total_wallets,
            "coin_balance_total": total_balance,
            "revenue_ntd": total_revenue,
            "scans": total_scans,
            "scans_this_month": scans_this_month,
            "reviews": total_reviews,
            "reviews_pending": pending_reviews,
            "avg_rating": avg_rating,
        },
        "recent_purchases": AdminCoinTransactionSerializer(
            recent_purchases, many=True,
        ).data,
        "recent_scans": AdminScanJobSerializer(recent_scans, many=True).data,
    })


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def users_list(request):
    user_model = get_user_model()
    qs = user_model.objects.select_related("coin_wallet").order_by("-date_joined")
    search = (request.query_params.get("q") or "").strip()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    items, page, total_pages, total = _paginate(request, qs)
    return Response({
        "users": AdminUserListSerializer(items, many=True).data,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def user_detail(request, user_id: int):
    user_model = get_user_model()
    user = get_object_or_404(
        user_model.objects.select_related("coin_wallet"), pk=user_id,
    )
    return Response(AdminUserDetailSerializer(user).data)


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def adjust_coin(request, user_id: int):
    """管理員手動加減 coin（含退費）。delta 可正可負；超扣會夾到 0。"""
    user_model = get_user_model()
    target = get_object_or_404(user_model, pk=user_id)
    serializer = AdjustCoinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    tx = admin_adjust(
        target_user=target,
        delta=serializer.validated_data["delta"],
        admin_actor=request.user,
        note=serializer.validated_data.get("note") or "管理員手動調整",
    )
    return Response({
        "transaction": AdminCoinTransactionSerializer(tx).data,
        "wallet_balance": tx.balance_after,
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def transactions_list(request):
    qs = CoinTransaction.objects.select_related(
        "wallet__user", "scan_job", "plan", "admin_actor",
    ).order_by("-created_at")
    kind = request.query_params.get("kind")
    if kind:
        qs = qs.filter(kind=kind)
    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(wallet__user_id=user_id)
    items, page, total_pages, total = _paginate(request, qs)
    return Response({
        "transactions": AdminCoinTransactionSerializer(items, many=True).data,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def reviews_list(request):
    qs = PlatformReview.objects.select_related(
        "user", "admin_replied_by",
    ).order_by("-created_at")
    only_pending = request.query_params.get("pending") in {"1", "true", "yes"}
    if only_pending:
        qs = qs.filter(admin_reply="")
    items, page, total_pages, total = _paginate(request, qs)
    return Response({
        "reviews": AdminReviewSerializer(items, many=True).data,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "pending_count": PlatformReview.objects.filter(admin_reply="").count(),
    })


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def reply_review(request, review_id: int):
    review = get_object_or_404(PlatformReview, pk=review_id)
    serializer = AdminReplyReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    new_reply = serializer.validated_data["reply"].strip()
    review.admin_reply = new_reply
    if new_reply:
        review.admin_replied_at = timezone.now()
        review.admin_replied_by = request.user
    else:
        # 清空回覆時，把時間與回覆者也清空，避免畫面顯示空回覆但有時間
        review.admin_replied_at = None
        review.admin_replied_by = None
    review.save(update_fields=[
        "admin_reply", "admin_replied_at", "admin_replied_by", "updated_at",
    ])
    return Response(AdminReviewSerializer(review).data)


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def scans_list(request):
    qs = (
        ScanJob.objects.select_related("user")
        .annotate(
            findings_count=Count("findings", distinct=True),
            pages_count=Count("pages", distinct=True),
        )
        .order_by("-created_at")
    )
    search = (request.query_params.get("q") or "").strip()
    if search:
        qs = qs.filter(
            Q(origin__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
        )
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    items, page, total_pages, total = _paginate(request, qs)
    return Response({
        "scans": AdminScanJobSerializer(items, many=True).data,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def scan_detail(request, scan_id: int):
    scan = get_object_or_404(
        ScanJob.objects.select_related("user").annotate(
            findings_count=Count("findings", distinct=True),
            pages_count=Count("pages", distinct=True),
        ),
        pk=scan_id,
    )
    return Response({
        "scan": AdminScanJobSerializer(scan).data,
        "warning_summary": scan.warning_summary,
        "top_actions": scan.top_actions,
        "category_scores": scan.category_scores,
        "error_message": scan.error_message,
    })


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """前端用來判斷「我是不是 admin」以決定是否顯示 /admin 入口。"""
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    })
