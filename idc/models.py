from django.db import models

class IDC(models.Model):
    """
    机房模型
    一个城市可以有多个机房
    """

    # 机房名称
    name = models.CharField(
        max_length=100,
        verbose_name="机房名称"
    )

    # 机房地址
    address = models.CharField(
        max_length=255,
        verbose_name="机房地址"
    )

    # 所属城市
    city = models.ForeignKey(
        "city.City",
        on_delete=models.PROTECT,
        related_name="idcs",
        verbose_name="所属城市"
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
        db_table = "idc"
        verbose_name = "机房"
        verbose_name_plural = "机房"

    def __str__(self):
        return self.name

