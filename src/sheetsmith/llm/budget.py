"""Per-operation budget management for LLM calls."""

from typing import Literal, Optional

OperationType = Literal["parser", "ai_assist", "planning", "tool_continuation"]


class OperationBudgetLimits:
    """Budget limits for different operation types."""
    
    # Maximum cost in cents per operation type
    BUDGET_LIMITS = {
        "parser": 0.001,      # $0.001 max for parser (0.1 cents)
        "ai_assist": 0.01,    # $0.01 max for assist (1 cent)
        "planning": 0.05,     # $0.05 max for planning (5 cents)
        "tool_continuation": 0.02,  # $0.02 max for continuation (2 cents)
    }
    
    # Maximum input tokens per operation type
    TOKEN_LIMITS = {
        "parser": 500,
        "ai_assist": 1000,
        "planning": 5000,
        "tool_continuation": 3000,
    }
    
    # Maximum output tokens per operation type
    OUTPUT_TOKEN_LIMITS = {
        "parser": 300,
        "ai_assist": 400,
        "planning": 800,
        "tool_continuation": 600,
    }


class OperationBudgetGuard:
    """Guards budget for specific operation types."""
    
    def __init__(self):
        self.limits = OperationBudgetLimits()
    
    def get_budget_limit(self, operation: OperationType) -> float:
        """Get budget limit for operation in cents.
        
        Args:
            operation: The operation type
            
        Returns:
            Budget limit in cents
        """
        return self.limits.BUDGET_LIMITS.get(operation, 0.001)
    
    def get_token_limit(self, operation: OperationType) -> int:
        """Get input token limit for operation.
        
        Args:
            operation: The operation type
            
        Returns:
            Maximum input tokens allowed
        """
        return self.limits.TOKEN_LIMITS.get(operation, 500)
    
    def get_output_token_limit(self, operation: OperationType) -> int:
        """Get output token limit for operation.
        
        Args:
            operation: The operation type
            
        Returns:
            Maximum output tokens allowed
        """
        return self.limits.OUTPUT_TOKEN_LIMITS.get(operation, 300)
    
    def check_operation_budget(
        self,
        operation: OperationType,
        estimated_cost_cents: float,
        estimated_input_tokens: int,
    ) -> tuple[bool, Optional[str]]:
        """Check if operation is within budget.
        
        Args:
            operation: The operation type
            estimated_cost_cents: Estimated cost in cents
            estimated_input_tokens: Estimated input token count
            
        Returns:
            Tuple of (allowed, error_message)
        """
        budget_limit = self.get_budget_limit(operation)
        token_limit = self.get_token_limit(operation)
        
        # Check cost budget
        if estimated_cost_cents > budget_limit:
            return False, (
                f"Operation '{operation}' exceeds budget: "
                f"${estimated_cost_cents:.4f} > ${budget_limit:.4f}. "
                f"Reduce context or use cheaper operation mode."
            )
        
        # Check token limit
        if estimated_input_tokens > token_limit:
            return False, (
                f"Operation '{operation}' exceeds token limit: "
                f"{estimated_input_tokens} > {token_limit}. "
                f"Reduce context or split into multiple operations."
            )
        
        return True, None
