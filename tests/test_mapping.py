"""Tests for header-based mapping system."""

import pytest
import pytest_asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from sheetsmith.mapping import (
    MappingManager,
    MappingStorage,
    MappingValidator,
    DisambiguationHandler,
    ColumnMapping,
    CellMapping,
    ColumnCandidate,
    MappingStatus,
    DisambiguationRequiredError,
    HeaderNotFoundError,
    DisambiguationResponse,
)
from sheetsmith.sheets.models import CellData, SheetRange


@pytest_asyncio.fixture
async def mapping_storage(tmp_path: Path):
    """Create a test mapping storage."""
    db_path = tmp_path / "test_mappings.db"
    storage = MappingStorage(db_path)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
def mock_sheets_client():
    """Create a mocked Google Sheets client."""
    client = Mock()

    # Mock spreadsheet info
    client.get_spreadsheet_info = Mock(
        return_value={
            "id": "test-sheet-123",
            "title": "Test Sheet",
            "sheets": [
                {
                    "title": "Sheet1",
                    "id": 0,
                    "row_count": 100,
                    "col_count": 26,
                }
            ],
        }
    )

    # Mock read_range with headers
    client.read_range = Mock(
        return_value=SheetRange(
            spreadsheet_id="test-sheet-123",
            sheet_name="Sheet1",
            range_notation="Sheet1!A1:ZZ10",
            cells=[
                # Headers in row 1
                CellData(
                    sheet_name="Sheet1",
                    cell="A1",
                    row=1,
                    col=0,
                    value="Name",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B1",
                    row=1,
                    col=1,
                    value="Base Damage",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="C1",
                    row=1,
                    col=2,
                    value="Level",
                ),
                # Data rows
                CellData(
                    sheet_name="Sheet1",
                    cell="A2",
                    row=2,
                    col=0,
                    value="Character A",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B2",
                    row=2,
                    col=1,
                    value=100,
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="C2",
                    row=2,
                    col=2,
                    value=5,
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="A3",
                    row=3,
                    col=0,
                    value="Character B",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B3",
                    row=3,
                    col=1,
                    value=150,
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="C3",
                    row=3,
                    col=2,
                    value=7,
                ),
            ],
        )
    )

    return client


@pytest_asyncio.fixture
async def mapping_manager(mock_sheets_client, mapping_storage):
    """Create a test mapping manager."""
    manager = MappingManager(
        sheets_client=mock_sheets_client,
        storage=mapping_storage,
    )
    await manager.initialize()
    yield manager
    await manager.close()


# Storage Tests


@pytest.mark.asyncio
async def test_storage_column_mapping_create(mapping_storage):
    """Test creating a column mapping."""
    mapping = ColumnMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        header_text="Base Damage",
        column_letter="B",
        column_index=1,
        header_row=0,
    )

    stored = await mapping_storage.store_column_mapping(mapping)

    assert stored.id is not None
    assert stored.spreadsheet_id == "test-sheet-123"
    assert stored.sheet_name == "Sheet1"
    assert stored.header_text == "Base Damage"
    assert stored.column_letter == "B"
    assert stored.column_index == 1


@pytest.mark.asyncio
async def test_storage_column_mapping_retrieve(mapping_storage):
    """Test retrieving a column mapping."""
    mapping = ColumnMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        header_text="Base Damage",
        column_letter="B",
        column_index=1,
        header_row=0,
    )

    await mapping_storage.store_column_mapping(mapping)

    retrieved = await mapping_storage.get_column_mapping("test-sheet-123", "Sheet1", "Base Damage")

    assert retrieved is not None
    assert retrieved.header_text == "Base Damage"
    assert retrieved.column_letter == "B"


@pytest.mark.asyncio
async def test_storage_cell_mapping_create(mapping_storage):
    """Test creating a cell mapping."""
    mapping = CellMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        column_header="Base Damage",
        row_label="Character A",
        cell_address="B2",
        row_index=1,
        column_letter="B",
        column_index=1,
    )

    stored = await mapping_storage.store_cell_mapping(mapping)

    assert stored.id is not None
    assert stored.column_header == "Base Damage"
    assert stored.row_label == "Character A"
    assert stored.cell_address == "B2"


