from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from .models import City
from .serializers import CitySerializer

class CityViewSet(ModelViewSet):

    queryset = City.objects.all()

    serializer_class = CitySerializer

    permission_classes = [AllowAny]

