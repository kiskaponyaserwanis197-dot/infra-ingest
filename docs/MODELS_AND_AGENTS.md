# 模型、隐私和 Agent 接入说明

这份文档说明 `infra-ingest` 当前到底什么时候会调用大模型、怎么切换模型、怎么接本地私有模型，以及 Agent 应该怎么把它当作工具使用。

## 当前可靠性边界

当前项目可以稳定做这些事：

- 本地文件、URL、音视频资料摄入。
- 本地 Whisper 转写。
- 文档转 Markdown。
- 生成 Markdown 笔记、manifest、segments、graph、SQLite 索引。
- 可选调用 OpenAI-compatible LLM 生成结构化笔记。
- 基于本地行情 CSV 做初步事件研究。

当前项目还不是这些东西：

- 不是完整 Agent 平台。
- 不是正式量化基金回测平台。
- 不是权限、审计、多人协作的数据平台。
- 不是保证投资结论正确的系统。

建议用法：把它当作“研究资料进入本地知识库，并做初步验证”的工具，而不是最终投研判断器。

## 什么时候会调用 LLM

是否调用 LLM 由两个条件决定：

1. 命令没有带 `--no-llm`。
2. 环境里有 `LLM_API_KEY` 或 `OPENAI_API_KEY`。

也就是说：

```bash
./run ingest -i examples/input.txt --no-llm
```

不会调用任何 LLM。

```bash
./run ingest -i examples/input.txt --env .env
```

如果 `.env` 里有 `LLM_API_KEY`，就会调用 LLM。

## 哪些资料会进入 LLM

只要启用了 LLM，项目会先把输入转成 `raw_text`，再把这个文本发给 LLM。

会进入 LLM 的内容包括：

- `.txt`、`.md`、`.markdown`：原文内容。
- `.pdf`、`.docx`、`.pptx`、`.xlsx`、`.csv`、`.json`、`.html` 等：转成 Markdown 后的文本。
- `.mp3`、`.wav`、`.m4a`、`.mp4`、`.mov` 等：本地 Whisper 转写后的文字。
- URL：先由 `yt-dlp` 下载/提取音频，再本地转写，最后把转写文本送给 LLM。

不会直接进入 LLM 的内容：

- 原始二进制文件本身。
- `.segments.json`、`.manifest.json`、`.backtest.json` sidecar。
- SQLite 数据库文件。

但是要注意：如果文档里有敏感内容，并且启用了远程 LLM API，提取出的文本会被发送到远程模型服务。

## 远程 API 模型

远程模型通过 OpenAI-compatible Chat Completions API 调用。

关键代码：

- `src/infra_ingest/llm_client.py`：真正调用 `/chat/completions`。
- `src/infra_ingest/pipeline.py`：决定是否调用 LLM。
- `src/infra_ingest/prompts.py`：系统 prompt。
- `src/infra_ingest/structured_note.py`：解析 JSON 并渲染 Markdown。
- `src/infra_ingest/rag.py`：资料库问答时调用 LLM。
- `app/whisper_gui.py`：GUI 写临时 env 后调用 CLI。

DeepSeek 示例：

```env
LLM_API_KEY=你的_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=120
LLM_TEMPERATURE=0.3
```

OpenAI 示例：

```env
LLM_API_KEY=你的_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT=120
LLM_TEMPERATURE=0.3
```

SiliconFlow 或其他 OpenAI-compatible 服务也一样，只要替换 `LLM_BASE_URL` 和 `LLM_MODEL`。

## 本地私有模型

本地模型也走 OpenAI-compatible API，只是 `LLM_BASE_URL` 指向本机。

Ollama 示例：

```env
LLM_API_KEY=local
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:14b
LLM_TIMEOUT=300
LLM_TEMPERATURE=0.2
```

LM Studio 示例：

```env
LLM_API_KEY=local
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=local-model
LLM_TIMEOUT=300
LLM_TEMPERATURE=0.2
```

vLLM 示例：

```env
LLM_API_KEY=local
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-14B-Instruct
LLM_TIMEOUT=300
LLM_TEMPERATURE=0.2
```

本地模型的 API key 通常不会被校验，但当前代码要求这个变量非空，所以可以写 `local`。

## 模型切换方式

推荐为不同模型准备不同 env 文件：

```text
.env.deepseek
.env.openai
.env.local
```

运行时切换：

```bash
./run ingest -i examples/input.txt --env .env.deepseek
./run ingest -i examples/input.txt --env .env.local
```

GUI 里可以在 LLM 区域填写：

- API Key
- Base URL
- 模型名

GUI 底层仍然调用同一套 CLI。

## Fallback 模型

可以配置主模型失败后自动切备用模型：

```env
LLM_API_KEY=主模型_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

LLM_FALLBACK_API_KEY=备用模型_key
LLM_FALLBACK_BASE_URL=https://api.openai.com/v1
LLM_FALLBACK_MODEL=gpt-4.1-mini
LLM_FALLBACK_TIMEOUT=120
```

## 私密资料建议

如果资料私密，优先用这三种方式：

1. 完全不调用 LLM：

```bash
./run ingest -i private.pdf --no-llm
```

2. 使用本地私有模型：

```bash
./run ingest -i private.pdf --env .env.local
```

3. 只把输出 Markdown 和 manifest 留在本地，不上传 `.infra_ingest/`、`outputs/`、原始资料和数据库。

## Agent 怎么接入

当前项目还没有内置“自主 Agent 编排器”，但已经很适合作为 Agent 的工具调用。

最简单方式：让 Agent 调 CLI。

```bash
./run ingest -i <file-or-url> -o ./outputs --material-type research_report
./run search "毛利率"
./run ask "这批资料里有哪些关于价格战的风险？"
./run runs
```

如果接 LangChain、AutoGen、CrewAI、OpenAI Agents SDK 或 MCP，建议把这些 CLI 包成工具：

- `ingest_source(input, output_dir, material_type, no_llm)`
- `search_library(query, filters)`
- `ask_library(question, filters)`
- `list_research_runs(limit)`

Agent 负责选择什么时候调用这些工具，`infra-ingest` 负责执行可复现处理。

下一步如果要更正式，可以新增：

- `src/infra_ingest/agent_tools.py`：Python 工具函数层。
- `src/infra_ingest/mcp_server.py`：MCP server，让 Claude/Codex/其他 Agent 直接调用。
- `src/infra_ingest/api_server.py`：HTTP API，用于网页前端或团队内部服务。

