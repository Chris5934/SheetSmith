# Deterministic Operations API

This document describes the deterministic operations endpoints that enable spreadsheet manipulations without LLM involvement.

## Overview

The ops endpoints provide a three-step workflow:
1. **Search** - Find cells matching criteria
2. **Preview** - Generate a diff of proposed changes
3. **Apply** - Execute the changes after confirmation

All operations are deterministic and use header-based mapping (never column letters).

## Endpoints

### POST `/api/ops/search`

Search for cells matching criteria.

**Request Body:**
```json
{
  "spreadsheet_id": "your-spreadsheet-id",
  "criteria": {
    "header_text": "Amount",           // Optional: Column header name
    "row_label": "Product A",          // Optional: Row identifier
    "formula_pattern": "SUM",          // Optional: Formula pattern (exact or regex)
    "value_pattern": "100",            // Optional: Value pattern
    "case_sensitive": false,
    "is_regex": false,
    "sheet_names": ["Sheet1"]          // Optional: Specific sheets
  },
  "limit": 1000
}
```

**Response:**
```json
{
  "matches": [
    {
      "spreadsheet_id": "...",
      "sheet_name": "Sheet1",
      "cell": "B2",
      "row": 2,
      "col": 1,
      "header": "Amount",
      "row_label": "Product A",
      "value": 100,
      "formula": "=SUM(C2:D2)"
    }
  ],
  "total_count": 1,
  "searched_sheets": ["Sheet1"],
  "execution_time_ms": 125.5
}
```

### POST `/api/ops/preview`

Generate a preview of proposed changes.

**Request Body:**
```json
{
  "spreadsheet_id": "your-spreadsheet-id",
  "operation": {
    "operation_type": "replace_in_formulas",
    "description": "Replace SUM with SUMIF",
    "find_pattern": "SUM",
    "replace_with": "SUMIF"
  }
}
```

**Operation Types:**
- `replace_in_formulas` - Find/replace text in formulas
- `set_value_by_header` - Set values in cells by header + row label
- `bulk_formula_update` - Update formulas matching pattern

**Response:**
```json
{
  "preview_id": "uuid-here",
  "spreadsheet_id": "...",
  "operation_type": "replace_in_formulas",
  "description": "Replace SUM with SUMIF",
  "changes": [
    {
      "sheet_name": "Sheet1",
      "cell": "B2",
      "old_formula": "=SUM(C2:D2)",
      "new_formula": "=SUMIF(C2:D2)",
      "header": "Amount",
      "row_label": "Product A"
    }
  ],
  "scope": {
    "total_cells": 1,
    "affected_sheets": ["Sheet1"],
    "affected_headers": ["Amount"],
    "sheet_count": 1,
    "requires_approval": false
  },
  "diff_text": "--- Sheet1!B2\n-  =SUM(C2:D2)\n+  =SUMIF(C2:D2)\n",
  "created_at": "2026-01-21T00:00:00",
  "expires_at": "2026-01-21T00:30:00",
  "dry_run": false
}
```

**Safety Features (NEW):**

The preview endpoint includes comprehensive safety validation:

- **Hard Limits**: Operations exceeding configured limits (cells, sheets, formula length) are blocked
- **Risk Assessment**: Operations are classified as low/medium/high risk based on scope
- **Scope Analysis**: Detailed analysis showing affected sheets, columns, rows, and estimated duration
- **Preview Requirement**: Large operations (> threshold) require explicit preview before execution
- **Automatic Blocking**: Operations exceeding hard limits are automatically rejected with clear error messages

Configuration options (via environment variables):
```bash
MAX_CELLS_PER_OPERATION=500          # Maximum cells per operation
MAX_SHEETS_PER_OPERATION=40          # Maximum sheets per operation
MAX_FORMULA_LENGTH=50000             # Maximum formula length
REQUIRE_PREVIEW_ABOVE_CELLS=10       # Preview required above this threshold
PREVIEW_TTL_SECONDS=300              # Preview expiration (5 minutes)
```

### POST `/api/ops/apply`

Apply previously previewed changes.

**Request Body:**
```json
{
  "preview_id": "uuid-from-preview-response",
  "confirmation": true
}
```

**Response:**
```json
{
  "success": true,
  "preview_id": "...",
  "spreadsheet_id": "...",
  "cells_updated": 1,
  "errors": [],
  "audit_log_id": "...",
  "applied_at": "2026-01-21T00:00:00"
}
```

## Safety Limits

The following limits are enforced (configurable via environment variables):

- `MAX_CELLS_PER_OPERATION` (default: 500)
- `MAX_SHEETS_PER_OPERATION` (default: 40)
- `MAX_FORMULA_LENGTH` (default: 50000)
- `REQUIRE_PREVIEW_ABOVE_CELLS` (default: 10)

Operations affecting more than `REQUIRE_PREVIEW_ABOVE_CELLS` require explicit confirmation.

## Example Workflows

### Replace text in formulas

```bash
# 1. Generate preview
curl -X POST http://localhost:8000/api/ops/preview \
  -H "Content-Type: application/json" \
  -d '{
    "spreadsheet_id": "your-id",
    "operation": {
      "operation_type": "replace_in_formulas",
      "description": "Replace OLD with NEW",
      "find_pattern": "OLD",
      "replace_with": "NEW"
    }
  }'

# 2. Review the preview response

# 3. Apply changes
curl -X POST http://localhost:8000/api/ops/apply \
  -H "Content-Type: application/json" \
  -d '{
    "preview_id": "uuid-from-step-1",
    "confirmation": true
  }'
```

### Update values by header and row

```bash
curl -X POST http://localhost:8000/api/ops/preview \
  -H "Content-Type: application/json" \
  -d '{
    "spreadsheet_id": "your-id",
    "operation": {
      "operation_type": "set_value_by_header",
      "description": "Update prices",
      "header_name": "Price",
      "row_labels": ["Product A", "Product B"],
      "new_values": {
        "Product A": "99.99",
        "Product B": "149.99"
      }
    }
  }'
```

## Audit Trail (Enhanced)

All applied operations are automatically logged to the audit trail with comprehensive details:

**Logged Information:**
- Timestamp and duration
- Operation type and status (success/failed/cancelled)
- Spreadsheet ID and user
- Preview ID (if applicable)
- Scope details (cells, sheets affected)
- Changes applied count
- Error messages (if any)

**Accessing Audit Logs:**

```bash
# Get recent audit logs
GET /api/audit-logs?limit=50

# Filter by spreadsheet
GET /api/audit-logs?spreadsheet_id=your-id&limit=100
```

**Response:**
```json
{
  "count": 2,
  "logs": [
    {
      "id": "audit-123",
      "timestamp": "2026-01-21T20:00:00",
      "action": "replace_in_formulas",
      "spreadsheet_id": "sheet-456",
      "description": "replace_in_formulas - success",
      "changes_applied": 15
    }
  ]
}
```

## Safety Limits

The following safety limits are enforced (configurable via environment variables):
- Spreadsheet ID
- Description
- Number of changes applied
- Success/failure status

Access audit logs via `/api/audit-logs`.

## Notes

- Previews expire after 30 minutes (configurable)
- All operations use header-based mapping (never column letters)
- No LLM calls are made during operations
- Changes are applied atomically where possible
- Preview IDs are single-use and removed after successful application
