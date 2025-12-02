# MCP 工具说明

本项目通过 MCP Server 暴露 4 个只读工具，供模型 / MCP 客户端调用。这些工具的业务逻辑实现在
`backend/api_mcp/server.py`，并在 `backend/api_mcp/main.py` 中通过 FastMCP 注册。

## 1. list_repos

- 名称：`list_repos`  
- 功能：列出当前系统中所有已登记的仓库（无论是否已完成索引）。  
- 入参：无  
- 返回：`RepoSummary[]`

每个元素包含：

- `id: string`  
- `name: string`  
- `git_url: string`  
- `default_branch: string` —— 通常为 `"main"`  
- `local_path: string | null` —— 本地 clone 路径（尚未 clone 时为 `null`）  
- `indexed_at: string | null` —— ISO8601 时间字符串，例如 `"2025-12-02T05:49:36.613335"`  
- `summary: string | null` —— 仓库简介（可选）  

典型用途：

- 让大模型/客户端先拿到有哪些 repo，再决定对哪个 `repo_id` 进行提问。  

---

## 2. list_repo_groups

- 名称：`list_repo_groups`  
- 功能：列出当前配置的「仓库组」。  
- 入参：无  
- 返回：`RepoGroupSummary[]`

每个元素包含：

- `id: string`  
- `name: string`  
- `description: string`  
- `repo_ids: string[]` —— 此组包含的仓库 id 列表  
- `indexed_at: string | null` —— 组级别索引时间（当前实现暂未使用，可预留）  

典型用途：

- 让模型知道有哪些仓库组可用，从而在回答「跨仓业务流」问题时，引导用户选择适合的 `group_id`，再通过 `ask_repo_group` 发起问答。  

---

## 3. ask_repo

- 名称：`ask_repo`  
- 功能：在单个仓库内进行问答（当前实现为「向量检索 + LLM 回答」）。  
- 入参：
  - `repo_id: string`  
  - `question: string`  
  - `top_k: int = 10` —— 每次检索最多返回多少代码片段  
  - `session_id?: string` —— 会话 ID（可选，推荐使用 UUID）  
  - `link_history: bool = true` —— 是否串联历史消息  
- 返回：`RepoAnswer`

结构：

- `repo_id: string` —— 目标仓库 id  
- `question: string` —— 原始问题  
- `answer_text: string` —— LLM 给出的自然语言回答  
- `references: Reference[]` —— 本次回答使用到的代码位置  
  - `repo_id: string`  
  - `file_path: string`  
  - `start_line: int`  
  - `end_line: int`  
  - `score: float` —— 相似度分数  
- `session_id?: string` —— 回传调用时使用的会话 ID（如果有）  
- `link_history: bool` —— 回传本次是否启用了历史联动  

多轮对话说明：

- 若提供 `session_id` 且 `link_history == true`：
  - 服务器会从内部的 `conversations` / `conversation_messages` 表中读取最近若干条历史消息；
  - 在构造 LLM `messages` 时，会先推入历史 `user/assistant` 对话，再追加本次的带上下文的 `user` 消息；
  - 同时会把本次用户输入和 LLM 回答也写回到该会话记录中。
- 若 `link_history == false`：
  - 无论是否传入 `session_id`，本次都视为单轮对话，仅使用当前问题 + 检索到的代码片段。

---

## 4. ask_repo_group

- 名称：`ask_repo_group`  
- 功能：在一个「仓库组」中进行跨仓问答。  
- 入参：
  - `group_id: string`  
  - `question: string`  
  - `top_k_per_repo: int = 5` —— 每个仓库最多返回多少代码片段  
  - `session_id?: string` —— 会话 ID（可选，推荐使用 UUID）  
  - `link_history: bool = true` —— 是否串联历史消息  
- 返回：`GroupAnswer`

结构：

- `group_id: string`  
- `question: string`  
- `answer_text: string` —— 聚合多个仓库后的自然语言回答  
- `references: Reference[]` —— 本次回答使用到的代码位置（包含来自不同 repo 的引用）  
  - 字段同 `ask_repo` 的 `Reference` 结构  
- `session_id?: string` —— 回传调用时使用的会话 ID（如果有）  
- `link_history: bool` —— 回传本次是否启用了历史联动  

多轮对话行为与 `ask_repo` 一致：

- 开启 `link_history` 且提供 `session_id`：
  - 服务器会以 scope=`group` 的形式维护会话，并在多次调用之间共享上下文；  
- 关闭 `link_history`：
  - 本次调用只看当前问题与检索结果，不拼接历史消息。  

---

## 5. MCP Server 启动方式（快速参考）

- 入口：`backend/api_mcp/main.py`  
- 使用 FastMCP 注册工具：
  - `list_repos`
  - `list_repo_groups`
  - `ask_repo`
  - `ask_repo_group`
- 本地调试：

```bash
python -m backend.api_mcp.main      # 使用 stdio 作为 transport
# 或者：
mcp dev backend/api_mcp/main.py
mcp run backend/api_mcp/main.py
```

不同 MCP 客户端可以选择各自支持的 transport 模式，但从工具 schema 的角度，上述 4 个工具已经可以直接注册与调用。
