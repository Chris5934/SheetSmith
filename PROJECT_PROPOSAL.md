# PROJECT_PROPOSAL.md
## Project Title
**SheetSmith TC Agent: Link-to-Sheet Kit Compiler + Spreadsheet Verifier**

## One-sentence pitch
A web app where an LLM-based agent ingests a character kit from a user-provided URL, compiles it into a structured “kit module,” proposes safe spreadsheet patches (diff preview → apply), and continuously verifies my theorycrafting workbook for mistakes and inconsistencies using MCP tools and long-term memory.

---

## Context (so this makes sense if you don’t do theorycrafting)
I maintain large Google Sheets workbooks used for “theorycrafting” damage calculations. Each character has a tab with formulas that compute expected damage under assumptions (rotation length, buffs, enemy states, stacks, etc.). These spreadsheets evolve constantly:
- adding/removing characters or builds (new columns, shifted layouts)
- updating kit mechanics when upstream info changes
- fixing subtle formula mistakes across 20–40 tabs

The hardest pain is *consistency at scale*: a small kit/balance change can require updating dozens of formulas in many tabs. Doing this manually is slow and error-prone.

This project builds an **agentic application** that can: fetch kit info from a URL I give it, normalize it into a schema, generate a patch plan, preview exact diffs, apply changes safely, and verify the workbook afterward — while learning my spreadsheet conventions over time.

---

## Why this is ambitious (not “one evening”)
This is not just chat. The agent must:
- Orchestrate **multi-step tool use** (fetch/normalize/diff/search/patch/verify)
- Maintain **project memory** (sheet schema, mappings, learned module patterns, prior patches)
- Generate **patch previews** and enforce guardrails (no silent edits)
- Support “upstream source changed → detect diff → propose update patch”
- Produce **verification reports** (new errors, inconsistent implementations, drift)
- Provide a GUI plus a reusable toolchain (MCP tools)

Even partial success is meaningful because it produces traceable artifacts: tool-call traces, patches, diffs, verification reports, and learned mappings.

---

## Users
Primary user: **me** (maintaining my own TC spreadsheets).  
Optional future users: other spreadsheet-heavy hobbyists.

---

## UI / App shape (required GUI)
**Web interface** with:
1) **Tools Panel (Deterministic / Safe Mode)**  
   Forms that run deterministic batch operations without the LLM:
   - Scoped “Replace in formulas” (sheet + columns + row range)
   - Set value across sheets via Header + RowLabel intersection
   - Copy a “module block” from a template to target tabs
   - Audit: list matches, list spreadsheet errors, list inconsistent references  
   Every write action: **Preview diff → explicit Apply**

2) **Agent Chat (Agentic Mode)**  
   Natural language requests like:
   - “Import this character from this URL and implement their passive.”
   - “Upstream kit changed—update my modules and verify nothing broke.”
   - “Find why this sheet has #DIV/0 and propose a fix.”  
   The agent never applies edits directly; it must call tools, produce a patch preview, and request approval.

---

## Agent behavior (rules / guardrails)
- Default workflow: **Plan → Tool calls → Patch preview → Ask approval → Apply → Verify**
- Never “freeform edit” a workbook without a diff preview.
- Hard limits (configurable):
  - max sheets touched per action
  - max cells changed per patch
- If sheet structure is ambiguous (duplicate headers, missing headers), agent must:
  - ask user to disambiguate OR
  - run an audit and refuse to guess

---

## Ambitious Core B: Link-to-Sheet Kit Ingestion + Update Pipeline
### Feature B1: “Paste a URL → ingest kit → compile to module”
User provides a link to a public third-party character database page (URL).  
The system uses tools to fetch and normalize the page into a structured kit schema:

**Normalized kit schema includes:**
- skills/actions (basic/skill/ult/passive/etc.)
- textual descriptions by section
- extracted numeric multipliers if available (e.g., “0.45 × ATK”)
- triggers/conditions (“when…”, “after…”, “for N seconds”)
- caps (max stacks/procs)
- tags (damage type, buff type, resource type)

Then the agent compiles a “kit module patch” for my spreadsheet template:
- writes formulas into a designated “kit module” block
- uses placeholder resolution (concept → header/rowlabel → A1 refs)
- generates a diff preview and requests approval

### Feature B2: “Detect upstream changes → propose update patch”
The system stores a versioned snapshot hash of the ingested kit data.  
When re-checking the URL later:
- tool computes structured diff vs stored snapshot
- agent maps diff → impacted spreadsheet module(s)
- proposes patch preview for updates
- applies only after approval
- runs verifier checks and writes a ChangeLog entry

