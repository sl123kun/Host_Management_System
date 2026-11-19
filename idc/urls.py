from rest_framework.routers import DefaultRouter
from .views import IDCViewSet

router = DefaultRouter()

router.register(
    "idcs",
    IDCViewSet,
    basename="idc"
)

urlpatterns = router.urls