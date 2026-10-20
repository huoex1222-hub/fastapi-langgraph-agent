# 本地启动手册：DeepSeek + SiliconFlow + 现有 Docker

适用环境：当前这台 Windows 机器（Docker Desktop 已运行，已有 pgvector / Langfuse 容器）。

目标：**不执行 `make docker-up`**，复用现有 Docker 里的 PostgreSQL 和 Langfuse，应用本体用 `uv` 在本机运行。

---

## 0. 最短启动路径（TL;DR）

如果数据库和 `.env.development` 已经准备好，只需要：

```bash
cd /d/stu/github/fastapi-langgraph-agent

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

然后打开 <http://127.0.0.1:8000/docs>。

下面的步骤是完整的从零操作说明。

---

## 1. 环境检查

在 Git Bash 中执行：

```bash
docker version
docker compose version
python --version
uv --version
```

本项目要求：

| 组件 | 要求 |
|---|---|
| Python | 3.13+ |
| uv | 已安装 |
| Docker | 正在运行 |
| 应用端口 | 8000 空闲 |

检查端口占用：

```bash
netstat -ano | grep -E ':(8000|5432|5433|6379|3000|9090|8080)\s'
```

当前机器上的实际情况：

| 端口 | 占用者 | 是否复用 |
|---|---|---|
| 5432 | dify Postgres | 不复用 |
| 6379 | dify Redis | 不复用 |
| 3000 | 本地 Langfuse Web | **复用** |
| 9090 | Langfuse MinIO | 不直接使用 |
| 8080 | Dify Weaviate | 不复用 |
| 5433 | `fastapi_langgraph_template-postgres-1`（pgvector） | **复用** |
| 8000 | 本项目 FastAPI | 使用 |

> 注意：正因如此，**不要直接执行 `make docker-up`**，它会把 db 映射到 5432、valkey 映射到 6379，和现有容器冲突。

---

## 2. 准备 PostgreSQL（复用现有 pgvector 容器）

### 2.1 确认容器在运行

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -i pgvector
```

应看到类似：

```text
fastapi_langgraph_template-postgres-1   pgvector/pgvector:pg18   Up ...   0.0.0.0:5433->5432/tcp
```

如果容器存在但没运行：

```bash
docker start fastapi_langgraph_template-postgres-1
```

### 2.2 创建本项目数据库

数据库名用 `fastapi_agent`，和现有 `agent_server` 隔离：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -c "CREATE DATABASE fastapi_agent;"
```

如果提示数据库已存在，说明之前已经创建过，可以跳过。

### 2.3 启用 pgvector 扩展

mem0 的长期记忆依赖 pgvector，**必须在迁移前启用**：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

验证：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent -Atc "select extname, extversion from pg_extension;"
```

应包含：

```text
plpgsql|1.0
vector|0.8.7
```

> 该容器的本地开发账号是 `postgres` / `postgres`，端口映射到宿主机 **5433**。

---

## 3. 准备 `.env.development`

### 3.1 如果文件不存在

```bash
cd /d/stu/github/fastapi-langgraph-agent
cp .env.example .env.development
```

> `.env.development` 已被 `.gitignore` 忽略，**不要提交**。

### 3.2 完整配置模板

把 `.env.development` 改成下面这样。尖括号部分换成你自己的值：

