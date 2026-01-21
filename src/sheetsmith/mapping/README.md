# Header-Based Mapping System

A robust column and concept cell mapping system that uses stable header text instead of volatile column letters. This system handles duplicate headers through user disambiguation and caches mappings for reuse.

## Core Principle

**NEVER use column letters (A, B, C, etc.) for automated actions.** Column letters shift when columns are inserted/deleted, breaking automation. Always use stable identifiers: header text, row labels, and named ranges.

## Features

### 1. Header-Based Column Mapping

Map columns by unique header text, not by letter position:

```python
from sheetsmith.mapping import MappingManager
from sheetsmith.sheets import GoogleSheetsClient

# Initialize
sheets_client = GoogleSheetsClient()
manager = MappingManager(sheets_client)
await manager.initialize()

# Get column by header text
mapping = await manager.get_column_by_header(
    spreadsheet_id="abc123",
    sheet_name="Base",
    header_text="Base Damage"
)

print(f"Column: {mapping.column_letter}")  # e.g., "F"
print(f"Index: {mapping.column_index}")    # e.g., 5
```

### 2. Concept Cell Mapping (Row × Column Intersection)

Map single-value "concept cells" by column header and row label:

```python
# Get cell at intersection of column header and row label
cell = await manager.get_concept_cell(
    spreadsheet_id="abc123",
    sheet_name="Base",
    column_header="Base Damage",
    row_label="Character A"
)

print(f"Cell: {cell.cell_address}")  # e.g., "F3"
```

### 3. Duplicate Header Disambiguation

When multiple columns share the same header, the system requires user disambiguation:

```python
from sheetsmith.mapping import DisambiguationRequiredError, DisambiguationResponse

try:
    mapping = await manager.get_column_by_header(
        spreadsheet_id="abc123",
        sheet_name="Base",
        header_text="Damage"  # Appears in multiple columns
    )
except DisambiguationRequiredError as e:
    # Present candidates to user
    request = e.request
    print(f"Request ID: {request.request_id}")
    
    for i, candidate in enumerate(request.candidates):
        print(f"\nCandidate {i}:")
        print(f"  Column: {candidate.column_letter}")
        print(f"  Sample values: {candidate.sample_values}")
        print(f"  Left header: {candidate.adjacent_headers.get('left')}")
        print(f"  Right header: {candidate.adjacent_headers.get('right')}")
    
    # User selects candidate 1
    response = DisambiguationResponse(
        request_id=request.request_id,
        selected_column_index=1,
        user_label="Elemental Damage"
    )
    
    # Store the disambiguation choice
    mapping = await manager.store_disambiguation(response)
```

### 4. Mapping Validation and Health Checks

Validate cached mappings before use:

```python
# Audit all mappings for a spreadsheet
report = await manager.audit_mappings("abc123")

print(f"Total mappings: {report.total_mappings}")
print(f"Valid: {report.valid_count}")
print(f"Moved: {report.moved_count}")
print(f"Missing: {report.missing_count}")
print(f"Ambiguous: {report.ambiguous_count}")

# Check each mapping
for entry in report.entries:
    if entry.status == MappingStatus.MOVED:
        print(f"⚠️ {entry.header_text} moved to {entry.current_address}")
    elif entry.status == MappingStatus.MISSING:
        print(f"❌ {entry.header_text} not found")
    elif entry.status == MappingStatus.AMBIGUOUS:
        print(f"⚠️ {entry.header_text} has duplicates - needs disambiguation")
```

### 5. Layout Change Detection

The system automatically detects when headers move or disappear:

```python
# Get a column (will validate if cached)
mapping = await manager.get_column_by_header(
    spreadsheet_id="abc123",
    sheet_name="Base",
    header_text="Base Damage"
)

# If the header moved, the mapping is automatically updated
# If the header is missing, HeaderNotFoundError is raised
# If duplicates are detected, DisambiguationRequiredError is raised
```

## API Endpoints

### GET /mappings/{spreadsheet_id}/audit

Audit all mappings for a spreadsheet:

```bash
curl http://localhost:8000/mappings/abc123/audit
```

