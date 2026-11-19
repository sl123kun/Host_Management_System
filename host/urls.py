from rest_framework.routers import DefaultRouter
from .views import HostViewSet, HostCheckLogViewSet, HostCredentialViewSet

router = DefaultRouter()

router.register("hosts", HostViewSet)
router.register("credentials", HostCredentialViewSet)
router.register("check-logs", HostCheckLogViewSet, basename="check-log")

urlpatterns = router.urls
