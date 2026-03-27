#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════╗
# ║                                                               ║
# ║   LeadFlow AI — 一站式安装                                   ║
# ║                                                               ║
# ║   这是你唯一需要运行的脚本。                                 ║
# ║   它会一步步引导你完成所有安装。                             ║
# ║                                                               ║
# ║   用法：bash one-click-setup.sh                              ║
# ║                                                               ║
# ╚═══════════════════════════════════════════════════════════════╝

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/backend/.env"
ERRORS=""

# --- 颜色 ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; }
info() { echo -e "  ${CYAN}$1${NC}"; }
step() { echo -e "\n${BOLD}━━━━━ $1 ━━━━━${NC}\n"; }

clear
echo ""
echo -e "${BOLD}"
echo "  ╔═════════════════════════════════════════╗"
echo "  ║                                         ║"
echo "  ║   LeadFlow AI — 智能外贸获客平台       ║"
echo "  ║                                         ║"
echo "  ║   跟着提示一步步来，5 分钟搞定安装     ║"
echo "  ║                                         ║"
echo "  ╚═════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "  这个脚本会帮你完成："
echo "  [1] 检查环境依赖"
echo "  [2] 填写 AI 密钥（粘贴一下就行）"
echo "  [3] 启动系统（全自动）"
echo "  [4] 安装浏览器控制工具"
echo ""
read -p "  准备好了吗？按回车开始... " _

# ============================================================
# [1] 检查环境依赖
# ============================================================
step "[1/4] 检查环境依赖"

# Docker
echo "  检查 Docker..."
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    ok "Docker 已安装并运行"
else
    if command -v docker &>/dev/null; then
        fail "Docker 已安装但未运行"
        echo ""
        echo "  请打开 Docker Desktop，等它启动完成后（任务栏出现鲸鱼图标），"
        echo "  再重新运行这个脚本。"
    else
        fail "Docker 未安装"
        echo ""
        echo "  请先安装 Docker Desktop："
        echo "  https://www.docker.com/products/docker-desktop/"
        echo ""
        echo "  安装完成后重新运行这个脚本。"
    fi
    exit 1
fi

# Node.js
echo "  检查 Node.js..."
if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    ok "Node.js $NODE_VER"
else
    warn "Node.js 未安装（浏览器控制功能需要，但不影响 Web 应用）"
    echo ""
    echo "  安装方法："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    brew install node"
    else
        echo "    https://nodejs.org/ 下载 LTS 版本"
    fi
    echo ""
    echo "  你可以先跳过，装完 Node.js 后再运行 bash install-agent.sh"
    echo ""
    ERRORS="$ERRORS\n- Node.js 未安装，浏览器控制功能暂不可用"
fi

# Python（静默检查）
if command -v python3 &>/dev/null; then
    ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"
else
    warn "Python3 未安装（MCP Server 需要）"
    ERRORS="$ERRORS\n- Python3 未安装"
fi

# ============================================================
# [2] 配置 AI 密钥
# ============================================================
step "[2/4] 配置系统"

