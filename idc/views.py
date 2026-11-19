from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from .models import IDC
from .serializers import IDCSerializer

class IDCViewSet(ModelViewSet):

    queryset = IDC.objects.select_related("city").all()

    serializer_class = IDCSerializer

    permission_classes = [AllowAny]
