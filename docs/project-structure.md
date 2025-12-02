# 项目目录结构说明

本项目围绕「Core Library + HTTP 管理 API + MCP Server + 前端」四个核心角色设计，目录结构建议如下（可根据实际需要微调）。

> 说明：下面是目标结构，实际仓库搭建时可以按 Milestone 渐进创建。

`	ext
.
├─ MCP_PROJECT_OVERVIEW.md       # 项目概览（根目录）
├─ MCP_PROJECT_PLAN.md           # 项目开发计划（根目录）
├─ backend/                      # 后端代码（Python）
│  ├─ core/                      # Core Library：代码解析 / 索引 / 问答
│  │  ├─ __init__.py
│  │  ├─ repo_manager.py         # Git 克隆 / 更新、本地路径管理
│  │  ├─ indexer.py              # 代码扫描、切片、Embedding 构建
│  │  ├─ outline_generator.py    # 仓库大纲（Markdown）生成
│  │  ├─ qa_service.py           # 单仓 / 多仓问答核心逻辑
│  │  └─ models.py               # 核心数据模型（Repo / RepoGroup / CodeChunk 等）
│  │
│  ├─ storage/                   # 存储层（DB + 向量库）
│  │  ├─ __init__.py
│  │  ├─ db.py                   # 访问关系型数据库（SQLite / Postgres）
│  │  └─ vector_store.py         # 向量索引封装（FAISS / Chroma / 自建）
│  │
│  ├─ api_http/                  # HTTP 管理 API（Admin API）
│  │  ├─ __init__.py
│  │  └─ app.py                  # FastAPI/Flask 入口：/repos /repo-groups /qa/*
│  │
│  ├─ api_mcp/                   # MCP Server 实现
│  │  ├─ __init__.py
│  │  └─ server.py               # 注册 MCP 工具：list_repos / list_repo_groups / ask_repo / ask_repo_group
│  │
│  └─ config/                    # 后端配置
│     ├─ __init__.py
│     └─ settings.example.yaml   # 示例配置：DB 路径、仓库存储根目录、LLM Key 等
│
├─ frontend/                     # 前端 Web 应用
│  ├─ src/
│  │  ├─ pages/
│  │  │  ├─ ReposPage.tsx        # 仓库列表页：展示 / 添加 / 触发分析
│  │  │  ├─ RepoDetailPage.tsx   # 仓库详情页：展示大纲、文件/模块树
│  │  │  ├─ RepoGroupsPage.tsx   # 仓库组管理：创建 / 编辑仓库组
│  │  │  └─ ChatPage.tsx         # 问答界面：单仓 / 仓库组对话
│  │  ├─ components/
│  │  │  ├─ RepoList.tsx
│  │  │  ├─ RepoGroupSelector.tsx
│  │  │  └─ ChatPanel.tsx
│  │  └─ api/                    # 调用后端 HTTP 管理 API 的封装
│  ├─ public/
│  └─ package.json
│
├─ docs/                         # 文档目录（当前文件所在位置）
│  ├─ README.md                  # 文档索引与阅读指南
│  └─ project-structure.md       # 项目结构说明（本文件）
│  # （后续可增加：architecture.md / http-api.md / mcp-tools.md 等）
│
└─ scripts/                      # 脚本 / 工具
   ├─ init_db.py                 # 初始化数据库
   ├─ reindex_repo.py            # 重建指定仓库索引（调用 Core Library）
   └─ dev_run_all.sh / .ps1      # 本地开发快捷启动脚本（可选）
`

---

## 1. 目录设计原则

1. **职责清晰**  
   - core/：只关注「代码 → 索引 → 问答」的能力，不关心 HTTP / MCP 协议细节。
   - pi_http/：只负责 HTTP 路由定义和参数校验，实际逻辑委托给 core/。
   - pi_mcp/：只负责 MCP 工具注册与调用，将 MCP 请求映射到 core/ 的能力上。
2. **读写分离**  
   - MCP Server 是「只读」视角，所有写操作统一由 HTTP 管理 API 暴露。
   - 代码层面，共享同一套 Core Library，避免两份逻辑各自维护。
3. **前端后端弱耦合**  
   - 前端只依赖 HTTP 管理 API 的契约，不直接感知 MCP 工具细节。
   - 如需将 MCP 回答展示到前端，可以通过中控服务或在后端扩展额外 Endpoint。

---