```env
# 应用
APP_ENV=development
PROJECT_NAME="Web Assistant"
VERSION=1.0.0
DEBUG=true
API_V1_STR=/api/v1
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8000"

# Langfuse（本地实例，可选）
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_PUBLIC_KEY="<本地 Langfuse public key>"
LANGFUSE_SECRET_KEY="<本地 Langfuse secret key>"
LANGFUSE_HOST=http://localhost:3000

# 主模型：DeepSeek（OpenAI 兼容协议）
OPENAI_API_KEY="<你的 DeepSeek key>"
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODELS=deepseek-chat,deepseek-reasoner
DEFAULT_LLM_MODEL=deepseek-chat
SESSION_NAMING_MODEL=deepseek-chat
DEFAULT_LLM_TEMPERATURE=0.2
SESSION_NAMING_ENABLED=true
MAX_TOKENS=2000
MAX_LLM_CALL_RETRIES=3
LLM_TOTAL_TIMEOUT=120

# JWT
JWT_SECRET_KEY="<用下面的命令生成>"
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_DAYS=30

# 数据库：复用宿主机 5433 上的 pgvector 容器
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=fastapi_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_POOL_SIZE=5
POSTGRES_MAX_OVERFLOW=10

# 缓存：留空使用进程内内存缓存；现有 Redis 在 6380，但非必需
VALKEY_HOST=
VALKEY_PORT=6380
CACHE_TTL_SECONDS=60

# 长期记忆：DeepSeek 做事实抽取，硅基流动做 embedding
LONG_TERM_MEMORY_MODEL=deepseek-chat
LONG_TERM_MEMORY_LLM_BASE_URL=https://api.deepseek.com/v1
LONG_TERM_MEMORY_LLM_API_KEY="<你的 DeepSeek key>"
LONG_TERM_MEMORY_EMBEDDER_PROVIDER=openai_compatible
LONG_TERM_MEMORY_EMBEDDER_MODEL=BAAI/bge-m3
LONG_TERM_MEMORY_EMBEDDER_BASE_URL=https://api.siliconflow.cn/v1
LONG_TERM_MEMORY_EMBEDDER_API_KEY="<你的 SiliconFlow key>"
LONG_TERM_MEMORY_EMBEDDER_DIMS=1024
LONG_TERM_MEMORY_COLLECTION_NAME=longterm_memory

# 限流
RATE_LIMIT_DEFAULT="1000 per day,200 per hour"
RATE_LIMIT_CHAT="100 per minute"
RATE_LIMIT_CHAT_STREAM="100 per minute"
RATE_LIMIT_MESSAGES="200 per minute"
RATE_LIMIT_LOGIN="100 per minute"

# 日志
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

生成 JWT secret：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3.3 本地 Langfuse key

如果要用本机已有的 Langfuse（<http://localhost:3000>）：

```bash
docker inspect langfuse-langfuse-web-1 \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep LANGFUSE_INIT_PROJECT
```

把得到的 `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` 和 `LANGFUSE_INIT_PROJECT_SECRET_KEY` 分别填入 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`。

如果暂时不需要 tracing：

```env
LANGFUSE_TRACING_ENABLED=false
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_SECRET_KEY=""
```

启动时会输出 `langfuse_tracing_disabled`，不会再因为 `auth_check()` 崩溃。

### 3.4 关于模型名

- `deepseek-chat`：默认模型，支持工具调用、function-calling 结构化输出。
- `deepseek-reasoner`：作为失败兜底。
- 当前 DeepSeek 的 `/v1/models` 实际列出 `deepseek-flash` / `deepseek-v4-pro`，但 `deepseek-chat` / `deepseek-reasoner` 仍可作为兼容名使用。
- `SESSION_NAMING_MODEL` 必须使用 `deepseek-chat` 这类非 thinking 模型：thinking 模式不支持强制 `tool_choice`，会导致会话命名失败。
- 硅基 embedding 用 `BAAI/bge-m3`，输出 **1024 维**，所以 `LONG_TERM_MEMORY_EMBEDDER_DIMS=1024`。

---

## 4. 安装依赖

```bash
cd /d/stu/github/fastapi-langgraph-agent
uv sync
```

说明：

- `uv sync` 会创建 `.venv/` 并安装 `pyproject.toml` 里的依赖。
- 不需要执行 `make install`；它额外安装 pre-commit，启动项目不是必需。
- 首次安装会下载较多依赖，耗时几分钟。

---

## 5. 初始化数据库

### 5.1 全新数据库

```bash
cd /d/stu/github/fastapi-langgraph-agent
uv run alembic upgrade head
```

初始迁移会创建：

- `user`
- `session`
- `thread`
- `alembic_version`

验证：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent -c "\dt"
```

### 5.2 已有数据库（当前机器的情况）

如果 `fastapi_agent` 之前已经初始化过，可以只做一致性检查：

```bash
uv run alembic check
```

期望输出：

```text
No new upgrade operations detected.
```

> `alembic check` 可能打印 `SAWarning: Did not recognize type 'vector'`，这是 mem0 的 pgvector 表引起的无害警告，不影响结果。

### 5.3 迁移失败时

旧版本的初始迁移在全新库上会报：

```text
relation "session" does not exist
```

当前仓库已经修复为真正建表；如果你切回了旧代码，请更新到包含修复的版本，或临时用下面的方式建表并标记迁移：

```bash
uv run python -c "
from sqlmodel import SQLModel
from app.models.user import User
from app.models.session import Session
from app.models.thread import Thread
from app.services.database import database_service
SQLModel.metadata.create_all(database_service.engine)
"
uv run alembic stamp head
```

---

## 6. 启动应用

推荐直接在前台运行，方便看日志：

```bash
cd /d/stu/github/fastapi-langgraph-agent
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

