from django.urls import path

from apps.admin_api import views

urlpatterns = [
    path("me/", views.me, name="admin-me"),
    path("overview/", views.overview, name="admin-overview"),
    path("users/", views.users_list, name="admin-users"),
    path("users/<int:user_id>/", views.user_detail, name="admin-user-detail"),
    path("users/<int:user_id>/adjust-coin/", views.adjust_coin, name="admin-adjust-coin"),
    path("transactions/", views.transactions_list, name="admin-transactions"),
    path("reviews/", views.reviews_list, name="admin-reviews"),
    path("reviews/<int:review_id>/reply/", views.reply_review, name="admin-reply-review"),
    path("scans/", views.scans_list, name="admin-scans"),
    path("scans/<int:scan_id>/", views.scan_detail, name="admin-scan-detail"),
    path("orders/", views.orders_list, name="admin-orders"),
    path("dashboard/", views.dashboard, name="admin-dashboard"),
]
