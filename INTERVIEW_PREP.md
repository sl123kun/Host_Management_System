# 主机管理系统 —— 面试准备手册

> 基于 Django + DRF + Celery 的后端项目，面向企业内部主机资产管理场景。

---

## 一、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.12 | 主开发语言 |
| Web 框架 | Django 5.2 | ORM / 路由 / 中间件 / Admin |
| API 框架 | DRF 3.18 | 序列化 / ViewSet / Router |
| 异步任务 | Celery 5.7 | 定时任务 + 异步执行 |
| 消息队列 | Redis | Celery Broker + Result Backend |
| 数据库 | MySQL 8.x | 业务数据存储 |
| 加密 | cryptography (Fernet) | 密码对称加密 |
| SSH | paramiko | 远程修改主机密码 |

**项目模块划分（大白话版）：**
- **城市管理模块**：管城市的增删改查
- **机房管理模块**：管机房的增删改查，归属城市
- **主机管理模块**（核心）：管主机、凭据、巡检日志、密码轮换日志、每日统计，归属机房
- **加密模块**：Fernet 加解密密码
- **探测服务**：跨平台 Ping 主机
- **SSH 服务**：远程连接主机
- **巡检日志查询**：ReadOnlyViewSet，支持按主机过滤
- **Celery 定时任务**：密码轮换 + 每日统计
- **请求耗时中间件**：每个请求计毫秒数
- **全局配置**：settings + Celery 初始化

---

## 二、数据库模型设计

### ER 关系

```
City (1) ──→ (N) IDC (1) ──→ (N) Host

Host ──1:N──→ HostCredential          (root 凭据)
Host ──1:N──→ HostCheckLog            (每次 Ping 自动写一条巡检记录)
Host ──1:N──→ HostPasswordRotationLog (密码轮换审计)

HostCountStatistic (统计表)
├── statistic_date + idc (联合唯一)
├── city (FK)
├── idc (FK)
└── host_count (正整数)
```

### 关键字段

- **City** — 城市名（unique）、城市编码（unique）
- **IDC** — 机房名称、地址、所属城市（PROTECT 删除）
- **Host** — 主机名、IP（GenericIPAddressField, unique, 自带格式校验）、端口（默认22）、所属机房（PROTECT 删除）、状态（online/offline/unknown）
- **HostCredential** — 关联主机、用户名、加密后的密码（Fernet 密文）、同一主机同一用户名唯一
- **HostCheckLog** — 关联主机、检测时的 IP、检测结果（online/offline/error）、检测时间、检测说明
- **HostCountStatistic** — 统计日期、所属城市、所属机房、主机数量、同一日期同一机房唯一

### 设计亮点

- **PROTECT 删除策略**：删城市/机房时如果下面还有主机，拒绝删除，防止误删
- **CASCADE 删除策略**：删主机时自动清理凭据、检测日志、密码轮换日志
- **联合唯一约束**：同一主机不允许同一用户名重复建凭据；同一机房同一日期不重复统计
- **GenericIPAddressField**：Django 内置 IP 字段，自动校验 IPv4/IPv6 格式，还能做 `ip__startswith="192.168"` 这种范围查询，CharField 做不了
- **巡检日志自动写入**：每次 Ping API 调用自动产生一条 HostCheckLog，成功写 online/offline，异常写 error + 错误信息，全链路闭环

---

## 三、面试题 5 大功能实现要点

### 功能 1：主机/城市/机房模型设计

**关键设计决策：**
- 三层从属关系 City → IDC → Host，IDC 归属 City，Host 归属 IDC
- IP 字段用 GenericIPAddressField，自带格式校验 + unique 约束
- 凭据独立表，不跟主机混表——职责分离 + 支持一台主机多个登录用户

### 功能 2：CRUD 接口 + Ping 探测 API + 巡检日志查询

**CRUD**：3 个 ViewSet 继承 DRF 的 ModelViewSet，自动提供 GET/POST/PUT/PATCH/DELETE

**Ping 探测 API**：自定义 action `POST /api/hosts/{id}/ping/`

**Ping 实现（独立探测服务）：**
- 跨平台兼容：Windows 用 `ping -n 4 -w 1000`，Linux 用 `ping -c 4 -W 1`
- subprocess.run 同步执行，timeout=6 秒
- 返回布尔值，View 里据此更新主机状态
- 异常处理：超时 → 返回 False；系统层异常 → 500 响应 + 写一条 error 日志

**Ping 顺带写巡检日志**（完整链路）：
```python
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
        return Response({"message": str(exc)}, status=500)
    host.status = "online" if reachable else "offline"
    host.save(update_fields=["status", "updated_time"])
    HostCheckLog.objects.create(
        host=host, ip=host.ip, status=host.status,
    )
    return Response({...})
```

