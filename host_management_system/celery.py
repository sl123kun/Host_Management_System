import os
from celery import Celery

# 指定 Django 配置文件
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "host_management_system.settings")

# 创建 Celery 实例
app = Celery("host_management_system")

# 从 Django settings.py 读取 CELERY_ 开头的配置
app.config_from_object("django.conf:settings", namespace="CELERY")

# 自动发现各个 Django App 中的 tasks.py
app.autodiscover_tasks()
