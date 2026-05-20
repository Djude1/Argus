from rest_framework.routers import DefaultRouter

from apps.scans.views import FindingViewSet, PageViewSet, ScanJobViewSet

router = DefaultRouter()
router.register("scans", ScanJobViewSet, basename="scan")
router.register("pages", PageViewSet, basename="page")
router.register("findings", FindingViewSet, basename="finding")

urlpatterns = router.urls

