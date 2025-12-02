# MCP 多仓库代码助手开发计划

> 目标：实现一个只读 MCP Server（list_repos / list_repo_groups / sk_repo / sk_repo_group），
> 以及配套的 Core Library、HTTP 管理 API 和前端管理页面。

## Milestone 0：项目初始化

- [ ] 选定技术栈与基础依赖
  - 后端语言：Python。
  - Web 框架：FastAPI / Flask（二选一）。
  - 向量库：本地 FAISS / Chroma / 自建 SQLite + 向量列（二选一）。
- [ ] 初始化后端代码结构
  - ackend/core/：RepoManager、Indexer、QAService 等。
  - ackend/storage/：数据库与向量存储封装。
  - ackend/api_http/：管理 API。
  - ackend/api_mcp/：MCP Server。
- [ ] 初始化前端工程
  - 选定 React / Next.js / Vite 等方案。
  - 搭建基本路由结构。

---

## Milestone 1：Core Library 与存储层

### 1.1 数据模型与数据库

- [ ] 设计核心数据模型（可用 Pydantic）：
  - Repo: id, 
ame, git_url, default_branch, local_path, indexed_at, summary。
  - RepoGroup: id, 
ame, description, epo_ids, indexed_at。
  - CodeChunk: id, epo_id, ile_path, symbol, symbol_type, start_line, end_line, code, summary 等。
- [ ] 初始化数据库（SQLite / Postgres）：
  - 表结构迁移工具或简单建表脚本。
- [ ] 实现 storage/db.py
  - 基本 CRUD 封装：仓库、仓库组、代码片段。

### 1.2 仓库管理与索引

- [ ] 实现 RepoManager
  - [ ] 克隆 / 更新 Git 仓库到本地。
  - [ ] 维护 local_path、分支、HEAD 等信息。
- [ ] 实现 Indexer
  - [ ] 扫描指定仓库下的文件（支持若干主流语言）。
  - [ ] 按函数 / 类 / 模块粒度切分代码。
  - [ ] 为每个片段生成摘要（可以先用简单规则 / 后续接 LLM 优化）。
- [ ] 实现 ector_store.py
  - [ ] 对每个 CodeChunk 生成 Embedding。
  - [ ] 提供按 	ext / question 的向量检索接口（支持按 epo_id / epo_ids 过滤）。

### 1.3 仓库大纲生成

- [ ] 实现 OutlineGenerator
  - [ ] 根据 Repo 的 CodeChunk 汇总信息生成 Markdown 结构大纲。
  - [ ] 调用大模型对整体结构给出更自然的描述。
- [ ] 在 Core Library 内暴露统一接口：
  - nalyze_repo(repo_id): 执行扫描 → 向量索引 → 大纲生成，更新 indexed_at。

---

## Milestone 2：HTTP 管理 API 与前端管理界面

### 2.1 HTTP 管理 API

- [ ] 在 ackend/api_http/app.py 中实现基础路由：

  - 仓库管理：
    - [ ] POST /repos：入参为 Git URL（及可选 branch）。
      - 调用 RepoManager 克隆 / 更新仓库。
      - 写入 Repo 元数据。
    - [ ] GET /repos：列出所有仓库及索引状态。
    - [ ] POST /repos/{id}/reindex：触发 nalyze_repo。
  - 仓库组管理：
    - [ ] POST /repo-groups：创建仓库组（包含若干 epo_ids）。
    - [ ] PATCH /repo-groups/{id}：更新组成员、描述等。
    - [ ] GET /repo-groups：列出所有仓库组。
  - 可选问答接口（便于前端调试）：
    - [ ] POST /qa/repo：内部调用 Core Library 的单仓问答。
    - [ ] POST /qa/repo-group：内部调用多仓问答。

### 2.2 前端管理页面

- [ ] 仓库列表页
  - [ ] 显示仓库：名称、Git URL、索引状态、最后索引时间。
  - [ ] 提供「添加仓库」表单 → 调用 POST /repos。
  - [ ] 提供「分析 / 重新分析」按钮 → 调用 POST /repos/{id}/reindex。
- [ ] 仓库详情页
  - [ ] 展示仓库大纲（Markdown 渲染）。
  - [ ] 显示文件 / 模块树（可选）。
- [ ] 仓库组管理页
  - [ ] 创建仓库组（选择多个仓库）。
  - [ ] 查看、编辑已有仓库组。

---

## Milestone 3：MCP Server（只读工具）

### 3.1 MCP Server 框架搭建

- [ ] 在 ackend/api_mcp/server.py 中初始化 MCP Server。
- [ ] 接入当前的 MCP SDK / 协议实现：
  - 注册工具：list_repos / list_repo_groups / sk_repo / sk_repo_group。

### 3.2 工具实现

- [ ] list_repos
  - [ ] 调用 DB 获取仓库列表。
  - [ ] 映射为 MCP 工具输出格式。
- [ ] list_repo_groups
  - [ ] 调用 DB 获取仓库组列表。
  - [ ] 映射为 MCP 工具输出格式。
- [ ] sk_repo
  - [ ] 根据 epo_id 使用 QAService 进行检索 + 大模型调用。
  - [ ] 返回回答文本 + 引用片段信息。
- [ ] sk_repo_group
  - [ ] 根据 group_id 获取对应 epo_ids。
  - [ ] 在多个仓库索引中进行混合检索，调用 QAService。
  - [ ] 返回跨仓分析的回答与引用信息。

### 3.3 与大模型客户端联调

- [ ] 使用一个简单的 MCP Client（或 IDE 插件）测试：
  - [ ] 调用 list_repos / list_repo_groups 确认格式正确。
  - [ ] 在已有仓库上调用 sk_repo，检查回答质量。
  - [ ] 在多仓组上调用 sk_repo_group，检查跨仓引用是否合理。

---

## Milestone 4：问答体验与工程优化

### 4.1 Prompt 与回答质量

- [ ] 梳理 sk_repo 的 Prompt 模板：
  - 清晰告知大模型：回答基于哪个仓库、哪些代码片段。
  - 鼓励给出「在当前代码结构下」的最佳实践建议。
- [ ] 梳理 sk_repo_group 的 Prompt 模板：
  - 明确多仓来源，鼓励大模型做对比、联动设计。
  - 输出中附带「推荐的接口 / 模块边界」等结构化建议。
- [ ] 根据实际使用反馈，对 Prompt 和上下文大小进行迭代调优。

### 4.2 性能与工程优化

- [ ] 支持增量索引（根据仓库更新差异，只更新部分 CodeChunk）。
- [ ] 为向量检索加缓存（同一问题 / 相似问题的加速）。
- [ ] 为 Admin API 与 MCP Server 加日志与基础监控（简单埋点即可）。

### 4.3 前端体验提升

- [ ] 在问答界面中展示「引用的代码片段」，支持展开 / 折叠。
- [ ] 支持点击引用跳转到具体文件、行号（在前端内高亮显示）。
- [ ] 为仓库列表、仓库组列表添加搜索 / 过滤能力。

---

## 验收标准（初版）

- [ ] 至少能完成以下流程：
  - 通过前端添加一个 GitHub 仓库并完成分析。
  - 在前端看到该仓库的大纲。
  - 通过 MCP Client 调用 list_repos 能看到该仓库。
  - 通过 sk_repo 能在该仓库内提出业务 / 代码问题并获得合理回答。
- [ ] 创建一个包含两个以上仓库的仓库组：
  - 通过 MCP Client 调用 list_repo_groups 能看到该仓库组。
  - 通过 sk_repo_group 提出跨仓问题，并在回答中能看到来自多个仓库的引用与建议。