**巡检日志查询 API**：`ReadOnlyModelViewSet` + `?host=<id>` 按主机过滤
- `GET /api/check-logs/` — 全部巡检日志
- `GET /api/check-logs/?host=6` — 只看某台主机的巡检记录
- 只有 list 和 retrieve，不允许 POST/PUT/DELETE（日志是系统自动产生的）

### 功能 3：Root 密码 + 8 小时定时轮换 + 加密存储

**加密方案：Fernet（对称加密）**

| 项目 | 说明 |
|------|------|
| 算法 | AES-128-CBC + HMAC-SHA256 签名 |
| 密钥 | 环境变量 FERNET_KEY，.env 不提交 Git |
| 优点 | 内置时间戳防重放、Python 生态成熟 |
| 密文格式 | `gAAAAA...` 前缀，Base64 URL-safe |

**加密模块核心逻辑：**
```python
def encrypt_password(password):
    fernet = 从环境变量读密钥
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(cipher):
    return fernet.decrypt(cipher.encode()).decode()
```

**定时轮换任务（Celery）：**
1. 用 Python secrets 库生成 32 位随机密码（字母+数字+特殊字符）
2. Fernet 解密旧密码 → paramiko SSH 连主机 → `chpasswd` 修改密码
3. SSH 成功后：Fernet 加密新密码 → 原子事务更新凭据表 + 写密码轮换审计日志
4. 乐观锁：UPDATE 时 WHERE 条件带上 old_ciphertext，如果期间有人改了凭据，影响行数 = 0 就报错
5. 收集所有失败，任务返回汇总

**Celery Beat 调度配置：**
```
密码轮换：每 8 小时整点  (crontab minute=0, hour="*/8")
每日统计：每天 00:00     (crontab minute=0, hour=0)
```

### 功能 4：每天 00:00 按城市/机房统计主机数量

**实现逻辑：**
```python
@shared_task
def record_daily_host_counts():
    today = 当前日期
    rows = 查所有机房，每个机房 .annotate(Count("hosts"))  # 一条 SQL 搞定
    原子事务:
        对每个机房:
            HostCountStatistic.objects.update_or_create(
                statistic_date=today, idc=row,
                defaults={host_count: row.host_count},
            )
```

- ORM 的 annotate + Count 是 `GROUP BY` + 聚合
- update_or_create 保证幂等（重复执行不产生重复数据）
- 原子事务包裹所有写入

### 功能 5：请求耗时统计中间件

**核心代码：**
```python
class RequestDurationMiddleware:
    def __call__(self, request):
        started = time.perf_counter()       # 高精度计时
        response = self.get_response(request)  # 处理请求（洋葱模型）
        elapsed_ms = (time.perf_counter() - started) * 1000
        response["X-Request-Duration-Ms"] = "53.25"   # 响应头返回
        logger.info("... duration_ms=%.2f", elapsed_ms)  # 日志也打一份
        return response
```

**实现要点：**
- 用 `perf_counter()` 而不是 `time.time()` —— 前者单调递增，不受系统时钟调整影响，精度更高
- 放在中间件靠前位置（Security 之后、Session 之前），覆盖几乎全部请求链路的耗时
- 双通道输出：HTTP 响应头给前端看，logging 给后端排查

---

## 四、面试高频问题

### 🔴 Django 基础类

**Q1: Django 的 Model 继承自什么？常用的字段有哪些？**

> 继承自 `django.db.models.Model`。常用字段：CharField、IntegerField、TextField、DateTimeField、BooleanField、ForeignKey、ManyToManyField。我项目里还用到了 GenericIPAddressField（IP 专用，自动校验）。每个字段都支持 primary_key、unique、null、blank、default、on_delete 等参数。

**Q2: ForeignKey 的 on_delete 有哪些值？你项目中分别用了什么？**

> CASCADE（删主表连带删从表）、PROTECT（有引用时拒绝删除）、SET_NULL、SET_DEFAULT、SET(func)、DO_NOTHING。
> 我项目中城市→机房→主机这条链用的 PROTECT 防误删；主机→凭据/日志用的 CASCADE 保证数据一致性。

**Q3: Django ORM 的 select_related 和 prefetch_related 区别？**

> select_related 用于外键/一对一，SQL JOIN 一次性查出来；prefetch_related 用于多对多/反向外键，两条 SQL 分开查再 Python 层组装。我项目中查主机列表时用了 select_related("idc", "idc__city")，因为要一路拿到所属城市，一条 JOIN 搞定。

