# Docker 部署指南

本文档说明如何使用 Docker 和 Docker Compose 构建和运行 FinGraph Insight 系统。

## 系统要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

## 快速开始

### 1. 环境配置

创建 `.env` 文件（可以从 `.env.example` 复制）：

```bash
cp .env.example .env
```

必须配置的环境变量：

```env
# LLM API 配置（必需）
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# 可选配置
STARTUP_REFRESH_AKSHARE=false
```

### 2. 构建和启动

```bash
# 构建所有服务
docker-compose build

# 启动所有服务（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 访问服务

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **Neo4j 浏览器**: http://localhost:7474
  - 用户名: `neo4j`
  - 密码: `password`

### 4. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（警告：会删除数据库数据）
docker-compose down -v
```

## 服务架构

### Neo4j 数据库

- **镜像**: `neo4j:5`
- **端口**: 
  - 7474 (HTTP 浏览器)
  - 7687 (Bolt 协议)
- **数据持久化**: `neo4j_data` 卷
- **内存配置**:
  - Heap: 512MB - 2GB
  - Page Cache: 512MB

### 后端服务

- **基础镜像**: `python:3.12-slim`
- **包管理**: uv 0.9.11
- **端口**: 8000
- **健康检查**: `/health` 端点
- **特性**:
  - 多阶段构建优化
  - 非 root 用户运行
  - 依赖层缓存
  - 字节码预编译

### 前端服务

- **构建镜像**: `node:22-alpine`
- **运行镜像**: `nginx:1.27-alpine`
- **端口**: 80 (映射到主机 5173)
- **特性**:
  - Vue.js 3 + TypeScript
  - Vite 构建优化
  - Nginx gzip 压缩
  - 静态资源缓存
  - SPA 路由回退
  - 非 root 用户运行

## 高级配置

### 性能优化

#### Neo4j 内存调优

根据可用内存调整 `docker-compose.yml` 中的设置：

```yaml
services:
  neo4j:
    environment:
      # 对于 8GB 内存系统
      NEO4J_dbms_memory_heap_initial__size: 1g
      NEO4J_dbms_memory_heap_max__size: 4g
      NEO4J_dbms_memory_pagecache_size: 1g
```

#### 后端并发配置

修改 CMD 以增加 workers：

```dockerfile
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 开发模式

使用卷挂载进行热重载开发：

```yaml
services:
  backend:
    volumes:
      - ./backend/app:/app/app:ro
      - ./data:/app/data:ro
    environment:
      - RELOAD=true
```

### 生产部署建议

1. **环境变量安全**
   - 使用 Docker secrets 或外部密钥管理
   - 不要在镜像中硬编码敏感信息

2. **资源限制**
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 2G
           reservations:
             cpus: '1'
             memory: 1G
   ```

3. **日志管理**
   ```yaml
   services:
     backend:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```

4. **HTTPS 配置**
   - 在前端 Nginx 前添加反向代理（如 Traefik、Caddy）
   - 或使用云服务的负载均衡器

5. **备份策略**
   ```bash
   # 备份 Neo4j 数据
   docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/data/backup
   
   # 导出数据卷
   docker run --rm -v fingraph-insight_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .
   ```

## 构建优化说明

### 前端 Dockerfile 优化

1. **多阶段构建**: 分离构建和运行环境，减小最终镜像大小
2. **依赖层缓存**: 先复制 package.json，后复制源码
3. **生产模式构建**: `npm run build` 包含 TypeScript 检查和优化
4. **健康检查**: 自动检测服务可用性
5. **安全加固**: 非 root 用户运行

### Nginx 配置优化

1. **Gzip 压缩**: 减少传输数据量 60-80%
2. **缓存策略**:
   - 静态资源 (JS/CSS/图片): 1 年缓存
   - HTML: 禁用缓存，确保更新
3. **安全头部**: 防止 XSS、点击劫持等攻击
4. **API 代理**: 
   - 长超时支持 LLM 操作
   - 禁用缓冲支持流式响应
5. **SPA 支持**: 所有路由回退到 index.html

