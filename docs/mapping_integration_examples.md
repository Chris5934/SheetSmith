# Mapping System Integration Examples

This document shows practical examples of using the header-based mapping system with SheetSmith's operations.

## Example 1: Safe Column Updates Using Header Mapping

Instead of hardcoding column letters, use header-based mappings:

### ❌ Bad (Brittle - breaks when columns are inserted):
```python
# DON'T DO THIS - column letters are fragile
operation = Operation(
    operation_type=OperationType.SET_VALUE_BY_HEADER,
    header_name="B",  # ❌ Will break if column A is inserted
    row_labels=["Character A", "Character B"],
    new_values={"Character A": 100, "Character B": 150},
)
```

### ✅ Good (Robust - survives column insertions):
```python
from sheetsmith.mapping import MappingManager
from sheetsmith.ops import DeterministicOpsEngine

# Initialize managers
sheets_client = GoogleSheetsClient()
mapping_manager = MappingManager(sheets_client)
ops_engine = DeterministicOpsEngine(sheets_client)

await mapping_manager.initialize()

# Get column by header (validates and caches)
mapping = await mapping_manager.get_column_by_header(
    spreadsheet_id="abc123",
    sheet_name="Base",
    header_text="Base Damage"  # ✅ Stable identifier
)

# Use the validated column letter
operation = Operation(
    operation_type=OperationType.SET_VALUE_BY_HEADER,
    header_name=mapping.column_letter,  # ✅ Current, validated position
    row_labels=["Character A", "Character B"],
    new_values={"Character A": 100, "Character B": 150},
)

# Preview and apply
preview = ops_engine.generate_preview("abc123", operation)
result = await ops_engine.apply_changes(preview.preview_id, confirmation=True)
```

## Example 2: Handling Duplicate Headers

When your spreadsheet has multiple columns with the same header name:

```python
from sheetsmith.mapping import DisambiguationRequiredError, DisambiguationResponse

async def update_damage_column(spreadsheet_id: str, sheet_name: str):
    """Update a 'Damage' column, handling potential duplicates."""
    
    mapping_manager = MappingManager(GoogleSheetsClient())
    await mapping_manager.initialize()
    
    try:
        # Try to get the column mapping
        mapping = await mapping_manager.get_column_by_header(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            header_text="Damage"
        )
        
        print(f"Using column {mapping.column_letter}")
        return mapping
        
    except DisambiguationRequiredError as e:
        # Multiple columns have "Damage" as header
        request = e.request
        
        print("Multiple 'Damage' columns found. Please select one:")
        for i, candidate in enumerate(request.candidates):
            print(f"\n{i}. Column {candidate.column_letter}")
            print(f"   Adjacent to: {candidate.adjacent_headers.get('left')} | "
                  f"{candidate.adjacent_headers.get('right')}")
            print(f"   Sample values: {', '.join(candidate.sample_values[:3])}")
        
        # Get user input (in real app, this would be from UI)
        selected = int(input("\nSelect column number: "))
        
        # Store the disambiguation
        response = DisambiguationResponse(
            request_id=request.request_id,
            selected_column_index=selected,
            user_label="Physical Damage"  # User's label for clarity
        )
        
        mapping = await mapping_manager.store_disambiguation(response)
        print(f"Saved preference: using column {mapping.column_letter}")
        return mapping
```

## Example 3: Concept Cell Lookups

Update specific cells by their semantic meaning, not their coordinates:

```python
async def update_character_stat(
    spreadsheet_id: str,
    sheet_name: str,
    character_name: str,
    stat_name: str,
    new_value: int
):
    """Update a character's stat using concept cell mapping."""
    
    mapping_manager = MappingManager(GoogleSheetsClient())
    await mapping_manager.initialize()
    
    # Get the cell by concept (column header × row label)
    cell_mapping = await mapping_manager.get_concept_cell(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        column_header=stat_name,      # e.g., "Base Damage"
        row_label=character_name       # e.g., "Character A"
    )
    
    print(f"Updating {character_name}'s {stat_name} at cell {cell_mapping.cell_address}")
    
    # Now update the cell using the validated address
    # (Use sheets_client or ops_engine to perform the actual update)
    return cell_mapping.cell_address


# Usage
cell_address = await update_character_stat(
    spreadsheet_id="abc123",
    sheet_name="Base",
    character_name="Character A",
    stat_name="Base Damage",
    new_value=125
)
# Output: "Updating Character A's Base Damage at cell B3"
```

## Example 4: Periodic Mapping Audit

Regularly audit mappings to detect layout changes:

```python
async def audit_and_fix_mappings(spreadsheet_id: str):
    """Audit all mappings and report/fix issues."""
    
    mapping_manager = MappingManager(GoogleSheetsClient())
    await mapping_manager.initialize()
    
    # Run the audit
    report = await mapping_manager.audit_mappings(spreadsheet_id)
    
    print(f"\n📊 Mapping Audit for '{report.spreadsheet_title}'")
    print(f"Total mappings: {report.total_mappings}")
    print(f"├─ ✅ Valid: {report.valid_count}")
    print(f"├─ ⚠️  Moved: {report.moved_count}")
    print(f"├─ ❌ Missing: {report.missing_count}")
    print(f"└─ ⚠️  Ambiguous: {report.ambiguous_count}")
    
    # Report issues
    if report.moved_count > 0:
        print("\n⚠️  Moved mappings (automatically updated):")
        for entry in report.entries:
            if entry.status == MappingStatus.MOVED:
                print(f"   • {entry.sheet_name}/{entry.header_text} → {entry.current_address}")
    
    if report.missing_count > 0:
        print("\n❌ Missing mappings (require attention):")
        for entry in report.entries:
            if entry.status == MappingStatus.MISSING:
                print(f"   • {entry.sheet_name}/{entry.header_text}")
                # Delete the invalid mapping
                await mapping_manager.delete_mapping(entry.mapping_id, entry.mapping_type)
    
    if report.ambiguous_count > 0:
        print("\n⚠️  Ambiguous mappings (require disambiguation):")
        for entry in report.entries:
            if entry.status == MappingStatus.AMBIGUOUS:
                print(f"   • {entry.sheet_name}/{entry.header_text}")
    
    return report


# Run audit daily/weekly
report = await audit_and_fix_mappings("abc123")
```

