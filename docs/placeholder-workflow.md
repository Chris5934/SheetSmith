# Placeholder Workflow

## Overview

The **Placeholder Mapping Assistant** allows you to write formulas using human-readable placeholders (like `{{column_name}}`) instead of cell references. SheetSmith resolves these placeholders to actual cell addresses **without inventing any formula logic**. This approach is:

- **Safer**: You control the formula logic, not the LLM
- **Cheaper**: Minimal or no LLM usage for straightforward mappings
- **Easier to audit**: Clear mapping from placeholder to cell reference

## Core Principle

**You own the formula logic; SheetSmith only maps placeholders to actual cell addresses.**

SheetSmith never generates formula logic. It only:
1. Detects placeholders in your formula
2. Finds matching headers in your spreadsheet
3. Replaces placeholders with cell references
4. Previews the result before applying

## Placeholder Syntax

### 1. Simple Header Reference: `{{header_name}}`

References a column by its header name in the current row.

**Example:**
```
={{base_damage}} * 1.5
```

**Resolution:**
- Finds column with header "Base Damage"
- Resolves to current row (e.g., row 2)
- Result: `=F2 * 1.5`

### 2. Intersection Reference: `{{header_name:row_label}}`

References a specific cell at the intersection of a column header and row label.

**Example:**
```
={{base_damage}} * {{multiplier:Jane}}
```

**Resolution:**
- `{{base_damage}}` → column "Base Damage" in current row
- `{{multiplier:Jane}}` → cell at column "Multiplier" and row with label "Jane"
- Result: `=F2 * $G$15`

Note: Intersection references are always absolute (`$G$15`) since they point to a specific cell.

### 3. Cross-Sheet Reference: `'Sheet'!{{header}}`

References a column in a different sheet.

**Example:**
```
='KitData'!{{burn_bonus}}
```

**Resolution:**
- Looks in sheet "KitData"
- Finds column with header "Burn Bonus"
- Result: `='KitData'!$C$2`

### 4. Variable Reference: `${variable}` (Future)

References a stored constant or variable. Not yet implemented.

## Use Cases

### Example 1: User-Generated Formula

**Your Formula:**
```
=SWITCH({{active_anom}}, "Burn", 0.5, "Shock", 1, "Corruption", 0.5, "iCorruption", 0.5, 0)
```

**SheetSmith Process:**
1. Detects placeholder: `{{active_anom}}`
2. Searches for header "Active Anom" in your spreadsheet
3. Finds it in column B
4. Replaces placeholder with cell reference

**Resolved Formula:**
```
=SWITCH($B$2, "Burn", 0.5, "Shock", 1, "Corruption", 0.5, "iCorruption", 0.5, 0)
```

**Next Steps:**
- Preview shows the resolved formula
- You verify it looks correct
- Apply to your spreadsheet

### Example 2: Calculation with Multiple Columns

**Your Formula:**
```
={{base_damage}} * {{multiplier}} + {{bonus_damage}}
```

**Resolution:**
- `{{base_damage}}` → F2 (Base Damage column, current row)
- `{{multiplier}}` → G2 (Multiplier column, current row)
- `{{bonus_damage}}` → H2 (Bonus Damage column, current row)

**Result:**
```
=F2 * G2 + H2
```

### Example 3: Row-Specific Value

**Your Formula:**
```
={{base_damage}} * {{multiplier:Jane}}
```

