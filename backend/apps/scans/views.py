from collections import Counter, defaultdict
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Count
from django.http import FileResponse, Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.scans.models import (
    AuthorizationConsent,
    Finding,
    Page,
    ScanJob,
    UserScanQuota,
)
from apps.scans.reports import build_scan_report
from apps.scans.serializers import (
    FindingSerializer,
    PageSerializer,
    ScanJobCreateSerializer,
    ScanJobSerializer,
    ScanJobStatusSerializer,
)
from apps.scans.services import get_client_ip
from apps.scans.tasks import run_scan_job


class ScanJobViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return (
            ScanJob.objects.filter(user=self.request.user)
            .annotate(
                findings_count=Count("findings", distinct=True),
                pages_count=Count("pages", distinct=True),
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ScanJobCreateSerializer
        if self.action == "status":
            return ScanJobStatusSerializer
        return ScanJobSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["client_ip"] = get_client_ip(self.request)
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scan_job = serializer.save()
        if settings.ARGUS_AUTO_QUEUE_SCANS:
            run_scan_job.delay(scan_job.id)
        output_serializer = ScanJobSerializer(scan_job, context=self.get_serializer_context())
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        scan_job = self.get_object()
        serializer = self.get_serializer(scan_job)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path=r"pages/(?P<page_id>[^/.]+)/screenshot")
    def screenshot(self, request, pk=None, page_id=None):
        scan_job = self.get_object()
        page = Page.objects.filter(scan_job=scan_job, id=page_id).first()
        if not page or not page.screenshot_path:
            raise Http404("找不到頁面截圖。")
        screenshot_path = Path(settings.BASE_DIR) / page.screenshot_path
        if not screenshot_path.exists():
            raise Http404("截圖檔案不存在。")
        return FileResponse(screenshot_path.open("rb"), content_type="image/png")

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        scan_job = self.get_object()
        report_path = Path(build_scan_report(scan_job))
        return FileResponse(
            report_path.open("rb"),
            as_attachment=True,
            filename=report_path.name,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


class PageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PageSerializer

    def get_queryset(self):
        queryset = Page.objects.filter(scan_job__user=self.request.user).order_by("depth", "url")
        scan_id = self.request.query_params.get("scan_id")
        if scan_id:
            queryset = queryset.filter(scan_job_id=scan_id)
        return queryset


class FindingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = FindingSerializer

    def get_queryset(self):
        queryset = Finding.objects.filter(scan_job__user=self.request.user).order_by(
            "-priority_score",
            "severity",
            "category",
        )
        scan_id = self.request.query_params.get("scan_id")
        if scan_id:
            queryset = queryset.filter(scan_job_id=scan_id)
        return queryset


# ============================================================
# Aggregate endpoints：Dashboard / History / Audit / Categories
# 從 ScanJob / Finding / AuthorizationConsent / UserScanQuota 聚合，不需新 model
# ============================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Dashboard 總覽：累計掃描、平均分、各類別平均、最近 5 次、本月配額。"""
    user = request.user
    scans = ScanJob.objects.filter(user=user)
    completed_scans = scans.filter(status=ScanJob.Status.COMPLETED)

    total_scans = scans.count()
    completed_count = completed_scans.count()
    failed_count = scans.filter(status=ScanJob.Status.FAILED).count()

    avg_score = completed_scans.aggregate(v=Avg("overall_score"))["v"]

    # 各類別平均分（從 ScanJob.category_scores JSONField aggregate）
    category_totals = defaultdict(lambda: {"sum": 0.0, "count": 0})
    for cs in completed_scans.values_list("category_scores", flat=True):
        if not isinstance(cs, dict):
            continue
        for cat, score in cs.items():
            if isinstance(score, (int, float)):
                category_totals[cat]["sum"] += score
                category_totals[cat]["count"] += 1
    category_avg = {
        cat: round(data["sum"] / data["count"], 1)
        for cat, data in category_totals.items()
        if data["count"]
    }

    recent = [
        {
            "id": s.id,
            "origin": s.origin,
            "status": s.status,
            "overall_score": s.overall_score,
            "completed_at": s.completed_at,
            "created_at": s.created_at,
        }
        for s in scans.order_by("-created_at")[:5]
    ]

    quota, _ = UserScanQuota.objects.get_or_create(user=user)
    quota_used = quota.consumed_this_month()

    severity_count = (
        Finding.objects.filter(scan_job__user=user)
        .values("severity")
        .annotate(c=Count("id"))
    )
    severity_totals = {row["severity"]: row["c"] for row in severity_count}

    return Response(
        {
            "total_scans": total_scans,
            "completed_scans": completed_count,
            "failed_scans": failed_count,
            "average_score": round(avg_score, 1) if avg_score is not None else None,
            "category_averages": category_avg,
            "severity_totals": severity_totals,
            "recent_scans": recent,
            "quota": {
                "monthly_limit": quota.monthly_limit,
                "used_this_month": quota_used,
                "remaining": max(quota.monthly_limit - quota_used, 0),
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def origin_history(request):
    """同網址歷史：每個 origin 的歷次 ScanJob 與分數。"""
    user = request.user
    scans = ScanJob.objects.filter(user=user).order_by("origin", "-created_at")

    grouped = defaultdict(list)
    for s in scans:
        grouped[s.origin].append(
            {
                "id": s.id,
                "status": s.status,
                "overall_score": s.overall_score,
                "category_scores": s.category_scores,
                "created_at": s.created_at,
                "completed_at": s.completed_at,
            }
        )

    items = []
    for origin, entries in grouped.items():
        completed_entries = [e for e in entries if e["overall_score"] is not None]
        latest_score = completed_entries[0]["overall_score"] if completed_entries else None
        previous_score = (
            completed_entries[1]["overall_score"] if len(completed_entries) > 1 else None
        )
        delta = (
            latest_score - previous_score
            if (latest_score is not None and previous_score is not None)
            else None
        )
        items.append(
            {
                "origin": origin,
                "total_scans": len(entries),
                "latest_score": latest_score,
                "previous_score": previous_score,
                "delta": delta,
                "scans": entries,
            }
        )

    items.sort(key=lambda x: (x["scans"][0]["created_at"]), reverse=True)
    return Response({"origins": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log(request):
    """使用者活動時間軸：從 ScanJob.created_at / completed_at 與 AuthorizationConsent 推導。"""
    user = request.user
    events = []

    for s in ScanJob.objects.filter(user=user).order_by("-created_at")[:100]:
        events.append(
            {
                "type": "scan_created",
                "timestamp": s.created_at,
                "scan_id": s.id,
                "origin": s.origin,
                "message": f"建立掃描 {s.origin}（模式 {s.scan_mode}）",
            }
        )
        if s.completed_at and s.status == ScanJob.Status.COMPLETED:
            events.append(
                {
                    "type": "scan_completed",
                    "timestamp": s.completed_at,
                    "scan_id": s.id,
                    "origin": s.origin,
                    "message": f"完成掃描 {s.origin}，分數 {s.overall_score}",
                }
            )
        elif s.completed_at and s.status == ScanJob.Status.FAILED:
            events.append(
                {
                    "type": "scan_failed",
                    "timestamp": s.completed_at,
                    "scan_id": s.id,
                    "origin": s.origin,
                    "message": f"掃描失敗 {s.origin}：{s.error_message[:120]}",
                }
            )

    for c in AuthorizationConsent.objects.filter(user=user).order_by("-created_at")[:100]:
        events.append(
            {
                "type": "authorization",
                "timestamp": c.created_at,
                "scan_id": c.scan_job_id,
                "origin": c.authorized_domain,
                "message": f"確認對 {c.authorized_domain} 的掃描授權（IP {c.ip_address}）",
            }
        )

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return Response({"events": events[:100]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def findings_by_category(request):
    """跨所有掃描，按類別聚合 findings。
    回傳每個 category 下的「同標題 finding 出現次數」，方便看共通問題。
    """
    user = request.user
    findings = (
        Finding.objects.filter(scan_job__user=user)
        .values("category", "severity", "title")
    )

    grouped = defaultdict(lambda: Counter())
    severity_by_title = defaultdict(dict)
    for row in findings:
        cat = row["category"]
        title = row["title"]
        grouped[cat][title] += 1
        severity_by_title[cat][title] = row["severity"]

    result = {}
    for cat, counter in grouped.items():
        items = [
            {"title": title, "count": cnt, "severity": severity_by_title[cat][title]}
            for title, cnt in counter.most_common()
        ]
        result[cat] = {"total_findings": sum(counter.values()), "items": items}

    return Response({"categories": result})
