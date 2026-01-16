"""Memory tools for storing and retrieving rules and logic blocks."""

from typing import Optional
import uuid

from ..memory import MemoryStore, Rule, LogicBlock
from .registry import Tool, ToolParameter, ToolRegistry


class MemoryTools:
    """Memory tools that can be registered with the agent."""

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()

    def register(self, registry: ToolRegistry):
        """Register all memory tools with the registry."""
        registry.register(self._store_rule_tool())
        registry.register(self._get_rules_tool())
        registry.register(self._delete_rule_tool())
        registry.register(self._store_logic_block_tool())
        registry.register(self._get_logic_blocks_tool())
        registry.register(self._search_logic_blocks_tool())

    def _store_rule_tool(self) -> Tool:
        """Create the store_rule tool."""

        async def handler(
            name: str,
            description: str,
            rule_type: str,
            content: str,
            examples: Optional[list[str]] = None,
            tags: Optional[list[str]] = None,
        ) -> dict:
            rule = Rule(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                rule_type=rule_type,
                content=content,
                examples=examples or [],
                tags=tags or [],
            )
            stored = await self.store.store_rule(rule)
            return {
                "success": True,
                "rule_id": stored.id,
                "message": f"Rule '{name}' stored successfully",
            }

        return Tool(
            name="memory.store_rule",
            description="Store a project-specific rule or convention. Rules help maintain "
            "consistency in formula writing, naming conventions, and structure. "
            "The agent will reference these rules when suggesting changes.",
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Short name for the rule",
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Detailed description of what the rule enforces",
                ),
                ToolParameter(
                    name="rule_type",
                    type="string",
                    description="Type of rule",
                    enum=["formula_style", "naming", "structure", "custom"],
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="The actual rule content or pattern",
                ),
                ToolParameter(
                    name="examples",
                    type="array",
                    description="Example formulas or patterns that follow this rule",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Tags for categorizing the rule",
                    required=False,
                ),
            ],
            handler=handler,
        )

    def _get_rules_tool(self) -> Tool:
        """Create the get_rules tool."""

        async def handler(
            rule_type: Optional[str] = None,
            tags: Optional[list[str]] = None,
        ) -> dict:
            rules = await self.store.get_rules(rule_type, tags)
            return {
                "count": len(rules),
                "rules": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "rule_type": r.rule_type,
                        "content": r.content,
                        "examples": r.examples,
                        "tags": r.tags,
                    }
                    for r in rules
                ],
            }

        return Tool(
            name="memory.get_rules",
            description="Retrieve stored rules. Use this to understand project conventions "
            "before making suggestions or applying changes.",
            parameters=[
                ToolParameter(
                    name="rule_type",
                    type="string",
                    description="Filter by rule type",
                    required=False,
                    enum=["formula_style", "naming", "structure", "custom"],
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Filter by tags",
                    required=False,
                ),
            ],
            handler=handler,
        )

    def _delete_rule_tool(self) -> Tool:
        """Create the delete_rule tool."""

        async def handler(rule_id: str) -> dict:
            deleted = await self.store.delete_rule(rule_id)
            return {
                "success": deleted,
                "message": "Rule deleted" if deleted else "Rule not found",
            }

        return Tool(
            name="memory.delete_rule",
            description="Delete a stored rule by its ID.",
            parameters=[
                ToolParameter(
                    name="rule_id",
                    type="string",
                    description="The ID of the rule to delete",
                ),
            ],
            handler=handler,
        )

    def _store_logic_block_tool(self) -> Tool:
        """Create the store_logic_block tool."""

        async def handler(
            name: str,
            block_type: str,
            description: str,
            formula_pattern: str,
            variables: Optional[dict[str, str]] = None,
            tags: Optional[list[str]] = None,
        ) -> dict:
            block = LogicBlock(
                id=str(uuid.uuid4()),
                name=name,
                block_type=block_type,
                description=description,
                formula_pattern=formula_pattern,
                variables=variables or {},
                tags=tags or [],
            )
            stored = await self.store.store_logic_block(block)
            return {
                "success": True,
                "block_id": stored.id,
                "message": f"Logic block '{name}' stored successfully",
            }

        return Tool(
            name="memory.store_logic_block",
            description="Store a known logic block pattern (character kit, teammate, rotation). "
            "This helps the agent recognize and update shared logic across sheets.",
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Name of the logic block (e.g., 'Abloom Status Mapping')",
                ),
                ToolParameter(
                    name="block_type",
                    type="string",
                    description="Type of logic block",
                    enum=["kit", "teammate", "rotation", "custom"],
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Description of what this logic block does",
                ),
                ToolParameter(
                    name="formula_pattern",
                    type="string",
                    description="The formula pattern for this logic block",
                ),
                ToolParameter(
                    name="variables",
                    type="object",
                    description="Dictionary of variable names to descriptions",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Tags for categorizing the logic block",
                    required=False,
                ),
            ],
            handler=handler,
        )

    def _get_logic_blocks_tool(self) -> Tool:
        """Create the get_logic_blocks tool."""

        async def handler(
            block_type: Optional[str] = None,
            tags: Optional[list[str]] = None,
        ) -> dict:
            blocks = await self.store.get_logic_blocks(block_type, tags)
            return {
                "count": len(blocks),
                "blocks": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "block_type": b.block_type,
                        "description": b.description,
                        "formula_pattern": b.formula_pattern,
                        "variables": b.variables,
                        "tags": b.tags,
                    }
                    for b in blocks
                ],
            }

        return Tool(
            name="memory.get_logic_blocks",
            description="Retrieve stored logic blocks. Use this to find known patterns "
            "for character kits, teammates, or rotations.",
            parameters=[
                ToolParameter(
                    name="block_type",
                    type="string",
                    description="Filter by block type",
                    required=False,
                    enum=["kit", "teammate", "rotation", "custom"],
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Filter by tags",
                    required=False,
                ),
            ],
            handler=handler,
        )

    def _search_logic_blocks_tool(self) -> Tool:
        """Create the search_logic_blocks tool."""

        async def handler(query: str) -> dict:
            blocks = await self.store.search_logic_blocks(query)
            return {
                "count": len(blocks),
                "blocks": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "block_type": b.block_type,
                        "description": b.description,
                        "formula_pattern": b.formula_pattern,
                    }
                    for b in blocks
                ],
            }

        return Tool(
            name="memory.search_logic_blocks",
            description="Search for logic blocks by name, description, or formula pattern.",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                ),
            ],
            handler=handler,
        )
