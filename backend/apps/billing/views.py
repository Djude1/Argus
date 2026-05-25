from rest_framework import permissions, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing.models import PricingPlan
from apps.billing.serializers import (
    CoinWalletSerializer,
    PricingPlanSerializer,
    PurchaseRequestSerializer,
)
from apps.billing.services import get_or_create_wallet, purchase_plan


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def my_wallet(request):
    """取得目前使用者的錢包餘額、累計資料與最近 20 筆交易。"""
    wallet = get_or_create_wallet(request.user)
    return Response(CoinWalletSerializer(wallet).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_plans(request):
    """列出所有啟用中的購點方案。"""
    plans = PricingPlan.objects.filter(is_active=True).order_by("sort_order", "price_ntd")
    return Response({"plans": PricingPlanSerializer(plans, many=True).data})


class PurchaseView(views.APIView):
    """模擬付款：選定方案後直接加 coin 到錢包並回傳更新後的 wallet。"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PurchaseRequestSerializer(data=request.data, context={})
        serializer.is_valid(raise_exception=True)
        plan = serializer.context["plan"]
        purchase_plan(request.user, plan)
        wallet = get_or_create_wallet(request.user)
        return Response(
            CoinWalletSerializer(wallet).data,
            status=status.HTTP_201_CREATED,
        )
