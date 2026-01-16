# SheetSmith — Agentic Google Sheets Automation Assistant

## Project overview
SheetSmith is an LLM-based agent with a simple web UI that helps maintain and update complex Google Sheets models.

The goal of the project is to automate repetitive, error-prone spreadsheet work such as propagating small logic changes across many sheets, auditing formulas, and safely applying batch updates. The agent connects directly to the Google Sheets API to read data and formulas, reason about them, suggest changes, and optionally write updates back to the sheet.

This project is motivated by my own experience maintaining large spreadsheet-based calculators, where small updates often require manual edits across many tabs and files.

---

## Quick Start

```bash
# Clone and install
git clone <repository-url>
cd SheetSmith
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Authenticate with Google Sheets
sheetsmith auth

# Start the web server
sheetsmith serve
```

Then open http://localhost:8000 in your browser.

---

## Features

### Implemented Capabilities
- **Google Sheets Integration**: Full read/write access via Google Sheets API
- **Pattern-Based Formula Search**: Regex search across all sheets to find matching formulas
- **Surgical Updates**: Change specific values in formulas while preserving sheet-specific references
- **Batch Updates**: Apply multiple changes in a single atomic operation
- **Diff Preview**: Review all proposed changes before applying them
- **Audit Logging**: Track all changes for accountability
- **Long-Term Memory**: Store rules, logic blocks, and fix summaries for future reference
- **Web UI**: Clean, modern interface for interacting with the agent

### MCP Tools
The agent has access to the following tools:

| Tool | Description |
|------|-------------|
| `gsheets.read_range` | Read values and formulas from a sheet range |
| `gsheets.search_formulas` | Search for formulas matching a regex pattern |
| `gsheets.batch_update` | Apply multiple cell updates atomically |
| `gsheets.get_info` | Get spreadsheet metadata and sheet list |
| `memory.store_rule` | Store a project convention or formula rule |
| `memory.get_rules` | Retrieve stored rules |
| `memory.store_logic_block` | Store a known formula pattern (kit, teammate, rotation) |
| `memory.get_logic_blocks` | Retrieve stored logic blocks |
| `memory.search_logic_blocks` | Search logic blocks by keyword |
| `patch.preview` | Generate a diff preview of proposed changes |
| `patch.apply` | Apply an approved patch |

---

## Architecture

```
SheetSmith/
├── src/sheetsmith/
│   ├── agent/          # LLM agent orchestration
│   │   ├── orchestrator.py  # Main agent class
│   │   └── prompts.py       # System prompts
│   ├── api/            # FastAPI backend
│   │   ├── app.py           # Application factory
│   │   └── routes.py        # API endpoints
│   ├── engine/         # Formula analysis engine
│   │   ├── analyzer.py      # Formula parsing and pattern detection
│   │   ├── differ.py        # Diff generation
│   │   └── patcher.py       # Patch management
│   ├── memory/         # Persistence layer
│   │   ├── models.py        # Data models
│   │   └── store.py         # SQLite storage
│   ├── sheets/         # Google Sheets client
│   │   ├── client.py        # API wrapper
│   │   └── models.py        # Data models
│   ├── tools/          # MCP-style tools
│   │   ├── gsheets.py       # Sheets tools
│   │   ├── memory.py        # Memory tools
│   │   └── registry.py      # Tool registry
│   ├── cli.py          # Command-line interface
│   └── config.py       # Configuration management
├── static/             # Web UI frontend
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── sample_data/        # Example data and patches
└── data/               # Runtime data (database, tokens)
```

---

## My current manual workflow
I maintain spreadsheets where each tab represents a different build or configuration.
While stats, teammates, and rotations may differ per sheet, many parts of the formulas encode shared logic that is repeated across sheets.

