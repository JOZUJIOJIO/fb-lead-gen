# LeadFlow AI -- 智能社媒获客工具

AI 驱动的社交媒体线索搜索 + 千人千面个性化私信工具。

## 两步启动

```bash
git clone <repo-url> && cd fb-lead-gen
bash setup.sh
```

引导脚本会交互式地帮你：
1. 检查 Docker 环境
2. 选择 AI 供应商（OpenAI / Claude / Kimi）
3. 填写 API Key
4. 可选配置代理和密码
5. 自动生成配置并启动所有服务

完成后打开 http://localhost:3000 即可使用。

> 也可以跳过脚本直接 `docker compose up -d`，首次打开网页时会有引导页面。

## 功能

- **Facebook 智能搜索** -- 按关键词、地区、行业精准搜索目标主页（更多平台即将支持）
- **AI 个性化消息** -- 分析目标主页内容，生成千人千面的问好消息
- **Web 仪表盘** -- 可视化管理任务、线索和消息发送状态
- **MCP 接入** -- 可选接入 OpenClaw，用自然语言操控获客流程

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 API | FastAPI + SQLAlchemy |
| 前端 | Next.js + TypeScript + Tailwind CSS |
| 浏览器自动化 | Patchright |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| AI | OpenAI / Anthropic / Kimi |
| 容器化 | Docker Compose |

## 项目结构

```
fb-lead-gen/
├── backend/          # FastAPI 后端
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # Next.js 前端仪表盘
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── mcp-server/       # MCP Server (OpenClaw 集成)
│   ├── server.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env.example      # 环境变量模板
└── README.md
```

## 日常使用

```bash
docker compose up -d       # 启动全部服务
docker compose down         # 停止全部服务
docker compose logs -f      # 查看实时日志
docker compose restart backend  # 重启单个服务
```

## 环境变量

复制 `.env.example` 到 `backend/.env`，按需修改:

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_PROVIDER` | 是 | `openai` / `anthropic` / `kimi` |
| `OPENAI_API_KEY` | 否* | OpenAI API Key（也支持兼容 API） |
| `ANTHROPIC_API_KEY` | 否* | Anthropic Claude API Key |
| `KIMI_API_KEY` | 否* | Moonshot Kimi API Key |
| `SEND_INTERVAL_MIN` | 否 | 消息间隔最小秒数（默认 60） |
| `SEND_INTERVAL_MAX` | 否 | 消息间隔最大秒数（默认 180） |
| `MAX_DAILY_MESSAGES` | 否 | 每日发送上限（默认 50） |
| `ADMIN_PASSWORD` | 否 | 管理后台密码（默认 admin123456） |

> *至少需要配置一个 AI Provider 的 API Key，与 `AI_PROVIDER` 对应。

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3000 | Next.js 仪表盘 |
| 后端 | 8000 | FastAPI (Swagger: /docs) |
| PostgreSQL | 5432 | 数据库（Docker 内部） |
| Redis | 6379 | 缓存 + 任务队列（Docker 内部） |

## OpenClaw 集成（可选）

LeadFlow 提供 MCP Server，可接入 OpenClaw 实现自然语言操控获客流程。

### 注册方式

在 OpenClaw 设置中添加 MCP Server:

```json
{
  "mcpServers": {
    "leadflow": {
      "command": "python",
      "args": ["mcp-server/server.py"],
      "cwd": "/path/to/fb-lead-gen"
    }
  }
}
```

或使用 Docker:

```json
{
  "mcpServers": {
    "leadflow": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network=host", "leadflow-mcp"]
    }
  }
}
```

### 可用指令示例

- "帮我在 Facebook 搜索深圳做外贸的商家，发 10 条问好消息"
- "查看任务 #3 的进度"
- "暂停所有正在运行的任务"
- "列出所有已回复的线索"

## License

MIT
