#!/bin/bash
# ============================================================
# LeadFlow AI — 浏览器代理安装脚本
# 安装 OpenCLI + MCP Server 依赖（本机运行部分）
# ============================================================

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🌐 LeadFlow AI — 浏览器代理安装"
echo "=================================="
echo ""
echo "这个脚本安装浏览器自动化组件（在本机运行，操控你的 Chrome）。"
echo "Web 应用部分请用 docker compose up -d 启动。"
echo ""

# 1. 检查 Node.js
echo "📋 Step 1/4: 检查 Node.js..."
if ! command -v node &>/dev/null; then
    echo "  ❌ 需要 Node.js 18+。请安装："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "     brew install node"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        echo "     curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
        echo "     sudo apt-get install -y nodejs"
    else
        echo "     https://nodejs.org/en/download/"
    fi
    exit 1
fi
echo "  ✅ Node $(node --version)"

# 2. 安装 OpenCLI
echo ""
echo "📋 Step 2/4: 安装 OpenCLI..."
if command -v opencli &>/dev/null; then
    echo "  ✅ OpenCLI 已安装 ($(opencli --version 2>/dev/null || echo 'installed'))"
else
    npm install -g @jackwener/opencli
    echo "  ✅ OpenCLI 安装完成"
fi

# 3. 检查 Python + 安装 MCP Server 依赖
echo ""
echo "📋 Step 3/4: 安装 MCP Server Python 依赖..."
if ! command -v python3 &>/dev/null; then
    echo "  ❌ 需要 Python 3.10+。请安装："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "     brew install python3"
    else
        echo "     sudo apt-get install -y python3 python3-pip"
    fi
    exit 1
fi
echo "  ✅ Python $(python3 --version | cut -d' ' -f2)"

cd "$PROJECT_DIR/mcp-server"
pip3 install -r requirements.txt -q 2>&1 | tail -1
echo "  ✅ Python 依赖安装完成"

# 4. 人设配置
echo ""
echo "📋 Step 4/4: 配置人设..."
if [ ! -f persona.json ]; then
    cp persona.example.json persona.json
    echo "  ✅ 已创建 persona.json（可按需编辑）"
else
    echo "  ✅ persona.json 已存在"
fi

echo ""
echo "========================================"
echo "✅ 浏览器代理安装完成！"
echo "========================================"
echo ""
echo "⚠️  还需要手动完成一步："
echo ""
echo "  在 Chrome 中安装 OpenCLI Browser Bridge 扩展："
echo "  1. 打开 Chrome → chrome://extensions/"
echo "  2. 开启「开发者模式」"
echo "  3. 点击「加载已解压的扩展程序」"
echo "  4. 选择 $PROJECT_DIR/opencli-vendor/extension/ 目录"
echo ""
echo "验证安装："
echo "  opencli doctor"
echo ""
echo "启动命令（Web 应用 + 浏览器代理）："
echo "  docker compose up -d          # 启动 Web 应用"
echo "  python3 mcp-server/server.py  # 启动 MCP Server（可选）"
echo ""