Response:
```json
{
  "spreadsheet_id": "abc123",
  "spreadsheet_title": "My Spreadsheet",
  "total_mappings": 10,
  "summary": {
    "valid": 8,
    "moved": 1,
    "missing": 0,
    "ambiguous": 1
  },
  "entries": [
    {
      "mapping_id": 1,
      "mapping_type": "column",
      "sheet_name": "Base",
      "header_text": "Base Damage",
      "current_address": "F",
      "status": "valid",
      "needs_action": false,
      "last_validated_at": "2024-01-20T10:30:00"
    }
  ],
  "generated_at": "2024-01-20T10:35:00"
}
```

### POST /mappings/disambiguate

Store user's disambiguation choice:

```bash
curl -X POST http://localhost:8000/mappings/disambiguate \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "selected_column_index": 1,
    "user_label": "Elemental Damage"
  }'
```

### DELETE /mappings/{mapping_id}

Delete a mapping:

```bash
curl -X DELETE http://localhost:8000/mappings/123?mapping_type=column
```

### POST /mappings/validate

Validate a specific mapping:

```bash
curl -X POST http://localhost:8000/mappings/validate \
  -H "Content-Type: application/json" \
  -d '{
    "mapping_id": 123,
    "mapping_type": "column"
  }'
```

## Database Schema

The mapping system uses a single table to store both column and cell mappings:

```sql
CREATE TABLE column_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    header_text TEXT NOT NULL,
    row_label TEXT NULL,  -- NULL for column mappings, set for cell mappings
    column_letter TEXT NOT NULL,
    column_index INTEGER NOT NULL,
    header_row INTEGER NOT NULL DEFAULT 0,
    cell_address TEXT NULL,  -- NULL for column mappings, set for cell mappings
    disambiguation_context TEXT NULL,  -- JSON with disambiguation info
    last_validated_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(spreadsheet_id, sheet_name, header_text, row_label)
);
```

## Testing

Run the mapping system tests:

```bash
pytest tests/test_mapping.py -v
```

All tests cover:
- Column mapping creation and retrieval
- Cell mapping creation and retrieval
- Duplicate header disambiguation
- Mapping validation (valid, moved, missing)
- Audit report generation

## Error Handling

The mapping system raises specific exceptions for different scenarios:

- `HeaderNotFoundError`: Header text not found in sheet
- `DisambiguationRequiredError`: Multiple columns have the same header
- `MappingNotFoundError`: Requested mapping doesn't exist (when auto_create=False)

## Best Practices

1. **Always use headers**: Never hardcode column letters in your operations
2. **Handle disambiguation**: Present clear options to users when duplicates exist
3. **Validate periodically**: Run audits to catch stale mappings
4. **Store context**: When disambiguating, provide user labels for clarity
5. **Use concept cells**: For single-value lookups, prefer concept cells over column-only mappings

## Integration with Ops Engine

The deterministic ops engine can use the mapping manager for all column lookups:

```python
from sheetsmith.ops import DeterministicOpsEngine
from sheetsmith.mapping import MappingManager

# Initialize both
sheets_client = GoogleSheetsClient()
mapping_manager = MappingManager(sheets_client)
ops_engine = DeterministicOpsEngine(sheets_client)

# Before operations, validate all required mappings
await mapping_manager.get_column_by_header(
    spreadsheet_id, sheet_name, "Base Damage"
)

# Then perform operations using the validated mappings
# The ops engine can query mapping_manager for column locations
```

## Architecture

```
MappingManager
  ├── MappingStorage (database persistence)
  ├── MappingValidator (validation logic)
  └── DisambiguationHandler (disambiguation requests)
```

- **MappingManager**: Main entry point, coordinates all operations
- **MappingStorage**: Handles database CRUD operations
- **MappingValidator**: Validates mappings against current spreadsheet state
- **DisambiguationHandler**: Manages disambiguation requests and responses

## Future Enhancements

- Persistent disambiguation request storage (currently in-memory)
- Mapping versioning and history
- Bulk mapping operations
- Mapping export/import
- Integration with named ranges
- Support for structured references
