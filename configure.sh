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

# --- 1. 选择 AI 供应商 ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "第 1 步：选择 AI 供应商（必填）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "系统需要一个 AI 来帮你分析客户。请选择："
echo ""
echo "  [1] Kimi K2.5（月之暗面）— 国内推荐，注册送免费额度"
echo "  [2] OpenAI GPT-5.4      — 海外推荐，综合最强"
echo "  [3] OpenRouter           — 多模型聚合，一个Key用所有模型"
echo "  [4] Anthropic Claude     — 海外备选"
echo ""

KIMI_KEY=""
OPENAI_KEY=""
OPENROUTER_KEY=""
ANTHROPIC_KEY=""
AI_PROVIDER="kimi"
OPENAI_MODEL="gpt-5.4"
OPENROUTER_MODEL="openai/gpt-5.4"

while true; do
    read -p "请输入数字 1、2、3 或 4: " AI_CHOICE
    case "$AI_CHOICE" in
        1) AI_PROVIDER="kimi"; break;;
        2) AI_PROVIDER="openai"; break;;
        3) AI_PROVIDER="openrouter"; break;;
        4) AI_PROVIDER="anthropic"; break;;
        *) echo "  请输入 1、2、3 或 4";;
    esac
done

echo ""

if [ "$AI_PROVIDER" = "kimi" ]; then
    while true; do
        read -p "请粘贴你的 Kimi API Key: " KIMI_KEY
        [ -n "$KIMI_KEY" ] && break
        echo "  不能为空"
    done
    echo "  ✅ 已保存"

elif [ "$AI_PROVIDER" = "openai" ]; then
    while true; do
        read -p "请粘贴你的 OpenAI API Key: " OPENAI_KEY
        [ -n "$OPENAI_KEY" ] && break
        echo "  不能为空"
    done
    echo "  ✅ 已保存"

elif [ "$AI_PROVIDER" = "openrouter" ]; then
    while true; do
        read -p "请粘贴你的 OpenRouter API Key: " OPENROUTER_KEY
        [ -n "$OPENROUTER_KEY" ] && break
        echo "  不能为空"
    done
    echo "  ✅ 已保存"
    echo ""
    echo "  选择默认模型："
    echo "  [1] openai/gpt-5.4       — GPT-5.4 旗舰（默认）"
    echo "  [2] openai/gpt-5.4-mini  — GPT-5.4 轻量版，快速便宜"
    echo "  [3] openai/gpt-5.4-nano  — GPT-5.4 最小版，超低价"
    echo "  [4] openai/gpt-5.3-codex — 编程专用"
    echo ""
    read -p "  输入 1/2/3/4（直接回车选 1）: " OR_MODEL
    case "$OR_MODEL" in
        2) OPENROUTER_MODEL="openai/gpt-5.4-mini";;
        3) OPENROUTER_MODEL="openai/gpt-5.4-nano";;
        4) OPENROUTER_MODEL="openai/gpt-5.3-codex";;
        *) OPENROUTER_MODEL="openai/gpt-5.4";;
    esac
    echo "  ✅ 使用模型: $OPENROUTER_MODEL"

elif [ "$AI_PROVIDER" = "anthropic" ]; then
    while true; do
        read -p "请粘贴你的 Anthropic API Key: " ANTHROPIC_KEY
        [ -n "$ANTHROPIC_KEY" ] && break
        echo "  不能为空"
    done
    echo "  ✅ 已保存"
fi

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
AI_PROVIDER=${AI_PROVIDER}

# Kimi K2.5 (月之暗面)
KIMI_API_KEY=${KIMI_KEY}
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5

# OpenAI GPT-5.4
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=${OPENAI_MODEL}

# OpenRouter (多模型聚合)
OPENROUTER_API_KEY=${OPENROUTER_KEY}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=${OPENROUTER_MODEL}

# Anthropic Claude
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}

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
