#!/usr/bin/env bash
# ============================================================
#  LeadFlow AI — 引导式安装
#  用法: bash setup.sh
# ============================================================

set -e

# ---- 颜色 ----
BOLD="\033[1m"
DIM="\033[2m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ENV_FILE="backend/.env"

clear
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║     🚀 LeadFlow AI — 引导式安装          ║${RESET}"
echo -e "${BOLD}║     智能社媒获客工具                      ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ============================================================
# Step 0: 环境检测
# ============================================================
echo -e "${CYAN}[1/5] 检查运行环境...${RESET}"

MISSING=""
if ! command -v docker &>/dev/null; then
    MISSING="${MISSING}  ❌ Docker 未安装 — 请先安装 Docker Desktop\n"
fi
if command -v docker &>/dev/null && ! docker info &>/dev/null 2>&1; then
    MISSING="${MISSING}  ❌ Docker 未运行 — 请先启动 Docker Desktop\n"
fi

if [ -n "$MISSING" ]; then
    echo -e "${RED}环境检查未通过:${RESET}"
    echo -e "$MISSING"
    echo -e "${DIM}安装 Docker: https://docs.docker.com/get-docker/${RESET}"
    exit 1
fi

echo -e "  ${GREEN}✓${RESET} Docker 已就绪"
echo ""

# ============================================================
# Step 1: 选择 AI 供应商
# ============================================================
echo -e "${CYAN}[2/5] 选择你的 AI 供应商${RESET}"
echo ""
echo "  1) OpenAI          (GPT-4o / GPT-4o-mini，也支持兼容 API)"
echo "  2) Anthropic        (Claude 系列)"
echo "  3) Kimi / Moonshot  (月之暗面，国内可直连)"
echo ""

while true; do
    read -rp "请选择 [1/2/3]: " AI_CHOICE
    case "$AI_CHOICE" in
        1) AI_PROVIDER="openai";    break ;;
        2) AI_PROVIDER="anthropic"; break ;;
        3) AI_PROVIDER="kimi";      break ;;
        *) echo -e "${YELLOW}请输入 1、2 或 3${RESET}" ;;
    esac
done
echo -e "  ${GREEN}✓${RESET} 已选择: ${BOLD}${AI_PROVIDER}${RESET}"
echo ""

# ============================================================
# Step 2: 填写 API Key
# ============================================================
echo -e "${CYAN}[3/5] 填写 API Key${RESET}"

OPENAI_API_KEY=""
OPENAI_BASE_URL=""
ANTHROPIC_API_KEY=""
KIMI_API_KEY=""

case "$AI_PROVIDER" in
    openai)
        echo -e "${DIM}  获取 Key: https://platform.openai.com/api-keys${RESET}"
        while true; do
            read -rp "  OpenAI API Key: " OPENAI_API_KEY
            if [ -n "$OPENAI_API_KEY" ]; then break; fi
            echo -e "${YELLOW}  API Key 不能为空${RESET}"
        done
        echo ""
        echo -e "${DIM}  如果使用兼容 API（如 DeepSeek、硅基流动），请填写 Base URL${RESET}"
        echo -e "${DIM}  直接使用 OpenAI 则留空回车${RESET}"
        read -rp "  Base URL (可选): " OPENAI_BASE_URL
        ;;
    anthropic)
        echo -e "${DIM}  获取 Key: https://console.anthropic.com/settings/keys${RESET}"
        while true; do
            read -rp "  Anthropic API Key: " ANTHROPIC_API_KEY
            if [ -n "$ANTHROPIC_API_KEY" ]; then break; fi
            echo -e "${YELLOW}  API Key 不能为空${RESET}"
        done
        ;;
    kimi)
        echo -e "${DIM}  获取 Key: https://platform.moonshot.cn/console/api-keys${RESET}"
        while true; do
            read -rp "  Kimi API Key: " KIMI_API_KEY
            if [ -n "$KIMI_API_KEY" ]; then break; fi
            echo -e "${YELLOW}  API Key 不能为空${RESET}"
        done
        ;;
esac

echo -e "  ${GREEN}✓${RESET} API Key 已设置"
echo ""

# ============================================================
# Step 3: 可选配置
# ============================================================
echo -e "${CYAN}[4/5] 可选配置${RESET}"
echo ""

# Proxy
echo -e "${DIM}  如果你在中国大陆且需要代理访问 Facebook，请填写代理地址${RESET}"
echo -e "${DIM}  格式: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080${RESET}"
read -rp "  代理地址 (留空跳过): " PROXY_SERVER

# Admin password
echo ""
echo -e "${DIM}  设置管理员密码（Web 登录用）${RESET}"
read -rp "  管理员密码 (留空使用默认 admin123456): " ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123456}

echo ""
echo -e "  ${GREEN}✓${RESET} 配置完成"
echo ""

# ============================================================
# Step 4: 生成 .env 并启动
# ============================================================
echo -e "${CYAN}[5/5] 生成配置并启动服务...${RESET}"
echo ""

cat > "$ENV_FILE" << ENVEOF
# ============================================================
#  LeadFlow AI 环境配置
#  由 setup.sh 自动生成于 $(date "+%Y-%m-%d %H:%M:%S")
# ============================================================

# AI 供应商
AI_PROVIDER=${AI_PROVIDER}

# OpenAI / 兼容 API
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_BASE_URL=${OPENAI_BASE_URL}

# Anthropic Claude
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Kimi / Moonshot
KIMI_API_KEY=${KIMI_API_KEY}

# 代理（可选）
PROXY_SERVER=${PROXY_SERVER}

# 数据库（Docker 内部自动连接，无需修改）
DATABASE_URL=postgresql+asyncpg://leadflow:leadflow123@postgres:5432/leadflow
REDIS_URL=redis://redis:6379/0

# 发送控制
SEND_INTERVAL_MIN=60
SEND_INTERVAL_MAX=180
MAX_DAILY_MESSAGES=50

# 管理员
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ENVEOF

echo -e "  ${GREEN}✓${RESET} 配置已写入 ${DIM}${ENV_FILE}${RESET}"
echo ""

# Start Docker
echo -e "  正在启动 Docker 服务..."
echo ""
docker compose up -d --build

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║     ${GREEN}✅ LeadFlow AI 启动成功！${RESET}${BOLD}              ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  🌐 打开浏览器访问:  ${BOLD}http://localhost:3000${RESET}"
echo ""
echo -e "  📧 登录账号:  ${BOLD}admin@leadflow.ai${RESET}"
echo -e "  🔑 登录密码:  ${BOLD}${ADMIN_PASSWORD}${RESET}"
echo ""
echo -e "${DIM}  停止服务: docker compose down${RESET}"
echo -e "${DIM}  查看日志: docker compose logs -f${RESET}"
echo -e "${DIM}  重新配置: bash setup.sh${RESET}"
echo ""
