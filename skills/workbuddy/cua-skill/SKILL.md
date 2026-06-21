---
name: "cua-skill"
description: "Microsoft CUA Skill - Computer Use Agent with Skills for Windows GUI automation. Use when user asks to automate Windows desktop applications, control GUI elements, execute desktop tasks, or interact with Windows applications like Chrome, Edge, Excel, Word, PowerPoint, Notepad, etc. Supports both Replay mode (execute pre-defined task graphs) and RAG mode (dynamic skill retrieval and execution)."
agent_created: true
---

# CUA Skill — Computer Use Agent with Skills

Microsoft CUA Skill is a skill-based autonomous GUI agent framework for Windows desktop applications. It retrieves and executes pre-recorded action sequences (skills) from an indexed library, enabling reliable and efficient task completion across 17+ Windows applications.

## When to Use This Skill

Use this skill when the user wants to:
- Automate Windows desktop applications (Chrome, Edge, Excel, Word, PowerPoint, Notepad, Paint, Calculator, etc.)
- Execute GUI-based tasks on Windows
- Control desktop applications through natural language instructions
- Replay pre-defined task sequences
- Use RAG-based dynamic task planning for Windows automation

## Prerequisites

- **Python 3.10+** installed
- **Windows OS** (agent interacts with Windows desktop)
- **Azure OpenAI access** (for LLM planner and grounding models)
- Cloned repository at `C:/Users/ASUS/cua_skill`

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r C:/Users/ASUS/cua_skill/agent/requirements.txt
   ```

2. Create `.env` file in `C:/Users/ASUS/cua_skill/agent/` with required credentials:
   ```
   UITARS_V1_BEARER_KEY="your_uitars_key"
   AZURE_AD_TOKEN="your_azure_ad_token"
   ```

## Configuration

Two configuration modes available:

### Replay Agent (config.json)
- Executes pre-defined task graphs (JSON format)
- Uses vision grounding to calibrate action coordinates
- Configure in `C:/Users/ASUS/cua_skill/agent/config.json`

### RAG Agent (config_rag.json)
- Dynamically retrieves and executes skills using LLM planner
- Hybrid search (BM25 + semantic) over skill library
- Configure in `C:/Users/ASUS/cua_skill/agent/config_rag.json`

Key configuration options:
- `planner.model_class`: LLM backend (`"gpt"` or `"qwen"`)
- `rag.semantic_weight`: Hybrid search weight (default: 0.7)
- `max_steps`: Maximum actions per task (default: 50)
- `max_wall_time`: Timeout in seconds (default: 300)

## Usage

### Replay Mode

Execute pre-defined task graphs:

```python
import sys
sys.path.insert(0, "C:/Users/ASUS/cua_skill")
from agent import CUAKnowledgeGraphAgent

agent = CUAKnowledgeGraphAgent(config="C:/Users/ASUS/cua_skill/agent/config.json")
agent.proceed(
    instruction="Open Notepad and type Hello World",
    example=task_json  # JSON task graph
)
```

### RAG Mode

Dynamic task planning and execution:

```python
import sys
sys.path.insert(0, "C:/Users/ASUS/cua_skill")
from agent import CUARAGAgent

agent = CUARAGAgent(config="C:/Users/ASUS/cua_skill/agent/config_rag.json")
agent.proceed(
    instruction="Search for 'weather today' on Bing and take a screenshot"
)
```

## Supported Applications

The skill supports 17+ Windows applications:
- Windows Start/Search/Run
- Bing Search, Google Chrome, Microsoft Edge
- Microsoft Excel, Word, PowerPoint
- Notepad, Paint, Calculator, Clock
- File Explorer, VLC Media Player
- VS Code, Amazon, YouTube, Windows Settings

Application-specific skill modules are located in `C:/Users/ASUS/cua_skill/agent/action/`.

## Key Components

- **Planner** — LLM-driven component for query generation, action selection, parameter configuration
- **Retriever** — Hybrid search engine (BM25 + semantic embeddings)
- **Mixture Grounding** — Vision-based coordinate refinement (UI-TARS v1)
- **Action System** — 20+ base actions with registry pattern, composable action graphs (DAGs)
- **Desktop Environment** — Wraps `pyautogui` and `pywinauto`

## Project Structure

```
C:/Users/ASUS/cua_skill/
├── agent/                        # Core agent framework
│   ├── agent.py                  # Replay agent
│   ├── agent_rag.py              # RAG agent
│   ├── config.json               # Replay configuration
│   ├── config_rag.json           # RAG configuration
│   ├── action/                   # Application-specific skills
│   └── utils/                    # Utilities
├── user_task_generation/         # Task synthesis pipeline
└── evaluation/                   # Windows Agent Arena integration
```

## References

- Complete README: `references/README.md`
- Configuration examples: `references/config_examples.md`
- Application skill modules: `C:/Users/ASUS/cua_skill/agent/action/`

## Important Notes

1. **Windows Only**: This skill requires Windows OS to interact with desktop applications
2. **Azure OpenAI Required**: Requires valid Azure OpenAI credentials for LLM planning
3. **Python Path**: Always add the repository to Python path before importing
4. **Screen Resolution**: Vision grounding depends on screen resolution; ensure consistent environment
5. **Administrator Rights**: Some operations may require administrator privileges

## Example Tasks

- "Open Chrome and search for 'WorkBuddy AI'"
- "Create an Excel spreadsheet with sample data"
- "Open Notepad and write a Python script"
- "Take a screenshot of the current window"
- "Navigate to YouTube and play a specific video"

For detailed documentation, refer to the references directory or the original [GitHub repository](https://github.com/microsoft/cua_skill).
