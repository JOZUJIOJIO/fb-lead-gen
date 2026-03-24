# LeadFlow AI — 智能外贸获客平台

Facebook-to-WhatsApp AI Lead Generation Platform for B2B Sales.

通过 Facebook 自动化搜索潜在客户，AI 分析画像并进行多轮对话，最终推送到 WhatsApp 完成获客转化。

> **第一次安装？** 请看 **[完整安装指南 (SETUP-GUIDE.md)](SETUP-GUIDE.md)** — 保姆级教程，非技术人员也能看懂。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Celery |
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 数据库 | PostgreSQL 16 + Redis 7 |
| AI | Kimi (Moonshot) / Anthropic Claude |
| 浏览器自动化 | **OpenCLI**（优先，复用 Chrome 登录态）/ Playwright（备选） |
| 部署 | Docker Compose（一键启动） |

## 快速开始（一键部署）

### 前提条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（唯一必需）
- Node.js 18+（用于 OpenCLI 浏览器代理）
- Python 3.10+（用于 MCP Server）

### 第一步：启动 Web 应用（Docker 一键搞定）

```bash
# 克隆仓库（含 OpenCLI 子模块）
git clone --recurse-submodules https://github.com/JOZUJIOJIO/fb-lead-gen.git
cd fb-lead-gen

# 配置 API Key
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 KIMI_API_KEY（必填）

# 一键启动全部服务
docker compose up -d
```

启动后访问：
- 网页界面: http://localhost:3000
- API 文档: http://localhost:8000/docs
- 账号: `admin@leadflow.com` / `admin123456`

### 第二步：安装浏览器代理（本机运行）

```bash
bash install-agent.sh
```

这个脚本自动安装：
1. OpenCLI CLI 工具
2. MCP Server Python 依赖
3. 人设配置文件

安装后还需要手动在 Chrome 中加载 Browser Bridge 扩展：
1. 打开 Chrome → `chrome://extensions/`
2. 开启「开发者模式」
3. 「加载已解压的扩展程序」→ 选择 `opencli-vendor/extension/` 目录

验证：`opencli doctor`

### 日常使用

```bash
docker compose up -d      # 启动 Web 应用
docker compose down        # 停止
docker compose logs -f     # 查看日志
```

## 架构说明

```
Docker 容器（docker compose up -d）:
├── frontend    (Next.js)     → localhost:3000
├── backend     (FastAPI)     → localhost:8000
├── celery      (异步任务)
├── postgres    (数据库)      → localhost:5432
└── redis       (缓存/队列)   → localhost:6379

本机运行（操控真实浏览器）:
└── OpenCLI Browser Agent
    ├── Chrome 扩展 (Browser Bridge)
    ├── 本地 daemon (localhost:19825)
    └── 你已登录 Facebook 的 Chrome ← 关键！
```

浏览器代理**必须在本机运行**，因为它需要操控你真实的 Chrome 浏览器（已登录 Facebook）。如果放在 Docker 里，Facebook 会检测到是自动化环境。

## 浏览器自动化方案

系统自动选择最优方案：

| | OpenCLI（推荐） | Playwright（备选） |
|--|-----------------|-------------------|
| 原理 | 控制你已打开的 Chrome | 启动独立的 Chromium |
| Facebook 登录 | 复用已登录状态 | 需要重新登录 |
| 被检测风险 | 低 | 高 |
| 需要 | Chrome + 扩展 | Playwright + Chromium |

## 项目结构

```
fb-lead-gen/
├── backend/                      # FastAPI 后端（Docker）
│   ├── app/
│   │   ├── main.py               # 入口 + 自动建表 + 账号 seed
│   │   ├── models.py             # SQLAlchemy 数据模型
│   │   ├── routers/              # API 路由
│   │   ├── services/             # 业务逻辑
│   │   └── tasks/                # Celery 异步任务
│   ├── .env.example              # 环境变量模板
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                     # Next.js 前端（Docker）
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── mcp-server/                   # MCP 集成层（本机运行）
│   ├── server.py                 # FastMCP 服务
│   ├── browser_agent_opencli.py  # OpenCLI 浏览器自动化（优先）
│   ├── browser_agent.py          # Playwright 浏览器自动化（备选）
│   ├── conversation_engine.py    # 多轮对话引擎
│   └── auto_poller.py            # 自动回复轮询
├── opencli-vendor/               # OpenCLI 源码（git submodule）
├── docker-compose.yml            # Docker 编排（一键启动）
├── install-agent.sh              # 浏览器代理安装脚本
├── setup.sh                      # 传统部署脚本（非 Docker）
└── start.sh                      # 传统启动脚本（非 Docker）
```

## 环境变量

编辑 `backend/.env`：

| 变量 | 必填 | 说明 |
|------|------|------|
| `SECRET_KEY` | 是 | JWT 签名密钥（随机字符串） |
| `AI_PROVIDER` | 是 | `kimi` 或 `anthropic` |
| `KIMI_API_KEY` | 是* | Kimi API 密钥 |
| `ANTHROPIC_API_KEY` | 否 | Claude API 密钥 |
| `WHATSAPP_BUSINESS_TOKEN` | 否 | WhatsApp Business API Token |
| `WHATSAPP_PHONE_NUMBER_ID` | 否 | WhatsApp 手机号 ID |

> *至少需要配置一个 AI Provider 的 API Key。
> DATABASE_URL 和 REDIS_URL 在 Docker 模式下会自动覆盖，无需修改。

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3000 | Next.js |
| 后端 | 8000 | FastAPI (含 Swagger: /docs) |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存 + 任务队列 |
| OpenCLI daemon | 19825 | 浏览器控制（本机） |

## License

MIT
