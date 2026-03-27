#!/bin/bash
# ============================================================
# LeadFlow AI — 一键启动
# 运行: bash start.sh
# 停止: bash start.sh stop
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "stop" ]; then
    echo "🛑 停止所有服务..."
    cd "$PROJECT_DIR"
    # Docker Compose 方式
    if docker compose ps --format '{{.Name}}' 2>/dev/null | grep -q .; then
        docker compose down
        echo "  ✅ Docker Compose 服务已停止"
    else
        # 本地进程方式
        lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "  后端已停止" || echo "  后端未运行"
        lsof -ti :3000 | xargs kill -9 2>/dev/null && echo "  前端已停止" || echo "  前端未运行"
        lsof -ti :3001 | xargs kill -9 2>/dev/null && echo "  自动化 API 已停止" || echo "  自动化 API 未运行"
        pkill -f "celery.*leadflow" 2>/dev/null && echo "  Celery Worker 已停止" || echo "  Celery Worker 未运行"
        pkill -f "auto_poller.py" 2>/dev/null && echo "  轮询器已停止" || echo "  轮询器未运行"
        pkill -f "http_api.py" 2>/dev/null && echo "  Automation HTTP API 已停止" || echo ""
        echo "  ✅ 已停止（数据库保持运行）"
    fi
    exit 0
fi

echo "🚀 LeadFlow AI 启动中..."
echo ""

# 检查 .env
if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    echo "❌ 未找到 backend/.env"
    echo "   请先运行: bash configure.sh 或 bash one-click-setup.sh"
    exit 1
fi

# --- 自动检测部署方式 ---
cd "$PROJECT_DIR"

# 方式 1：Docker Compose（优先）
if [ -f docker-compose.yml ] && command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    echo "  检测到 docker-compose.yml，使用 Docker Compose 启动..."
    echo ""
    docker compose up -d 2>&1 | while IFS= read -r line; do
        if echo "$line" | grep -qiE "Started|Created|Running|Error|error"; then
            echo "  $line"
        fi
    done

    # 等后端就绪
    echo ""
    echo "  等待服务启动..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:8000/health &>/dev/null; then
            break
        fi
        sleep 2
        echo -ne "\r  等待中... ${i}s"
    done
    echo ""

    if curl -s http://localhost:8000/health &>/dev/null; then
        echo "  ✅ 后端: http://localhost:8000"
    else
        echo "  ⚠️  后端还在启动中，稍等一会儿"
        echo "     查看日志: docker compose logs backend"
    fi

    # 检查前端
    sleep 3
    if curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
        echo "  ✅ 前端: http://localhost:3000"
    else
        echo "  ⚠️  前端还在编译，稍等 30 秒再访问"
    fi

else
    # 方式 2：本地进程启动
    echo "  使用本地进程方式启动..."
    echo ""

    # 启动数据库
    if ! lsof -i :5432 &>/dev/null; then
        echo "  启动 PostgreSQL..."
        docker start leadflow-postgres 2>/dev/null || {
            # 尝试找到任何 postgres 容器
            PG_CONTAINER=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i postgres | head -1)
            if [ -n "$PG_CONTAINER" ]; then
                docker start "$PG_CONTAINER" 2>/dev/null && echo "  ✅ PostgreSQL ($PG_CONTAINER)" || echo "  ⚠️ PostgreSQL 启动失败"
            else
                echo "  ⚠️ PostgreSQL 未找到，请先运行 setup.sh 或 docker compose up -d"
            fi
        }
    else
        echo "  ✅ PostgreSQL 已在运行"
    fi

    if ! lsof -i :6379 &>/dev/null; then
        echo "  启动 Redis..."
        docker start leadflow-redis 2>/dev/null || {
            REDIS_CONTAINER=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i redis | head -1)
            if [ -n "$REDIS_CONTAINER" ]; then
                docker start "$REDIS_CONTAINER" 2>/dev/null && echo "  ✅ Redis ($REDIS_CONTAINER)" || echo "  ⚠️ Redis 启动失败"
            else
                echo "  ⚠️ Redis 未找到，请先运行 setup.sh 或 docker compose up -d"
            fi
        }
    else
        echo "  ✅ Redis 已在运行"
    fi
    sleep 2

    # 停止已有进程
    lsof -ti :8000 | xargs kill -9 2>/dev/null
    lsof -ti :3000 | xargs kill -9 2>/dev/null
    sleep 1

    # 启动后端
    echo "  启动后端 API..."
    cd "$PROJECT_DIR/backend"
    uvicorn app.main:app --reload --port 8000 &>/tmp/leadflow-backend.log &
    BACKEND_PID=$!

    for i in {1..15}; do
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

    # 启动 Celery Worker
    echo "  启动 Celery Worker..."
    cd "$PROJECT_DIR/backend"
    celery -A app.tasks.celery_app worker --loglevel=info &>/tmp/leadflow-celery.log &
    CELERY_PID=$!
    sleep 2
    if ps -p $CELERY_PID &>/dev/null; then
        echo "  ✅ Celery Worker (PID: $CELERY_PID)"
    else
        echo "  ⚠️  Celery Worker 启动失败，查看日志: cat /tmp/leadflow-celery.log"
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
fi

# 启动 Automation HTTP API（浏览器自动化接口，运行在主机上）
echo "  启动 Automation API (浏览器自动化)..."
lsof -ti :3001 | xargs kill -9 2>/dev/null
cd "$PROJECT_DIR/mcp-server"
if [ -f http_api.py ]; then
    python3 http_api.py &>/tmp/leadflow-automation.log &
    AUTOMATION_PID=$!
    sleep 2
    if curl -s http://localhost:3001/status &>/dev/null 2>&1; then
        echo "  ✅ 自动化 API: http://localhost:3001"
    else
        echo "  ⚠️  自动化 API 启动中，稍等片刻"
        echo "     查看日志: cat /tmp/leadflow-automation.log"
    fi
else
    echo "  ⚠️  http_api.py 未找到，自动化功能不可用"
fi

echo ""
echo "========================================"
echo "✅ LeadFlow AI 已启动！"
echo "========================================"
echo ""
echo "  🌐 网页界面:  http://localhost:3000"
echo "  📡 API 文档:  http://localhost:8000/docs"
echo "  🤖 自动化:    http://localhost:3001"
echo "  📧 账号:      admin@leadflow.com"
echo "  🔑 密码:      admin123456"
echo ""
echo "  停止: bash $PROJECT_DIR/start.sh stop"
echo ""

# 打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000 2>/dev/null
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:3000 2>/dev/null
fi
