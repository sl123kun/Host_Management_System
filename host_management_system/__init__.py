import pymysql

# 让 Django 使用 PyMySQL 连接 MySQL
pymysql.install_as_MySQLdb()

# 加载 Celery 应用
from .celery import app as celery_app

__all__ = ("celery_app",)


