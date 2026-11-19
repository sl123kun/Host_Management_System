from django.db import models

class Host(models.Model):
    """
    主机模型
    """

    STATUS_CHOICES = [
        ("online", "在线"),
        ("offline", "离线"),
        ("unknown", "未知"),
    ]

    # 主机名称
    hostname = models.CharField(
        max_length=100,
        verbose_name="主机名称"
    )

    # 主机 IP
    ip = models.GenericIPAddressField(
        unique=True,
        verbose_name="IP 地址"
    )

    # SSH 端口
    port = models.PositiveIntegerField(
        default=22,
        verbose_name="SSH 端口"
    )

    # 所属机房
    idc = models.ForeignKey(
        "idc.IDC",
        on_delete=models.PROTECT,
        related_name="hosts",
        verbose_name="所属机房"
    )

    # 主机状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unknown",
        verbose_name="主机状态"
    )

    # 创建时间
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    # 更新时间
    updated_time = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = "host"
        verbose_name = "主机"
        verbose_name_plural = "主机"

    def __str__(self):
        return self.hostname


class HostCredential(models.Model):
    """
    主机登录凭据模型
    """
    # 主键 ID
    id = models.BigAutoField(primary_key=True)

    # 关联主机
    host = models.ForeignKey(
        "host.Host",
        on_delete=models.CASCADE,
        related_name="credentials"
    )

    # SSH 登录用户名
    username = models.CharField(max_length=100)

    # 加密后的密码
    encrypted_password = models.TextField()

    # 凭据备注
    description = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    # 创建时间
    created_time = models.DateTimeField(auto_now_add=True)

    # 更新时间
    updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "host_credential"

        # 同一台主机的用户名不能重复
        unique_together = ("host", "username")

        verbose_name = "主机凭据"
        verbose_name_plural = "主机凭据"

    def __str__(self):
        return f"{self.host.hostname} - {self.username}"

class HostCheckLog(models.Model):
    """
    主机巡检记录
    """

    STATUS_CHOICES = [
        ("online", "在线"),
        ("offline", "离线"),
        ("error", "检测异常"),
    ]

    # 关联被检测的主机
    host = models.ForeignKey(
        Host,
        on_delete=models.CASCADE,
        related_name="check_logs"
    )

    # 本次检测时的 IP 地址
    ip = models.GenericIPAddressField()

    # 本次检测结果
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES
    )

    # 检测时间
    checked_time = models.DateTimeField(auto_now_add=True)

    # 检测说明
    message = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    class Meta:
        db_table = "host_check_log"
        ordering = ["-checked_time"]

    def __str__(self):
        return f"{self.host.hostname} - {self.status}"


class HostPasswordRotationLog(models.Model):
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name="password_rotations")
    username = models.CharField(max_length=100, default="root")
    encrypted_password = models.TextField()
    rotated_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "host_password_rotation_log"
        ordering = ["-rotated_time"]


class HostCountStatistic(models.Model):
    statistic_date = models.DateField()
    city = models.ForeignKey("city.City", on_delete=models.PROTECT, related_name="host_statistics")
    idc = models.ForeignKey("idc.IDC", on_delete=models.PROTECT, related_name="host_statistics")
    host_count = models.PositiveIntegerField()
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "host_count_statistic"
        constraints = [models.UniqueConstraint(fields=["statistic_date", "idc"], name="uniq_daily_idc_host_count")]
        ordering = ["-statistic_date", "city_id", "idc_id"]
