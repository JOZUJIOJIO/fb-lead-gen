# LeadFlow AI — 智能外贸获客平台

Facebook-to-WhatsApp AI Lead Generation Platform for B2B Sales.

通过 Facebook 自动化搜索潜在客户，AI 分析画像并进行多轮对话，最终推送到 WhatsApp 完成获客转化。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Celery |
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 数据库 | PostgreSQL 16 + Redis 7 |
| AI | Kimi (Moonshot) / Anthropic Claude |
| 自动化 | Playwright (Facebook 浏览器自动化) |
| 部署 | Docker Compose |

## 快速开始

### 前提条件

- macOS (已测试)
- Docker Desktop
- Python 3.10+
- Node.js 18+

### 一键部署

```bash
git clone https://github.com/JOZUJIOJIO/fb-lead-gen.git
cd fb-lead-gen
bash setup.sh
```

`setup.sh` 会自动完成：
1. 检查系统依赖 (Homebrew, Python, Node, Docker)
2. 启动 PostgreSQL + Redis (Docker)
3. 安装后端 Python 依赖
4. 创建 `.env` 并自动生成 `SECRET_KEY`
5. 安装前端 Node 依赖
6. 安装 MCP Server + Playwright 浏览器引擎

### 启动服务

```bash
bash start.sh        # 启动所有服务
bash start.sh stop   # 停止所有服务
```

启动后自动打开浏览器访问 http://localhost:3000

### 默认账号

| 项目 | 值 |
|------|------|
| 邮箱 | admin@leadflow.com |
| 密码 | admin123456 |

> 默认账号在首次启动后端时自动创建，可直接登录。

## 项目结构

```
fb-lead-gen/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口 + 自动建表 + 账号 seed
│   │   ├── models.py        # SQLAlchemy 数据模型
│   │   ├── routers/         # API 路由 (auth, leads, campaigns...)
│   │   ├── services/        # 业务逻辑 (AI, WhatsApp, Facebook, CSV)
│   │   └── tasks/           # Celery 异步任务
│   ├── .env.example         # 环境变量模板
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Next.js 前端
│   ├── src/
│   │   ├── app/             # 页面 (仪表盘, 线索, 对话, 营销...)
│   │   ├── components/      # 通用组件
│   │   └── lib/             # API 客户端 + 认证
│   └── package.json
├── mcp-server/              # MCP 集成层
│   ├── server.py            # FastMCP 服务 (OpenClaw 集成)
│   ├── browser_agent.py     # Facebook 浏览器自动化
│   ├── conversation_engine.py  # 多轮对话引擎
│   ├── auto_poller.py       # 自动回复轮询
│   └── persona.example.json # 对话人设模板
├── docker-compose.yml       # Docker 编排
├── setup.sh                 # 一键部署脚本
└── start.sh                 # 一键启动脚本
```

## 环境变量

编辑 `backend/.env`：

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | PostgreSQL 连接串 (setup.sh 自动配置) |
| `REDIS_URL` | 是 | Redis 连接串 (setup.sh 自动配置) |
| `SECRET_KEY` | 是 | JWT 签名密钥 (setup.sh 自动生成) |
| `AI_PROVIDER` | 是 | `kimi` 或 `anthropic` |
| `KIMI_API_KEY` | 是* | Kimi API 密钥 (默认 AI 提供商) |
| `ANTHROPIC_API_KEY` | 否 | Claude API 密钥 (备选) |
| `WHATSAPP_BUSINESS_TOKEN` | 否 | WhatsApp Business API Token |
| `WHATSAPP_PHONE_NUMBER_ID` | 否 | WhatsApp 手机号 ID |
| `FACEBOOK_APP_ID` | 否 | Facebook App ID (Graph API) |
| `FACEBOOK_APP_SECRET` | 否 | Facebook App Secret |
| `FACEBOOK_ACCESS_TOKEN` | 否 | Facebook Access Token |

> *至少需要配置一个 AI Provider 的 API Key。

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3000 | Next.js 开发服务器 |
| 后端 | 8000 | FastAPI (含 Swagger: /docs) |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存 + 任务队列 |

## 日志

```bash
tail -f /tmp/leadflow-backend.log   # 后端
tail -f /tmp/leadflow-celery.log    # Celery Worker
tail -f /tmp/leadflow-frontend.log  # 前端
```

## License

MIT
