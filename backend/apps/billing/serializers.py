from rest_framework import serializers

from apps.billing.models import CoinTransaction, CoinWallet, PricingPlan


class PricingPlanSerializer(serializers.ModelSerializer):
    coin_per_ntd = serializers.SerializerMethodField()

    class Meta:
        model = PricingPlan
        fields = [
            "id",
            "code",
            "name",
            "price_ntd",
            "coin_amount",
            "badge",
            "description",
            "sort_order",
            "coin_per_ntd",
        ]

    def get_coin_per_ntd(self, obj: PricingPlan) -> float:
        if obj.price_ntd <= 0:
            return 0.0
        return round(obj.coin_amount / obj.price_ntd, 3)


class CoinTransactionSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    scan_origin = serializers.SerializerMethodField()
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    admin_actor_username = serializers.CharField(
        source="admin_actor.username", read_only=True, default=None,
    )

    class Meta:
        model = CoinTransaction
        fields = [
            "id",
            "amount",
            "kind",
            "kind_label",
            "balance_after",
            "scan_job",
            "scan_origin",
            "plan",
            "plan_name",
            "admin_actor_username",
            "note",
            "created_at",
        ]

    def get_scan_origin(self, obj: CoinTransaction) -> str | None:
        return obj.scan_job.origin if obj.scan_job_id else None


class CoinWalletSerializer(serializers.ModelSerializer):
    recent_transactions = serializers.SerializerMethodField()
    coin_per_page = serializers.SerializerMethodField()

    class Meta:
        model = CoinWallet
        fields = [
            "balance",
            "total_purchased_ntd",
            "total_scans_used",
            "coin_per_page",
            "recent_transactions",
            "updated_at",
        ]

    def get_recent_transactions(self, obj: CoinWallet):
        qs = obj.transactions.all()[:20]
        return CoinTransactionSerializer(qs, many=True).data

    def get_coin_per_page(self, obj):
        from django.conf import settings as dj_settings

        return dj_settings.ARGUS_COIN_PER_PAGE


class PurchaseRequestSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()

    def validate_plan_code(self, value: str) -> str:
        try:
            self.context["plan"] = PricingPlan.objects.get(code=value, is_active=True)
        except PricingPlan.DoesNotExist as exc:
            raise serializers.ValidationError("找不到該方案或方案已停用。") from exc
        return value
