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
- **Deterministic Mass Replace**: Fast, cost-efficient bulk replacements without LLM overhead (99% cost reduction for simple operations)
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
| `formula.mass_replace` | **NEW:** Fast deterministic mass replacement for simple operations (99% cost reduction) |
| `memory.store_rule` | Store a project convention or formula rule |
| `memory.get_rules` | Retrieve stored rules |
| `memory.store_logic_block` | Store a known formula pattern (kit, teammate, rotation) |
| `memory.get_logic_blocks` | Retrieve stored logic blocks |
| `memory.search_logic_blocks` | Search logic blocks by keyword |
| `patch.preview` | Generate a diff preview of proposed changes |
| `patch.apply` | Apply an approved patch |

---

### Header-Based Mapping System
SheetSmith includes a robust mapping system that uses stable header text instead of column letters:
- Automatic column mapping by header name
- Concept cell mapping (row × column intersection)
- Duplicate header disambiguation with user confirmation
- Mapping validation and health checks
- API endpoints for mapping management

See `src/sheetsmith/mapping/README.md` for complete documentation.

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
│   ├── mapping/        # Header-based column/cell mapping
│   │   ├── manager.py       # Mapping orchestration
│   │   ├── storage.py       # Database persistence
│   │   └── validator.py     # Mapping validation
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

## Cost Optimization

SheetSmith now uses **Deterministic Mass Replace** for simple operations, dramatically reducing LLM API costs:

### Example: Replace VLOOKUP with XLOOKUP across 100 formulas

**Before (Traditional approach)**:
- 1 LLM call to understand the request
- 100 LLM calls to process each formula
- **Total cost**: ~$0.10, ~30 seconds

**After (Optimized approach)**:
- 1 LLM call to understand the request
- 0 LLM calls for replacements (deterministic string replacement)
- **Total cost**: ~$0.001, ~0.5 seconds
- **Savings**: 99% cost reduction, 98% time reduction

The system automatically chooses the most efficient path based on the complexity of your request. Simple find/replace operations use deterministic replacement, while complex logic changes still leverage the LLM's reasoning capabilities.

See [docs/deterministic-mass-replace.md](docs/deterministic-mass-replace.md) for details.

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

### Mapping API
```
GET  /api/mappings/{spreadsheet_id}/audit  # Audit all mappings
POST /api/mappings/disambiguate            # Store disambiguation choice
DELETE /api/mappings/{mapping_id}          # Delete a mapping
POST /api/mappings/validate                # Validate a mapping
```

### Memory API
```
GET  /api/rules           # List rules
POST /api/rules           # Create rule
GET  /api/logic-blocks    # List logic blocks
POST /api/logic-blocks    # Create logic block
GET  /api/audit-logs      # View audit history
```

### Operations API
```
POST /api/ops/search      # Search cells deterministically
POST /api/ops/preview     # Preview changes before apply
POST /api/ops/apply       # Apply previewed changes
POST /api/ops/preflight   # Preflight check for operations
POST /api/ops/audit/mappings  # Audit mappings for operations
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
| `LLM_PROVIDER` | LLM provider to use (`anthropic` or `openrouter`) | `anthropic` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required when using `anthropic` provider) | Required for Anthropic |
| `MODEL_NAME` | Claude model to use with Anthropic | `claude-sonnet-4-20250514` |
| `OPENROUTER_API_KEY` | Your OpenRouter API key (required when using `openrouter` provider) | Required for OpenRouter |
| `OPENROUTER_MODEL` | Model to use with OpenRouter (e.g., `anthropic/claude-3.5-sonnet`) | `anthropic/claude-3.5-sonnet` |
| `DATABASE_PATH` | SQLite database location | `data/sheetsmith.db` |
| `HOST` | Server host | `127.0.0.1` |
| `PORT` | Server port | `8000` |
| `MAX_CELLS_PER_OPERATION` | Maximum cells that can be modified in a single operation | `500` |
| `MAX_SHEETS_PER_OPERATION` | Maximum sheets that can be modified in a single operation | `40` |
| `MAX_FORMULA_LENGTH` | Maximum length of a formula (guard against corruption) | `50000` |
| `REQUIRE_PREVIEW_ABOVE_CELLS` | Number of cells above which preview is required | `10` |
| `PLANNING_MODEL` | Cheaper model for simple planning tasks (optional) | `` |

### Using OpenRouter

To use OpenRouter instead of direct Anthropic API:

1. Set `LLM_PROVIDER=openrouter` in your `.env` file
2. Set `OPENROUTER_API_KEY` to your OpenRouter API key
3. Set `OPENROUTER_MODEL` to your desired model (e.g., `anthropic/claude-3.5-sonnet`, `openai/gpt-4`)
4. You do NOT need to set `ANTHROPIC_API_KEY` or `MODEL_NAME` when using OpenRouter

## Safety Features

SheetSmith includes several safety constraints to prevent expensive or dangerous operations:

### Automatic Limits
- **Max cells per operation**: Operations affecting more than 500 cells (configurable) require explicit scoping
- **Max sheets per operation**: Operations can't affect more than 40 sheets (configurable) in a single action
- **Formula length guard**: Prevents accidentally creating or accepting malformed formulas
- **Preview requirement**: Large operations automatically trigger preview mode

### Scope Control
When operations exceed safety limits, the agent will:
1. Report the constraint violation
2. Suggest narrowing the scope (specific sheets, columns, or patterns)
3. Ask which subset to process
4. Prevent execution until scope is narrowed

### Example
```
User: "Replace SEED! with Base! everywhere"
Agent: "I found 750 matches across 50 sheets, which exceeds the safety limit of 500 cells per operation.
        Let's narrow the scope. Which sheets would you like me to update first?"
```

Configure limits in your `.env` file or use defaults.

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
