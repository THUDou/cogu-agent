---
name: hello-cogu
description: COGU AGENT sample skill — demonstrates the Markdown skill format with YAML frontmatter, inline scripts, and context injection
version: 0.1.0
author: COGU Team
tools:
  - shell
  - web-search
dependencies:
  - python>=3.10
---

# Hello COGU

This is a demonstration skill for the COGU AGENT framework. Skills are defined as Markdown files with YAML frontmatter and can include embedded scripts, reference files, and structured instructions.

## Capabilities

- Echo the current date and COGU version
- List available Python packages in the environment
- Perform a simple web search

## Instructions

When asked to "hello", respond with a greeting that includes:
1. The current date and time
2. The COGU AGENT version (run `python -m cogu version`)
3. A fun fact about cognitive agents

When asked to "scan", list the Python environment:
1. Show Python version (`python --version`)
2. List key installed packages (`pip list`)

When asked to "lookup <query>", use web search to find information.

## Context

COGU AGENT (Cognitive Unified Agent) is a Python agent framework that fuses patterns from:
- Huawei JiuwenCLAW
- Xiaomi MiMo-Code
- Baidu LoongFlow
- ByteDance M3-Agent
- DeepSeek-TUI
- AgentScope CoPaw
