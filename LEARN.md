# LEARN.md — MCP Chat CLI

> A guide to understanding this project deeply — not just what it does, but *why* it works the way it does, what you can learn from it, and what traps to avoid.

---

## What Is This, Really?

At its surface, this is a command-line chat interface for Claude AI. But zoom out, and it's something more interesting: a working example of the **agentic loop pattern** — the architectural blueprint that powers every modern AI assistant that can actually *do things*, not just talk.

Think of it like this: a basic chatbot is a parrot. It hears you, it responds. This project is more like a chess player — it can hear your request, decide it needs to look something up, look it up, think about what it found, potentially look up something else, and *then* answer you. That back-and-forth between the AI and its tools is the heart of what makes "AI agents" different from plain LLMs.

---

## The Big Picture

```
You type something
    → CLI (prompt-toolkit) captures it elegantly
    → CliChat preprocesses: pulls in @documents, resolves /commands
    → Chat sends message to Claude with available tools described
    → Claude thinks... and might ask to use a tool
    → ToolManager executes the tool via an MCP server
    → Result goes back to Claude
    → Claude thinks again... maybe requests another tool
    → Eventually: Claude says "I'm done" → you see the answer
```

That middle loop — **LLM → tool request → execute → back to LLM** — runs until Claude signals it's satisfied. This is the **agentic loop**, and almost every serious AI application is built around it.

---

## The Tech Stack (and Why Each Piece Was Chosen)

### Python + asyncio
The entire app is async (`async/await` everywhere). This wasn't an aesthetic choice — it's a necessity. When you're waiting for Claude to respond, you don't want your app to freeze and block everything. Async lets the event loop do other things while waiting for the network. It also maps cleanly onto MCP's own async protocol.

### prompt-toolkit
This is what makes the CLI feel *good* — autocomplete that pops up when you type `@` or `/`, history you can scroll through, colored output. The standard Python `input()` function would've been fine for a toy, but prompt-toolkit makes it feel like a real tool. It's the difference between Notepad and VS Code. Worth knowing for any serious CLI project.

### Anthropic SDK (via Google Vertex AI)
Instead of calling Anthropic's API directly, this project routes through **Google Cloud's Vertex AI**. Why? Enterprise deployments often require this for billing, compliance, and data residency reasons. The `AnthropicVertex` client handles the routing transparently — you write the same code, it just hits a different endpoint. The tradeoff: you need GCP credentials set up, which adds operational complexity.

### MCP (Model Context Protocol)
This is the most architecturally significant piece. MCP is a protocol (like HTTP, but for AI tool use) that lets Claude talk to "servers" that expose tools, resources, and prompts. Instead of hardcoding every capability into your app, you define servers — each a standalone process — and Claude can discover and use their tools dynamically.

The analogy: MCP is to AI tools what USB is to peripherals. You don't hardcode your laptop to work with one specific keyboard. You implement the USB standard, and any USB device just works. MCP does the same for AI capabilities.

---

## Code Architecture: The Layers

The project has a clean layered design. Each layer has one job:

| Layer | File(s) | Job |
|-------|---------|-----|
| Entry Point | `main.py` | Wire everything together, start the event loop |
| CLI | `core/cli.py` | Capture user input beautifully (autocomplete, history) |
| Chat Logic | `core/cli_chat.py` | Pre-process input (resolve @docs, /commands) |
| Agent Loop | `core/chat.py` | The core LLM↔tool loop |
| LLM Wrapper | `core/claude.py` | Talk to Claude via Vertex AI |
| Tool Manager | `core/tools.py` | Aggregate tools from MCP servers, execute them |
| MCP Client | `mcp_client.py` | Speak the MCP protocol to a server process |
| MCP Server | `mcp_server.py` | A server that provides document tools and resources |

The beauty here is that each file can be read and understood in isolation. `core/chat.py` doesn't know or care whether tools come from MCP, a REST API, or a hardcoded function. It just calls `tool_manager.execute(name, args)` and gets a result back. That's good separation of concerns.

---

## The Agentic Loop (The Most Important Thing to Understand)

Open `core/chat.py`. The `run()` method is the beating heart of this project:

```python
while True:
    response = await self.claude.send(messages, tools)

    if response.stop_reason == "end_turn":
        break  # Claude is done, return the answer

    if response.stop_reason == "tool_use":
        # Claude wants to use a tool
        tool_results = await self.tools.execute_all(response.tool_calls)
        # Add results back to message history
        messages.append(tool_results)
        # Loop again — Claude now has the results
```

This loop is what makes the system "agentic." The LLM isn't just generating one response — it's *reasoning* across multiple turns, using tools as extensions of its thinking. If you understand this loop, you understand 80% of how modern AI agents work.

**The gotcha here:** you must cap the number of loop iterations in production. An LLM can theoretically loop forever if it keeps requesting tools. This project doesn't add a hard cap, which is fine for a learning project — but something to remember when building for real users.

---

## The @ and / Syntax: A UX Design Decision

When you type `@my_document`, the app doesn't make Claude search for that document. Instead, `core/cli_chat.py` intercepts the message *before* it reaches Claude, fetches the document content via MCP, and injects it directly into the prompt as context.

Why? Two reasons:
1. **Reliability** — Document retrieval via tool calls adds latency and an extra loop. Direct injection is faster.
2. **Clarity** — The user is explicitly saying "include this document." Claude doesn't need to decide whether to retrieve it.

This is a subtle but important UX principle: give the user direct control over context, rather than asking the AI to infer what context it needs.

---

## MCP in Practice: Two Roles, One Protocol

This project uses MCP in *both* directions:
- `mcp_server.py` — **as a server**, exposing document tools and resources *to* Claude
- `mcp_client.py` — **as a client**, connecting *to* those servers and translating MCP responses into Anthropic-compatible tool results

