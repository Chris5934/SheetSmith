# Deterministic Mass Replace - Usage Guide

## Overview

SheetSmith now includes a **Deterministic Mass Replace** feature that dramatically reduces LLM API costs for simple find/replace operations. Instead of using the LLM to process each formula individually, the system now:

1. Uses LLM **only for planning** - understanding the user's request
2. Uses **deterministic string/regex replacement** for actual formula updates
3. Processes bulk operations up to **99% cheaper and faster**

## When to Use

### ✅ Perfect for Deterministic Replace
- Simple text replacements: `VLOOKUP` → `XLOOKUP`
- Value updates: `28.6%` → `30.0%`
- Function name changes: `AVERAGE` → `AVERAGEIF`
- Consistent string substitutions: `"Corruption"` → `"Enhanced Corruption"`

### ❌ Use LLM Path Instead
- Logic restructuring (changing formula structure)
- Complex transformations requiring cell reference understanding
- Conditional replacements based on formula context
- Operations needing reasoning about the formula's purpose

## Performance Comparison

### Small Operation (10 formulas)
- **Traditional**: ~10 LLM calls, ~2-3 seconds, ~$0.01
- **Deterministic**: ~1 LLM call, ~0.3 seconds, ~$0.001
- **Savings**: 90% time, 90% cost

### Medium Operation (100 formulas)
- **Traditional**: ~100 LLM calls, ~20-30 seconds, ~$0.10
- **Deterministic**: ~1 LLM call, ~0.5 seconds, ~$0.001
- **Savings**: 98% time, 99% cost

### Large Operation (1000 formulas)
- **Traditional**: ~1000 LLM calls, ~5-10 minutes, ~$1.00
- **Deterministic**: ~1 LLM call, ~2 seconds, ~$0.001
- **Savings**: 99%+ time, 99.9% cost
