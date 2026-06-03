#!/bin/bash
# Docker Compose 快速命令参考
# 用法: ./docker-commands.sh [command]

set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="fingraph-insight"

case "${1:-help}" in
  start|up)
    echo "🚀 启动所有服务..."
    docker-compose up -d
    echo "✓ 服务已启动"
    echo "  前端: http://localhost:5173"
    echo "  后端: http://localhost:8000"
    echo "  Neo4j: http://localhost:7474"
    ;;

  stop|down)
    echo "🛑 停止所有服务..."
    docker-compose down
    echo "✓ 服务已停止"
    ;;

  restart)
    echo "🔄 重启所有服务..."
    docker-compose restart
    echo "✓ 服务已重启"
    ;;

  build)
    echo "🔨 构建所有镜像..."
    docker-compose build --parallel
    echo "✓ 构建完成"
    ;;

  rebuild)
    echo "🔨 强制重新构建所有镜像..."
    docker-compose build --no-cache --parallel
    echo "✓ 重新构建完成"
    ;;

  logs)
    SERVICE=${2:-}
    if [ -z "$SERVICE" ]; then
      echo "📋 查看所有服务日志 (Ctrl+C 退出)..."
      docker-compose logs -f
    else
      echo "📋 查看 $SERVICE 服务日志 (Ctrl+C 退出)..."
      docker-compose logs -f "$SERVICE"
    fi
    ;;

  status|ps)
    echo "📊 服务状态:"
    docker-compose ps
    ;;

  health)
    echo "🏥 健康检查:"
    echo ""
    echo "Backend:"
    curl -s http://localhost:8000/health | grep -q "healthy" && echo "  ✓ 健康" || echo "  ✗ 异常"
    echo ""
    echo "Frontend:"
    curl -s http://localhost:5173 > /dev/null && echo "  ✓ 健康" || echo "  ✗ 异常"
    echo ""
    echo "Neo4j:"
    docker-compose exec -T neo4j cypher-shell -u neo4j -p password "RETURN 1" > /dev/null 2>&1 && echo "  ✓ 健康" || echo "  ✗ 异常"
    ;;

  clean)
    echo "🧹 清理未使用的 Docker 资源..."
    docker system prune -f
    echo "✓ 清理完成"
    ;;

  reset)
    echo "⚠️  警告: 这将删除所有数据!"
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
      echo "🗑️  停止并删除所有容器和数据卷..."
      docker-compose down -v
      echo "✓ 重置完成"
    else
      echo "✗ 操作已取消"
    fi
    ;;

  backup)
    BACKUP_FILE="neo4j-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "💾 备份 Neo4j 数据..."
    docker run --rm \
      -v ${PROJECT_NAME}_neo4j_data:/data \
      -v "$(pwd):/backup" \
      alpine tar czf "/backup/$BACKUP_FILE" -C /data .
    echo "✓ 备份完成: $BACKUP_FILE"
    ;;

  restore)
    if [ -z "$2" ]; then
      echo "❌ 用法: $0 restore <backup-file>"
      exit 1
    fi
    BACKUP_FILE="$2"
    if [ ! -f "$BACKUP_FILE" ]; then
      echo "❌ 备份文件不存在: $BACKUP_FILE"
      exit 1
    fi
    echo "⚠️  警告: 这将覆盖现有数据!"
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
      echo "📥 恢复 Neo4j 数据..."
      docker-compose down
      docker run --rm \
        -v ${PROJECT_NAME}_neo4j_data:/data \
        -v "$(pwd):/backup" \
        alpine sh -c "cd /data && tar xzf /backup/$BACKUP_FILE --strip 1"
      docker-compose up -d
      echo "✓ 恢复完成"
    else
      echo "✗ 操作已取消"
    fi
    ;;

  shell)
    SERVICE=${2:-backend}
    echo "🐚 进入 $SERVICE 容器..."
    if [ "$SERVICE" = "frontend" ]; then
      docker-compose exec "$SERVICE" sh
    else
      docker-compose exec "$SERVICE" bash
    fi
    ;;

  update)
    echo "🔄 更新应用..."
    git pull
    docker-compose build --parallel
    docker-compose up -d
    echo "✓ 更新完成"
    ;;

  help|*)
    cat << 'EOF'
📚 Docker Compose 命令参考

基础命令:
  start|up       启动所有服务
  stop|down      停止所有服务
  restart        重启所有服务
  status|ps      查看服务状态

构建命令:
  build          构建所有镜像
  rebuild        强制重新构建所有镜像

日志和调试:
  logs [service] 查看日志 (可指定服务名)
  health         检查所有服务健康状态
  shell [service] 进入容器 Shell (默认 backend)

维护命令:
  clean          清理未使用的 Docker 资源
  reset          停止并删除所有容器和数据 (危险!)
  backup         备份 Neo4j 数据
  restore <file> 从备份恢复数据
  update         拉取最新代码并重新部署

示例:
  $0 start                  # 启动所有服务
  $0 logs backend           # 查看后端日志
  $0 shell frontend         # 进入前端容器
  $0 backup                 # 备份数据库
  $0 restore backup.tar.gz  # 恢复数据库

访问地址:
  前端: http://localhost:5173
  后端: http://localhost:8000
  Neo4j: http://localhost:7474 (用户名: neo4j, 密码: password)
EOF
    ;;
esac