### 后端 Dockerfile 优化

1. **uv 包管理器**: 比 pip 快 10-100 倍
2. **依赖锁定**: `uv.lock` 确保可重复构建
3. **字节码预编译**: 加速启动时间
4. **最小化镜像**: 使用 slim 基础镜像
5. **安全加固**: 非 root 用户运行

## 故障排查

### 服务启动失败

```bash
# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs backend
docker-compose logs frontend
docker-compose logs neo4j
```

### Neo4j 连接失败

1. 检查 Neo4j 是否就绪：
   ```bash
   docker-compose logs neo4j | grep "Started"
   ```

2. 验证连接：
   ```bash
   docker-compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1"
   ```

### 前端无法访问后端

1. 检查后端健康状态：
   ```bash
   curl http://localhost:8000/health
   ```

2. 检查 Nginx 配置：
   ```bash
   docker-compose exec frontend nginx -t
   ```

3. 查看 Nginx 日志：
   ```bash
   docker-compose logs frontend
   ```

### 构建缓存问题

```bash
# 清理并重新构建
docker-compose build --no-cache

# 清理所有未使用的资源
docker system prune -a
```

## 监控和维护

### 健康检查

所有服务都配置了健康检查：

```bash
# 查看健康状态
docker-compose ps
```

健康状态：
- `healthy`: 服务正常
- `starting`: 启动中
- `unhealthy`: 异常

### 资源使用

```bash
# 查看容器资源使用
docker stats
```

### 数据持久化

数据存储在 Docker 卷中：

```bash
# 查看卷信息
docker volume ls
docker volume inspect fingraph-insight_neo4j_data

# 备份数据卷
docker run --rm -v fingraph-insight_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .

# 恢复数据卷
docker run --rm -v fingraph-insight_neo4j_data:/data -v $(pwd):/backup alpine sh -c "cd /data && tar xzf /backup/neo4j-backup.tar.gz --strip 1"
```

## 开发工作流

### 前端开发

```bash
# 仅启动后端服务
docker-compose up -d neo4j backend

# 本地运行前端开发服务器
cd frontend
npm install
npm run dev
```

### 后端开发

```bash
# 仅启动数据库
docker-compose up -d neo4j

# 本地运行后端
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

### 数据库管理

```bash
# 进入 Neo4j Shell
docker-compose exec neo4j cypher-shell -u neo4j -p password

# 重置数据库
docker-compose exec neo4j cypher-shell -u neo4j -p password "MATCH (n) DETACH DELETE n"

# 导入测试数据
docker-compose exec -T neo4j cypher-shell -u neo4j -p password < scripts/seed-data.cypher
```

## 更新和升级

### 更新代码

```bash
# 拉取最新代码
git pull

# 重新构建并重启
docker-compose up -d --build
```

### 更新依赖

#### 前端依赖

```bash
cd frontend
npm update
npm run build  # 本地测试构建
```

#### 后端依赖

```bash
cd backend
uv sync --upgrade
uv lock
```

### 更新 Docker 镜像

```bash
# 拉取最新基础镜像
docker-compose pull

# 重新构建
docker-compose build --pull
```

## 常见问题

**Q: 首次启动很慢？**  
A: 首次启动需要下载基础镜像、构建应用、初始化数据库。后续启动会快很多。

**Q: 修改代码后如何更新？**  
A: 运行 `docker-compose up -d --build` 重新构建并重启服务。

**Q: 如何清理旧数据？**  
A: 使用 `docker-compose down -v` 删除所有数据卷（警告：不可恢复）。

**Q: 端口冲突怎么办？**  
A: 修改 `docker-compose.yml` 中的端口映射，如将 `"5173:80"` 改为 `"8080:80"`。

**Q: 内存不足？**  
A: 减小 Neo4j 内存配置或增加系统交换空间。

## 技术支持

- 查看日志：`docker-compose logs -f [service_name]`
- 进入容器：`docker-compose exec [service_name] sh`
- 重启服务：`docker-compose restart [service_name]`

## 许可证

遵循项目主许可证。