@pytest.mark.asyncio
async def test_storage_get_all_mappings(mapping_storage):
    """Test retrieving all mappings for a spreadsheet."""
    # Create multiple mappings
    mapping1 = ColumnMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        header_text="Base Damage",
        column_letter="B",
        column_index=1,
        header_row=0,
    )
    mapping2 = ColumnMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        header_text="Level",
        column_letter="C",
        column_index=2,
        header_row=0,
    )

    await mapping_storage.store_column_mapping(mapping1)
    await mapping_storage.store_column_mapping(mapping2)

    all_mappings = await mapping_storage.get_all_column_mappings("test-sheet-123")

    assert len(all_mappings) == 2
    assert any(m.header_text == "Base Damage" for m in all_mappings)
    assert any(m.header_text == "Level" for m in all_mappings)


# Validator Tests


@pytest.mark.asyncio
async def test_validator_find_header(mock_sheets_client):
    """Test finding a header in a sheet."""
    validator = MappingValidator(mock_sheets_client)

    candidates = await validator._find_header_in_sheet("test-sheet-123", "Sheet1", "Base Damage")

    assert len(candidates) == 1
    assert candidates[0].column_letter == "B"
    assert candidates[0].column_index == 1


@pytest.mark.asyncio
async def test_validator_validate_valid_mapping(mock_sheets_client):
    """Test validating a valid mapping."""
    validator = MappingValidator(mock_sheets_client)

    mapping = ColumnMapping(
        spreadsheet_id="test-sheet-123",
        sheet_name="Sheet1",
        header_text="Base Damage",
        column_letter="B",
        column_index=1,
        header_row=0,
    )

    result = await validator.validate_column_mapping(mapping)

    assert result.is_valid is True
    assert result.status == MappingStatus.VALID


# Disambiguator Tests


def test_disambiguator_create_request():
    """Test creating a disambiguation request."""
    handler = DisambiguationHandler()

    candidates = [
        ColumnCandidate(
            column_letter="B",
            column_index=1,
            header_row=0,
            sample_values=["100", "150"],
            adjacent_headers={"left": "Name", "right": "Level"},
        ),
        ColumnCandidate(
            column_letter="E",
            column_index=4,
            header_row=0,
            sample_values=["200", "250"],
            adjacent_headers={"left": "Type", "right": "Multiplier"},
        ),
    ]

    request = handler.create_disambiguation_request(
        "test-sheet-123", "Sheet1", "Damage", candidates
    )

    assert request.request_id is not None
    assert request.spreadsheet_id == "test-sheet-123"
    assert request.header_text == "Damage"
    assert len(request.candidates) == 2


def test_disambiguator_resolve():
    """Test resolving a disambiguation request."""
    handler = DisambiguationHandler()

    candidates = [
        ColumnCandidate(
            column_letter="B",
            column_index=1,
            header_row=0,
            sample_values=["100", "150"],
            adjacent_headers={"left": "Name", "right": "Level"},
        ),
        ColumnCandidate(
            column_letter="E",
            column_index=4,
            header_row=0,
            sample_values=["200", "250"],
            adjacent_headers={"left": "Type", "right": "Multiplier"},
        ),
    ]

    request = handler.create_disambiguation_request(
        "test-sheet-123", "Sheet1", "Damage", candidates
    )

    response = DisambiguationResponse(
        request_id=request.request_id, selected_column_index=1, user_label="Elemental Damage"
    )

    selected = handler.resolve_disambiguation(response)

    assert selected.column_letter == "E"
    assert selected.column_index == 4


# Manager Tests


@pytest.mark.asyncio
async def test_manager_get_column_by_header(mapping_manager, mock_sheets_client):
    """Test getting a column by header text."""
    mapping = await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Base Damage")

    assert mapping.header_text == "Base Damage"
    assert mapping.column_letter == "B"
    assert mapping.column_index == 1