或者：

```bash
make dev
```

两者等价，`make dev` 会先加载 `.env.development`，再执行带 `--reload` 的 uvicorn。

### 为什么 Windows 下必须带 `--reload`

Windows 默认事件循环是 `ProactorEventLoop`，而 psycopg 的异步连接不支持它，会报：

```text
Psycopg cannot use the 'ProactorEventLoop' to run in async mode
```

uvicorn 只有在 `--reload` / 多 worker 的子进程模式下才会切换到 `WindowsSelectorEventLoopPolicy`。所以本机启动**不要省略 `--reload`**。

### 正常启动日志

看到以下内容说明启动成功：

```text
llm_service_initialized        default_model=deepseek-chat total_models=2
langfuse_auth_success          # 或 langfuse_tracing_disabled
application_startup
graph_pre_warmed
memory_service_initialized
```

首次启动时，LangGraph 和 mem0 还会自动创建：

- `checkpoints`
- `checkpoint_blobs`
- `checkpoint_writes`
- `checkpoint_migrations`
- `longterm_memory`（1024 维）
- `mem0migrations`

这些表不由 Alembic 管理。

### VS Code 启动 + mitmweb 抓包

仓库里提供了本机用的 VS Code 配置：

| 文件 | 作用 |
|---|---|
| `.vscode/launch.json` | 3 个启动配置：普通热重载、热重载 + mitmweb、断点调试 + mitmweb |
| `.vscode/tasks.json` | `proxy: mitmweb`、后端启动、`db: migrate`、并行启动任务 |
| `scripts/run_dev.py` | 无 `--reload` 时安装 Windows SelectorEventLoop，保证断点调试可用 |

`.vscode/launch.json` 和 `.vscode/tasks.json` 已加入 `.gitignore`，属于本机配置，不会误提交。

#### 前置条件

```bash
mitmdump --version      # 当前机器已安装 mitmproxy 12.x
ls "$USERPROFILE/.mitmproxy/mitmproxy-ca-cert.pem"
```

如果 CA 文件不存在，先启动一次 mitmweb，它会自动生成。

#### 启动步骤

> 如果 8000 端口已有手动启动的服务，先在原终端 `Ctrl+C`，避免端口冲突。

1. 用 VS Code 打开项目目录。
2. `Ctrl+Shift+P` → **Python: Select Interpreter**，选择：

   ```text
   .venv/Scripts/python.exe
   ```

3. 先启动代理。`Ctrl+Shift+P` → **Tasks: Run Task** → **proxy: mitmweb**。
   也可以直接按 `Ctrl+Shift+B` 运行默认任务 **dev: proxy + backend (mitm)**，它会并行启动代理和后端。

4. 代理启动后：

   - 代理监听：`127.0.0.1:8082`
   - Web UI：<http://127.0.0.1:8081>
   - 登录密码：`agent`

5. 打开 **Run and Debug**，选择启动配置：

   | 配置 | 用途 |
   |---|---|
   | `Server (hot reload)` | 普通热重载，不走代理 |
   | `Server (hot reload, via mitmweb)` | 热重载，LLM 请求走 mitmweb |
   | `Server (debug breakpoints, via mitmweb)` | 无 reload，断点可用，LLM 请求走 mitmweb |

6. 按 `F5` 启动，然后在 mitmweb 里查看发往 `api.deepseek.com` 和 `api.siliconflow.cn` 的请求。

#### 说明