if [ -f "$ENV_FILE" ]; then
    # 检查是否已经配置了真实的 Key（任意一个供应商）
    EXISTING_KIMI=$(grep "^KIMI_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    EXISTING_OPENAI=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    EXISTING_ANTHROPIC=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    EXISTING_OPENROUTER=$(grep "^OPENROUTER_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    HAS_KEY=false
    [ -n "$EXISTING_KIMI" ] && [ "$EXISTING_KIMI" != "sk-xxx" ] && HAS_KEY=true
    [ -n "$EXISTING_OPENAI" ] && HAS_KEY=true
    [ -n "$EXISTING_ANTHROPIC" ] && HAS_KEY=true
    [ -n "$EXISTING_OPENROUTER" ] && HAS_KEY=true
    if [ "$HAS_KEY" = true ]; then
        echo "  检测到已有配置（API Key 已填写）。"
        read -p "  要重新配置吗？(y/N) " RECONFIG
        if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
            ok "保持现有配置"
            SKIP_CONFIG=true
        fi
    fi
fi

if [ "$SKIP_CONFIG" != "true" ]; then

    # --- 选择 AI 供应商 ---
    echo ""
    echo "  系统需要一个 AI 来分析客户画像。请选择你要用的 AI："
    echo ""
    echo -e "  ${BOLD}[1] Kimi K2.5（月之暗面）${NC}— 国内用户推荐，性价比最高，注册送免费额度"
    echo -e "  ${BOLD}[2] OpenAI GPT-5.4${NC}    — 海外用户推荐，综合能力最强"
    echo -e "  ${BOLD}[3] Anthropic Claude${NC}   — 海外备选，推理能力强"
    echo -e "  ${BOLD}[4] OpenRouter${NC}         — 多模型聚合平台，一个 Key 用所有模型（推荐海外用户）"
    echo ""

    while true; do
        read -p "  请输入数字 1、2、3 或 4: " AI_CHOICE
        case "$AI_CHOICE" in
            1) AI_PROVIDER="kimi"; break;;
            2) AI_PROVIDER="openai"; break;;
            3) AI_PROVIDER="anthropic"; break;;
            4) AI_PROVIDER="openrouter"; break;;
            *) echo "  请输入 1、2、3 或 4";;
        esac
    done

    echo ""
    KIMI_KEY=""
    OPENAI_KEY=""
    ANTHROPIC_KEY=""
    OPENROUTER_KEY=""
    OPENROUTER_MODEL="openai/gpt-5.4"

    # --- 根据选择填写 Key ---
    if [ "$AI_PROVIDER" = "kimi" ]; then
        while true; do
            read -p "  粘贴你的 Kimi API Key: " KIMI_KEY
            KIMI_KEY=$(echo "$KIMI_KEY" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [ -n "$KIMI_KEY" ] && break
            fail "不能为空"
        done
        ok "已保存"

    elif [ "$AI_PROVIDER" = "openai" ]; then
        while true; do
            read -p "  粘贴你的 OpenAI API Key: " OPENAI_KEY
            OPENAI_KEY=$(echo "$OPENAI_KEY" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [ -n "$OPENAI_KEY" ] && break
            fail "不能为空"
        done
        ok "已保存"

    elif [ "$AI_PROVIDER" = "anthropic" ]; then
        while true; do
            read -p "  粘贴你的 Anthropic API Key: " ANTHROPIC_KEY
            ANTHROPIC_KEY=$(echo "$ANTHROPIC_KEY" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [ -n "$ANTHROPIC_KEY" ] && break
            fail "不能为空"
        done
        ok "已保存"

    elif [ "$AI_PROVIDER" = "openrouter" ]; then
        while true; do
            read -p "  粘贴你的 OpenRouter API Key: " OPENROUTER_KEY
            OPENROUTER_KEY=$(echo "$OPENROUTER_KEY" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [ -n "$OPENROUTER_KEY" ] && break
            fail "不能为空"
        done
        ok "已保存"

        # 选择模型
        echo ""
        echo "  选择默认模型："
        echo -e "  ${BOLD}[1] openai/gpt-5.4${NC}       — GPT-5.4 旗舰（默认）"
        echo -e "  ${BOLD}[2] openai/gpt-5.4-mini${NC}  — GPT-5.4 轻量版，快速便宜"
        echo -e "  ${BOLD}[3] openai/gpt-5.4-nano${NC}  — GPT-5.4 最小版，超低价"
        echo -e "  ${BOLD}[4] openai/gpt-5.3-codex${NC} — 编程专用"
        echo ""
        read -p "  输入 1/2/3/4（直接回车选 1）: " OR_MODEL_CHOICE
        case "$OR_MODEL_CHOICE" in
            2) OPENROUTER_MODEL="openai/gpt-5.4-mini";;
            3) OPENROUTER_MODEL="openai/gpt-5.4-nano";;
            4) OPENROUTER_MODEL="openai/gpt-5.3-codex";;
            *) OPENROUTER_MODEL="openai/gpt-5.4";;
        esac
        ok "使用模型: $OPENROUTER_MODEL"
    fi

    # 生成 SECRET_KEY（用户不需要知道这个）
    if command -v python3 &>/dev/null; then
        SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    elif command -v openssl &>/dev/null; then
        SECRET=$(openssl rand -base64 32 | tr -d '/+=')
    else
        SECRET="leadflow-$(date +%s)-$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"
    fi

    # 写入配置文件
    cat > "$ENV_FILE" << ENVFILE
DATABASE_URL=postgresql://leadflow:leadflow_dev_password@localhost:5432/leadflow
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=${SECRET}

AI_PROVIDER=${AI_PROVIDER}

# Kimi K2.5 (月之暗面)
KIMI_API_KEY=${KIMI_KEY}
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5

# OpenAI GPT-5.4
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=${OPENAI_MODEL:-gpt-5.4-mini}

# OpenRouter (多模型聚合)
OPENROUTER_API_KEY=${OPENROUTER_KEY}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=${OPENROUTER_MODEL}

# Anthropic Claude
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}

WHATSAPP_BUSINESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
TELEGRAM_BOT_TOKEN=
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_ACCESS_TOKEN=
ENVFILE

    ok "配置已保存（AI 供应商: $AI_PROVIDER）"
fi

# ============================================================
# [3] 启动 Docker 服务
# ============================================================
step "[3/4] 启动系统"

echo "  正在启动 5 个服务（首次需要下载和构建，大约 3-5 分钟）..."
echo "  （数据库、后端、前端、任务队列、缓存）"
echo ""

cd "$PROJECT_DIR"
docker compose up -d --build 2>&1 | while IFS= read -r line; do
    # 只显示关键信息
    if echo "$line" | grep -qE "Started|Created|Running|Building|Pulling|Error|error"; then
        echo "  $line"
    fi
