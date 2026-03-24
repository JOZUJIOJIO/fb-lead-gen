#!/bin/bash
# ============================================================
# LeadFlow AI — 配置向导
# 运行一次就行，帮你生成所有配置文件
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/backend/.env"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     LeadFlow AI — 配置向导          ║"
echo "║     回答几个问题就能用了            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- 如果已有配置，询问是否重新配置 ---
if [ -f "$ENV_FILE" ]; then
    echo "检测到已有配置文件。"
    read -p "要重新配置吗？(y/n，直接回车跳过) " RECONFIG
    if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
        echo "保持现有配置。"
        exit 0
    fi
    echo ""
fi

# --- 1. Kimi API Key ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第 1 步：填写 AI 密钥（必填）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "系统需要一个 AI 来帮你分析客户。"
echo "我们用的是 Kimi（月之暗面），注册就有免费额度。"
echo ""
echo "获取方法："
echo "  1. 打开 https://platform.moonshot.cn/"
echo "  2. 注册/登录"
echo "  3. 进入 API Keys 页面"
echo "  4. 创建一个 Key，复制过来"
echo ""
echo "Key 长这样：sk-xxxxxxxxxxxxxxxxxxxxxxxx"
echo ""

while true; do
    read -p "请粘贴你的 Kimi API Key: " KIMI_KEY
    if [ -z "$KIMI_KEY" ]; then
        echo "  API Key 不能为空，请重新输入。"
    elif [[ "$KIMI_KEY" == sk-* ]]; then
        echo "  ✅ 格式正确"
        break
    else
        echo "  ⚠️  Key 通常以 sk- 开头，你确定吗？"
        read -p "  继续使用这个 Key？(y/n) " CONFIRM
        if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
            break
        fi
    fi
done

# --- 2. WhatsApp（可选）---
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第 2 步：WhatsApp 配置（可选，直接回车跳过）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "如果你有 WhatsApp Business API，可以让系统直接"
echo "通过 WhatsApp 发消息给客户。没有的话直接回车跳过。"
echo ""

read -p "WhatsApp Business Token（没有就回车跳过）: " WA_TOKEN
read -p "WhatsApp Phone Number ID（没有就回车跳过）: " WA_PHONE

# --- 3. 生成密钥 ---
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第 3 步：自动生成安全密钥..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 生成随机 SECRET_KEY
if command -v python3 &>/dev/null; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
elif command -v openssl &>/dev/null; then
    SECRET=$(openssl rand -base64 32 | tr -d '/+=')
else
    SECRET="leadflow-$(date +%s)-$(head -c 20 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
echo "  ✅ 已自动生成"

# --- 4. 写入配置文件 ---
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "正在保存配置..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cat > "$ENV_FILE" << ENVFILE
DATABASE_URL=postgresql://leadflow:leadflow_dev_password@localhost:5432/leadflow
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=${SECRET}

# AI Provider
AI_PROVIDER=kimi
KIMI_API_KEY=${KIMI_KEY}
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5

# Anthropic Claude (optional)
ANTHROPIC_API_KEY=

# WhatsApp
WHATSAPP_BUSINESS_TOKEN=${WA_TOKEN}
WHATSAPP_PHONE_NUMBER_ID=${WA_PHONE}

# Telegram Bot
TELEGRAM_BOT_TOKEN=

# Facebook Graph API
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_ACCESS_TOKEN=
ENVFILE

echo "  ✅ 配置已保存到 backend/.env"

# --- 完成 ---
echo ""
echo "╔══════════════════════════════════════╗"
echo "║         ✅ 配置完成！               ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "现在可以启动系统了："
echo ""
echo "  docker compose up -d"
echo ""
echo "启动后打开 http://localhost:3000"
echo "账号: admin@leadflow.com"
echo "密码: admin123456"
echo ""