- **必须先启动 mitmweb**，否则应用访问 LLM 会连接失败或证书校验失败。
- `HTTPS_PROXY` 和 `SSL_CERT_FILE` 只写在 launch/task 配置里，不写进 `.env.development`；普通 `make dev` 不受影响。
- `SSL_CERT_FILE` 指向 `%USERPROFILE%/.mitmproxy/mitmproxy-ca-cert.pem`，只信任 mitmproxy 的 CA。
- `NO_PROXY=localhost,127.0.0.1,::1` 保证本地 Langfuse（`:3000`）和数据库流量不经过代理。
- 热重载配置使用 `--reload`，应用运行在子进程中，断点可能不生效；需要断点时用 `Server (debug breakpoints, via mitmweb)`。
- 8080 已被 dify-weaviate 占用，所以代理用 8082、Web UI 用 8081；如需修改，`launch.json` 和 `tasks.json` 里的端口要一起改。

---

## 7. 验证接口

### 7.1 健康检查

```bash
curl http://127.0.0.1:8000/health
```

期望：

```json
{"status":"healthy","components":{"api":"healthy","database":"healthy"}}
```

### 7.2 Swagger

浏览器打开：

- <http://127.0.0.1:8000/docs>
- <http://127.0.0.1:8000/redoc>

### 7.3 注册用户

```bash
USER_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"Secret123!","username":"you"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])")

echo "$USER_TOKEN"
```

如果邮箱已注册，会返回 400；改用 7.4 登录获取 token。

### 7.4 登录（注意是 form 表单）

```bash
USER_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -F 'email=you@example.com' \
  -F 'password=Secret123!' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "$USER_TOKEN"
```

> 登录/注册只返回**用户级 token**（`sub` = user id），不会自动创建聊天会话。
> 聊天接口需要**会话级 token**（`sub` = session id），所以必须单独调用 `POST /auth/session`。
> 一个会话创建一次即可，后续消息复用同一个 `SESSION_TOKEN`，不需要每条消息都新建会话。

### 7.5 创建会话

```bash
SESSION_JSON=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/session \
  -H "Authorization: Bearer $USER_TOKEN")

SESSION_ID=$(echo "$SESSION_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
SESSION_TOKEN=$(echo "$SESSION_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])")

echo "session_id=$SESSION_ID"
echo "session_token=$SESSION_TOKEN"
```

### 7.6 普通聊天

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chatbot/chat \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"你好，用一句话介绍你自己"}]}'
```

### 7.7 流式聊天

```bash
curl -N -X POST http://127.0.0.1:8000/api/v1/chatbot/chat/stream \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"讲一个短笑话"}]}'
```

### 7.8 长期记忆闭环测试

先为同一个用户创建两个会话 A/B：

```bash
SESSION_A=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/session \
  -H "Authorization: Bearer $USER_TOKEN")
SESSION_TOKEN_A=$(echo "$SESSION_A" | python -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])")

SESSION_B=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/session \
  -H "Authorization: Bearer $USER_TOKEN")
SESSION_TOKEN_B=$(echo "$SESSION_B" | python -c "import sys,json; print(json.load(sys.stdin)['token']['access_token'])")
```

第一轮（会话 A）：

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chatbot/chat \
  -H "Authorization: Bearer $SESSION_TOKEN_A" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"我叫 Alice，我喜欢绿茶。请用一句话回复。"}]}'
```

等待约 10 秒，让后台 mem0 写入完成，然后检查：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent \
  -Atc "select payload->>'data' from longterm_memory;"
```

应看到类似：

```text
Likes green tea
Name is Alice
```

再用**同一个用户的新会话 B** 提问：

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chatbot/chat \
  -H "Authorization: Bearer $SESSION_TOKEN_B" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"我喜欢喝什么？用一句话回答。"}]}'
```

应能回答出 "绿茶 / green tea"。

### 7.9 消息历史

```bash
curl -s http://127.0.0.1:8000/api/v1/chatbot/messages \
  -H "Authorization: Bearer $SESSION_TOKEN"
```

---

## 8. 常见问题

### 8.1 端口 8000 被占用

```bash
netstat -ano | grep ':8000\s'
```

找到 PID 后结束进程，或换端口启动：

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### 8.2 数据库连接失败

确认：

- 容器在运行：`docker ps | grep pgvector`
- 端口是 **5433**，不是 5432
- `.env.development` 中 `POSTGRES_HOST=localhost`、`POSTGRES_PORT=5433`
- 数据库 `fastapi_agent` 已创建

### 8.3 `ProactorEventLoop` 错误

启动命令缺少 `--reload`。改用：

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 8.4 DeepSeek 返回 404 `/embeddings`

说明长期记忆的 embedding 还在请求 DeepSeek。检查：