**Resolution:**
- `{{base_damage}}` → F2 (current row)
- `{{multiplier:Jane}}` → $G$15 (Jane's row in Multiplier column)

**Result:**
```
=F2 * $G$15
```

This is useful when you want to reference a specific teammate's stats.

### Example 4: Cross-Sheet Lookup

**Your Formula:**
```
={{base_damage}} * 'Constants'!{{damage_modifier}}
```

**Resolution:**
- `{{base_damage}}` → F2 (current sheet)
- `'Constants'!{{damage_modifier}}` → 'Constants'!$B$2

**Result:**
```
=F2 * 'Constants'!$B$2
```

## API Endpoints

### 1. Parse Placeholders

**Endpoint:** `POST /placeholders/parse`

**Purpose:** Extract and validate placeholders without resolving them.

**Request:**
```json
{
  "formula": "={{base_damage}} * {{multiplier}}",
  "spreadsheet_id": "your-spreadsheet-id",
  "sheet_name": "Base",
  "target_row": 2
}
```

**Response:**
```json
{
  "placeholders": [
    {
      "name": "base_damage",
      "type": "header",
      "syntax": "{{base_damage}}",
      "sheet": null,
      "row_label": null
    },
    {
      "name": "multiplier",
      "type": "header",
      "syntax": "{{multiplier}}",
      "sheet": null,
      "row_label": null
    }
  ],
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  }
}
```

### 2. Resolve Placeholders

**Endpoint:** `POST /placeholders/resolve`

**Purpose:** Resolve all placeholders to cell references.

**Request:**
```json
{
  "formula": "={{base_damage}} * {{multiplier}}",
  "spreadsheet_id": "your-spreadsheet-id",
  "sheet_name": "Base",
  "target_row": 2,
  "absolute_references": false
}
```

**Response:**
```json
{
  "resolved_formula": "=F2 * G2",
  "mappings": [
    {
      "placeholder": "{{base_damage}}",
      "resolved_to": "F2",
      "header": "Base Damage",
      "column": "F",
      "row": 2,
      "confidence": 1.0
    },
    {
      "placeholder": "{{multiplier}}",
      "resolved_to": "G2",
      "header": "Multiplier",
      "column": "G",
      "row": 2,
      "confidence": 1.0
    }
  ],
  "warnings": []
}
```

### 3. Preview Mappings

**Endpoint:** `POST /placeholders/preview`

**Purpose:** See potential matches for placeholders before resolving.

**Request:**
```json
{
  "formula": "={{base_damage}} * {{multiplier}}",
  "spreadsheet_id": "your-spreadsheet-id",
  "sheet_name": "Base",
  "target_row": 2
}
```

**Response:**
```json
{
  "formula": "={{base_damage}} * {{multiplier}}",
  "placeholders": [...],
  "potential_mappings": {
    "{{base_damage}}": ["Base Damage", "Damage Base"],
    "{{multiplier}}": ["Multiplier", "Mult"]
  },
  "requires_disambiguation": []
}
```

### 4. Apply Formula

**Endpoint:** `POST /placeholders/apply`

**Purpose:** Resolve placeholders and apply formula to cells.

**Request:**
```json
{
  "formula": "={{base_damage}} * {{multiplier}}",
  "spreadsheet_id": "your-spreadsheet-id",
  "target": {
    "sheet_name": "Base",
    "header": "Total Damage",
    "rows": [2, 3, 4, 5]
  }
}
```

**Response:**
```json
{
  "preview_id": "preview-abc123",
  "resolved_formula": "=F2 * G2",
  "original_formula": "={{base_damage}} * {{multiplier}}",
  "mappings": [...],
  "scope": {
    "total_cells": 4,
    "affected_sheets": ["Base"],
    "affected_headers": ["Total Damage"]
  },
  "message": "Preview ready. Use preview_id with /ops/apply to apply changes."
}
```

**Next Step:** Call `/ops/apply` with the `preview_id` to apply changes.

## Handling Ambiguity

### Duplicate Headers

If multiple columns have the same header, SheetSmith will return a disambiguation request:

**Error Response (HTTP 409):**
```json
{
  "error": "disambiguation_required",
  "message": "Multiple columns found with header 'Damage'",
  "request_id": "disambig-xyz789",
  "header_text": "Damage",
  "candidates": [
    {
      "column_letter": "F",
      "column_index": 5,
      "header_row": 1,
      "sample_values": [100, 120, 95],
      "adjacent_headers": {
        "left": "Name",
        "right": "Multiplier"
      }
    },
    {
      "column_letter": "J",
      "column_index": 9,
      "header_row": 1,
      "sample_values": [50, 60, 45],
      "adjacent_headers": {
        "left": "Defense",
        "right": "Total"
      }
    }
  ]
}
```

**Resolution:**
Use the `/mappings/disambiguate` endpoint to specify which column to use:

```json
{
  "request_id": "disambig-xyz789",
  "selected_column_index": 5,
  "user_label": "Base Damage (not Bonus Damage)"
}
```

SheetSmith will remember your choice for future operations.

## Best Practices

### Placeholder Naming

1. **Use descriptive names:**
   - Good: `{{base_damage}}`, `{{multiplier}}`
   - Avoid: `{{x}}`, `{{val1}}`

2. **Match your header names:**
   - If header is "Base Damage", use `{{base_damage}}` or `{{Base Damage}}`
   - SheetSmith is flexible with spaces vs underscores and case

3. **Be consistent:**
   - Use the same naming pattern throughout your formulas
   - Either `snake_case` or `Space Case`, not both

### Formula Design

1. **Keep formula logic visible:**
   - Don't hide complex logic in placeholders
   - Placeholders should only represent cell references

2. **Use absolute references for constants:**
   - When referencing fixed values, use intersection syntax
   - Example: `{{modifier:Master}}` instead of `{{modifier}}`

3. **Test with preview first:**
   - Always call `/placeholders/preview` before `/placeholders/resolve`
   - Verify mappings make sense

### Error Handling

1. **Check validation results:**
   - Parse endpoint returns validation errors
   - Fix syntax errors before attempting resolution

2. **Handle missing headers gracefully:**
   - If a header doesn't exist, you'll get a 404 error
   - Consider using `/placeholders/preview` to see available headers

3. **Store disambiguation choices:**
   - When you disambiguate, SheetSmith caches your choice
   - Future operations will use the same mapping automatically

## Integration with Other Features

### With Deterministic Ops (Issue #2)

Placeholder resolution integrates seamlessly with the deterministic ops engine:

1. You provide a formula with placeholders
2. SheetSmith resolves placeholders (deterministically, no LLM)
3. The resolved formula goes to `/ops/preview`
4. You review the preview
5. Apply via `/ops/apply`

No LLM usage except for optional disambiguation assistance.

### With Header Mapping (Issue #3)

Placeholders use the header mapping system:

- Cached header mappings speed up resolution
- User disambiguation choices are respected
- Mapping validation detects moved/missing headers

### With Safety & Preview (Issue #5)

All placeholder operations include safety checks:

- Preview required before applying changes
- Scope summary shows affected cells
- Clear before/after values for each change

### With LLM Budget (Issue #6)

Placeholder resolution is designed for minimal LLM usage:

- Deterministic header matching (no LLM)
- Optional LLM assistance only for ambiguous cases
- Tiny prompts when LLM is needed

## Troubleshooting

### "Header not found"

**Problem:** SheetSmith can't find the header you referenced.

**Solutions:**
1. Check spelling and capitalization
2. Use `/placeholders/preview` to see available headers
3. Verify the sheet name is correct for cross-sheet references

### "Multiple columns with same header"

**Problem:** Duplicate headers require disambiguation.

**Solutions:**
1. Review the candidates returned in the error
2. Use `/mappings/disambiguate` to select the correct column
3. Consider renaming duplicate headers in your spreadsheet

### "Invalid placeholder syntax"

**Problem:** Malformed placeholder (missing brackets, etc.)

**Solutions:**
1. Check bracket matching: `{{name}}` not `{{name}`
2. Verify placeholder name is valid (alphanumeric, starts with letter)
3. Use `/placeholders/parse` to validate syntax before resolving

### "Formula doesn't start with ="

**Problem:** Formula is missing the equals sign.

**Solutions:**
1. Add `=` at the start: `={{damage}}` not `{{damage}}`
2. This is just a warning - formulas work without it, but Sheets expects it

## Examples

### Complete Workflow: Simple Formula

```bash
# 1. Parse and validate
curl -X POST http://localhost:8000/placeholders/parse \
  -H "Content-Type: application/json" \
  -d '{
    "formula": "={{base_damage}} * 1.5",
    "spreadsheet_id": "abc123",
    "sheet_name": "Base",
    "target_row": 2
  }'

# 2. Preview mappings
curl -X POST http://localhost:8000/placeholders/preview \
  -H "Content-Type: application/json" \
  -d '{
    "formula": "={{base_damage}} * 1.5",
    "spreadsheet_id": "abc123",
    "sheet_name": "Base",
    "target_row": 2
  }'

# 3. Resolve placeholders
curl -X POST http://localhost:8000/placeholders/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "formula": "={{base_damage}} * 1.5",
    "spreadsheet_id": "abc123",
    "sheet_name": "Base",
    "target_row": 2
  }'

# 4. Apply to cells
curl -X POST http://localhost:8000/placeholders/apply \
  -H "Content-Type: application/json" \
  -d '{
    "formula": "={{base_damage}} * 1.5",
    "spreadsheet_id": "abc123",
    "target": {
      "sheet_name": "Base",
      "header": "Adjusted Damage",
      "rows": [2, 3, 4, 5]
    }
  }'

# 5. Apply changes (use preview_id from step 4)
curl -X POST http://localhost:8000/ops/apply \
  -H "Content-Type: application/json" \
  -d '{
    "preview_id": "preview-abc123",
    "confirmation": true
  }'
```

### Complete Workflow: Complex Formula

```python
import requests

# Your formula with placeholders
formula = """
=SWITCH({{active_anom}},
  "Burn", {{burn_mult:Jane}} * {{base_damage}},
  "Shock", {{shock_mult:Jane}} * {{base_damage}},
  0
)
"""

# 1. Resolve placeholders
response = requests.post(
    "http://localhost:8000/placeholders/resolve",
    json={
        "formula": formula,
        "spreadsheet_id": "your-id",
        "sheet_name": "Calculations",
        "target_row": 2,
    }
)

resolved = response.json()
print(f"Resolved: {resolved['resolved_formula']}")

# 2. Apply to cells
response = requests.post(
    "http://localhost:8000/placeholders/apply",
    json={
        "formula": formula,
        "spreadsheet_id": "your-id",
        "target": {
            "sheet_name": "Calculations",
            "header": "Anomaly Damage",
            "rows": list(range(2, 102))  # Rows 2-101
        }
    }
)

preview = response.json()
print(f"Preview ID: {preview['preview_id']}")
print(f"Scope: {preview['scope']}")

# 3. Review and apply
input("Review the preview and press Enter to apply...")

response = requests.post(
    "http://localhost:8000/ops/apply",
    json={
        "preview_id": preview["preview_id"],
        "confirmation": True
    }
)

result = response.json()
print(f"Applied! {result['cells_updated']} cells updated")
```

## Conclusion

The Placeholder Mapping Assistant gives you:

- **Control**: You write the formulas, SheetSmith just maps names to cells
- **Safety**: Preview before applying, with clear scope information
- **Efficiency**: No LLM for straightforward mappings, minimal cost
- **Flexibility**: Support for simple references, intersections, and cross-sheet lookups

Use placeholders to make your formulas more readable and maintainable, while keeping full control over the logic.