done

echo ""

# 等后端就绪
echo "  等待系统启动..."
READY=false
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/health &>/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 2
    echo -ne "\r  等待中... ${i}s"
done
echo ""

if [ "$READY" = true ]; then
    ok "后端 API 已就绪"
else
    warn "后端还在启动中，可能需要再等一会儿"
    info "可以运行 docker compose logs backend 查看日志"
fi

# 检查前端
sleep 3
if curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
    ok "前端已就绪"
else
    warn "前端还在编译中，稍等 30 秒再打开网页"
fi

# ============================================================
# [4] 安装浏览器控制工具
# ============================================================
step "[4/4] 安装浏览器控制工具"

if ! command -v node &>/dev/null; then
    warn "Node.js 未安装，跳过浏览器控制工具"
    info "装好 Node.js 后运行 bash install-agent.sh 补装"
else
    # 安装 OpenCLI
    echo "  安装 OpenCLI（浏览器控制引擎）..."
    if command -v opencli &>/dev/null; then
        ok "OpenCLI 已安装"
    else
        npm install -g @jackwener/opencli 2>&1 | tail -1
        if command -v opencli &>/dev/null; then
            ok "OpenCLI 安装完成"
        else
            warn "OpenCLI 安装可能需要 sudo，请手动运行："
            info "sudo npm install -g @jackwener/opencli"
        fi
    fi

    # MCP Server Python 依赖
    if command -v python3 &>/dev/null; then
        echo "  安装 MCP Server 依赖..."
        cd "$PROJECT_DIR/mcp-server"
        pip3 install -r requirements.txt -q 2>&1 | tail -1
        ok "Python 依赖安装完成"

        # 人设文件
        if [ ! -f persona.json ]; then
            cp persona.example.json persona.json 2>/dev/null
        fi
    fi
fi

# ============================================================
# [5] 启动 Automation API（浏览器自动化接口）
# ============================================================
if command -v python3 &>/dev/null && [ -f "$PROJECT_DIR/mcp-server/http_api.py" ]; then
    echo ""
    echo "  启动 Automation API (浏览器自动化)..."
    lsof -ti :3001 | xargs kill -9 2>/dev/null 2>&1
    cd "$PROJECT_DIR/mcp-server"
    python3 http_api.py &>/tmp/leadflow-automation.log &
    sleep 2
    if curl -s http://localhost:3001/status &>/dev/null 2>&1; then
        ok "Automation API: http://localhost:3001"
    else
        warn "Automation API 启动中，稍等片刻"
        info "查看日志: cat /tmp/leadflow-automation.log"
    fi
    cd "$PROJECT_DIR"
fi

# ============================================================
# 完成！
# ============================================================
echo ""
echo ""
echo -e "${BOLD}"
echo "  ╔═════════════════════════════════════════╗"
echo "  ║                                         ║"
echo "  ║        安装完成！系统已在运行           ║"
echo "  ║                                         ║"
echo "  ╚═════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  ${BOLD}打开浏览器，访问：${NC}"
echo ""
echo -e "     ${CYAN}http://localhost:3000${NC}"
echo ""
echo -e "  ${BOLD}登录账号：${NC}"
echo ""
echo "     邮箱：admin@leadflow.com"
echo "     密码：admin123456"
echo ""

# Chrome 扩展提示
if command -v opencli &>/dev/null; then
    echo -e "  ${BOLD}最后一步 — 安装 Chrome 扩展（一次性）：${NC}"
    echo ""
    echo "  这个扩展让系统能控制你的 Chrome 去 Facebook 找客户。"
    echo "  安装方法："
    echo ""
    echo "  1. 打开 Chrome，地址栏输入："
    echo -e "     ${CYAN}chrome://extensions/${NC}"
    echo ""
    echo "  2. 右上角打开「开发者模式」开关"
    echo ""
    echo "  3. 点左上角「加载已解压的扩展程序」"
    echo ""
    echo "  4. 选择这个文件夹："
    echo -e "     ${CYAN}${PROJECT_DIR}/opencli-vendor/extension/${NC}"
    echo ""
    echo "  5. 确认 Chrome 已登录 Facebook"
    echo ""
fi

# 日常操作提示
echo -e "  ${BOLD}日常使用：${NC}"
echo ""
echo "  启动系统：cd $(basename "$PROJECT_DIR") && docker compose up -d"
echo "  停止系统：docker compose down"
echo "  查看日志：docker compose logs -f"
echo ""

# 如果有报错
if [ -n "$ERRORS" ]; then
    echo -e "  ${YELLOW}${BOLD}注意事项：${NC}"
    echo -e "$ERRORS" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "  ${YELLOW}$line${NC}"
    done
    echo ""
fi

# 尝试自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open "http://localhost:3000" 2>/dev/null
elif command -v xdg-open &>/dev/null; then
    sleep 2
    xdg-open "http://localhost:3000" 2>/dev/null
fi