```env
LONG_TERM_MEMORY_EMBEDDER_BASE_URL=https://api.siliconflow.cn/v1
LONG_TERM_MEMORY_EMBEDDER_MODEL=BAAI/bge-m3
LONG_TERM_MEMORY_EMBEDDER_API_KEY="<SiliconFlow key>"
LONG_TERM_MEMORY_EMBEDDER_PROVIDER=openai_compatible
```

### 8.5 硅基返回 `The parameter is invalid`（dimensions）

硅基 embedding API 不接受 `dimensions` 参数。项目已通过 `app/services/embeddings.py` 的 `OpenAICompatibleEmbedding` 省略该参数，并依赖：

```env
LONG_TERM_MEMORY_EMBEDDER_PROVIDER=openai_compatible
LONG_TERM_MEMORY_EMBEDDER_DIMS=1024
```

### 8.6 向量维度不匹配

如果 `longterm_memory` 表之前按 1536 维创建过，而当前 embedding 是 1024 维，会出现维度错误。开发环境可清空记忆表后重启：

```bash
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent \
  -c "DROP TABLE IF EXISTS longterm_memory; DROP TABLE IF EXISTS mem0migrations;"
```

然后重启应用，mem0 会按 1024 维重建。**这会删除已有长期记忆，生产环境不要直接这样做。**

### 8.7 结构化输出报 json_schema 错误

DeepSeek 不支持 `response_format: json_schema`。项目已改为 `method="function_calling"`（见 `app/services/llm/service.py`）。如果看到类似错误，确认代码是修复后的版本。

### 8.8 thinking 模式不支持 tool_choice

`deepseek-reasoner` / `deepseek-flash` 在 thinking 模式下不支持强制 `tool_choice`。会话命名固定使用：

```env
SESSION_NAMING_MODEL=deepseek-chat
```

### 8.9 Langfuse 启动 401

确认 `.env.development` 中的 key 是本地 Langfuse 的 `LANGFUSE_INIT_PROJECT_*` 值。或者直接关闭：

```env
LANGFUSE_TRACING_ENABLED=false
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_SECRET_KEY=""
```

当前代码在关闭 tracing 或 key 无效时不会再阻断启动。

### 8.10 `make docker-up` 端口冲突

当前机器的 5432/6379 已被 dify 占用，完整 stack 还会撞 3000/9090/8080。不要直接执行 `make docker-up`。本手册的启动方式是：

- 数据库和 Langfuse 复用现有 Docker 容器
- FastAPI 用 `uv` 在本机运行

---

## 9. 停止与重启

- 前台运行：`Ctrl+C`
- 后台运行：找到 uvicorn 进程并结束，或使用任务管理器
- 重启：

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

数据位置：

- PostgreSQL：`fastapi_agent` 库，宿主机 5433
- 长期记忆：`longterm_memory` 表（pgvector）
- 应用日志：`logs/`（未跟踪，不要提交）

---

## 10. 本次改动涉及的文件

| 文件 | 作用 |
|---|---|
| `app/core/config.py` | 新增 provider / memory 相关配置项 |
| `app/services/llm/registry.py` | 支持 `OPENAI_BASE_URL` + `LLM_MODELS` 动态模型列表 |
| `app/services/llm/service.py` | 结构化输出改用 function calling |
| `app/services/session_naming.py` | 会话命名模型可配置；兼容服务不传 `reasoning` |
| `app/services/embeddings.py` | 新增兼容 embedder，省略 `dimensions` |
| `app/services/memory.py` | DeepSeek LLM + 硅基 embedding，pgvector 1024 维 |
| `app/core/observability.py` | Langfuse 关闭/无效 key 时不再阻断启动 |
| `alembic/versions/b25d38b0cd7c_initial_schema.py` | 初始迁移真正创建三张表 |
| `.env.example` | 新增 provider 配置示例 |

---

## 11. 快速排障命令

```bash
# 应用健康
curl -s http://127.0.0.1:8000/health

# 数据库表
docker exec fastapi_langgraph_template-postgres-1 \
  psql -U postgres -d fastapi_agent -c "\dt"

# 迁移状态
uv run alembic current
uv run alembic check

# 运行日志
tail -f logs/dev-server.log

# 最近错误
grep -iE 'error|exception|failed' logs/dev-server.log | tail -20
```
