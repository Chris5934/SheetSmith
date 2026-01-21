"""Formula analysis and patching engine."""

from .analyzer import FormulaAnalyzer
from .differ import FormulaDiffer
from .patcher import PatchEngine
from .replace import DeterministicReplacer, ReplacementPlan, ReplacementResult
from .safety import SafetyValidator, SafetyViolation, OperationScope, SafetyCheck
from .scope import ScopeAnalyzer
from .audit import AuditLogger, AuditEntry

__all__ = [
    "FormulaAnalyzer",
    "FormulaDiffer",
    "PatchEngine",
    "DeterministicReplacer",
    "ReplacementPlan",
    "ReplacementResult",
    "SafetyValidator",
    "SafetyViolation",
    "OperationScope",
    "SafetyCheck",
    "ScopeAnalyzer",
    "AuditLogger",
    "AuditEntry",
]
