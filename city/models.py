from django.db import models

class City(models.Model):
    """
    城市模型
    用于管理企业主机所在的城市
    """

    # 城市名称
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="城市名称"
    )

    # 城市编码
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="城市编码"
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
        db_table = "city"
        verbose_name = "城市"
        verbose_name_plural = "城市"

    def __str__(self):
        return self.name

