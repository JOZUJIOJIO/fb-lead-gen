#!/bin/bash
# ============================================================
# LeadFlow AI — 升级脚本
# 从 GitHub 拉取最新代码并重启服务
#
# 用法：bash upgrade.sh
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/backend/.env"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     LeadFlow AI — 升级             ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- 检查是否在 git 仓库中 ---
cd "$PROJECT_DIR"
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "❌ 当前目录不是 Git 仓库，无法升级。"
    exit 1
fi

# --- 显示当前版本 ---
CURRENT=$(git log --oneline -1)
echo "  当前版本: $CURRENT"
echo ""

# --- 检查本地是否有未提交的改动 ---
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "⚠️  检测到本地有未提交的改动："
    git status --short
    echo ""
    read -p "  继续升级会保留这些改动（stash）。继续吗？(y/N) " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "  已取消。"
        exit 0
    fi
    echo "  暂存本地改动..."
    git stash push -m "upgrade-$(date +%Y%m%d%H%M%S)"
    STASHED=true
fi

# --- 拉取最新代码 ---
echo ""
echo "━━━━━ 拉取最新代码 ━━━━━"
echo ""
git pull origin "$(git rev-parse --abbrev-ref HEAD)"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 拉取失败，请检查网络或手动解决冲突。"
    if [ "$STASHED" = true ]; then
        echo "  恢复本地改动: git stash pop"
    fi
    exit 1
fi

# --- 更新子模块（OpenCLI 等）---
if [ -f ".gitmodules" ]; then
    echo ""
    echo "━━━━━ 更新子模块 ━━━━━"
    echo ""
    git submodule update --init --recursive
fi

# --- 显示更新内容 ---
NEW=$(git log --oneline -1)
echo ""
echo "  更新后版本: $NEW"
echo ""

# --- 检测部署方式并重启 ---
echo "━━━━━ 重启服务 ━━━━━"
echo ""

if docker compose ps &>/dev/null 2>&1 && docker compose ps --format '{{.Name}}' 2>/dev/null | grep -q .; then
    # Docker Compose 部署
    echo "  检测到 Docker Compose 部署，重新构建并启动..."
    echo ""
    docker compose up -d --build
    echo ""

    # 等待后端就绪
    echo "  等待服务启动..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:8000/health &>/dev/null; then
            break
        fi
        sleep 2
    done

    if curl -s http://localhost:8000/health &>/dev/null; then
        echo "  ✅ 后端已就绪"
    else
        echo "  ⚠️  后端还在启动中，可运行 docker compose logs backend 查看"
    fi

elif lsof -i :8000 &>/dev/null; then
    # 本地进程部署
    echo "  检测到本地进程部署，重启中..."

    # 更新后端依赖
    echo "  安装后端依赖..."
    cd "$PROJECT_DIR/backend"
    pip3 install -r requirements.txt -q 2>&1 | tail -1

    # 更新前端依赖
    echo "  安装前端依赖..."
    cd "$PROJECT_DIR/frontend"
    npm install --silent 2>&1 | tail -1

    # 更新 MCP Server 依赖
    if [ -f "$PROJECT_DIR/mcp-server/requirements.txt" ]; then
        echo "  安装 MCP Server 依赖..."
        cd "$PROJECT_DIR/mcp-server"
        pip3 install -r requirements.txt -q 2>&1 | tail -1
    fi

    # 重启
    cd "$PROJECT_DIR"
    bash start.sh stop 2>/dev/null
    sleep 2
    bash start.sh

else
    # 服务未运行，只更新依赖
    echo "  服务未运行，仅更新依赖..."

    if [ -f "$PROJECT_DIR/backend/requirements.txt" ]; then
        echo "  安装后端依赖..."
        cd "$PROJECT_DIR/backend"
        pip3 install -r requirements.txt -q 2>&1 | tail -1
    fi

    if [ -f "$PROJECT_DIR/frontend/package.json" ]; then
        echo "  安装前端依赖..."
        cd "$PROJECT_DIR/frontend"
        npm install --silent 2>&1 | tail -1
    fi

    if [ -f "$PROJECT_DIR/mcp-server/requirements.txt" ]; then
        echo "  安装 MCP Server 依赖..."
        cd "$PROJECT_DIR/mcp-server"
        pip3 install -r requirements.txt -q 2>&1 | tail -1
    fi

    echo ""
    echo "  依赖已更新。启动服务请运行："
    echo "    docker compose up -d    （Docker 方式）"
    echo "    bash start.sh           （本地方式）"
fi

# --- 恢复本地改动 ---
if [ "$STASHED" = true ]; then
    echo ""
    echo "  恢复之前暂存的本地改动..."
    cd "$PROJECT_DIR"
    git stash pop
fi

# --- 完成 ---
echo ""
echo "╔══════════════════════════════════════╗"
echo "║         ✅ 升级完成！               ║"
echo "╚══════════════════════════════════════╝"
echo ""
