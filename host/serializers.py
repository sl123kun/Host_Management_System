from rest_framework import serializers
from .models import Host, HostCredential
from .encryption import encrypt_password
from .models import HostCheckLog

class HostSerializer(serializers.ModelSerializer):
    """
    主机序列化器
    """

    class Meta:
        model = Host

        fields = [
            "id",
            "hostname",
            "ip",
            "port",
            "idc",
            "status",
            "created_time",
            "updated_time",
        ]

        read_only_fields = [
            "id",
            "created_time",
            "updated_time",
        ]

class HostCredentialSerializer(serializers.ModelSerializer):
    # 接收前端提交的明文密码，但不允许在响应中返回
    password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False
    )

    class Meta:
        model = HostCredential

        fields = [
            "id",
            "host",
            "username",
            "password",
            "description",
            "created_time",
            "updated_time",
        ]

        read_only_fields = [
            "id",
            "created_time",
            "updated_time",
        ]

    def create(self, validated_data):
        """
        创建：
        1. 获取明文密码
        2. 加密密码
        3. 保存加密后的密码
        """

        password = validated_data.pop("password")

        encrypted_password = encrypt_password(password)

        credential = HostCredential.objects.create(
            encrypted_password=encrypted_password,
            **validated_data
        )

        return credential

    def update(self, instance, validated_data):
        """
        修改：
        如果提交了新密码，就重新加密。
        如果没有提交密码，则保留原来的密文。
        """

        password = validated_data.pop("password", None)

        if password is not None:
            instance.encrypted_password = encrypt_password(password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance

class HostCheckLogSerializer(serializers.ModelSerializer):

    class Meta:
        model = HostCheckLog
        fields = [
            "id",
            "host",
            "ip",
            "status",
            "checked_time",
            "message",
        ]
        read_only_fields = fields