A typical workflow looks like this:
1. I discover a kit update, a balance change, or a mistake in a formula or rotation.
2. I locate the relevant logic in one sheet.
3. I manually open every other sheet that uses the same logic and:
   - find the corresponding formulas,
   - verify it is the same logical version,
   - change a small part (often a single number, condition, or block of logic),
   - make sure I did not break any sheet-specific references.
4. I repeat this across many tabs or even multiple spreadsheets.

This process is slow, tedious, and easy to get wrong.

---

## Concrete example: shared kit logic
Many of my formulas contain logic that represents part of a character's kit.
For example, a mapping from status name to a damage ratio:

    SWITCH(TRIM(statusNow),
      "Corruption", 28.6%,
      "Shock", 14.9%,
      "Burn", 37.1%,
      0
    )

This mapping from status → damage ratio is identical across all sheets, even though the surrounding formula references different stat cells per sheet.

If one value changes (for example, Corruption becomes 30.0%), I must manually update this logic everywhere, even though the rest of each formula should remain untouched.

**With SheetSmith**, I simply say:
> "Update the Corruption ratio from 28.6% to 30.0% everywhere"

The agent finds all matching formulas, shows me a diff, and applies the changes with my approval.

---

## Additional recurring pain points

### Teammate replacement
Sheets often encode teammate logic directly into formulas (buff windows, triggers, multipliers, and rotation interactions).

When I replace a teammate, I must:
- remove all formulas associated with the old teammate,
- insert the new teammate's logic,
- rewire references so the rest of the sheet still functions correctly.

This process is largely mechanical but must be done carefully.

---

### Rotation fixes
Some sheets share the exact same rotation logic.
If I discover a mistake in a rotation (timing, trigger condition, or ordering), I must manually update every sheet that uses that rotation.

There is no single "source of truth" for rotations or teammate logic; instead, they are copied and slightly adapted across sheets, making global fixes tedious and error-prone.

---

## API Reference

### Chat API
```
POST /api/chat
{
  "message": "Update Corruption from 28.6% to 30.0%",
  "spreadsheet_id": "your-spreadsheet-id"
}
```

### Sheets API
```
POST /api/sheets/info     # Get spreadsheet metadata
POST /api/sheets/read     # Read a range
POST /api/sheets/search   # Search formulas
```

### Memory API
```
GET  /api/rules           # List rules
POST /api/rules           # Create rule
GET  /api/logic-blocks    # List logic blocks
POST /api/logic-blocks    # Create logic block
GET  /api/audit-logs      # View audit history
```

---

## Long-term memory
The agent stores:
- Project-specific rules (e.g., how formulas should be written).
- Summaries of previous fixes.
- Known mappings and logic blocks that represent character kits, teammates, or rotations.

This allows the agent to improve suggestions over time and adapt to a specific spreadsheet ecosystem.

---

## Sample data
The `/sample_data` folder contains example data demonstrating SheetSmith's capabilities:

- `example_spreadsheet.json` - Simulated spreadsheet with formulas
- `example_patches/` - Example before/after patch files
- `logic_blocks/` - Common formula patterns
- `rules/` - Formula style conventions

---

## Demo scenario
1. Connect the agent to a test Google Sheet.
2. Ask: "Update the Corruption ratio in the Abloom formula from 28.6% to 30.0% everywhere."
3. The agent finds matching formulas, proposes a patch, and shows a diff.
4. The user approves the patch, and the agent applies it via batch update.

---

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CREDENTIALS_PATH` | Path to Google OAuth credentials | `credentials.json` |
| `GOOGLE_TOKEN_PATH` | Path to store OAuth token | `token.json` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |
| `DATABASE_PATH` | SQLite database location | `data/sheetsmith.db` |
| `HOST` | Server host | `127.0.0.1` |
| `PORT` | Server port | `8000` |
| `MODEL_NAME` | Claude model to use | `claude-sonnet-4-20250514` |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/

# Run in development mode with auto-reload
sheetsmith serve --reload
```

---

## License

MIT License - See LICENSE file for details.