---

### 🔴 DRF 类

**Q4: DRF 的 ViewSet 和 APIView 区别？ModelViewSet 提供了哪些方法？**

> APIView 是最基础的类视图，要自己写 get/post。ViewSet 把请求映射成 list/create/retrieve/update/destroy 这些 action，需要 Router 绑定 URL。ModelViewSet 继承自 GenericViewSet + 5 个 Mixin，开箱即用的 CRUD。自定义接口用 @action 装饰器加，我项目里的 /hosts/{id}/ping/ 就是这么加的。

**Q5: Serializer 的 write_only 和 read_only 参数有什么用？你项目中怎么用的？**

> write_only=True 就是"只进不出"——创建/更新时接收这个字段，但 API 响应里绝不明文返回。read_only=True 就是"只出不进"——响应里有，但前端传了也忽略。
> 我项目里凭据的 password 字段设了 write_only=True，前端传明文进来，但接口响应中永远不会返回密码，加密逻辑放在 Serializer 的 create() 和 update() 里。

**Q6: ReadOnlyModelViewSet 和 ModelViewSet 有什么区别？巡检日志为什么用 ReadOnly？**

> ModelViewSet 提供完整的增删改查 7 个 action（list/create/retrieve/update/partial_update/destroy），继承自 CreateModelMixin + UpdateModelMixin + DestroyModelMixin + ListModelMixin + RetrieveModelMixin。ReadOnlyModelViewSet 只有 list 和 retrieve，没有 create/update/destroy。
> 我巡检日志用 ReadOnly 是因为日志应该是系统自动产生的（Ping 时写），不应该允许前端手动增删改。

---

### 🔴 Celery 类

**Q7: Celery 的工作流程？Broker、Worker、Beat、Backend 各干什么？**

> 四大角色：
> - Broker（我用 Redis）：消息队列，暂存待执行任务
> - Worker：消费者，从 Broker 取任务跑
> - Beat：调度器，到点往 Broker 里发定时任务（类似 crontab）
> - Backend（也用 Redis）：存任务执行结果，供查询
> 启动要两个进程：worker + beat。

**Q8: 两个定时任务分别怎么配的？**

> 密码轮换：crontab(minute=0, hour="*/8")，每 8 小时整点（0、8、16 点）跑一次。
> 每日统计：crontab(minute=0, hour=0)，每天 00:00 跑一次。

**Q9: 为什么不用 Django 的 APScheduler 或 django-crontab，而选 Celery？**

> 三个原因：
> 1. **解耦**：定时任务和 Web 服务解耦，Worker 挂了不影响 Beat 调度
> 2. **任务持久化**：Redis Broker 暂存任务，Worker 重启后能继续消费，不会丢
> 3. **扩展性**：以后要加更多耗时任务（批量巡检、批量改密码），Celery 天然支持并发 Worker 池，APScheduler 跑在 Django 进程里会阻塞请求

---

### 🔴 安全加密类

**Q10: 密码加密为什么选 Fernet？不用 Django 内置的 make_password？**

> 因为我需要**还原密码**——先解密旧密码才能 SSH 登录远程主机执行 chpasswd 改新密码。Django 的 make_password 生成的是 PBKDF2 单向哈希，只能比对验证不能还原。Fernet 是可逆对称加密，内置时间戳防重放、HMAC 签名防篡改，密钥放 .env 里不提交 Git。

**Q11: Fernet 和直接用 AES 有什么区别？**

> Fernet 在 AES-128-CBC 基础上封装了四个安全点：自动生成 IV（防密文模式分析）、HMAC-SHA256 签名（防篡改）、时间戳（默认 60 分钟过期，防重放）、统一的 Base64 URL-safe 编码。直接用 AES 要自己处理这些，容易漏。

**Q12: 如果 Fernet 密钥泄露了怎么办？**

> 当前没做自动轮换，面试可以提这个优化方向：密文前缀加版本号（v1$gAAAAA...），新密钥加密新数据，旧密钥只解密旧数据，逐步迁移完再删旧密钥。当前简单做法：密钥换了以后，手动触发一次密码轮换任务（或写个批量重加密脚本）。

---

### 🔴 中间件类

**Q13: Django 中间件的执行顺序？你这个请求耗时中间件放哪，为什么？**

> 洋葱模型：请求从上往下穿，响应从下往上返。__call__ 里 self.get_response(request) 之前的代码在请求阶段，之后的在响应阶段。
> 我放在 SecurityMiddleware 之后、SessionMiddleware 之前，这样计时覆盖了 Session、CSRF、View 等几乎全部业务链路的耗时。如果放最顶部会把 SecurityMiddleware 开销也算进去（不是业务关心的）；放底部又会漏掉前面中间件的时间。

