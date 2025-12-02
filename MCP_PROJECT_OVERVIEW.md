# MCP 多仓库代码助手（只读 MCP 版）

## 1. 背景与目标

本项目希望实现一套「多仓库代码知识库 + 问答系统」，核心能力包括：

- 支持从 GitHub 等来源克隆多个代码仓库，并在本地统一管理。
- 对单个仓库进行静态分析，生成结构化的大纲（Markdown），并构建向量索引。
- 支持对「单个仓库」和「仓库组」进行自然语言问答与编码建议，尤其是跨多个仓库联动时的最佳实践指导。

**重要设计原则：**

- **MCP Server 只提供「只读」能力给大模型使用**：仅暴露查询与问答工具。
- 仓库的添加、更新、重建索引、仓库组管理等「写操作」全部通过 Web 前端 + HTTP 管理 API 完成。
- MCP 工具与 HTTP 管理 API 共用同一套核心代码分析与问答逻辑（Core Library），避免重复实现。

---

## 2. 系统角色与边界

整个系统分为四个主要角色：

### 2.1 Core Library（代码分析内核）

- 负责所有与代码分析相关的核心逻辑：
  - 仓库本地路径管理、Git 克隆 / 更新（供 HTTP 管理 API 调用）。
  - 代码解析与切分、Embedding 构建、向量检索。
  - 仓库大纲（Markdown）生成。
  - 问答服务 QAService：给定 repo/group + question → Answer。
- 被以下两个上层复用：
  - HTTP 管理 API（前端用，包含写操作）。
  - MCP Server（大模型用，只暴露读操作）。

### 2.2 HTTP 管理 API（Admin API）

- 面向前端页面，负责所有「写入」和管理操作：
  - POST /repos：根据 GitHub URL 克隆 / 更新仓库。
  - POST /repos/{id}/reindex：重建索引和大纲。
  - GET /repos / GET /repo-groups：给前端列表展示。
  - POST /repo-groups / PATCH /repo-groups/{id}：创建 / 修改仓库组。
- 可选地提供 HTTP 版问答接口（复用 QAService）：
  - POST /qa/repo
  - POST /qa/repo-group
- **不**直接被 MCP 使用；MCP Client 面向的是 MCP Server 的工具接口。

### 2.3 MCP Server（Python MCP 服务）

- 面向大模型 / MCP Client，只暴露 **只读工具**：
  - list_repos
  - list_repo_groups
  - sk_repo
  - sk_repo_group
- MCP Server 自身不执行克隆 / 修改仓库组等写操作，所有写操作都由 Admin API 完成。
- MCP Server 内部通过 Core Library 访问本地数据库和向量索引，构造大模型调用上下文。

### 2.4 前端 Web 页面

- 面向用户的人机界面：
  - 仓库管理：添加仓库（Git URL）、查看状态、触发分析 / 重新索引。
  - 仓库组管理：创建仓库组、将多个仓库加入同一组。
  - 问答界面：
    - 单仓问答：选中一个仓库，与该仓库上下文进行对话。
    - 仓库组问答：选中一个仓库组，对该组内所有仓库进行联动问答。
- 前端与 HTTP 管理 API 通信，不直接调用 MCP 工具。
  - 如果需要，也可以由一个「中控服务」同时作为 MCP Client 和前端后端，将 MCP 答案转给前端显示。

---

## 3. MCP 暴露的工具设计

### 3.1 list_repos

- 目的：让大模型知道当前有哪些可用仓库，并能在回答中引用仓库标识。
- 输入：
  - 可选过滤：language?, 	ag?, keyword?（可后续扩展）。
- 输出：仓库对象列表，例如：
  - epo_id: string
  - 
ame: string
  - git_url: string
  - default_branch: string
  - indexed_at: datetime（最后索引时间）
  - summary: string（一两句话的仓库简介）

### 3.2 list_repo_groups

- 目的：让大模型了解当前的仓库组配置，支持多仓联动问答。
- 输出：仓库组列表，例如：
  - group_id: string
  - 
ame: string
  - description: string
  - epo_ids: string[]
  - indexed_at: datetime

### 3.3 sk_repo

- 目的：在 **单个仓库** 内进行问答与代码建议。
- 典型问题类型：
  - 「这个库有没有实现 xxx 功能？」
  - 「如果我要在这个库里实现 xxx 功能，应该在哪些模块改动？」
  - 「这个函数是怎么实现的？有没有最佳实践改写建议？」
