# 主机管理系统

基于 Django + DRF + Celery 的后端项目，面向企业内部主机资产管理场景。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

生成 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把输出填到 `.env` 的 `FERNET_KEY`，并配置好 MySQL / Redis 连接信息。

### 3. 数据库迁移

确保 MySQL 已启动：

```bash
python manage.py migrate
```

### 4. 启动三个进程

```bash
# 终端 1：Django Web
python manage.py runserver

# 终端 2：Celery Worker（Windows 需 -P solo）
celery -A host_management_system worker -l info -P solo

# 终端 3：Celery Beat 调度器
celery -A host_management_system beat -l info
```

服务启动后访问 `http://127.0.0.1:8000/api/` 即可调用所有接口，`http://127.0.0.1:8000/admin/` 进入管理后台。
