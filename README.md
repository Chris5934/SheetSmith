# SheetSmith — Agentic Google Sheets Automation Assistant

## Project overview
SheetSmith is an LLM-based agent with a simple web UI that helps maintain and update complex Google Sheets models.

The goal of the project is to automate repetitive, error-prone spreadsheet work such as propagating small logic changes across many sheets, auditing formulas, and safely applying batch updates. The agent connects directly to the Google Sheets API to read data and formulas, reason about them, suggest changes, and optionally write updates back to the sheet.

This project is motivated by my own experience maintaining large spreadsheet-based calculators, where small updates often require manual edits across many tabs and files.

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
Many of my formulas contain logic that represents part of a character’s kit.  
For example, a mapping from status name to a damage ratio:

    SWITCH(TRIM(statusNow),
      "Corruption", 28.6%,
      "Shock", 14.9%,
      "Burn", 37.1%,
      0
    )

This mapping from status → damage ratio is identical across all sheets, even though the surrounding formula references different stat cells per sheet.

If one value changes (for example, Corruption becomes 30.0%), I must manually update this logic everywhere, even though the rest of each formula should remain untouched.

---

## Additional recurring pain points

### Teammate replacement
Sheets often encode teammate logic directly into formulas (buff windows, triggers, multipliers, and rotation interactions).

When I replace a teammate, I must:
- remove all formulas associated with the old teammate,
- insert the new teammate’s logic,
- rewire references so the rest of the sheet still functions correctly.

This process is largely mechanical but must be done carefully.

---

### Rotation fixes
Some sheets share the exact same rotation logic.
If I discover a mistake in a rotation (timing, trigger condition, or ordering), I must manually update every sheet that uses that rotation.

There is no single “source of truth” for rotations or teammate logic; instead, they are copied and slightly adapted across sheets, making global fixes tedious and error-prone.

---

## What I want to automate
SheetSmith is intended to automate tasks such as:
- Finding all formulas that contain a specific piece of shared logic.
- Suggesting targeted updates (e.g., changing one coefficient or condition without altering stat wiring).
- Replacing teammate or rotation logic across multiple sheets in a consistent way.
- Applying batch updates safely across many tabs or files.
- Generating a patch or diff so changes can be reviewed before being applied.
- Logging applied changes for auditability.

---

## Agent capabilities (planned)
The agent will:
- Connect to the Google Sheets API.
- Read cell values and formulas.
- Search for formulas matching specific patterns.
- Distinguish shared logic (kits, teammates, rotations) from sheet-specific wiring (stats, ranges).
- Generate a structured patch describing proposed edits.
- Optionally apply those edits via batch updates.

---

## MCP tools (planned)
Planned tools include:
1. gsheets.read_range — read values and formulas from a sheet.
2. gsheets.search_formulas — locate formulas matching a pattern across sheets.
3. gsheets.batch_update — apply multiple updates safely in one operation.
4. memory.store_rule / memory.get_rules — store long-term project conventions (formula style rules, known logic blocks).

---

## Long-term memory
The agent will store:
- Project-specific rules (e.g., how formulas should be written).
- Summaries of previous fixes.
- Known mappings and logic blocks that represent character kits, teammates, or rotations.

This allows the agent to improve suggestions over time and adapt to a specific spreadsheet ecosystem.

---

## Sample data (planned)
This repository will include a `/sample_data` folder containing fake spreadsheet exports and example patches that demonstrate the expected structure of inputs and outputs, without using real data.

At the time of submission, this folder has not yet been populated and serves as a placeholder for future development.


---

## Intended demo scenario
1. Connect the agent to a test Google Sheet.
2. Ask: “Update the Corruption ratio in the Abloom formula from 28.6% to 30.0% everywhere.”
3. The agent finds matching formulas, proposes a patch, and shows a diff.
4. The user approves the patch, and the agent applies it via batch update.

