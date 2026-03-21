#!/bin/bash
# ============================================================
# LeadFlow AI — 一键启动
# 运行: bash start.sh
# 停止: bash start.sh stop
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "stop" ]; then
    echo "🛑 停止所有服务..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "  后端已停止" || echo "  后端未运行"
    lsof -ti :3000 | xargs kill -9 2>/dev/null && echo "  前端已停止" || echo "  前端未运行"
    pkill -f "auto_poller.py" 2>/dev/null && echo "  轮询器已停止" || echo "  轮询器未运行"
    echo "✅ 已停止（数据库保持运行）"
    exit 0
fi

echo "🚀 LeadFlow AI 启动中..."
echo ""

# 检查数据库
if ! lsof -i :5432 &>/dev/null; then
    echo "  启动 PostgreSQL..."
    docker start leadflow-postgres 2>/dev/null || echo "  ⚠️ PostgreSQL 未找到，请先运行 setup.sh"
fi
if ! lsof -i :6379 &>/dev/null; then
    echo "  启动 Redis..."
    docker start leadflow-redis 2>/dev/null || echo "  ⚠️ Redis 未找到，请先运行 setup.sh"
fi
sleep 2

# 检查 .env
if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    echo "❌ 未找到 backend/.env，请先运行 setup.sh"
    exit 1
fi

# 停止已有进程
lsof -ti :8000 | xargs kill -9 2>/dev/null
lsof -ti :3000 | xargs kill -9 2>/dev/null
sleep 1

# 启动后端
echo "  启动后端 API..."
cd "$PROJECT_DIR/backend"
uvicorn app.main:app --reload --port 8000 &>/tmp/leadflow-backend.log &
BACKEND_PID=$!

# 等后端就绪
for i in {1..10}; do
    if curl -s http://localhost:8000/health &>/dev/null; then
        break
    fi
    sleep 1
done

if curl -s http://localhost:8000/health &>/dev/null; then
    echo "  ✅ 后端: http://localhost:8000"
else
    echo "  ❌ 后端启动失败，查看日志: cat /tmp/leadflow-backend.log"
    exit 1
fi

# 启动前端
echo "  启动前端..."
cd "$PROJECT_DIR/frontend"
npm run dev &>/tmp/leadflow-frontend.log &
FRONTEND_PID=$!
sleep 5

if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q 200; then
    echo "  ✅ 前端: http://localhost:3000"
else
    echo "  ⚠️ 前端可能还在编译，稍等几秒再访问 http://localhost:3000"
fi

echo ""
echo "========================================"
echo "✅ LeadFlow AI 已启动！"
echo "========================================"
echo ""
echo "  🌐 网页界面:  http://localhost:3000"
echo "  📡 API 文档:  http://localhost:8000/docs"
echo "  📧 账号:      admin@leadflow.com"
echo "  🔑 密码:      admin123456"
echo ""
echo "  自动轮询器（可选）:"
echo "    启动: python3 $PROJECT_DIR/mcp-server/auto_poller.py"
echo "    自定义间隔: python3 $PROJECT_DIR/mcp-server/auto_poller.py --interval 3"
echo ""
echo "  停止: bash $PROJECT_DIR/start.sh stop"
echo "  后端日志: tail -f /tmp/leadflow-backend.log"
echo "  前端日志: tail -f /tmp/leadflow-frontend.log"
echo ""

# 打开浏览器
open http://localhost:3000