This dual role is unusual and educational. Most apps only use one side. Seeing both helps you understand the full protocol flow.

When `main.py` boots, it:
1. Starts the MCP document server as a subprocess
2. Creates an `MCPClient` that connects to it via stdin/stdout (the "stdio" transport)
3. Lists available tools from the server
4. Makes those tools available to Claude

The subprocess-over-stdio design is elegant — each MCP server is an independent process. They can be written in any language. They crash without taking down your main app. This is the Unix philosophy applied to AI tooling.

---

## Async Context Management: The AsyncExitStack

In `mcp_client.py`, you'll see `AsyncExitStack`. This is an underappreciated Python pattern for managing multiple async resources (like open connections) that all need to be cleaned up when you're done.

Think of it like a stack of dishes. You load dishes (resources) onto the stack as you open connections. When you exit, Python automatically washes them all in reverse order. Without it, you'd need nested `async with` blocks — ugly and error-prone.

If you're building any app that manages multiple async connections (databases, MCP servers, WebSockets), learn `AsyncExitStack`. It'll save you.

---

## Lessons Learned and Pitfalls to Avoid

### 1. MCP Message Type Mismatch
When converting MCP `PromptMessage` objects to Anthropic's `MessageParam` format, there's a subtle trap: MCP returns content as either a plain dict *or* a Pydantic model object, depending on context. If you just call `.model_dump()` on everything, you'll crash when a dict shows up.

The fix in this codebase:
```python
content = msg.content if isinstance(msg.content, dict) else msg.content.model_dump()
```

Lesson: **always check what types a library actually returns at runtime**, not just what the type hints say. Type hints are aspirational; runtime behavior is truth.

### 2. Vertex AI vs. Direct Anthropic API
The `AnthropicVertex` client requires a GCP project and region. If you try to run this without proper GCP credentials configured (`gcloud auth application-default login`), you'll get cryptic auth errors. The `.env` file needs `GCP_PROJECT_ID` and `GCP_REGION` — forgetting either causes silent failures that look like network errors.

### 3. The Agentic Loop Needs a Safety Valve
As mentioned above: in production, always add `max_iterations` to any agentic loop. An LLM in a bad state can generate tool call after tool call, burning tokens and money. Add a guard.

### 4. MCP Servers Start as Subprocesses
When `main.py` runs `python mcp_server.py` as a subprocess, that server lives and dies with your main process. If the server crashes, the MCP client's connection breaks. The app doesn't have crash-recovery logic here — something to add if building on top of this.

### 5. Document Store Is In-Memory
`mcp_server.py` stores documents in a plain Python dict. Restart the server and all documents are gone. For a CLI tool you use locally and restart often, this is fine. For anything stateful or shared, you'd want a real store (SQLite, Redis, a file).

---

## New Things You Can Learn From This Project

### The Anthropic Tool Use API
Claude's tool use follows a specific pattern: you describe tools in a schema (name, description, input JSON Schema), Claude returns a `tool_use` block when it wants to call one, you run the tool and return a `tool_result` block, and Claude continues. This project implements that loop cleanly in `core/chat.py` and `core/tools.py`. Reading these is a great primer on the raw Anthropic API.

### FastMCP for Rapid Server Development
`mcp_server.py` uses `FastMCP`, which dramatically reduces boilerplate for writing MCP servers. Decorators like `@mcp.tool()` and `@mcp.resource()` let you expose functions and data to Claude with minimal setup. If you ever need to give Claude access to a custom data source or API, FastMCP is the fastest path.

### prompt-toolkit for Professional CLIs
The completers in `core/cli.py` show how to build context-aware autocomplete. The `WordCompleter` and custom completer classes give users a guided, IDE-like experience in the terminal. If you're building developer tools, this library is worth deep-diving.

### The "Thin Wrapper" Pattern for LLM Clients
`core/claude.py` is intentionally thin — it just wraps the Anthropic client and handles one specific concern (sending messages with tools). This is good design: if Anthropic changes their API, there's exactly one place to update. If you want to swap Claude for GPT-4, you only touch this file.

---

## How an Experienced Engineer Thinks About This Codebase

A few meta-lessons about how this project was built:

**Prefer composition over god objects.** No single class does everything. `Chat` knows about the loop. `CliChat` knows about pre-processing. `Claude` knows about the API. Each is small and testable in isolation.

**Separate what changes from what stays the same.** The agentic loop logic in `chat.py` is stable — it barely changes. The tool implementations in MCP servers change constantly. Keeping them separate means you can evolve your tools without touching the core loop.

**Make the right thing easy.** The `@` syntax for documents is a great example. It would've been technically correct to make users ask Claude to retrieve documents. But making retrieval *explicit and easy* via `@` syntax reduces cognitive load and makes the tool more predictable.

**Error messages are part of the interface.** When tools fail, this codebase returns the error *to Claude* rather than crashing the app. Claude can then explain the error to the user in natural language. This is a small decision with big UX impact — the user never sees a raw Python traceback.

---

## Future Directions (If You Build on This)

- **Persistent storage** for the document server (SQLite would be perfect)
- **Multiple Claude models** selectable at runtime
- **Streaming responses** — Claude can stream tokens, making responses feel faster
- **Tool call limits** — add `max_tool_calls` to the agentic loop
- **Rich formatting** — use `rich` library for better terminal output
- **Session logging** — save chat history to disk for later review

---

*This project is a working foundation for serious AI CLI tooling. The patterns here — agentic loops, MCP integration, layered architecture — are the same patterns powering production AI applications at scale. Learn them here, and they'll serve you everywhere.*
