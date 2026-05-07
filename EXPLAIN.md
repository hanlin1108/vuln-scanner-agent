# EXPLAIN.md — Understanding the Vulnerability Scanner Agent

> This file teaches you exactly how this project works, what every piece of code does, and why it was built this way. Read this alongside the code.

---

## 🗺️ Big Picture: What Does This Project Do?

This project is a **multi-agent AI system** that automatically scans a codebase for security vulnerabilities. Instead of one AI doing everything, we have **4 specialized AI agents** working as a team:

```
You type: "Scan /path/to/my/project for vulnerabilities"
                        ↓
        ┌───────────────────────────────────┐
        │       SequentialAgent             │  ← the "manager"
        │  (runs everything in order)       │
        └──────────┬────────────────────────┘
                   │
          ┌────────▼────────┐
          │    Planner       │  Step 1: "Which files should we look at?"
          └────────┬─────────┘
                   │
          ┌────────▼────────────────────────┐
          │       LoopAgent                  │  Step 2: "Keep reviewing until good"
          │  ┌──────────┐  ┌──────────┐     │
          │  │ Reviewer │→ │  Critic  │     │  ← loop up to 3 times
          │  └──────────┘  └──────────┘     │
          └────────┬─────────────────────────┘
                   │
          ┌────────▼────────┐
          │    Reporter      │  Step 3: "Write the final report"
          └─────────────────┘
                   ↓
        Final markdown vulnerability report
```

**Why 4 agents instead of 1?**
- Each agent is an expert at ONE thing → better quality
- The critic catches what the reviewer missed → fewer false negatives
- The loop means the review improves over time → more thorough
- The reporter formats everything cleanly → professional output

---

## 📁 File-by-File Breakdown

### `vuln_scanner/tools.py` — The "Hands" of the Agents

Tools are Python functions that agents can call to interact with the real world. Without tools, the AI can only think — tools let it actually DO things.

```python
import os
from pathlib import Path
```
`os` and `pathlib` are built-in Python libraries for working with files and directories.

---

```python
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".php", ".rb", ".c", ".cpp"}
```
We only care about programming languages that can have vulnerabilities. We skip things like `.txt`, `.md`, `.json` config files.

---

```python
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
```
These directories contain generated or third-party code — not our code. We skip them to save time and focus on what matters.

---

```python
def list_files(target_path: str) -> str:
    """
    Scans a directory and returns a list of code files.
    ...
    """
```

**What it does:** Walks every folder and subfolder of `target_path`, finds all code files, and returns their paths as a single text string (one path per line).

**Why return a string?** The AI receives tool results as text. A string is easy for the AI to read and reason about.

```python
    found = []
    root = Path(target_path)

    if not root.exists():
        return f"Error: path '{target_path}' does not exist."
```
Always check if the path is valid before doing anything. Return a clear error message — this helps the agent understand what went wrong and try to fix it.

```python
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # Remove skip dirs so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
```
`os.walk()` recursively visits every subdirectory. The `dirnames[:] = ...` trick tells Python to skip certain directories entirely (it modifies the list in-place, which controls where `os.walk` goes next).

```python
        for fname in filenames:
            if Path(fname).suffix in ALLOWED_EXTENSIONS:
                full_path = Path(dirpath) / fname
                found.append(str(full_path.relative_to(root)))
```
For each file, we check if its extension is in our allowed list. If yes, we add its **relative** path (relative to the root being scanned) so paths are short and readable.

---

```python
def read_file(file_path: str) -> str:
    """
    Reads a file and returns its content, capped at 30KB.
    ...
    """
```

**What it does:** Opens a file and returns its content as text. If the file is too big (>30KB), it reads only the first 30KB and adds a warning.

**Why cap at 30KB?** AI models have a limit on how much text they can process at once (called the "context window"). Very large files could overwhelm the model or make it slow. 30KB is enough to see most vulnerabilities.

```python
    MAX_BYTES = 30 * 1024  # 30KB
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_BYTES)
```
`errors="replace"` means if there's a character that can't be decoded as UTF-8 (like binary data), replace it with a placeholder instead of crashing. This makes the tool robust.

```python
        if len(content) == MAX_BYTES:
            content += "\n\n[... FILE TRUNCATED AT 30KB ...]"
```
If we read exactly 30KB, the file was probably cut off. We add a note so the AI knows the file continues.

```python
    except FileNotFoundError:
        return f"Error: file '{file_path}' not found."
    except Exception as e:
        return f"Error reading file: {e}"
```
Always handle errors gracefully. Returning an error string (instead of crashing) lets the agent see what went wrong and decide what to do next.

