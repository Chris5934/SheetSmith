"""Tests for memory models."""

from datetime import datetime
import json

import pytest

from sheetsmith.memory.models import Rule, LogicBlock, AuditLog, FixSummary


class TestRuleModel:
    """Test the Rule model."""

    def test_rule_creation_with_required_fields(self):
        """Test creating a Rule with required fields."""
        rule = Rule(
            id="rule-123",
            name="Test Rule",
            description="A test rule",
            rule_type="formula_style",
            content="Use VLOOKUP instead of INDEX/MATCH",
        )
        
        assert rule.id == "rule-123"
        assert rule.name == "Test Rule"
        assert rule.description == "A test rule"
        assert rule.rule_type == "formula_style"
        assert rule.content == "Use VLOOKUP instead of INDEX/MATCH"
        assert rule.examples == []
        assert rule.tags == []
        assert isinstance(rule.created_at, datetime)
        assert isinstance(rule.updated_at, datetime)

    def test_rule_creation_with_all_fields(self):
        """Test creating a Rule with all fields."""
        created = datetime(2024, 1, 1, 12, 0, 0)
        updated = datetime(2024, 1, 2, 12, 0, 0)
        
        rule = Rule(
            id="rule-456",
            name="Complete Rule",
            description="A complete rule",
            rule_type="naming",
            content="Use snake_case for variables",
            examples=["my_variable", "another_var"],
            created_at=created,
            updated_at=updated,
            tags=["naming", "style"],
        )
        
        assert len(rule.examples) == 2
        assert rule.examples[0] == "my_variable"
        assert len(rule.tags) == 2
        assert rule.created_at == created
        assert rule.updated_at == updated

    def test_rule_default_timestamps(self):
        """Test that Rule creates default timestamps."""
        before = datetime.utcnow()
        rule = Rule(
            id="rule-789",
            name="Timestamp Test",
            description="Test timestamps",
            rule_type="custom",
            content="Test content",
        )
        after = datetime.utcnow()
        
        assert before <= rule.created_at <= after
        assert before <= rule.updated_at <= after

    def test_rule_serialization(self):
        """Test Rule serialization to dict."""
        rule = Rule(
            id="rule-serial",
            name="Serial Rule",
            description="Serialization test",
            rule_type="structure",
            content="Test structure",
            tags=["test"],
        )
        
        rule_dict = rule.model_dump()
        
        assert rule_dict["id"] == "rule-serial"
        assert rule_dict["name"] == "Serial Rule"
        assert rule_dict["rule_type"] == "structure"
        assert "created_at" in rule_dict
        assert "updated_at" in rule_dict


class TestLogicBlockModel:
    """Test the LogicBlock model."""

    def test_logic_block_creation_with_required_fields(self):
        """Test creating a LogicBlock with required fields."""
        block = LogicBlock(
            id="block-123",
            name="Test Block",
            block_type="kit",
            description="A test logic block",
            formula_pattern="=SUM({range})",
        )
        
        assert block.id == "block-123"
        assert block.name == "Test Block"
        assert block.block_type == "kit"
        assert block.description == "A test logic block"
        assert block.formula_pattern == "=SUM({range})"
        assert block.variables == {}
        assert block.version == "1.0"
        assert block.tags == []
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)

    def test_logic_block_with_variables(self):
        """Test creating a LogicBlock with variables."""
        variables = {
            "range": "The range to sum",
            "criteria": "Optional criteria",
        }
        
        block = LogicBlock(
            id="block-456",
            name="Block with Variables",
            block_type="teammate",
            description="Has variables",
            formula_pattern="=SUMIF({range}, {criteria})",
            variables=variables,
        )
        
        assert len(block.variables) == 2
        assert block.variables["range"] == "The range to sum"
        assert block.variables["criteria"] == "Optional criteria"

    def test_logic_block_with_tags_and_version(self):
        """Test LogicBlock with tags and custom version."""
        block = LogicBlock(
            id="block-789",
            name="Versioned Block",
            block_type="rotation",
            description="With version",
            formula_pattern="=IF({condition}, {true_value}, {false_value})",
            version="2.1",
            tags=["conditional", "logic"],
        )
        
        assert block.version == "2.1"
        assert len(block.tags) == 2
        assert "conditional" in block.tags

    def test_logic_block_default_timestamps(self):
        """Test that LogicBlock creates default timestamps."""
        before = datetime.utcnow()
        block = LogicBlock(
            id="block-time",
            name="Time Test",
            block_type="custom",
            description="Test",
            formula_pattern="=TEST()",
        )
        after = datetime.utcnow()
        
        assert before <= block.created_at <= after
        assert before <= block.updated_at <= after

    def test_logic_block_serialization(self):
        """Test LogicBlock serialization."""
        block = LogicBlock(
            id="block-serial",
            name="Serial Block",
            block_type="kit",
            description="Serialization test",
            formula_pattern="=AVERAGE({range})",
            variables={"range": "Data range"},
            tags=["math"],
        )
        
        block_dict = block.model_dump()
        
        assert block_dict["id"] == "block-serial"
        assert block_dict["name"] == "Serial Block"
        assert block_dict["block_type"] == "kit"
        assert "variables" in block_dict
        assert block_dict["variables"]["range"] == "Data range"


