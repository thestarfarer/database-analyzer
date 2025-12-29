# Database Analyzer WebUI

Watch the LLM think. See every query. Know what it knows.

A real-time interface for monitoring sessions as they run—not a dashboard you check later, but a window into what's happening now.

## Features

- **Live Monitoring** — Watch iterations unfold as they execute
- **Tool Call Inspection** — Every SQL query, every memory operation, with timing
- **Memory Browser** — See what the LLM has learned, organized by category
- **Memory Verification** — Check if stored insights still hold against current data
- **Session Control** — Start, stop, resume from the browser
- **Real-time Updates** — WebSocket-powered, no refresh needed
- **i18n Support** — Multilingual interface

## Quick Start

```bash
pip install -r webui/requirements.txt
python -m webui.app
# http://localhost:5000
```

## Pages

| Route | What It Shows |
|-------|---------------|
| `/en/` | All sessions with status indicators |
| `/{lang}/session/{id}` | Session detail with iteration list |
| `/{lang}/session/{id}/iteration/{num}` | Single iteration: prompt, tool calls, response |
| `/{lang}/session/{id}/memory` | Composed memory with verification |

## API

### Reading

```
GET /api/sessions                      # List all sessions
GET /api/sessions/{id}                 # Full session with iterations
GET /api/sessions/{id}/iteration/{num} # Single iteration detail
GET /api/sessions/{id}/memory          # Composed memory state
```

### Control

```
POST /api/sessions/new
  {"first_user_input": "Explore the database"}

POST /api/sessions/{id}/resume
  {"resume_guidance": "Focus on Q2 data"}

POST /api/sessions/{id}/stop

DELETE /api/sessions/{id}
```

### Memory Verification

```
POST /api/sessions/{id}/memory/verify
  {"category": "insights", "key": "record_count"}

POST /api/sessions/{id}/memory/update
  {"category": "insights", "key": "record_count", "new_value": "..."}
```

## WebSocket Events

Subscribe to `file_changed` for live updates:

```javascript
socket.on('file_changed', (data) => {
  // data: {session_id, event_type, timestamp}
  // event_type: 'created' | 'modified' | 'deleted'
});
```

Visual feedback: green flash for new sessions, yellow for updates, red for deletions.

## Session Status

Computed from process state:

| Status | Meaning |
|--------|---------|
| 🟢 running | Has PID, process alive |
| 🟣 completed | No PID (graceful exit) |
| 🟠 interrupted | Has PID, process dead |

## Structure

```
webui/
├── app.py              # Flask + SocketIO routes
├── services/
│   ├── unified_session_reader.py
│   └── file_watcher.py
├── templates/          # Jinja2
└── static/
    ├── css/
    │   ├── colors.css  # All colors as CSS custom properties
    │   └── *.css
    ├── js/
    │   ├── utils.js    # Shared utilities (use WebUIUtils)
    │   └── *.js
    └── translations/   # i18n JSON (auto-discovered)
```

## Adding a Language

Drop a JSON file in `static/translations/`:

```json
// static/translations/de.json
{
  "app": {
    "title": "Datenbank-Analysator",
    "subtitle": "WebUI",
    "language_name": "Deutsch"  // Shown in dropdown
  },
  // ... copy structure from en.json
}
```

The language appears automatically in the dropdown. No code changes needed.

## Testing

```bash
pytest tests/webui/                        # All 147 tests
pytest tests/webui/test_api_endpoints.py   # API (39)
pytest tests/webui/test_socketio.py        # WebSocket (24)
pytest tests/webui/test_session_reader.py  # Services (30)
pytest tests/webui/test_file_watcher.py    # File monitoring (23)
```

## Notes

- Colors live in `colors.css` as custom properties—don't hardcode elsewhere
- JavaScript utilities go through `WebUIUtils` for consistency
- Development server only; use Gunicorn/uWSGI for production
