# TUDOU_agent Project Rules

## Project Overview
TUDOU_agent is a CLI-based AI agent that uses the terminal as its UI. It can call command-line tools, web search, file operations, and execute SKILL.md skills from the Hermes Agent ecosystem.

## Architecture
- Python 3.12+ with rich + prompt_toolkit for UI
- Multi-provider LLM support (Anthropic, OpenAI-compatible)
- ReAct agent loop: LLM <-> Tool cycle
- Skills system compatible with Hermes Agent SKILL.md format
- MCP protocol for external tool integration

## Configuration
- API Key 配置文件: `projact/config.yaml`
- 配置优先级: defaults < `~/.tudou_agent/config.yaml` < `.tudou_agent.yaml` < `projact/config.yaml` < 环境变量

## Directory Convention
- `rule/` — Project rules and memory
- `projact/` — Source code
- `builtin_skills/` — Built-in skill files (150 SKILL.md skills)
- `tests/` — Test suite

## Skills Management
- `/importdangerskills <name>` — Import a skill from `dangerskills/` into `builtin_skills/`
- `/removeskills <name>` — Remove a skill from `builtin_skills/` and move it to `dangerskills/`
- The `dangerskills/` quarantine directory is at `C:\Users\wa\Desktop\TUDOU_area\dangerskills\`

## Behavior Rules


## Key Modules
- `agent.py` — Core ReAct loop
- `cli.py` — Terminal interface
- `tools/` — Tool implementations
- `skills/` — SKILL.md parsing and execution
- `llm/` — LLM provider abstraction
- `context/` — Context and memory management
- `permissions/` — Tool permission system
