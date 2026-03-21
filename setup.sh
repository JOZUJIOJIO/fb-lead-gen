#!/bin/bash
# ============================================================
# LeadFlow AI — Mac 一键部署脚本
# 在新的 Mac 上运行: bash setup.sh
# ============================================================

set -e
echo "🚀 LeadFlow AI 一键部署"
echo "========================"

# 1. 检查基础依赖
echo ""
echo "📋 Step 1/6: 检查系统依赖..."

# Homebrew
if ! command -v brew &>/dev/null; then
    echo "  安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "  ✅ Homebrew"

# Python 3
if ! command -v python3 &>/dev/null; then
    echo "  安装 Python3..."
    brew install python3
fi
echo "  ✅ Python $(python3 --version | cut -d' ' -f2)"

# Node.js
if ! command -v node &>/dev/null; then
    echo "  安装 Node.js..."
    brew install node
fi
echo "  ✅ Node $(node --version)"

# Docker
if ! command -v docker &>/dev/null; then
    echo "  ⚠️  需要安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
    echo "     安装后重新运行本脚本。"
    exit 1
fi
echo "  ✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# 2. 启动数据库
echo ""
echo "📋 Step 2/6: 启动 PostgreSQL + Redis..."

# 检查端口是否已被占用（可能已有 Docker 容器）
if lsof -i :5432 &>/dev/null; then
    echo "  ⚠️  端口 5432 已被占用，尝试复用现有 PostgreSQL..."
    # 尝试创建数据库和用户
    CONTAINER=$(docker ps --format '{{.Names}}' | grep -i postgres | head -1)
    if [ -n "$CONTAINER" ]; then
        PG_USER=$(docker exec "$CONTAINER" psql -U postgres -tAc "SELECT 1" 2>/dev/null && echo "postgres" || echo "")
        if [ -z "$PG_USER" ]; then
            # 尝试其他常见用户
            for u in openclaw leadflow admin; do
                if docker exec "$CONTAINER" psql -U "$u" -tAc "SELECT 1" &>/dev/null; then
                    PG_USER="$u"
                    break
                fi
            done
        fi
        if [ -n "$PG_USER" ]; then
            docker exec "$CONTAINER" psql -U "$PG_USER" -c "CREATE USER leadflow WITH PASSWORD 'leadflow_dev_password';" 2>/dev/null || true
            docker exec "$CONTAINER" psql -U "$PG_USER" -c "CREATE DATABASE leadflow OWNER leadflow;" 2>/dev/null || true
            echo "  ✅ 复用现有 PostgreSQL (用户: $PG_USER)"
        fi
    fi
else
    docker run -d --name leadflow-postgres \
        -e POSTGRES_DB=leadflow \
        -e POSTGRES_USER=leadflow \
        -e POSTGRES_PASSWORD=leadflow_dev_password \
        -p 5432:5432 \
        postgres:16-alpine 2>/dev/null || docker start leadflow-postgres 2>/dev/null
    echo "  ✅ PostgreSQL 已启动"
fi

if lsof -i :6379 &>/dev/null; then
    echo "  ✅ 复用现有 Redis"
else
    docker run -d --name leadflow-redis \
        -p 6379:6379 \
        redis:7-alpine 2>/dev/null || docker start leadflow-redis 2>/dev/null
    echo "  ✅ Redis 已启动"
fi

# 等数据库就绪
sleep 3

# 3. 安装后端依赖
echo ""
echo "📋 Step 3/6: 安装后端 Python 依赖..."
cd "$(dirname "$0")/backend"
pip3 install -r requirements.txt -q 2>&1 | tail -1
echo "  ✅ 后端依赖安装完成"

# 4. 配置环境变量
echo ""
echo "📋 Step 4/6: 配置环境变量..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ⚠️  已创建 .env 文件，请编辑填入你的 API Key:"
    echo "     $(pwd)/.env"
    echo ""
    echo "     必须填写: KIMI_API_KEY=你的Kimi密钥"
    echo ""
    read -p "  现在要打开编辑吗? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open .env
        echo "  编辑完保存后，按回车继续..."
        read
    fi
else
    echo "  ✅ .env 已存在，跳过"
fi

# 5. 安装前端依赖
echo ""
echo "📋 Step 5/6: 安装前端 Node 依赖..."
cd "$(dirname "$0")/../frontend"
npm install --silent 2>&1 | tail -1
echo "  ✅ 前端依赖安装完成"

# 6. 安装 MCP Server 依赖 + Playwright
echo ""
echo "📋 Step 6/6: 安装 MCP Server + 浏览器引擎..."
cd "$(dirname "$0")/../mcp-server"
pip3 install -r requirements.txt -q 2>&1 | tail -1
python3 -m playwright install chromium 2>/dev/null
echo "  ✅ MCP Server + Playwright 安装完成"

echo ""
echo "========================================"
echo "✅ 部署完成！"
echo "========================================"
echo ""
echo "启动命令:"
echo "  bash $(dirname "$0")/start.sh"
echo ""