---

## Ambitious Core C: Spreadsheet Verifier + Mistake/Optimization Detector
After any patch preview/apply (and optionally on demand), the agent runs automated checks and creates a report:
- new spreadsheet errors introduced (#DIV/0!, #REF!, #N/A)
- inconsistent references across character tabs (e.g., some still use an old baseline)
- duplicate/ambiguous headers causing unreliable automation
- “pattern drift”: a shared logic block implemented differently across tabs
- suspected opportunities for simplification (optional suggestions, never auto-applied)

This makes the agent useful even when “kit compilation” is imperfect.

---

## “Learning my TC process” (controlled learning from examples)
I already have several character tabs where kits are implemented correctly.  
The agent will:
1) extract those kit module blocks + context,
2) infer a reusable module template pattern (“how I structure this workbook”),
3) store the recipe in long-term memory,
4) apply it when generating new modules or updating existing ones.

Stretch goal (explicitly optional): propose rotation ideas as *suggestions* only, with simulation/verification hooks, not auto-application.

---

## MCP Tools (requirement: at least 3)
I will run an MCP tool server that exposes tools the agent calls during workflows.
Minimum 3 tools (I plan 6 for ambition):

### Tool category: web kit ingest
1) **`web_kit.fetch(url_or_id)`**  
   Fetch a character page from a user-provided URL and return raw + parsed content.

2) **`web_kit.normalize(raw_payload)`**  
   Convert raw content into my normalized kit schema (skills, triggers, caps, multipliers, tags).

3) **`web_kit.diff(character_id_or_url)`**  
   Compare current fetched kit to stored snapshot; return structured diff + new hash; store snapshot.

### Tool category: sheets patching
4) **`gsheets.search_formulas(spreadsheet_id, pattern, scope)`**  
   Deterministic search across sheets/ranges; returns match list.

5) **`gsheets.preview_patch(spreadsheet_id, changes)`**  
   Generates diff preview (old/new) + patch_id. Required before apply.

6) **`gsheets.apply_patch(patch_id)`**  
   Applies patch; appends to a `ChangeLog` tab and stores patch metadata in DB.

(Only 3 are required; this plan exceeds that.)

---

## Long-term memory (requirement)
Two layers:

### A) Project memory DB (SQLite)
Stores:
- spreadsheet metadata + per-project settings
- inferred sheet schema (header row, label column)
- duplicate-header disambiguation choices (ask once → remember)
- placeholder mappings (concept → resolved cell/range)
- kit snapshots + hashes + diffs
- “module recipes” learned from existing implementations
- verification results + recurring failure patterns

### B) In-spreadsheet ChangeLog tab
Appends on apply:
- timestamp, request summary, patch_id
- #cells changed, sheets touched
- sample diffs
- verification outcome

---

## Technical approach (enough to be concrete)
- Frontend: web UI (chat + tools panel + diff preview modal)
- Backend: API server + MCP tool server
- Agent: LLM-driven planner/orchestrator calling MCP tools
- Spreadsheet ops: Google Sheets API
- Patch model: immutable patches with preview/apply separation
- Caching: cache fetched kit pages + parsed schema + diffs (prevents repeated cost)

---

## Testing plan (verify it works)
Even if results are imperfect, I can test measurable behaviors.

### Unit tests
- kit normalization: extracted schema fields are consistent
- diffing: upstream changes detected reliably (hash + structured diff)
- placeholder resolution: header/rowlabel mapping works; duplicates trigger disambiguation
- patch building: only intended cells change

### Integration tests (fixture spreadsheet)
- a copy of a test workbook with known template + known “modules”
- workflow tests:
  1) ingest kit → preview patch generated
  2) apply patch → ChangeLog entry created
  3) verifier reports errors/inconsistencies correctly
  4) simulate upstream kit change → diff detected → update patch proposed

### Regression/invariant checks
- “No apply without preview”
- “No patch exceeds max cell/sheet limits”
- “No edits outside declared scope”
- “Second run is idempotent” (re-applying same recipe makes no changes)

---

## Demo plan (what I will show in class)
1) Paste a character URL → agent ingests kit → proposes module patch preview
2) Apply patch → verifier report shows “no new errors” (or flags issues)
3) Simulate upstream kit change → tool detects diff → agent proposes update patch
4) Show memory effect: duplicate header resolved once and remembered