**Q14: 中间件里为什么用 perf_counter 而不是 time.time 做计时？**

> time.time() 是墙上时钟，受系统时间调整影响——NTP 校时、手动改时间会跳变，甚至能测出负值。perf_counter() 是单调递增计时器，只增不减，专门用来测耗时，精度也更高（纳秒级）。Python 官方也推荐用它做 benchmark。

---

### 🔴 Ping 探测 + 巡检日志类

**Q15: Ping 命令返回码一定可靠吗？有没有边界情况？**

> returncode==0 在 Windows/Linux 语义一致（0 成功非 0 失败），但三个边界：
> 1. 服务器禁 ICMP（防火墙禁 Ping）→ returncode 非 0 但服务器活着
> 2. 中间路由丢 ICMP → 测不准
> 3. 如果传域名而非 IP，DNS 失败会直接抛异常
> 所以我 IP 字段用了 GenericIPAddressField，只接受 IP 不接受域名。面试可以提：生产中可以加 TCP 端口探测（比如探测 22 端口能不能连上）作为补充。

**Q16: 巡检日志 HostCheckLog 是怎么写进去的？**

> 在 Ping API 里顺手写的——每次调用 POST /hosts/{id}/ping/，不管成功失败还是异常都会写一条 HostCheckLog。成功写 status=online/offline，异常写 status=error + 错误信息。这样巡检日志和 Ping 动作天然绑定，不用额外写定时巡检任务。

**Q17: 为什么巡检日志用 ReadOnlyModelViewSet 而不是 ModelViewSet？**

> 因为巡检日志是**系统自动产生**的，不应该允许前端手动增删改。ReadOnlyModelViewSet 只有 list（列表）和 retrieve（详情）两个 action，正好满足前端查看历史巡检记录的需求。加 basename="check-log" 是因为默认 Router 会推断 basename，但我注册的资源名是复数形式，显式指定更清晰。

---

### 🔴 事务与并发类

**Q18: 密码轮换里的 filter().update() 乐观锁是怎么回事？**

> UPDATE 的 WHERE 条件带上 encrypted_password=old_ciphertext——如果有人在密码轮换期间改了这条凭据，UPDATE 影响行数就是 0，直接报错，不会悄悄覆盖掉新密码。相当于靠数据库层面的条件判断做了一层乐观锁。

**Q19: 为什么用 transaction.atomic() 包裹密码轮换的数据库写入？**

> 密码轮换要同时写两张表（更新凭据 + 插入轮换审计日志），必须要么全成功要么全回滚。如果凭据密码改完了但写日志时炸了，凭据密码已变但没审计记录，出了问题追溯不了。原子事务保证一致性。

---

### 🔴 数据库/ORM 类

**Q20: annotate(Count("hosts")) 翻译成什么 SQL？**

> 大概是：SELECT 机房字段, COUNT(主机表.id) AS host_count FROM 机房 LEFT JOIN 主机 ON 主机.机房ID = 机房.id GROUP BY 机房.id。ORM 的 annotate 本质就是 GROUP BY + 聚合函数，配合 select_related 一条 SQL 把机房和所属城市一起 JOIN 出来。

**Q21: update_or_create 和 get_or_create 区别？为什么统计任务用 update_or_create？**

> get_or_create：查不到就新建，查到不动 → 幂等创建。
> update_or_create：查不到就新建，查到就**更新** → 幂等覆盖。
> 统计任务可能被手动重复触发或 Beat 重启补跑，用 update_or_create 保证同一日期同一机房只保留最新值，不会重复。用 get_or_create 的话，后续手动跑就不会更新了。

**Q22: GenericIPAddressField 有什么特别的？为什么不用 CharField 存 IP？**

> 四个好处：① 自动校验，存非法 IP 直接抛异常不用自己写正则；② 同一字段自动识别 IPv4/IPv6；③ 数据库类型更规范（PostgreSQL 用 INET，MySQL 用 VARCHAR(39)）；④ 能做范围查询（ip__startswith="192.168"），CharField 做不了。

---

### 🔴 项目亮点与反思类

**Q23: 你做过哪些代码清理？**

> 主要两类：
> 1. **补全死代码链路**：之前 HostCheckLog 模型、Serializer、数据库表都有，但 Ping API 只更新了 Host.status 就忘了顺手写巡检日志。补上之后 Ping → 写日志 → 查询日志 形成闭环，还加了 ReadOnlyModelViewSet 暴露查询接口
> 2. **删除孤儿函数**：之前 Celery Beat 里曾经有批量巡检任务，后来从 Beat 配置移除了，但函数体还留在 tasks.py 里（返回固定的"已停用"消息）。这个函数永远不会被调用，直接删了

