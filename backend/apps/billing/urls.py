from django.urls import path

from apps.billing.views import PurchaseView, dev_cheat_coins, list_plans, my_orders, my_wallet

urlpatterns = [
    path("wallet/", my_wallet, name="billing-wallet"),
    path("plans/", list_plans, name="billing-plans"),
    path("purchase/", PurchaseView.as_view(), name="billing-purchase"),
    path("orders/", my_orders, name="billing-orders"),
    # [TEST ONLY] 拿掉前請確認 DEBUG=False 或直接刪除此行
    path("dev-cheat/", dev_cheat_coins, name="billing-dev-cheat"),
]