## 2. backend/core 模块说明

### 2.1 epo_manager.py

- 负责：
  - 根据 Git URL 克隆 / 更新仓库到本地。
  - 维护仓库的本地路径、默认分支、当前 HEAD 等元信息。
- 被调用者：
  - HTTP 管理 API 的 /repos 创建 / 更新接口。
  - scripts/reindex_repo.py 等工具脚本。

### 2.2 indexer.py

- 负责：
  - 扫描指定仓库目录，遍历代码文件。
  - 按函数 / 类 / 模块粒度拆分代码（CodeChunk）。
  - 为每个 CodeChunk 生成 Embedding 并写入 ector_store。
- 被调用者：
  - nalyze_repo(repo_id) 流程。
  - 后续可能的增量索引功能。

### 2.3 outline_generator.py

- 负责：
  - 读取某仓库的 CodeChunk、文件结构信息。
  - 调用大模型生成仓库大纲（Markdown），包括：
    - 项目简介；
    - 模块结构；
    - 关键类 / 函数说明。
- 输出：
  - 存储于固定路径（例如 data/outlines/<repo_id>.md）或 DB 中。
  - 可被前端、MCP 问答上下文复用。

### 2.4 qa_service.py

- 负责：
  - 提供统一的问答接口：
    - nswer_for_repo(repo_id, question, ...)
    - nswer_for_repo_group(group_id, question, ...)
  - 内部步骤：
    1. 使用向量检索从相关仓库中取回 CodeChunk。
    2. 组合问题、仓库大纲与代码片段，构造 Prompt。
    3. 调用大模型，解析返回结果。
  - 输出结构：
    - 回答文本；
    - 引用片段列表（文件路径、符号、行号等）。

---

## 3. backend/api_http 模块说明

- pp.py 是 HTTP 管理 API 的入口，主要路由包括：

  - 仓库管理：
    - POST /repos：创建 / 更新仓库记录并触发克隆。
    - GET /repos：获取仓库列表和索引状态。
    - POST /repos/{id}/reindex：触发 nalyze_repo(repo_id)。
  - 仓库组管理：
    - POST /repo-groups：创建仓库组。
    - PATCH /repo-groups/{id}：修改仓库组（增删仓库、改名等）。
    - GET /repo-groups：列出所有仓库组。
  - 可选问答接口（直接面向前端）：
    - POST /qa/repo
    - POST /qa/repo-group

- 路由层只做参数校验和错误处理，实际业务逻辑全部委托给 core/。

---

## 4. backend/api_mcp 模块说明

- server.py 是 MCP Server 的入口：
  - 注册工具：
    - list_repos
    - list_repo_groups
    - sk_repo
    - sk_repo_group
  - 每个工具的实现逻辑：
    - 从 DB 读数据（通过 storage/db.py）。
    - 调用 qa_service.py 完成检索与问答。
    - 将结果映射为 MCP 协议规定的返回格式。

- 关键点：
  - MCP 只做「读」，不暴露任何写端点。
  - 与 HTTP API 共用同一套 Core Library，保证行为一致。

---

## 5. frontend 结构说明

- src/pages/：
  - ReposPage.tsx：展示仓库列表，可添加仓库、触发分析。
  - RepoDetailPage.tsx：展示仓库大纲，未来可以展示文件树。
  - RepoGroupsPage.tsx：创建 / 编辑仓库组。
  - ChatPage.tsx：统一的问答界面（根据当前选中对象是仓库还是仓库组，调用不同的后端接口）。
- src/components/：
  - RepoList.tsx：仓库列表组件。
  - RepoGroupSelector.tsx：仓库组选取 / 过滤组件。
  - ChatPanel.tsx：对话区域组件，显示问题、回复和引用代码片段。
- src/api/：
  - 封装调用 HTTP 管理 API 的方法，统一处理错误和 Loading 状态。

---

## 6. scripts 说明

- init_db.py：
  - 初始化数据库表结构，或执行迁移前检查。
- eindex_repo.py：
  - 通过命令行触发对指定 epo_id 的重索引，便于调试。
- dev_run_all.sh / dev_run_all.ps1（可选）：
  - 一键启动：
    - 后端 HTTP 管理 API；
    - MCP Server；
    - 前端开发服务器。

在实际开发过程中，可以根据需要对脚本进行增删，但建议保持「一个命令启动全部服务」的能力，提升迭代效率。