class TestAuditLogModel:
    """Test the AuditLog model."""

    def test_audit_log_creation_with_required_fields(self):
        """Test creating an AuditLog with required fields."""
        log = AuditLog(
            id="log-123",
            action="search",
            description="Searched for formulas",
        )
        
        assert log.id == "log-123"
        assert log.action == "search"
        assert log.description == "Searched for formulas"
        assert log.spreadsheet_id is None
        assert log.details == {}
        assert log.user_approved is False
        assert log.changes_applied == 0
        assert isinstance(log.timestamp, datetime)

    def test_audit_log_with_spreadsheet_details(self):
        """Test AuditLog with spreadsheet and details."""
        details = {
            "pattern": "VLOOKUP",
            "matches": 5,
        }
        
        log = AuditLog(
            id="log-456",
            action="update",
            spreadsheet_id="sheet-123",
            description="Updated formulas",
            details=details,
            user_approved=True,
            changes_applied=5,
        )
        
        assert log.spreadsheet_id == "sheet-123"
        assert log.details["pattern"] == "VLOOKUP"
        assert log.details["matches"] == 5
        assert log.user_approved is True
        assert log.changes_applied == 5

    def test_audit_log_default_timestamp(self):
        """Test that AuditLog creates default timestamp."""
        before = datetime.utcnow()
        log = AuditLog(
            id="log-time",
            action="test",
            description="Timestamp test",
        )
        after = datetime.utcnow()
        
        assert before <= log.timestamp <= after

    def test_audit_log_action_types(self):
        """Test various audit log action types."""
        actions = ["search", "update", "batch_update", "rule_change"]
        
        for action in actions:
            log = AuditLog(
                id=f"log-{action}",
                action=action,
                description=f"Test {action}",
            )
            assert log.action == action

    def test_audit_log_serialization(self):
        """Test AuditLog serialization."""
        log = AuditLog(
            id="log-serial",
            action="batch_update",
            spreadsheet_id="sheet-999",
            description="Batch update test",
            details={"count": 10},
            changes_applied=10,
        )
        
        log_dict = log.model_dump()
        
        assert log_dict["id"] == "log-serial"
        assert log_dict["action"] == "batch_update"
        assert log_dict["spreadsheet_id"] == "sheet-999"
        assert "timestamp" in log_dict
        assert log_dict["details"]["count"] == 10


class TestFixSummaryModel:
    """Test the FixSummary model."""

    def test_fix_summary_creation_with_required_fields(self):
        """Test creating a FixSummary with required fields."""
        summary = FixSummary(
            id="fix-123",
            title="Fixed VLOOKUP formulas",
            description="Replaced all VLOOKUP with XLOOKUP",
            spreadsheet_id="sheet-123",
        )
        
        assert summary.id == "fix-123"
        assert summary.title == "Fixed VLOOKUP formulas"
        assert summary.description == "Replaced all VLOOKUP with XLOOKUP"
        assert summary.spreadsheet_id == "sheet-123"
        assert summary.pattern_searched is None
        assert summary.cells_modified == 0
        assert summary.before_example is None
        assert summary.after_example is None
        assert summary.tags == []
        assert isinstance(summary.timestamp, datetime)

    def test_fix_summary_with_all_fields(self):
        """Test creating a FixSummary with all fields."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        summary = FixSummary(
            id="fix-456",
            title="Complete Fix",
            description="Full fix with all details",
            spreadsheet_id="sheet-456",
            timestamp=timestamp,
            pattern_searched="VLOOKUP.*",
            cells_modified=15,
            before_example="=VLOOKUP(A1, B:C, 2, FALSE)",
            after_example="=XLOOKUP(A1, B:B, C:C)",
            tags=["vlookup", "xlookup", "upgrade"],
        )
        
        assert summary.timestamp == timestamp
        assert summary.pattern_searched == "VLOOKUP.*"
        assert summary.cells_modified == 15
        assert summary.before_example is not None
        assert summary.after_example is not None
        assert len(summary.tags) == 3
        assert "upgrade" in summary.tags

    def test_fix_summary_default_timestamp(self):
        """Test that FixSummary creates default timestamp."""
        before = datetime.utcnow()
        summary = FixSummary(
            id="fix-time",
            title="Timestamp Test",
            description="Test timestamp",
            spreadsheet_id="sheet-time",
        )
        after = datetime.utcnow()
        
        assert before <= summary.timestamp <= after

    def test_fix_summary_serialization(self):
        """Test FixSummary serialization."""
        summary = FixSummary(
            id="fix-serial",
            title="Serial Fix",
            description="Serialization test",
            spreadsheet_id="sheet-serial",
            cells_modified=5,
            tags=["test"],
        )
        
        summary_dict = summary.model_dump()
        
        assert summary_dict["id"] == "fix-serial"
        assert summary_dict["title"] == "Serial Fix"
        assert summary_dict["spreadsheet_id"] == "sheet-serial"
        assert summary_dict["cells_modified"] == 5
        assert "timestamp" in summary_dict