---

### `vuln_scanner/agent.py` — The Brain: 4 Agents Wired Together

```python
from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.tools import exit_loop
from .tools import list_files, read_file
```

- `LlmAgent` — a single AI agent powered by a language model (Gemini)
- `SequentialAgent` — runs a list of agents one after another
- `LoopAgent` — runs agents in a loop until told to stop
- `exit_loop` — a special built-in tool that tells a LoopAgent "we're done, stop the loop"
- `.tools` — our custom tools from `tools.py`

```python
MODEL = "gemini-2.5-flash"
```
All agents use the same model. `gemini-2.5-flash` is Google's latest fast + capable model. We define it once so it's easy to change.

---

#### The Planner Agent

```python
planner = LlmAgent(
    name="planner",
    model=MODEL,
    instruction="""You are a security planner...""",
    tools=[list_files],
    output_key="files_to_review",
)
```

- `name` — identifies this agent in the ADK web UI
- `instruction` — tells the AI what role to play and what to do. This is the most important part!
- `tools=[list_files]` — the planner can ONLY call `list_files`. It can't read files or do anything else.
- `output_key="files_to_review"` — when the planner finishes, its final response is automatically saved to `session.state["files_to_review"]`. Other agents can then read this value.

**What happens:** The planner calls `list_files("/path/you/gave")`, gets back a list of code files, uses its intelligence to rank them by security importance, and outputs the top 10 with reasons.

---

#### The Reviewer Agent

```python
reviewer = LlmAgent(
    name="reviewer",
    model=MODEL,
    instruction="""You are a security code reviewer. Use read_file to read each file from {files_to_review}...""",
    tools=[read_file],
    output_key="findings",
)
```

Notice `{files_to_review}` in the instruction — ADK automatically replaces this with the actual value from `session.state["files_to_review"]` (set by the planner). This is how agents pass data to each other.

**What happens:** The reviewer reads each file the planner prioritized, looks for security issues, and outputs detailed findings with file names, line numbers, and severity ratings.

---

#### The Critic Agent

```python
critic = LlmAgent(
    name="critic",
    model=MODEL,
    instruction="""You are a security review critic. Evaluate {findings} against {files_to_review}...""",
    tools=[exit_loop],
    output_key="review_feedback",
)
```

The critic has access to `exit_loop` — a special ADK tool. When called, it signals the LoopAgent to stop iterating.

**What happens:**
- If the reviewer's findings are thorough → critic calls `exit_loop` → loop stops
- If the reviewer missed things → critic writes specific feedback in `review_feedback`
- On the next loop iteration, the reviewer reads `{review_feedback}` and improves

This is the **evaluator-optimizer pattern** — one agent generates, another evaluates, and they loop until quality is good enough.

---

#### The LoopAgent

```python
review_loop = LoopAgent(
    name="review_loop",
    sub_agents=[reviewer, critic],
    max_iterations=3,
)
```

- Runs reviewer → critic → reviewer → critic → ... 
- Stops when critic calls `exit_loop` OR after 3 iterations (safety cap)
- `max_iterations=3` is crucial — without it, the loop could run forever

---

#### The Reporter Agent

```python
reporter = LlmAgent(
    name="reporter",
    model=MODEL,
    instruction="""You are a security report writer. Using {findings}, write a clean vulnerability report...""",
    output_key="final_report",
)
```

No tools needed — the reporter just reads `{findings}` from session state and writes a clean, formatted markdown report. Pure writing task.

---

#### The Root Agent (Orchestrator)

```python
root_agent = SequentialAgent(
    name="vuln_scanner",
    description="Scans a codebase for security vulnerabilities using a multi-agent review loop.",
    sub_agents=[planner, review_loop, reporter],
)
```

**Important:** `root_agent` must be named exactly `root_agent` — ADK's `adk web` command looks for a variable with this exact name in your package.

The SequentialAgent runs its sub-agents in order:
1. `planner` runs → saves files list to state
2. `review_loop` runs → reviewer + critic loop, saves findings to state
3. `reporter` runs → reads findings, writes final report

---

### `vuln_scanner/__init__.py` — Package Registration

```python
from . import agent
```

This one line tells Python: "this folder is a package, and the `agent` module is part of it." ADK needs this to discover `root_agent`.

---

