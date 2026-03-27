#!/bin/bash
# ============================================================
# LeadFlow AI — 注册到 OpenClaw
# 运行一次，自动把 LeadFlow 注册为 OpenClaw 的 MCP 插件
#
# 用法：bash register-openclaw.sh
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_PY="$PROJECT_DIR/mcp-server/server.py"
ENV_FILE="$PROJECT_DIR/backend/.env"
OPENCLAW_CONFIG="$HOME/.openclaw/mcp.json"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  LeadFlow → OpenClaw 一键注册       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- 读取 .env 中的配置 ---
if [ -f "$ENV_FILE" ]; then
    AI_PROVIDER=$(grep "^AI_PROVIDER=" "$ENV_FILE" | cut -d= -f2)
    KIMI_API_KEY=$(grep "^KIMI_API_KEY=" "$ENV_FILE" | cut -d= -f2)
    KIMI_BASE_URL=$(grep "^KIMI_BASE_URL=" "$ENV_FILE" | cut -d= -f2)
    KIMI_MODEL=$(grep "^KIMI_MODEL=" "$ENV_FILE" | cut -d= -f2)
    OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2)
    OPENAI_BASE_URL=$(grep "^OPENAI_BASE_URL=" "$ENV_FILE" | cut -d= -f2)
    OPENAI_MODEL=$(grep "^OPENAI_MODEL=" "$ENV_FILE" | cut -d= -f2)
    OPENROUTER_API_KEY=$(grep "^OPENROUTER_API_KEY=" "$ENV_FILE" | cut -d= -f2)
    OPENROUTER_BASE_URL=$(grep "^OPENROUTER_BASE_URL=" "$ENV_FILE" | cut -d= -f2)
    OPENROUTER_MODEL=$(grep "^OPENROUTER_MODEL=" "$ENV_FILE" | cut -d= -f2)
    ANTHROPIC_API_KEY=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" | cut -d= -f2)
    WHATSAPP_BUSINESS_TOKEN=$(grep "^WHATSAPP_BUSINESS_TOKEN=" "$ENV_FILE" | cut -d= -f2)
    WHATSAPP_PHONE_NUMBER_ID=$(grep "^WHATSAPP_PHONE_NUMBER_ID=" "$ENV_FILE" | cut -d= -f2)
    echo "  ✅ 已读取 backend/.env 配置"
else
    echo "  ⚠️  未找到 backend/.env，将使用默认值"
    echo "     请先运行 bash configure.sh 或 bash one-click-setup.sh"
fi

# --- 构建 MCP 配置 JSON ---
MCP_JSON=$(cat <<MCPEOF
{
  "mcpServers": {
    "leadflow": {
      "command": "python3",
      "args": ["${SERVER_PY}"],
      "env": {
        "LEADFLOW_BASE_URL": "http://localhost:8000",
        "LEADFLOW_EMAIL": "admin@leadflow.com",
        "LEADFLOW_PASSWORD": "admin123456",
        "AI_PROVIDER": "${AI_PROVIDER:-kimi}",
        "KIMI_API_KEY": "${KIMI_API_KEY}",
        "KIMI_BASE_URL": "${KIMI_BASE_URL:-https://api.moonshot.cn/v1}",
        "KIMI_MODEL": "${KIMI_MODEL:-kimi-k2.5}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "OPENAI_BASE_URL": "${OPENAI_BASE_URL:-https://api.openai.com/v1}",
        "OPENAI_MODEL": "${OPENAI_MODEL:-gpt-5.4-mini}",
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",
        "OPENROUTER_BASE_URL": "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}",
        "OPENROUTER_MODEL": "${OPENROUTER_MODEL:-openai/gpt-5.4}",
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
        "WHATSAPP_BUSINESS_TOKEN": "${WHATSAPP_BUSINESS_TOKEN}",
        "WHATSAPP_PHONE_NUMBER_ID": "${WHATSAPP_PHONE_NUMBER_ID}",
        "FB_EMAIL": "",
        "FB_PASSWORD": ""
      }
    }
  }
}
MCPEOF
)

# --- 写入 OpenClaw MCP 配置 ---
mkdir -p "$(dirname "$OPENCLAW_CONFIG")"

if [ -f "$OPENCLAW_CONFIG" ]; then
    # 已有配置，用 python 合并（保留其他 MCP server）
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, sys

existing = json.load(open('${OPENCLAW_CONFIG}'))
new_server = json.loads('''${MCP_JSON}''')

if 'mcpServers' not in existing:
    existing['mcpServers'] = {}
existing['mcpServers']['leadflow'] = new_server['mcpServers']['leadflow']

with open('${OPENCLAW_CONFIG}', 'w') as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
print('  ✅ 已合并到现有配置（保留其他 MCP 服务）')
" 2>/dev/null || {
        # python 合并失败，备份后覆盖
        cp "$OPENCLAW_CONFIG" "${OPENCLAW_CONFIG}.bak"
        echo "$MCP_JSON" > "$OPENCLAW_CONFIG"
        echo "  ✅ 已写入配置（旧配置备份到 mcp.json.bak）"
    }
    else
        cp "$OPENCLAW_CONFIG" "${OPENCLAW_CONFIG}.bak"
        echo "$MCP_JSON" > "$OPENCLAW_CONFIG"
        echo "  ✅ 已写入配置（旧配置备份到 mcp.json.bak）"
    fi
else
    echo "$MCP_JSON" > "$OPENCLAW_CONFIG"
    echo "  ✅ 已创建 MCP 配置"
fi

echo ""
echo "  配置文件: $OPENCLAW_CONFIG"
echo "  MCP 服务: leadflow"
echo "  Server:   $SERVER_PY"
echo ""

# --- 重启 OpenClaw Gateway ---
if command -v openclaw &>/dev/null; then
    echo "  重启 OpenClaw Gateway..."
    openclaw gateway restart 2>/dev/null
    echo "  ✅ Gateway 已重启"
else
    echo "  提示：重启 OpenClaw 使配置生效"
    echo "    openclaw gateway restart"
fi

# --- 验证 ---
echo ""
echo "╔══════════════════════════════════════╗"
echo "║         ✅ 注册完成！               ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  验证方法："
echo "    1. 确保 LeadFlow 已启动（docker compose up -d）"
echo "    2. 在 OpenClaw 聊天中说：「帮我搜索 Facebook 上做电子产品的买家」"
echo "    3. 如果 OpenClaw 调用了 leadflow 的工具，说明连接成功"
echo ""
echo "  查看已注册的 MCP："
echo "    openclaw mcp list"
echo ""
