# CUA Skill Configuration Guide

## Overview

CUA Skill uses two configuration files:
- `config.json` — For Replay Agent (execute pre-defined task graphs)
- `config_rag.json` — For RAG Agent (dynamic skill retrieval and execution)

## Configuration Files

### 1. config.json (Replay Agent)

Located at: `C:/Users/ASUS/cua_skill/agent/config.json`

```json
{
    "name": "CUA_Skill_Agent",
    "version": "1.0.0",
    "platform": "windows",
    "max_attempts": 1,
    "max_grounding_attempts": 3,
    "max_steps": 50,
    "max_wall_time": 300,
    "step_interval_time": 2,
    "env": {
        "name": "windows_env",
        "platform": "windows",
        "url": "localhost",
        "screen_height": null,
        "screen_width": null,
        "observation_type": "screenshot_a11y_tree",
        "observe_screenshot_in_bytes": true,
        "a11y_tree_max_tokens": 1000
    },
    "mixture_grounding": {
        "expertises": [
            {
                "model": "uitars_v1_grounding",
                "weight": 1.0,
                "azure_endpoint": true,
                "endpoint_url": "YOUR_ENDPOINT_URL_HERE",
                "bearer_key_env_var": "UITARS_V1_BEARER_KEY"
            },
            {
                "model": "uia_tree",
                "weight": 0.0
            }
        ]
    },
    "logger": {
        "enable": true,
        "log_level_desc": "one of the following: [debug, info, warning, error, critical]",
        "log_level": "debug",
        "log_file": "log.jsonl",
        "log_dir": "./logs",
        "record": true
    }
}
```

#### Key Settings Explained

| Setting | Description | Default |
|---------|-------------|---------|
| `max_steps` | Maximum number of actions per task | 50 |
| `max_wall_time` | Timeout in seconds | 300 |
| `step_interval_time` | Seconds to wait between steps | 2 |
| `mixture_grounding.expertises` | Vision grounding model endpoints | See above |
| `env.observation_type` | Type of observation (`screenshot`, `a11y_tree`, `screenshot_a11y_tree`) | `screenshot_a11y_tree` |

### 2. config_rag.json (RAG Agent)

Located at: `C:/Users/ASUS/cua_skill/agent/config_rag.json`

```json
{
    "name": "CUA_RAG_Agent",
    "version": "1.0.0",
    "platform": "windows",
    "max_steps": 50,
    "max_wall_time": 300,
    "max_attempts": 1,
    "env": {
        "name": "windows_env",
        "platform": "windows",
        "url": "localhost",
        "screen_height": null,
        "screen_width": null,
        "observation_type": "screenshot_a11y_tree",
        "observe_screenshot_in_bytes": true,
        "a11y_tree_max_tokens": 1000
    },
    "planner": {
        "model_class": "gpt",
        "model": "gpt-4o",
        "temperature": 0.0,
        "max_tokens": 4096
    },
    "rag": {
        "index_path": "./index",
        "semantic_weight": 0.7,
        "top_k": 5
    },
    "mixture_grounding": {
        "expertises": [
            {
                "model": "uitars_v1_grounding",
                "weight": 1.0,
                "azure_endpoint": true,
                "endpoint_url": "YOUR_ENDPOINT_URL_HERE",
                "bearer_key_env_var": "UITARS_V1_BEARER_KEY"
            }
        ]
    },
    "logger": {
        "enable": true,
        "log_level": "debug",
        "log_file": "log_rag.jsonl",
        "log_dir": "./logs",
        "record": true
    }
}
```

#### Key Settings Explained

| Setting | Description | Default |
|---------|-------------|---------|
| `planner.model_class` | LLM backend: `"gpt"` or `"qwen"` | `"gpt"` |
| `planner.model` | Specific model name | `"gpt-4o"` |
| `rag.semantic_weight` | Weight for semantic search in hybrid retrieval | 0.7 |
| `rag.top_k` | Number of top results to retrieve | 5 |
| `rag.index_path` | Path to the RAG index directory | `"./index"` |

## Environment Variables (.env file)

Create a `.env` file in `C:/Users/ASUS/cua_skill/agent/` with the following content:

```
# Required: UI-TARS Vision Grounding Model
UITARS_V1_BEARER_KEY="your_uitars_api_key_here"

# Optional: Azure AD Token (if using Azure OpenAI)
AZURE_AD_TOKEN="your_azure_ad_token_here"

# Optional: Azure OpenAI Configuration (if not using .env)
AZURE_OPENAI_API_KEY="your_azure_openai_key"
AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT_NAME="your_deployment_name"
```

## Setup Instructions

### Step 1: Install Dependencies

```bash
pip install -r C:/Users/ASUS/cua_skill/agent/requirements.txt
```

### Step 2: Configure Environment Variables

1. Navigate to `C:/Users/ASUS/cua_skill/agent/`
2. Create a new file named `.env`
3. Add your API keys and endpoints (see template above)

### Step 3: Update Configuration Files

1. Open `config.json` or `config_rag.json`
2. Replace `"YOUR_ENDPOINT_URL_HERE"` with your actual UI-TARS endpoint URL
3. Adjust other settings as needed (max_steps, timeout, etc.)

### Step 4: Build RAG Index (for RAG Agent only)

```bash
cd C:/Users/ASUS/cua_skill/agent
python retrieval.py --build-index --index-path ./index
```

## Troubleshooting

### Common Issues

1. **"UITARS_V1_BEARER_KEY not found"**
   - Ensure `.env` file exists in `C:/Users/ASUS/cua_skill/agent/`
   - Verify the environment variable name matches exactly

2. **"Endpoint URL not reachable"**
   - Check your UI-TARS endpoint URL in `config.json`
   - Verify network connectivity and authentication

3. **"Python module not found"**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version (requires 3.10+)

4. **"Screen resolution mismatch"**
   - Vision grounding depends on consistent screen resolution
   - Avoid changing screen resolution between runs

## Advanced Configuration

### Customizing Action Parameters

To customize action behavior, modify the action modules in:
`C:/Users/ASUS/cua_skill/agent/action/<app>_action.py`

### Adding New Applications

1. Create a new action module: `agent/action/myapp_action.py`
2. Define primitive operations and compositions
3. Register the actions in `agent/action/base_action.py`
4. Rebuild the RAG index if using RAG mode

## References

- Original GitHub Repository: https://github.com/microsoft/cua_skill
- UI-TARS Model: https://github.com/bytedance/UI-TARS
- Azure OpenAI Documentation: https://learn.microsoft.com/azure/ai-services/openai/
