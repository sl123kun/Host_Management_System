from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from rest_framework.exceptions import ValidationError
from .models import Host, HostCheckLog, HostCredential
from .serializers import HostSerializer, HostCheckLogSerializer, HostCredentialSerializer
from .services import ping_host


class HostViewSet(ModelViewSet):
    queryset = Host.objects.select_related("idc", "idc__city")
    serializer_class = HostSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"], url_path="ping")
    def ping(self, request, pk=None):
        host = self.get_object()
        try:
            reachable = ping_host(host.ip)
        except OSError as exc:
            HostCheckLog.objects.create(
                host=host, ip=host.ip,
                status="error", message=str(exc)[:255],
            )
            return Response({"message": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        host.status = "online" if reachable else "offline"
        host.save(update_fields=["status", "updated_time"])
        HostCheckLog.objects.create(
            host=host, ip=host.ip,
            status=host.status,
        )
        return Response({"hostname": host.hostname, "ip": host.ip,
                         "status": host.status, "reachable": reachable})


class HostCheckLogViewSet(ReadOnlyModelViewSet):
    """只读查询巡检日志，支持 ?host=<id> 按主机过滤。"""
    queryset = HostCheckLog.objects.select_related("host")
    serializer_class = HostCheckLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        host_id = self.request.query_params.get("host")
        if not host_id:
            return queryset
        try:
            return queryset.filter(host_id=int(host_id))
        except ValueError as exc:
            raise ValidationError({"host": "主机 ID 必须是整数"}) from exc


class HostCredentialViewSet(ModelViewSet):
    queryset = HostCredential.objects.select_related("host")
    serializer_class = HostCredentialSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        host_id = self.request.query_params.get("host")
        if not host_id:
            return queryset
        try:
            return queryset.filter(host_id=int(host_id))
        except ValueError as exc:
            raise ValidationError({"host": "主机 ID 必须是整数"}) from exc
