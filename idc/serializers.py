from rest_framework import serializers
from .models import IDC

class IDCSerializer(serializers.ModelSerializer):
    """
    机房序列化器
    """

    class Meta:
        model = IDC

        fields = [
            "id",
            "name",
            "address",
            "city",
            "created_time",
            "updated_time",
        ]

        read_only_fields = [
            "id",
            "created_time",
            "updated_time",
        ]
