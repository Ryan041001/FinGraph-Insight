@echo off
REM Docker Compose 快速命令参考 (Windows)
REM 用法: docker-commands.bat [command]

setlocal enabledelayedexpansion

set PROJECT_NAME=fingraph-insight

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="start" goto start
if "%1"=="up" goto start
if "%1"=="stop" goto stop
if "%1"=="down" goto stop
if "%1"=="restart" goto restart
if "%1"=="build" goto build
if "%1"=="rebuild" goto rebuild
if "%1"=="logs" goto logs
if "%1"=="status" goto status
if "%1"=="ps" goto status
if "%1"=="health" goto health
if "%1"=="clean" goto clean
if "%1"=="reset" goto reset
if "%1"=="backup" goto backup
if "%1"=="restore" goto restore
if "%1"=="shell" goto shell
if "%1"=="update" goto update
goto help

:start
echo 🚀 启动所有服务...
docker-compose up -d
echo ✓ 服务已启动
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000
echo   Neo4j: http://localhost:7474
goto end

:stop
echo 🛑 停止所有服务...
docker-compose down
echo ✓ 服务已停止
goto end

:restart
echo 🔄 重启所有服务...
docker-compose restart
echo ✓ 服务已重启
goto end

:build
echo 🔨 构建所有镜像...
docker-compose build --parallel
echo ✓ 构建完成
goto end

:rebuild
echo 🔨 强制重新构建所有镜像...
docker-compose build --no-cache --parallel
echo ✓ 重新构建完成
goto end

:logs
if "%2"=="" (
    echo 📋 查看所有服务日志 (Ctrl+C 退出)...
    docker-compose logs -f
) else (
    echo 📋 查看 %2 服务日志 (Ctrl+C 退出)...
    docker-compose logs -f %2
)
goto end

:status
echo 📊 服务状态:
docker-compose ps
goto end

:health
echo 🏥 健康检查:
echo.
echo Backend:
curl -s http://localhost:8000/health | findstr "healthy" >nul && echo   ✓ 健康 || echo   ✗ 异常
echo.
echo Frontend:
curl -s http://localhost:5173 >nul 2>&1 && echo   ✓ 健康 || echo   ✗ 异常
echo.
echo Neo4j:
docker-compose exec -T neo4j cypher-shell -u neo4j -p password "RETURN 1" >nul 2>&1 && echo   ✓ 健康 || echo   ✗ 异常
goto end

:clean
echo 🧹 清理未使用的 Docker 资源...
docker system prune -f
echo ✓ 清理完成
goto end

:reset
echo ⚠️  警告: 这将删除所有数据!
set /p confirm="确认继续? (yes/no): "
if /i "%confirm%"=="yes" (
    echo 🗑️  停止并删除所有容器和数据卷...
    docker-compose down -v
    echo ✓ 重置完成
) else (
    echo ✗ 操作已取消
)
goto end

:backup
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ("%TIME%") do (set mytime=%%a%%b)
set BACKUP_FILE=neo4j-backup-%mydate%-%mytime%.tar.gz
echo 💾 备份 Neo4j 数据...
docker run --rm -v %PROJECT_NAME%_neo4j_data:/data -v "%CD%":/backup alpine tar czf /backup/%BACKUP_FILE% -C /data .
echo ✓ 备份完成: %BACKUP_FILE%
goto end

:restore
if "%2"=="" (
    echo ❌ 用法: %0 restore ^<backup-file^>
    goto end
)
if not exist "%2" (
    echo ❌ 备份文件不存在: %2
    goto end
)
echo ⚠️  警告: 这将覆盖现有数据!
set /p confirm="确认继续? (yes/no): "
if /i "%confirm%"=="yes" (
    echo 📥 恢复 Neo4j 数据...
    docker-compose down
    docker run --rm -v %PROJECT_NAME%_neo4j_data:/data -v "%CD%":/backup alpine sh -c "cd /data && tar xzf /backup/%2 --strip 1"
    docker-compose up -d
    echo ✓ 恢复完成
) else (
    echo ✗ 操作已取消
)
goto end

:shell
set SERVICE=%2
if "%SERVICE%"=="" set SERVICE=backend
echo 🐚 进入 %SERVICE% 容器...
if "%SERVICE%"=="frontend" (
    docker-compose exec %SERVICE% sh
) else (
    docker-compose exec %SERVICE% bash
)
goto end

:update
echo 🔄 更新应用...
git pull
docker-compose build --parallel
docker-compose up -d
echo ✓ 更新完成
goto end

:help
echo 📚 Docker Compose 命令参考
echo.
echo 基础命令:
echo   start^|up       启动所有服务
echo   stop^|down      停止所有服务
echo   restart        重启所有服务
echo   status^|ps      查看服务状态
echo.
echo 构建命令:
echo   build          构建所有镜像
echo   rebuild        强制重新构建所有镜像
echo.
echo 日志和调试:
echo   logs [service] 查看日志 (可指定服务名)
echo   health         检查所有服务健康状态
echo   shell [service] 进入容器 Shell (默认 backend)
echo.
echo 维护命令:
echo   clean          清理未使用的 Docker 资源
echo   reset          停止并删除所有容器和数据 (危险!)
echo   backup         备份 Neo4j 数据
echo   restore ^<file^> 从备份恢复数据
echo   update         拉取最新代码并重新部署
echo.
echo 示例:
echo   %0 start                  # 启动所有服务
echo   %0 logs backend           # 查看后端日志
echo   %0 shell frontend         # 进入前端容器
echo   %0 backup                 # 备份数据库
echo   %0 restore backup.tar.gz  # 恢复数据库
echo.
echo 访问地址:
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000
echo   Neo4j: http://localhost:7474 (用户名: neo4j, 密码: password)
goto end

:end
endlocal
