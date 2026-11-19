from rest_framework import serializers
from .models import City

class CitySerializer(serializers.ModelSerializer):
    """
    城市序列化器
    """

    class Meta:
        model = City

        fields = [
            "id",
            "name",
            "code",
            "created_time",
            "updated_time",
        ]

        read_only_fields = [
            "id",
            "created_time",
            "updated_time",
        ]
