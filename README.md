# MCP Chat

> This project is based on and modified from the [Anthropic online learning course](https://anthropic.skilljar.com/). The original used Anthropic's Claude via Google Vertex AI; this version has been migrated to use the OpenAI API.

MCP Chat is a command-line interface application for interactive AI chat, powered by OpenAI models. It supports document retrieval via `@mentions`, command-based prompts via `/commands`, and extensible tool integrations through the MCP (Model Context Protocol) architecture.

## Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

### Step 1: Configure environment variables

Create or edit the `.env` file in the project root:

```
OPENAI_API_KEY="sk-..."       # Your OpenAI API key
OPENAI_MODEL="gpt-4o-mini"    # Or any other OpenAI model (e.g. gpt-4o)
USE_UV=1                       # Set to 0 if not using uv
```

### Step 2: Install dependencies

#### Option 1: Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

1. Install uv if not already installed:

```bash
pip install uv
```

2. Install dependencies:

```bash
uv sync
```

3. Run the project:

```bash
uv run main.py
```

#### Option 2: Using plain pip

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install openai python-dotenv prompt-toolkit "mcp[cli]>=1.8.0"
```

3. Run the project:

```bash
python main.py
```

## Usage

### Basic Chat

Type your message and press Enter:

```
> What is the capital of France?
```

### Document Retrieval

Use `@` followed by a document ID to include a document's content in your query:

```
> Summarize @deposition.md
```

Documents are injected directly into the prompt — no extra tool call needed.

### Commands

Use `/` to run predefined prompt commands defined in the MCP server:

```
> /summarize deposition.md
```

Press `Tab` to autocomplete available commands and document IDs.

### Loading Additional MCP Servers

Pass extra server scripts as arguments when starting the app:

```bash
uv run main.py my_custom_server.py
```

## MCP Inspector

MCP Inspector is a browser-based tool for inspecting and testing your MCP server — you can browse available tools, resources, and prompts, and call them interactively without running the full app.

To launch it:

```bash
uv run mcp dev mcp_server.py
```

Then open the URL shown in the terminal (usually `http://localhost:5173`) in your browser.

### Tips for using the Inspector

- When calling `read_doc_contents`, use the full filename including extension as the `doc_id`, e.g. `deposition.md`.
- Available document IDs are: `deposition.md`, `report.pdf`, `financials.docx`, `outlook.pdf`, `plan.md`, `spec.txt`.

### Why edits don't appear in `mcp_server.py`

You might notice that after calling `edit_document` in the Inspector, the `docs` dictionary inside `mcp_server.py` doesn't change. This is expected — and understanding why is a useful lesson.

The `docs` dict lives in **memory (RAM)**, not in the file. When the server starts, Python reads `mcp_server.py` and loads `docs` into memory. `edit_document` modifies that in-memory copy, which is why a subsequent `read_doc_contents` call returns the updated content. But the source file itself is never touched — it's just the recipe book. The cook writes on a notepad, not back into the book.

When you restart the server, the notepad is thrown away and `docs` is reloaded from the original source file — so all edits disappear.

This is a known limitation of the current design. If you want edits to persist across restarts, `docs` would need to be backed by a real store (a JSON file, SQLite, etc.) rather than an in-memory dict.

### End-to-end testing

The fastest way to verify the whole system is working is to run through these five cases in order:

**1. Basic chat** — confirms OpenAI connectivity
```
> What is 1 + 1?
```

**2. `@` document injection** — confirms MCP server is running and document content is injected into the prompt
```
> What is @deposition.md about?
```

**3. Tool use** — confirms the agentic loop, ToolManager, and MCP tool execution are all working
```
> Use the read_doc_contents tool to read report.pdf and tell me what it says.
```

**4. Tool use + edit** — confirms multi-turn tool use and in-memory edits
```
> Use edit_document to change the word "condenser" to "cooling" in report.pdf, then read it back to confirm.
```

**5. `/` command** — confirms MCP Prompt retrieval and the full command pipeline
```
> /format financials.docx
```

Each case exercises a different layer of the stack. If all five pass, the entire end-to-end flow is verified.

### What happens during `/format`

The `/format` command is a good illustration of how all the layers work together:

1. `_process_command()` in `core/cli_chat.py` detects the `/` prefix and fetches the `format` prompt from the MCP server
2. The prompt instructs the model to reformat the document using Markdown and use the `edit_document` tool to save the result
3. The model calls `edit_document` — the agentic loop in `core/chat.py` detects `finish_reason == "tool_calls"` and executes the tool
4. The result is added back to the message history, the loop runs again, and the model outputs the final formatted document

**One thing to be aware of:** if the original document is very short (like `financials.docx`, which is just one sentence), the model may invent plausible-sounding content — budget figures, categories, etc. — that doesn't exist in the source. This is normal LLM behaviour: when information is sparse, the model fills in what seems reasonable rather than saying "I don't know."

In real applications, guard against this by adding an explicit instruction to the prompt: *only use information already present in the document, do not add anything new.*

---

## Development

### Adding New Documents

Edit the `docs` dictionary in `mcp_server.py` to add new documents.

### Adding New MCP Servers

Any Python script that implements the MCP protocol can be passed as an argument to `main.py`. Each server runs as its own subprocess and exposes its tools automatically to the model.

### Linting and Type Checks

No lint or type checks are currently configured.

---

## 同場加映：uv 和 venv 是什麼？

### 先從一個比喻開始

想像你是一個廚師，你有很多食譜（專案），每個食譜需要不同的食材（套件）。

問題來了：食譜 A 需要「醬油 1.0 版」，食譜 B 需要「醬油 2.0 版」——這兩個版本的 API 不相容。如果你家廚房（電腦）只有一瓶醬油，你就麻煩了。

**venv 和 uv 都是為了解決這個問題。**

### venv 是什麼？

`venv` 是 Python 內建的工具，用來建立「虛擬環境」。

虛擬環境的本質很簡單：**就是在你的專案資料夾裡，複製一套獨立的 Python 執行空間**，讓這個專案裝的套件跟其他專案完全隔離，互不干擾。

```bash
python -m venv .venv        # 建立虛擬環境（產生 .venv 資料夾）
source .venv/bin/activate   # 「進入」這個環境
pip install openai          # 現在 openai 只裝在這個專案裡
```

你在這個專案裝的 `openai`，不會影響你電腦上的其他專案。這就是「隔離」。

`.venv` 資料夾裡裝的就是這套獨立的 Python 和所有套件，這也是為什麼它通常有幾百 MB——裡面真的有一份完整的執行環境。

### 那 uv 又是什麼？

`uv` 是一個更現代的工具，用來**取代** `pip` + `venv` 的組合。

可以把它想成：`venv` + `pip` + 套件版本鎖定，全部打包成一個更快、更聰明的工具。

```bash
# 以前的做法（三個步驟）
python -m venv .venv
source .venv/bin/activate
pip install openai

# uv 的做法（一個步驟）
uv add openai
```

### uv 好在哪？

**1. 快得離譜**
`pip` 安裝套件是一個一個下載、一個一個安裝。`uv` 是用 Rust 寫的，幾乎是平行處理，速度快 10~100 倍。

**2. 自動管理 `.venv`**
你不需要手動 `python -m venv .venv` 再 `activate`。執行 `uv run main.py`，它會自動找到（或建立）正確的虛擬環境然後在裡面執行。

**3. lockfile（鎖定版本）**
專案裡的 `uv.lock` 檔案記錄了**每一個套件的精確版本**。這樣做的好處是：你今天在自己電腦跑得好好的，三個月後換一台電腦、或者交給同事，執行 `uv sync` 就能還原**完全一樣的環境**，不會出現「在我電腦上沒問題」的悲劇。

### 一張圖總結

```
你的電腦
│
├── 專案 A/
│   └── .venv/          ← 專案 A 的獨立環境
│       └── openai 1.0
│
├── 專案 B/
│   └── .venv/          ← 專案 B 的獨立環境
│       └── openai 2.0
│
└── 系統 Python         ← 盡量不要在這裡裝東西
```

每個 `.venv` 都是一個獨立的泡泡，互不干擾。`uv` 就是幫你管理這些泡泡的現代工具。

### 實際上你只需要記住這幾個指令

| 情境 | 指令 |
|------|------|
| 第一次拿到專案，安裝所有依賴 | `uv sync` |
| 新增一個套件 | `uv add openai` |
| 移除一個套件 | `uv remove anthropic` |
| 執行程式 | `uv run main.py` |

不需要手動 `activate`，不需要管 `pip`，`uv` 全包了。