## Example 5: Bulk Operations with Header Validation

Validate all required headers before performing bulk operations:

```python
async def bulk_update_with_validation(
    spreadsheet_id: str,
    sheet_name: str,
    updates: dict[str, dict[str, any]]
):
    """
    Perform bulk updates after validating all required headers exist.
    
    Args:
        spreadsheet_id: The spreadsheet ID
        sheet_name: The sheet name
        updates: Dict mapping header_text to {row_label: value}
                 Example: {"Base Damage": {"Character A": 100, "Character B": 150}}
    """
    
    mapping_manager = MappingManager(GoogleSheetsClient())
    await mapping_manager.initialize()
    
    # Validate all headers exist and are unambiguous
    validated_mappings = {}
    
    print("Validating headers...")
    for header_text in updates.keys():
        try:
            mapping = await mapping_manager.get_column_by_header(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                header_text=header_text
            )
            validated_mappings[header_text] = mapping
            print(f"✅ {header_text} → Column {mapping.column_letter}")
            
        except DisambiguationRequiredError as e:
            print(f"❌ {header_text} has duplicates - disambiguation required")
            raise
        except HeaderNotFoundError as e:
            print(f"❌ {header_text} not found in sheet")
            raise
    
    print(f"\nAll {len(validated_mappings)} headers validated!")
    
    # Now perform the bulk update using validated column letters
    # (Actual update logic would go here using ops_engine)
    
    return validated_mappings


# Usage
updates = {
    "Base Damage": {"Character A": 100, "Character B": 150},
    "Level": {"Character A": 5, "Character B": 7},
    "Health": {"Character A": 500, "Character B": 750},
}

mappings = await bulk_update_with_validation(
    spreadsheet_id="abc123",
    sheet_name="Base",
    updates=updates
)
```

## Example 6: Integration with Search Operations

Combine mapping with search to find and update cells:

```python
from sheetsmith.ops.models import SearchCriteria

async def update_cells_by_header_and_pattern(
    spreadsheet_id: str,
    sheet_name: str,
    header_text: str,
    pattern: str,
    new_value: any
):
    """Find cells in a column by pattern and update them."""
    
    # Get the column by header
    mapping_manager = MappingManager(GoogleSheetsClient())
    await mapping_manager.initialize()
    
    mapping = await mapping_manager.get_column_by_header(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        header_text=header_text
    )
    
    print(f"Searching in column {mapping.column_letter} (header: {header_text})")
    
    # Search for cells matching the pattern in this column
    ops_engine = DeterministicOpsEngine(GoogleSheetsClient())
    
    search_result = ops_engine.search(
        spreadsheet_id=spreadsheet_id,
        criteria=SearchCriteria(
            header_text=header_text,  # ✅ Use header, not column letter
            value_pattern=pattern,
            sheet_names=[sheet_name]
        ),
        limit=100
    )
    
    print(f"Found {search_result.total_count} matching cells")
    
    # Update the matching cells
    # (Actual update logic would go here)
    
    return search_result


# Usage: Find all cells with "Pending" status in "Status" column and update to "Complete"
result = await update_cells_by_header_and_pattern(
    spreadsheet_id="abc123",
    sheet_name="Tasks",
    header_text="Status",
    pattern="Pending",
    new_value="Complete"
)
```

## Best Practices Summary

1. **Always validate before operations**: Get the current column position from the mapping manager before any operation
2. **Handle disambiguation gracefully**: Present clear choices to users when duplicates exist
3. **Run periodic audits**: Check mapping health regularly to catch layout changes
4. **Use concept cells for lookups**: When accessing single cells, use column_header × row_label intersection
5. **Cache wisely**: The mapping manager caches validations, but you can force revalidation by re-fetching
6. **Log disambiguation choices**: Store user labels when disambiguating to make future operations clearer
7. **Fail fast**: If a header doesn't exist, fail the operation early rather than guessing

## Migration Guide

If you have existing code using column letters, here's how to migrate:

### Before (Column Letters):
```python
# Old way - brittle
values = {
    "A": "Name",
    "B": "Value", 
    "C": "Status"
}
```

### After (Header-Based):
```python
# New way - robust
mapping_manager = MappingManager(sheets_client)
await mapping_manager.initialize()

# Get current positions
name_col = await mapping_manager.get_column_by_header(
    spreadsheet_id, sheet_name, "Name"
)
value_col = await mapping_manager.get_column_by_header(
    spreadsheet_id, sheet_name, "Value"
)
status_col = await mapping_manager.get_column_by_header(
    spreadsheet_id, sheet_name, "Status"
)

values = {
    name_col.column_letter: "Name",
    value_col.column_letter: "Value",
    status_col.column_letter: "Status"
}
```

The mapping system ensures your operations continue working even as the spreadsheet structure evolves!