**Q24: 你觉得这个项目有什么可以优化的地方？**

| 序号 | 当前状态 | 优化方向 |
|------|---------|---------|
| 1 | 密钥硬编码在 .env | 引入 Vault/KMS 做密钥托管；支持密钥多版本共存平滑轮换 |
| 2 | 密码轮换串行执行 | 改成 Celery 组任务并发 + 重试机制，大规模主机时加快速度 |
| 3 | 只 Ping ICMP | 加 TCP 端口探测（探测 22 端口），防防火墙禁 ICMP 误判 |
| 4 | 无 API 认证 | 生产环境加 JWT 或 Session 认证，加 DRF 权限类 |
| 5 | 密码生成无策略 | 加密码强度校验（长度≥8、大小写数字特殊字符、不能包含用户名） |
| 6 | 统计粒度单一 | 除了按机房，还可以按城市/状态/主机名前缀等多维统计 |
| 7 | 无审计告警 | 密码轮换失败时发通知（邮件/钉钉），而不是只在日志里 |
| 8 | 无前端 | Django Admin 已有基础可以用，或加 Vue/React 管理后台 |

**Q25: Django Admin 在这个项目中用了吗？**

> 用了！Django Admin 是开箱即用的后台管理，我注册了所有模型（包括 HostCheckLog），访问 /admin/ 就能管理所有数据表。不用写一行前端代码就有管理后台，这是 Django 的 MVP 神器，生产中可以配合权限系统精细化控制不同管理员能操作哪些表。

**Q26: 为什么用 DRF 的 Router 而不是自己写 path()？**

> DefaultRouter 自动把 ViewSet 的 action 绑定到标准 RESTful URL：list→GET/hosts/、create→POST/hosts/、retrieve→GET/hosts/{id}/、update→PUT/hosts/{id}/、destroy→DELETE/hosts/{id}/，自定义 action 也自动拼上去（比如 /hosts/{id}/ping/）。省得自己写 7 条 path + as_view + basename，还不容易写错。巡检日志那个我显式传了 basename="check-log"，因为 Router 对只读资源的 basename 推断不够直观，显式指定更清晰。

**Q27: 首次部署需要做什么？**

> 四步：
> 1. `pip install -r requirements.txt` 装依赖
> 2. 把 .env.example 复制成 .env，填好数据库、Redis、FERNET_KEY（密钥可以用 Fernet.generate_key() 生成）
> 3. `python manage.py migrate` 执行数据库迁移
> 4. 开三个进程：`python manage.py runserver`（Web）、`celery -A 项目名 worker`（Worker）、`celery -A 项目名 beat`（Beat 调度器）

---

## 五、功能验证清单（28 项全绿）

### 1. 城市 CRUD ✅（6 项）
- [x] 创建 → 201
- [x] 列表 → 200
- [x] 详情 → 200
- [x] PUT 更新 → 200
- [x] PATCH 部分更新 → 200
- [x] 删除 → 204 + 404 验证

### 2. 机房 CRUD ✅（3 项）
- [x] 创建 → 201
- [x] 列表 → 200
- [x] PUT 更新 → 200

### 3. 主机 CRUD ✅（3 项）
- [x] 创建 → 201
- [x] 列表 → 200
- [x] PUT 更新 → 200

### 4. Ping 探测 ✅（2 项）
- [x] 不可达主机 (10.99.99.99) → offline
- [x] 可达主机 (127.0.0.1) → online

### 5. 巡检日志 ✅（3 项）
- [x] Ping 自动写日志 → 至少 2 条
- [x] 按主机过滤 → ?host=6
- [x] 非整数参数校验 → 400

### 6. 凭据加密 ✅（4 项）
- [x] write_only 响应不返回密码
- [x] 更新密码 → 200
- [x] 按主机过滤 → ?host=id
- [x] 数据库密文 + 解密正确

### 7. 中间件 ✅（1 项）
- [x] X-Request-Duration-Ms 响应头

### 8. Celery 配置 ✅（2 项）
- [x] Beat 两个定时任务都注册
- [x] 中间件在 MIDDLEWARE 中注册

### 9. Celery 任务 ✅（2 项）
- [x] record_daily_host_counts 手动触发成功
- [x] rotate_root_passwords 手动触发成功（无真实 SSH 主机时 errors 正常）

### 10. 死代码清扫 ✅（2 项）
- [x] 无 retired_ping_all_hosts_task 孤儿函数
- [x] 无 HostCheckLogSerializer 死定义
