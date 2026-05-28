# 智链金析 / FinGraph Insight

这是一个面向金融关系发现与风险研判的知识图谱和大模型应用，也是课程大作业方向二的项目骨架。当前版本先完成整体工程架构、mock API、前端页面骨架、Docker Compose 和样例数据。

## 快速启动

后端本地启动：

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端本地启动：

```powershell
cd frontend
npm install
npm run dev
```

Docker Compose：

```powershell
docker compose up --build
```

## 当前状态

- 后端 API 先用 mock 数据返回统一契约。
- 前端页面先对齐接口和演示流程。
- Neo4j、LLM、AKShare 的真实逻辑留给后续模块替换。

## 文档

项目规划见 [项目规划文档.md](项目规划文档.md) 和 `docs/`。
