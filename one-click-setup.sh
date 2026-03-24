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
    # 检查是否已经配置了真实的 Key
    EXISTING_KEY=$(grep "^KIMI_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    if [ -n "$EXISTING_KEY" ] && [ "$EXISTING_KEY" != "sk-xxx" ]; then
        echo "  检测到已有配置（API Key 已填写）。"
        read -p "  要重新配置吗？(y/N) " RECONFIG
        if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
            ok "保持现有配置"
            SKIP_CONFIG=true
        fi
    fi
fi

if [ "$SKIP_CONFIG" != "true" ]; then

    echo ""
    echo "  系统需要一个 AI 密钥来分析客户画像。"
    echo "  我们用的是 Kimi（月之暗面的 AI），注册就有免费额度。"
    echo ""
    echo -e "  ${BOLD}怎么获取：${NC}"
    echo ""
    echo "  1. 用浏览器打开这个网址（可以直接复制粘贴到地址栏）："
    echo ""
    echo -e "     ${CYAN}https://platform.moonshot.cn/${NC}"
    echo ""
    echo "  2. 用手机号注册一个账号"
    echo "  3. 登录后，在左侧菜单找到「API Key 管理」"
    echo "  4. 点「新建」，创建一个 Key"
    echo "  5. 点「复制」，把 Key 复制到剪贴板"
    echo ""
    echo "  Key 长这样：sk-xxxxxxxxxxxxxxxxxxxxxxxx"
    echo ""

    while true; do
        read -p "  请把 Key 粘贴到这里，然后按回车: " KIMI_KEY
        # 去掉首尾空格
        KIMI_KEY=$(echo "$KIMI_KEY" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        if [ -z "$KIMI_KEY" ]; then
            echo ""
            fail "不能为空哦，请粘贴你的 API Key"
            echo ""
        elif [[ "$KIMI_KEY" == sk-* ]]; then
            echo ""
            ok "Key 格式正确"
            break
        else
            echo ""
            warn "Key 通常以 sk- 开头，你粘贴的好像不对"
            echo "  你粘贴的是: $KIMI_KEY"
            echo ""
            read -p "  确定要用这个？(y/N) " CONFIRM
            if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
                break
            fi
            echo ""
        fi
    done

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

AI_PROVIDER=kimi
KIMI_API_KEY=${KIMI_KEY}
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-latest

ANTHROPIC_API_KEY=
WHATSAPP_BUSINESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
TELEGRAM_BOT_TOKEN=
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_ACCESS_TOKEN=
ENVFILE

    ok "配置已保存"
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
