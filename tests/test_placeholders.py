"""Tests for placeholder mapping system."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock

from sheetsmith.placeholders import (
    PlaceholderParser,
    PlaceholderResolver,
    PlaceholderAssistant,
    Placeholder,
    PlaceholderType,
    ResolutionContext,
)
from sheetsmith.placeholders.syntax import (
    normalize_name,
    fuzzy_match_score,
    is_valid_placeholder_name,
)
from sheetsmith.mapping import (
    MappingManager,
    MappingStorage,
)
from sheetsmith.sheets.models import CellData, SheetRange


class TestPlaceholderSyntax:
    """Test placeholder syntax utilities."""

    def test_normalize_name(self):
        """Test name normalization."""
        assert normalize_name("Base Damage") == "basedamage"
        assert normalize_name("base_damage") == "basedamage"
        assert normalize_name("  Base  Damage  ") == "basedamage"
        assert normalize_name("BASE_DAMAGE") == "basedamage"

    def test_fuzzy_match_score(self):
        """Test fuzzy matching scores."""
        # Exact match after normalization
        assert fuzzy_match_score("base_damage", "Base Damage") == 1.0

        # Contains match
        assert fuzzy_match_score("damage", "Base Damage") > 0.8

        # No match
        assert fuzzy_match_score("foo", "bar") < 0.5

    def test_is_valid_placeholder_name(self):
        """Test placeholder name validation."""
        # Valid names
        assert is_valid_placeholder_name("base_damage") is True
        assert is_valid_placeholder_name("Base Damage") is True
        assert is_valid_placeholder_name("multiplier") is True

        # Invalid names
        assert is_valid_placeholder_name("") is False
        assert is_valid_placeholder_name("  ") is False
        assert is_valid_placeholder_name("123invalid") is False
        assert is_valid_placeholder_name("in-valid") is False


class TestPlaceholderParser:
    """Test placeholder parser."""

    def test_extract_header_placeholder(self):
        """Test extracting simple header placeholder."""
        parser = PlaceholderParser()
        formula = "={{base_damage}} * 1.5"

        placeholders = parser.extract_placeholders(formula)

        assert len(placeholders) == 1
        assert placeholders[0].name == "base_damage"
        assert placeholders[0].type == PlaceholderType.HEADER
        assert placeholders[0].syntax == "{{base_damage}}"

    def test_extract_multiple_placeholders(self):
        """Test extracting multiple placeholders."""
        parser = PlaceholderParser()
        formula = "={{base_damage}} * {{multiplier}}"

        placeholders = parser.extract_placeholders(formula)

        assert len(placeholders) == 2
        assert placeholders[0].name == "base_damage"
        assert placeholders[1].name == "multiplier"

    def test_extract_intersection_placeholder(self):
        """Test extracting intersection placeholder."""
        parser = PlaceholderParser()
        formula = "={{base_damage}} * {{multiplier:Jane}}"

        placeholders = parser.extract_placeholders(formula)

        assert len(placeholders) == 2
        assert placeholders[0].type == PlaceholderType.HEADER
        assert placeholders[1].type == PlaceholderType.INTERSECTION
        assert placeholders[1].name == "multiplier"
        assert placeholders[1].row_label == "Jane"

    def test_extract_cross_sheet_placeholder(self):
        """Test extracting cross-sheet placeholder."""
        parser = PlaceholderParser()
        formula = "='KitData'!{{burn_bonus}}"

        placeholders = parser.extract_placeholders(formula)

        assert len(placeholders) == 1
        assert placeholders[0].type == PlaceholderType.CROSS_SHEET
        assert placeholders[0].name == "burn_bonus"
        assert placeholders[0].sheet == "KitData"

    def test_validate_syntax_valid(self):
        """Test validating valid placeholder syntax."""
        parser = PlaceholderParser()
        result = parser.validate_syntax("={{base_damage}} * 1.5")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_syntax_mismatched_brackets(self):
        """Test validating mismatched brackets."""
        parser = PlaceholderParser()
        result = parser.validate_syntax("={{base_damage} * 1.5")

        assert result.valid is False
        assert any("Mismatched" in error for error in result.errors)

    def test_validate_syntax_no_equals(self):
        """Test validating formula without equals sign."""
        parser = PlaceholderParser()
        result = parser.validate_syntax("{{base_damage}} * 1.5")

        assert result.valid is True  # Still valid placeholder syntax
        assert len(result.warnings) > 0  # But warns about missing =

    def test_get_placeholder_types(self):
        """Test getting placeholder types."""
        parser = PlaceholderParser()
        formula = "={{base_damage}} * {{multiplier:Jane}}"

        types = parser.get_placeholder_types(formula)

        assert len(types) == 2
        assert types["{{base_damage}}"] == PlaceholderType.HEADER
        assert types["{{multiplier:Jane}}"] == PlaceholderType.INTERSECTION


@pytest_asyncio.fixture
async def mock_sheets_client():
    """Create a mocked Google Sheets client."""
    client = Mock()

    # Mock spreadsheet info
    client.get_spreadsheet_info = Mock(
        return_value={
            "id": "test-sheet-123",
            "title": "Test Sheet",
            "sheets": [
                {
                    "title": "Base",
                    "id": 0,
                    "row_count": 100,
                    "col_count": 26,
                }
            ],
        }
    )

    # Mock read_range with headers
    def mock_read_range(spreadsheet_id, range_notation, include_formulas=True):
        return SheetRange(
            spreadsheet_id=spreadsheet_id,
            sheet_name="Base",
            range_notation=range_notation,
            cells=[
                # Headers in row 1
                CellData(
                    sheet_name="Base",
                    cell="A1",
                    row=1,
                    col=0,
                    value="Name",
                ),
                CellData(
                    sheet_name="Base",
                    cell="F1",
                    row=1,
                    col=5,
                    value="Base Damage",
                ),
                CellData(
                    sheet_name="Base",
                    cell="G1",
                    row=1,
                    col=6,
                    value="Multiplier",
                ),
                # Data rows
                CellData(
                    sheet_name="Base",
                    cell="A2",
                    row=2,
                    col=0,
                    value="Character A",
                ),
                CellData(
                    sheet_name="Base",
                    cell="F2",
                    row=2,
                    col=5,
                    value=100,
                ),
                CellData(
                    sheet_name="Base",
                    cell="G2",
                    row=2,
                    col=6,
                    value=1.5,
                ),
            ],
        )

    client.read_range = Mock(side_effect=mock_read_range)

    return client


@pytest_asyncio.fixture
async def mapping_storage(tmp_path: Path):
    """Create a test mapping storage."""
    db_path = tmp_path / "test_placeholders.db"
    storage = MappingStorage(db_path)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest_asyncio.fixture
async def placeholder_resolver(mock_sheets_client, mapping_storage):
    """Create a placeholder resolver with mocked dependencies."""
    mapping_manager = MappingManager(
        sheets_client=mock_sheets_client,
        storage=mapping_storage,
    )
    await mapping_manager.initialize()

    resolver = PlaceholderResolver(
        sheets_client=mock_sheets_client,
        mapping_manager=mapping_manager,
    )
    await resolver.initialize()

    yield resolver

    await resolver.close()


class TestPlaceholderResolver:
    """Test placeholder resolver."""

    @pytest.mark.asyncio
    async def test_resolve_header_placeholder(self, placeholder_resolver):
        """Test resolving a simple header placeholder."""
        context = ResolutionContext(
            current_sheet="Base",
            current_row=2,
            spreadsheet_id="test-sheet-123",
            absolute_references=False,
        )

        placeholder = Placeholder(
            name="Base Damage",
            type=PlaceholderType.HEADER,
            syntax="{{Base Damage}}",
            start_pos=1,
            end_pos=16,
        )

        mapping = await placeholder_resolver.resolve(
            placeholder=placeholder,
            spreadsheet_id="test-sheet-123",
            context=context,
        )

        assert mapping.resolved_to == "F2"
        assert mapping.header == "Base Damage"
        assert mapping.column == "F"
        assert mapping.row == 2

    @pytest.mark.asyncio
    async def test_resolve_all_placeholders(self, placeholder_resolver):
        """Test resolving all placeholders in a formula."""
        context = ResolutionContext(
            current_sheet="Base",
            current_row=2,
            spreadsheet_id="test-sheet-123",
            absolute_references=False,
        )

        formula = "={{Base Damage}} * {{Multiplier}}"

        resolved = await placeholder_resolver.resolve_all(
            formula=formula,
            spreadsheet_id="test-sheet-123",
            context=context,
        )

        assert resolved.original == formula
        assert resolved.resolved == "=F2 * G2"
        assert len(resolved.mappings) == 2

    @pytest.mark.asyncio
    async def test_resolve_with_absolute_references(self, placeholder_resolver):
        """Test resolving with absolute references."""
        context = ResolutionContext(
            current_sheet="Base",
            current_row=2,
            spreadsheet_id="test-sheet-123",
            absolute_references=True,
        )

        formula = "={{Base Damage}} * {{Multiplier}}"

        resolved = await placeholder_resolver.resolve_all(
            formula=formula,
            spreadsheet_id="test-sheet-123",
            context=context,
        )

        assert "$F$2" in resolved.resolved
        assert "$G$2" in resolved.resolved

    @pytest.mark.asyncio
    async def test_preview_mappings(self, placeholder_resolver):
        """Test previewing placeholder mappings."""
        formula = "={{Base Damage}} * {{Multiplier}}"

        preview = await placeholder_resolver.preview_mappings(
            formula=formula,
            spreadsheet_id="test-sheet-123",
            sheet_name="Base",
        )

        assert len(preview.placeholders) == 2
        assert "{{Base Damage}}" in preview.potential_mappings
        assert "{{Multiplier}}" in preview.potential_mappings
        assert "Base Damage" in preview.potential_mappings["{{Base Damage}}"]


class TestPlaceholderAssistant:
    """Test placeholder assistant."""

    @pytest.mark.asyncio
    async def test_suggest_mapping_no_llm(self):
        """Test that suggestion returns empty without LLM."""
        assistant = PlaceholderAssistant(llm_client=None)

        # Should return empty list when no LLM client
        result = await assistant.suggest_mapping(
            "base_damage",
            ["Base Damage", "Damage", "Total Damage"],
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_clarify_intent_no_llm(self):
        """Test that clarification returns empty without LLM."""
        assistant = PlaceholderAssistant(llm_client=None)

        # Should return empty dict when no LLM client
        result = await assistant.clarify_intent(
            "={{foo}} * {{bar}}",
            ["{{foo}}", "{{bar}}"],
        )

        assert result == {}
