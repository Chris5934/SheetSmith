"""Formula analysis for identifying shared logic and patterns."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class FormulaComponent:
    """A component identified within a formula."""

    component_type: str  # "function", "reference", "literal", "operator", "logic_block"
    content: str
    start: int
    end: int
    nested_level: int = 0


@dataclass
class AnalysisResult:
    """Result of analyzing a formula."""

    formula: str
    components: list[FormulaComponent]
    functions_used: list[str]
    cell_references: list[str]
    named_ranges: list[str]
    literals: list[str]
    complexity_score: int
    identified_patterns: list[dict]


class FormulaAnalyzer:
    """Analyzes Google Sheets formulas to identify patterns and components."""

    # Common Google Sheets functions
    FUNCTIONS = {
        "IF",
        "IFS",
        "SWITCH",
        "CHOOSE",
        "AND",
        "OR",
        "NOT",
        "SUM",
        "SUMIF",
        "SUMIFS",
        "AVERAGE",
        "AVERAGEIF",
        "AVERAGEIFS",
        "COUNT",
        "COUNTIF",
        "COUNTIFS",
        "MAX",
        "MIN",
        "VLOOKUP",
        "HLOOKUP",
        "INDEX",
        "MATCH",
        "INDIRECT",
        "OFFSET",
        "ROW",
        "COLUMN",
        "ABS",
        "ROUND",
        "ROUNDUP",
        "ROUNDDOWN",
        "FLOOR",
        "CEILING",
        "MOD",
        "POWER",
        "SQRT",
        "LEN",
        "LEFT",
        "RIGHT",
        "MID",
        "TRIM",
        "UPPER",
        "LOWER",
        "CONCATENATE",
        "CONCAT",
        "TEXT",
        "VALUE",
        "ISNUMBER",
        "ISTEXT",
        "ISBLANK",
        "ISERROR",
        "IFERROR",
        "IFNA",
        "ARRAYFORMULA",
        "FILTER",
        "SORT",
        "UNIQUE",
        "QUERY",
    }

    # Pattern for cell references (A1, $A$1, Sheet1!A1, etc.)
    CELL_REF_PATTERN = re.compile(
        r"(?:\'[^\']+\'!|\w+!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?",
        re.IGNORECASE,
    )

    # Pattern for named ranges
    NAMED_RANGE_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    def __init__(self):
        self.known_patterns: list[dict] = []

    def register_pattern(
        self, name: str, pattern: str, description: str, category: str = "custom"
    ):
        """Register a known formula pattern for identification."""
        self.known_patterns.append(
            {
                "name": name,
                "pattern": re.compile(pattern, re.IGNORECASE | re.DOTALL),
                "description": description,
                "category": category,
            }
        )

    def analyze(self, formula: str) -> AnalysisResult:
        """Analyze a formula and identify its components."""
        if not formula.startswith("="):
            return AnalysisResult(
                formula=formula,
                components=[],
                functions_used=[],
                cell_references=[],
                named_ranges=[],
                literals=[],
                complexity_score=0,
                identified_patterns=[],
            )

        components = []
        functions_used = []
        cell_references = []
        named_ranges = []
        literals = []

        # Extract functions
        for func in self.FUNCTIONS:
            pattern = re.compile(rf"\b{func}\s*\(", re.IGNORECASE)
            for match in pattern.finditer(formula):
                functions_used.append(func)
                components.append(
                    FormulaComponent(
                        component_type="function",
                        content=func,
                        start=match.start(),
                        end=match.end() - 1,
                    )
                )

        # Extract cell references
        for match in self.CELL_REF_PATTERN.finditer(formula):
            ref = match.group(0)
            if ref.upper() not in self.FUNCTIONS:
                cell_references.append(ref)
                components.append(
                    FormulaComponent(
                        component_type="reference",
                        content=ref,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract string literals
        string_pattern = re.compile(r'"([^"]*)"')
        for match in string_pattern.finditer(formula):
            literals.append(match.group(1))
            components.append(
                FormulaComponent(
                    component_type="literal",
                    content=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        # Extract numeric literals
        num_pattern = re.compile(r"(?<![A-Z$])\b(\d+\.?\d*%?)\b", re.IGNORECASE)
        for match in num_pattern.finditer(formula):
            literals.append(match.group(1))
            components.append(
                FormulaComponent(
                    component_type="literal",
                    content=match.group(1),
                    start=match.start(),
                    end=match.end(),
                )
            )

        # Calculate complexity score
        complexity_score = (
            len(functions_used) * 2
            + len(cell_references)
            + len(literals)
            + formula.count("(")
            + formula.count(",") // 2
        )

        # Identify known patterns
        identified_patterns = []
        for pattern_def in self.known_patterns:
            if pattern_def["pattern"].search(formula):
                identified_patterns.append(
                    {
                        "name": pattern_def["name"],
                        "description": pattern_def["description"],
                        "category": pattern_def["category"],
                    }
                )

        return AnalysisResult(
            formula=formula,
            components=sorted(components, key=lambda c: c.start),
            functions_used=list(set(functions_used)),
            cell_references=cell_references,
            named_ranges=named_ranges,
            literals=literals,
            complexity_score=complexity_score,
            identified_patterns=identified_patterns,
        )

    def find_switch_mappings(self, formula: str) -> list[dict]:
        """Extract key-value mappings from SWITCH statements."""
        mappings = []
        switch_pattern = re.compile(
            r"SWITCH\s*\(\s*([^,]+),\s*(.*?)\s*\)", re.IGNORECASE | re.DOTALL
        )

        for match in switch_pattern.finditer(formula):
            expression = match.group(1).strip()
            cases_str = match.group(2)

            # Parse cases (alternating key, value pairs)
            cases = []
            in_string = False
            paren_depth = 0
            current = ""

            for char in cases_str:
                if char == '"' and (not current or current[-1] != "\\"):
                    in_string = not in_string
                elif char == "(" and not in_string:
                    paren_depth += 1
                elif char == ")" and not in_string:
                    paren_depth -= 1
                elif char == "," and not in_string and paren_depth == 0:
                    cases.append(current.strip())
                    current = ""
                    continue
                current += char

            if current.strip():
                cases.append(current.strip())

            # Pair up as key-value (last one might be default)
            pairs = []
            for i in range(0, len(cases) - 1, 2):
                if i + 1 < len(cases):
                    pairs.append({"key": cases[i], "value": cases[i + 1]})

            # Check for default value
            default = None
            if len(cases) % 2 == 1:
                default = cases[-1]

            mappings.append(
                {
                    "expression": expression,
                    "pairs": pairs,
                    "default": default,
                    "full_match": match.group(0),
                }
            )

        return mappings

    def extract_shared_logic(
        self, formulas: list[str], min_occurrences: int = 2
    ) -> list[dict]:
        """Identify shared logic patterns across multiple formulas."""
        # Find common substrings that appear in multiple formulas
        shared_patterns = []

        # Look for SWITCH statements
        switch_mappings = {}
        for formula in formulas:
            for mapping in self.find_switch_mappings(formula):
                key = tuple((p["key"], p["value"]) for p in mapping["pairs"])
                if key not in switch_mappings:
                    switch_mappings[key] = {"mapping": mapping, "count": 0, "formulas": []}
                switch_mappings[key]["count"] += 1
                switch_mappings[key]["formulas"].append(formula[:100])

        for key, data in switch_mappings.items():
            if data["count"] >= min_occurrences:
                shared_patterns.append(
                    {
                        "type": "switch_mapping",
                        "occurrences": data["count"],
                        "pattern": data["mapping"]["full_match"],
                        "details": data["mapping"],
                    }
                )

        return shared_patterns