### `vuln_scanner/.env` — Configuration

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
```

- `GOOGLE_GENAI_USE_VERTEXAI=TRUE` — tells ADK to use your Google Cloud account (Vertex AI) instead of a direct API key
- `GOOGLE_CLOUD_PROJECT` — your GCP project where Vertex AI is enabled
- `GOOGLE_CLOUD_LOCATION` — the region where Gemini runs

⚠️ **Replace `YOUR_PROJECT_ID` with your actual GCP project ID before running!**

---

## 🔄 How Data Flows Between Agents

This is the key insight that makes multi-agent systems work:

```
session.state = {}  ← shared memory between all agents

Planner runs:
  → calls list_files("/target")
  → outputs: "1. auth.py (auth logic)\n2. routes.py (API)..."
  → ADK saves to: session.state["files_to_review"] = "1. auth.py..."

Reviewer runs (loop iteration 1):
  → reads {files_to_review} from session.state
  → calls read_file("auth.py"), read_file("routes.py"), ...
  → outputs: "CRITICAL: auth.py line 42 — SQL injection..."
  → ADK saves to: session.state["findings"] = "CRITICAL: auth.py..."

Critic runs (loop iteration 1):
  → reads {findings} and {files_to_review} from session.state
  → thinks: "reviewer missed routes.py entirely"
  → outputs: "Please review routes.py more carefully"
  → ADK saves to: session.state["review_feedback"] = "Please review..."
  → does NOT call exit_loop → loop continues

Reviewer runs (loop iteration 2):
  → reads {files_to_review} AND {review_feedback}
  → focuses on routes.py this time
  → outputs improved findings

Critic runs (loop iteration 2):
  → thinks: "findings look thorough now"
  → calls exit_loop → loop stops

Reporter runs:
  → reads {findings} from session.state
  → writes clean markdown report
```

All communication happens through `session.state` — agents don't talk to each other directly. They read and write a shared "whiteboard."

---

## 🧠 Key ADK Concepts Explained Simply

### `output_key`
When an agent finishes, its response is saved to `session.state[output_key]`. Other agents can reference this with `{output_key}` in their instructions. This is how agents pass data to each other.

### `{variable}` in instructions
ADK replaces `{variable}` in agent instructions with the current value of `session.state["variable"]` before sending the instruction to the AI. So the AI always sees the actual data, not a placeholder.

### `exit_loop` tool
A special built-in ADK tool. When any agent inside a LoopAgent calls it, the loop stops. The critic uses this to signal "we're done, the review is good enough."

### Agent types comparison
| Type | What it does | Use for |
|---|---|---|
| `LlmAgent` | One AI making decisions | Any task that needs reasoning |
| `SequentialAgent` | Runs agents A → B → C in order | Pipelines with clear steps |
| `LoopAgent` | Runs agents in a loop | Iterative refinement |

---

## 🐛 Common Issues & How to Fix Them

| Problem | Likely Cause | Fix |
|---|---|---|
| `adk web` can't find the agent | `root_agent` not exported properly | Check `__init__.py` imports `agent`, and `agent.py` has `root_agent` |
| "Project not found" error | Wrong project ID in `.env` | Edit `.env` with your real GCP project ID |
| "Permission denied" on Vertex AI | Not authenticated | Run `gcloud auth application-default login` |
| Agent loops forever | `exit_loop` never called | Check critic instructions; `max_iterations=3` is the safety cap |
| File not found in read_file | Wrong path format | Use absolute paths in your scan prompt |
| Empty findings | Planner picked wrong files | Try scanning a specific subfolder instead of the whole repo |

---

## 💡 How to Extend This Project

### Add a new vulnerability type
Edit the reviewer's `instruction` in `agent.py` to add more vulnerability categories.

### Scan more file types
Add extensions to `ALLOWED_EXTENSIONS` in `tools.py`:
```python
ALLOWED_EXTENSIONS = {".py", ".js", ..., ".yaml", ".tf"}  # add Terraform, YAML
```

### Increase loop depth
Change `max_iterations` in the LoopAgent:
```python
review_loop = LoopAgent(..., max_iterations=5)  # more thorough but slower
```

### Add a new agent
Add a `patch_writer` agent after the reporter that generates code fixes for each finding.

### Save the report to a file
Add a `write_report` tool that saves `final_report` to disk.

---

## 📚 Further Reading

- [Google ADK Docs](https://google.github.io/adk-docs/) — Official documentation
- [ADK Quickstart](https://google.github.io/adk-docs/get-started/quickstart/)
- [Hanlin's ADK Notes](https://github.com/hanlin1108/learning-notes/blob/main/google_adk_notes.md) — Your personal reference
- [Google ADK GitHub](https://github.com/google/adk-python) — Source code + examples

---

*Written by your AI assistant — May 2026*