@pytest.mark.asyncio
async def test_manager_get_column_cached(mapping_manager, mock_sheets_client):
    """Test that getting a column uses cache on second call."""
    # First call creates the mapping
    mapping1 = await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Base Damage")

    # Second call should use cached mapping
    mapping2 = await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Base Damage")

    assert mapping1.id == mapping2.id
    assert mapping2.last_validated_at is not None


@pytest.mark.asyncio
async def test_manager_get_concept_cell(mapping_manager, mock_sheets_client):
    """Test getting a concept cell by column header × row label."""
    mapping = await mapping_manager.get_concept_cell(
        "test-sheet-123", "Sheet1", "Base Damage", "Character A"
    )

    assert mapping.column_header == "Base Damage"
    assert mapping.row_label == "Character A"
    assert mapping.cell_address == "B2"
    assert mapping.column_letter == "B"
    assert mapping.row_index == 1


@pytest.mark.asyncio
async def test_manager_audit_mappings(mapping_manager, mock_sheets_client):
    """Test auditing all mappings."""
    # Create some mappings
    await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Base Damage")
    await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Level")

    # Audit
    report = await mapping_manager.audit_mappings("test-sheet-123")

    assert report.spreadsheet_id == "test-sheet-123"
    assert report.total_mappings == 2
    assert report.valid_count == 2
    assert len(report.entries) == 2


@pytest.mark.asyncio
async def test_manager_header_not_found(mapping_manager, mock_sheets_client):
    """Test that getting a non-existent header raises HeaderNotFoundError."""
    with pytest.raises(HeaderNotFoundError):
        await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "NonExistent Header")


# Duplicate Header Tests


@pytest.mark.asyncio
async def test_manager_duplicate_header_disambiguation(mapping_manager, mock_sheets_client):
    """Test that duplicate headers trigger disambiguation."""
    # Mock read_range to return duplicate headers
    mock_sheets_client.read_range = Mock(
        return_value=SheetRange(
            spreadsheet_id="test-sheet-123",
            sheet_name="Sheet1",
            range_notation="Sheet1!A1:ZZ10",
            cells=[
                CellData(sheet_name="Sheet1", cell="B1", row=1, col=1, value="Damage"),
                CellData(sheet_name="Sheet1", cell="E1", row=1, col=4, value="Damage"),
                CellData(sheet_name="Sheet1", cell="B2", row=2, col=1, value=100),
                CellData(sheet_name="Sheet1", cell="E2", row=2, col=4, value=200),
            ],
        )
    )

    with pytest.raises(DisambiguationRequiredError) as exc_info:
        await mapping_manager.get_column_by_header("test-sheet-123", "Sheet1", "Damage")

    request = exc_info.value.request
    assert len(request.candidates) == 2
    assert request.header_text == "Damage"


@pytest.mark.asyncio
async def test_manager_store_disambiguation(mapping_manager, mock_sheets_client):
    """Test storing a disambiguation choice."""
    # Create a disambiguation request
    candidates = [
        ColumnCandidate(
            column_letter="B",
            column_index=1,
            header_row=0,
            sample_values=["100", "150"],
            adjacent_headers={"left": "Name", "right": "Level"},
        ),
        ColumnCandidate(
            column_letter="E",
            column_index=4,
            header_row=0,
            sample_values=["200", "250"],
            adjacent_headers={"left": "Type", "right": "Multiplier"},
        ),
    ]

    request = mapping_manager.disambiguator.create_disambiguation_request(
        "test-sheet-123", "Sheet1", "Damage", candidates
    )

    # Store disambiguation choice
    response = DisambiguationResponse(
        request_id=request.request_id, selected_column_index=1, user_label="Elemental"
    )

    mapping = await mapping_manager.store_disambiguation(response)

    assert mapping.header_text == "Damage"
    assert mapping.column_letter == "E"
    assert mapping.disambiguation_context is not None
    assert mapping.disambiguation_context["user_label"] == "Elemental"
