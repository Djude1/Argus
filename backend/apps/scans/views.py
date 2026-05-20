from pathlib import Path

from django.conf import settings
from django.db.models import Count
from django.http import FileResponse, Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scans.models import Finding, Page, ScanJob
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
