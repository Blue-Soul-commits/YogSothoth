# LLM / Embedding 配置说明

本项目将「向量检索 + LLM 问答」拆成三层：

1. **模型配置**：描述有哪些模型服务商、各自的 base_url、API Key 环境变量名、chat / embedding 模型名等；
2. **客户端封装**：`EmbeddingClient` / `LLMClient`，根据配置调用实际模型服务接口；
3. **业务层使用**：`VectorStore` 用 embedding 做检索，`LLMOrchestrator` 拼接 prompt，`QAService` 将两者串起来。

本文档说明如何配置模型，以及这些配置在代码中的使用方式。

---

## 1. 配置文件位置与格式

配置文件位于：

- 示例文件：`backend/config/models.example.json`
- 实际使用文件（推荐）：`backend/config/models.json`

如果 `models.json` 不存在，代码将自动回退到 `models.example.json`。

### 1.1 示例结构

```json
{
  "default_provider": "default",
  "providers": {
    "default": {
      "type": "openai-compatible",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "models": {
        "chat": "gpt-4.1-mini",
        "embedding": "text-embedding-3-large"
      }
    }
  }
}
```

- `default_provider`：表示默认使用哪个 provider 的配置。
- `providers`：一个字典，每个 key 是 provider 名称（如 `default`）。
  - `type`：服务商类型，目前实现了：
    - `openai-compatible`：使用 OpenAI 风格的 HTTP 接口：
      - `POST {base_url}/embeddings`
      - 未来可扩展 `POST {base_url}/chat/completions` 等。
  - `base_url`：API 根地址。
  - `api_key_env`：从哪个环境变量读取 API Key。
  - `models.chat`：聊天模型名称（未来 LLM 调用会用到）。
  - `models.embedding`：Embedding 模型名称。

你可以根据实际服务商（OpenAI、兼容接口、私有网关等）修改：

- `base_url`
- `api_key_env`
- `models.chat` / `models.embedding`

只要遵循相同的 JSON 结构即可。

---

## 2. 代码中如何加载配置

文件：`backend/config/models.py`

主要接口：

```python
from backend.config.models import load_models_config

cfg = load_models_config()
provider = cfg.get_default_provider()

print(provider.base_url)
print(provider.api_key_env)
print(provider.api_key)          # 从环境变量读取 API Key
print(provider.models.chat)      # chat 模型名
print(provider.models.embedding) # embedding 模型名
```

`load_models_config()` 会：

1. 优先尝试加载 `backend/config/models.json`；
2. 如不存在，则加载 `backend/config/models.example.json`。

---

## 3. Embedding 管线如何使用配置

### 3.1 EmbeddingClient

文件：`backend/core/embedding_client.py`

```python
from backend.core.embedding_client import EmbeddingClient

client = EmbeddingClient.from_default_config()
vectors = client.embed_texts(["hello world", "another text"])
```

- 内部会调用 `load_models_config()` 获取默认 provider。
- 当前实现支持 `type == "openai-compatible"` 的服务商：
  - 调用 `POST {base_url}/embeddings`，
  - 请求体：`{"model": "<embedding_model>", "input": ["text1", "text2", ...]}`
  - 从返回 JSON 的 `data[*].embedding` 字段解析向量。
- 如果没有配置环境变量（例如 `OPENAI_API_KEY` 未设置），会抛出：
  - `RuntimeError: No API key found in environment variable OPENAI_API_KEY...`

### 3.2 VectorStore：基于 Embedding 的检索

文件：`backend/storage/vector_store.py`

```python
from backend.storage.vector_store import VectorStore
from backend.storage.db import Database
from pathlib import Path

db = Database(Path("data/app.db"))
vs = VectorStore(db)

# 为若干 CodeChunk 生成并存储 embedding（通常在 reindex 时调用）
vs.add_chunks(chunks)

# 用问题做相似度检索
results = vs.search(repo_ids=["my-repo"], query="如何初始化数据库？", top_k=10)
```

- `add_chunks(chunks)`：
  - 从配置中读取 embedding 模型；
  - 对每个 `CodeChunk` 的 `summary + code` 调用 `EmbeddingClient`；
  - 将 `(chunk_id, repo_id, provider, model, embedding_json)` 写入 `chunk_embeddings` 表。
- `search(repo_ids, query, top_k)`：
  - 对 `query` 调用 `EmbeddingClient` 生成 embedding；
  - 从 DB 中取出这些 repo 下所有 chunk 的 embedding；
  - 计算余弦相似度，按 score 排序返回前 `top_k`。

对应的 DB 结构在 `backend/storage/db.py` 中维护：

- `chunk_embeddings(chunk_id, repo_id, provider, model, embedding_json)`

---

## 4. QAService 与 LLMOrchestrator 的协作

文件：`backend/core/qa_service.py` 与 `backend/core/llm_orchestrator.py`

### 4.1 检索 + Prompt 构造

`QAService` 中：

- 使用 `VectorStore` 进行检索：

  ```python
  chunks_with_scores = self._search_chunks(repo_ids, question, top_k_per_repo)
  ```

- 使用 `LLMOrchestrator` 构造 prompt：

  ```python
  from backend.core.llm_orchestrator import LLMOrchestrator

  orchestrator = LLMOrchestrator()
  prompt = orchestrator.build_prompt_for_repo(repo_id, question, chunks)
  ```

- 对外暴露了两个 helper：

  ```python
  qa = QAService(db)

  prompt_repo = qa.build_prompt_for_repo("repo-id", "问题")
  prompt_group = qa.build_prompt_for_repo_group("group-id", "问题")
  ```

这些 prompt 可直接用于调用你配置的 chat 模型，实现「embedding 检索 + LLM 回答」的完整流水线。

### 4.2 真正的 LLM 调用位置

当前项目没有直接在代码中调用 chat 接口，而是：

- 在后端准备好「模型配置 + embedding 检索 + prompt 生成」；
- 留给你在「中控服务 / MCP Client / 前端后台」中根据自己的需要调用 Chat 模型。

伪代码示例：

```python
from backend.storage.db import Database
from backend.core.qa_service import QAService
from backend.config.models import load_models_config

db = Database(Path("data/app.db"))
qa = QAService(db)
cfg = load_models_config()
provider = cfg.get_default_provider()

prompt = qa.build_prompt_for_repo("my-repo", "这个仓库如何初始化？")

# 然后你用任意 HTTP 客户端调用 provider.base_url 对应的 chat API，
# 使用 provider.models.chat 作为模型名，把 prompt 塞进去即可。
```

---

## 5. 使用步骤总结

1. 复制配置文件：
   - 从 `backend/config/models.example.json` 复制为 `backend/config/models.json`；
   - 修改为你的模型服务商参数（base_url、api_key_env、chat/embedding 模型名）。
2. 设置环境变量：
   - 如：`export OPENAI_API_KEY=...` 或在系统环境变量中配置。
3. 重建索引：
   - 调用 HTTP `POST /repos/{id}/reindex`，系统会：
     - 重写 `code_chunks`；
     - 调用 `VectorStore.add_chunks` 生成并写入 embeddings。
4. 发起问答：
   - 方案 A：使用现有 `/qa/repo` / `/qa/repo-group`，返回结构化引用；
   - 方案 B：调用 `QAService.build_prompt_for_repo/group`，再用 chat 模型生成自然语言回答。

这样就完成了从「配置模型」到「embedding 检索 + LLM 问答」的整条链路。