- 输入：
  - epo_id: string
  - question: string
  - 可选：	op_k: int = 10, nswer_lang: "zh" | "en" 等。
- 内部流程（通过 Core Library 完成）：
  1. 在该仓库的向量索引中检索与问题最相关的代码片段 / 文档片段。
  2. 读取该仓库的大纲（Markdown）作为辅助背景。
  3. 将问题 + 片段 + 大纲摘要构造 Prompt，调用大模型。
  4. 返回回答文本以及引用的代码片段信息（文件路径、符号名、行号等）。
- 输出示例字段：
  - nswer_text: string
  - code_suggestions[]（包含建议的代码 / 重构方案）
  - eferences[]（epo_id, ile_path, symbol, start_line 等元信息）

### 3.4 sk_repo_group

- 目的：在 **一个仓库组** 内做多仓联动问答。
- 典型问题类型：
  - 「A、B 两个仓库如何协同提供某个业务能力？」
  - 「如果把 A 的功能迁移到 B，应该怎么设计接口？」
  - 「在这个仓库组里，哪些仓库有实现类似的工具模块？」
- 输入：
  - group_id: string
  - question: string
  - 可选：	op_k_per_repo: int, nswer_lang 等。
- 内部流程：
  1. 查询该 group_id 对应的 epo_ids。
  2. 在所有这些仓库的向量索引中进行检索，记录每个片段的来源仓库。
  3. 在 Prompt 中明确标注每个片段属于哪个仓库。
  4. 调用大模型，让其进行跨仓对比、联动设计与代码建议。
- 输出示例字段：
  - nswer_text: string
  - per_repo_references[]（按仓库聚合的引用片段列表）
  - 可选：design_suggestions[]（如建议的跨仓接口、适配层等）

---

## 4. 典型工作流程（端到端）

### 4.1 由前端添加并分析仓库

1. 用户在前端输入 GitHub 仓库 URL，点击「添加仓库」。
2. 前端调用 Admin API：POST /repos。
3. Admin API 调用 Core Library 的 RepoManager：
   - 克隆 / 更新 Git 仓库到本地；
   - 注册元数据到数据库，生成唯一的 epo_id。
4. 用户在前端点击「分析仓库」：
   - 调用 POST /repos/{id}/reindex 触发索引：
     - 代码扫描、切分；
     - 生成 Embedding、写入向量库；
     - 调用大模型生成仓库大纲 Markdown。

### 4.2 单仓问答（MCP 工具）

1. 大模型客户端（例如一个 IDE 插件、或者你自己的中控服务）使用 MCP 的 list_repos 获取仓库列表。
2. 用户选择一个具体仓库（或通过文字指定），然后发问。
3. 客户端调用 MCP 工具 sk_repo(repo_id, question)。
4. MCP Server 通过 Core Library 检索相关片段，构造 Prompt，调用大模型。
5. MCP 返回回答和引用信息，客户端将其展示给用户。

### 4.3 仓库组问答（MCP 工具）

1. 用户在前端通过 Admin API 创建仓库组（例如选择 A、B、C 三个仓库构成一组）。
2. 大模型客户端通过 list_repo_groups 获取可用仓库组。
3. 用户选定一个 group_id，提出跨仓问题。
4. 客户端调用 MCP 工具 sk_repo_group(group_id, question)。
5. MCP 在组内各仓库的索引中检索，并生成跨仓分析答案。

---

## 5. 非目标与约束

- MCP Server 不负责：
  - 直接克隆 Git 仓库；
  - 创建 / 删除 / 修改仓库及仓库组；
  - 管理用户权限等。
- 所有「写操作」统一由 HTTP 管理 API + 前端完成，MCP 只负责读与问答逻辑。
- 初版将聚焦于：
  - 主流语言（Python / JS / TS / Go 等）的结构化索引；
  - 较好的问答质量与代码建议；
  - 简单易维护的架构，便于后续扩展更多语言与功能。

---

## 6. 后续扩展方向（可选）

- 支持更多语言与框架（Java、C#、Rust 等）的解析与索引。
- 支持增量索引（根据 Git diff 局部更新 Embedding）。
- 在前端中集成「跳转到代码位置」「一键生成 PR 草案」等更深度的工程能力。
- 扩展 MCP 工具的资源类型，例如暴露只读的 Markdown 大纲、文件结构树等。
