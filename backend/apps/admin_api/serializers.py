from rest_framework import serializers

from apps.billing.models import CoinTransaction, CoinWallet, PurchaseOrder
from apps.reviews.models import PlatformReview
from apps.scans.models import ScanJob


class AdminUserListSerializer(serializers.Serializer):
    """使用者列表精簡欄位（不暴露 password / permissions）。"""

    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
    is_staff = serializers.BooleanField()
    balance = serializers.SerializerMethodField()
    total_purchased_ntd = serializers.SerializerMethodField()
    total_scans_used = serializers.SerializerMethodField()

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_balance(self, obj) -> int:
        w = getattr(obj, "coin_wallet", None)
        return w.balance if w else 0

    def get_total_purchased_ntd(self, obj) -> int:
        w = getattr(obj, "coin_wallet", None)
        return w.total_purchased_ntd if w else 0

    def get_total_scans_used(self, obj) -> int:
        w = getattr(obj, "coin_wallet", None)
        return w.total_scans_used if w else 0


class AdminCoinTransactionSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    scan_origin = serializers.SerializerMethodField()
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    admin_actor_username = serializers.CharField(
        source="admin_actor.username", read_only=True, default=None,
    )

    class Meta:
        model = CoinTransaction
        fields = [
            "id", "amount", "kind", "kind_label", "balance_after",
            "scan_job", "scan_origin", "plan", "plan_name",
            "admin_actor_username", "note", "created_at",
        ]

    def get_scan_origin(self, obj):
        return obj.scan_job.origin if obj.scan_job_id else None


class AdminWalletSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CoinWallet
        fields = [
            "balance", "total_purchased_ntd", "total_scans_used",
            "last_bonus_year", "last_bonus_month",
        ]


class AdminUserDetailSerializer(AdminUserListSerializer):
    """使用者詳情：基本資料 + wallet + 最近 30 筆交易。"""

    wallet = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    is_superuser = serializers.BooleanField()

    def get_wallet(self, obj):
        w = getattr(obj, "coin_wallet", None)
        if not w:
            return None
        return AdminWalletSummarySerializer(w).data

    def get_recent_transactions(self, obj):
        w = getattr(obj, "coin_wallet", None)
        if not w:
            return []
        qs = w.transactions.all()[:30]
        return AdminCoinTransactionSerializer(qs, many=True).data


class AdjustCoinSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
    note = serializers.CharField(max_length=255, allow_blank=True, required=False)

    def validate_delta(self, value: int) -> int:
        if value == 0:
            raise serializers.ValidationError("delta 不可為 0。")
        return value


class AdminReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    admin_replied_by_username = serializers.CharField(
        source="admin_replied_by.username", read_only=True, default=None,
    )
    is_pending = serializers.SerializerMethodField()

    class Meta:
        model = PlatformReview
        fields = [
            "id", "username", "full_name",
            "rating", "comment",
            "admin_reply", "admin_replied_at", "admin_replied_by_username",
            "is_pending", "created_at", "updated_at",
        ]

    def get_full_name(self, obj) -> str:
        u = obj.user
        return f"{u.first_name} {u.last_name}".strip() or u.username

    def get_is_pending(self, obj) -> bool:
        return not bool(obj.admin_reply)


class AdminReplyReviewSerializer(serializers.Serializer):
    reply = serializers.CharField(max_length=2000, allow_blank=True)


class AdminScanJobSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    findings_count = serializers.IntegerField(read_only=True)
    pages_count = serializers.IntegerField(read_only=True)
    duration_sec = serializers.SerializerMethodField()

    class Meta:
        model = ScanJob
        fields = [
            "id", "username", "origin",
            "status", "scan_mode",
            "overall_score", "pages_count", "findings_count",
            "max_pages", "duration_sec",
            "created_at", "completed_at",
        ]

    def get_duration_sec(self, obj) -> int | None:
        if obj.started_at and obj.completed_at:
            return int((obj.completed_at - obj.started_at).total_seconds())
        return None


class AdminPurchaseOrderSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    invoice_type_label = serializers.CharField(
        source="get_invoice_type_display", read_only=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "created_at", "paid_at",
            "username", "plan_name",
            "price_ntd", "coin_amount",
            "buyer_name", "buyer_email",
            "invoice_type", "invoice_type_label",
            "company_name", "tax_id",
            "status", "status_label",
        ]
