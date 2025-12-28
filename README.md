# Database Analyzer

Point an LLM at your database. Let it explore. Come back tomorrow and pick up where it left off.

An iterative analysis tool with persistent memory—the LLM remembers what it's found across sessions, building understanding instead of starting fresh every time.

<!-- ![WebUI Screenshot](docs/images/webui.png) -->

## Features

- **Multi-LLM Support** — Qwen (local/self-hosted) or Claude (Anthropic API)
- **Iterative Analysis** — Natural conversation that goes somewhere
- **Persistent Memory** — Insights survive across iterations and sessions
- **Real-time WebUI** — Watch it think, inspect every query, manage what it knows
- **Session Management** — Stop, resume, redirect, continue
- **Memory Verification** — Check stored insights against current data
- **Prompt Presets** — Different prompts for different databases
- **i18n Support** — Multilingual interface

## Installation

```bash
# Core
pip install pymssql qwen-agent

# WebUI
pip install -r webui/requirements.txt

# Claude support (optional)
pip install anthropic

# Tests (optional)
pip install -r tests/requirements-test.txt
```

## Quick Start

```bash
cp .env.example .env
# Edit with your DB_SERVER, DB_USER, DB_PASSWORD, DB_NAME

python main.py --task "Explore the database and find interesting patterns"
```

After each iteration:
- **Enter** → keep going
- **Type guidance** → redirect ("focus on the orders table")
- **`report`** → generate summary
- **Ctrl+C** → save and exit

### Resume Later

```bash
python main.py --latest                    # Pick up most recent session
python main.py --latest --task "Now look at seasonal trends"  # Resume with new direction
python main.py --continue-session output/session_20250101_120000.json
python main.py --list-sessions             # See what's available
```

### Use Claude Instead of Qwen

```bash
python main.py --task "Find anomalies" --llm-backend claude
```

### WebUI

```bash
python -m webui.app
# http://localhost:5000
```

Live session monitoring. Tool call inspection. Memory browser with category filtering. Start, stop, resume from the browser.

## Configuration

### LLM Backends

**Qwen (Local)**
```env
QWEN_MODEL=qwen-max
QWEN_MODEL_SERVER=http://localhost:5001/api/v1
QWEN_API_KEY=EMPTY
```

**Claude (Anthropic)**
```env
ANTHROPIC_API_KEY=your_api_key
CLAUDE_MODEL=claude-opus-4-5
CLAUDE_EXTENDED_THINKING=true
```

### Prompt Presets

Drop JSON files in `prompts/` to customize system prompts for different databases or analysis styles. See `prompts/lifecycle_test.json` for the structure.

### Memory Verification

Check if a stored insight still holds:
```bash
python main.py --verify-memory SESSION_ID category:key
```

## Project Structure

```
├── main.py              # CLI entry point
├── config/              # Settings
├── core/                # Session management, execution, state
├── database/            # MSSQL connection layer
├── llm/                 # Qwen and Claude providers
├── tools/               # SQL tool, Memory tool
├── services/            # Reports, verification
├── ui/                  # CLI interface
├── webui/               # Flask app, templates, static assets
├── tests/               # 580+ tests
├── prompts/             # Preset templates
└── output/              # Session files (gitignored)
```

## Testing

```bash
pytest                          # Everything
pytest tests/unit/              # Fast
pytest --cov=. --cov-report=html  # Coverage
pytest -n auto                  # Parallel
```

## License

[CC BY-NC-4.0](LICENSE) — Free to share and adapt for non-commercial use with attribution.

---

*For databases you inherited without documentation. For patterns you didn't know to look for.*
