"""Tests for LLM diagnostics module."""

import pytest
import json
from datetime import datetime

from sheetsmith.llm.diagnostics import (
    DiagnosticReport,
    LLMDiagnostics,
    CostSpikeDetector,
    DiagnosticAlertSystem,
)


class TestDiagnosticReport:
    """Test DiagnosticReport dataclass."""
    
    def test_report_initialization(self):
        """Test report can be initialized."""
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
        )
        
        assert report.operation_type == "parser"
        assert report.model_used == "claude-3-haiku"
        assert report.warnings == []
        assert report.errors == []
    
    def test_report_to_dict(self):
        """Test report can be converted to dict."""
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
        )
        
        data = report.to_dict()
        assert isinstance(data, dict)
        assert data["operation_type"] == "parser"
        assert data["model_used"] == "claude-3-haiku"
    
    def test_report_to_json_log(self):
        """Test report can be converted to JSON log format."""
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
            input_tokens=150,
            output_tokens=50,
            estimated_cost=0.1,
            duration_ms=245.5,
        )
        
        log_data = report.to_json_log()
        assert log_data["operation"] == "parser"
        assert log_data["model"] == "claude-3-haiku"
        assert log_data["duration_ms"] == 245.5
        assert log_data["input_tokens"] == 150
        assert log_data["output_tokens"] == 50
        assert log_data["estimated_cost_usd"] == 0.001
        assert "validation" in log_data
        assert log_data["validation"]["model_ok"] is True
        assert log_data["validation"]["tools_ok"] is True


class TestCostSpikeDetector:
    """Test CostSpikeDetector class."""
    
    def test_detector_initialization(self):
        """Test detector can be initialized."""
        detector = CostSpikeDetector(threshold_multiplier=2.0)
        assert detector.threshold_multiplier == 2.0
    
    def test_calculate_threshold(self):
        """Test threshold calculation."""
        detector = CostSpikeDetector(threshold_multiplier=2.0)
        
        # Parser expected cost: 0.1 cents
        threshold = detector.calculate_threshold("parser")
        assert threshold == 0.2  # 0.1 * 2.0
        
        # Planning expected cost: 5.0 cents
        threshold = detector.calculate_threshold("planning")
        assert threshold == 10.0  # 5.0 * 2.0
    
    def test_is_spike_detects_normal_cost(self):
        """Test spike detection with normal cost."""
        detector = CostSpikeDetector(threshold_multiplier=2.0)
        
        # Parser normal cost
        assert not detector.is_spike(0.1, "parser")
        assert not detector.is_spike(0.15, "parser")
    
    def test_is_spike_detects_spike(self):
        """Test spike detection with high cost."""
        detector = CostSpikeDetector(threshold_multiplier=2.0)
        
        # Parser spike (threshold = 0.2 cents)
        assert detector.is_spike(0.25, "parser")
        assert detector.is_spike(1.0, "parser")
        
        # Planning spike (threshold = 10.0 cents)
        assert detector.is_spike(11.0, "planning")
    
    def test_is_spike_with_unknown_operation(self):
        """Test spike detection with unknown operation type."""
        detector = CostSpikeDetector(threshold_multiplier=2.0)
        
        # Unknown operation uses default of 1.0 cent
        # Threshold = 2.0 cents
        assert not detector.is_spike(1.5, "unknown_op")
        assert detector.is_spike(2.5, "unknown_op")


class TestLLMDiagnostics:
    """Test LLMDiagnostics class."""
    
    def test_diagnostics_initialization(self):
        """Test diagnostics can be initialized."""
        diagnostics = LLMDiagnostics(
            max_system_prompt_chars=500,
            max_history_messages=10,
            max_sheet_content_chars=5000,
            max_tools_schema_bytes=0,
        )
        
        assert diagnostics.max_system_prompt_chars == 500
        assert diagnostics.max_history_messages == 10
        assert diagnostics.spike_detector is not None
    
    def test_pre_call_check_valid_payload(self):
        """Test pre-call check with valid payload."""
        diagnostics = LLMDiagnostics()
        
        payload = {
            "model": "claude-3-haiku",
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "tools": [],
            "max_tokens": 300,
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.operation_type == "parser"
        assert report.model_used == "claude-3-haiku"
        assert report.model_validation is True
        assert report.has_tools_schema is False
        assert report.system_prompt_ok is True
        assert report.history_ok is True
        assert report.max_tokens_ok is True
        assert len(report.errors) == 0
        assert len(report.warnings) == 0
    
    def test_pre_call_check_detects_tools(self):
        """Test pre-call check detects tools schema."""
        diagnostics = LLMDiagnostics(max_tools_schema_bytes=0)
        
        payload = {
            "model": "claude-3-haiku",
            "system": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [{"name": "test_tool", "description": "A test tool"}],
            "max_tokens": 300,
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.has_tools_schema is True
        assert report.tools_schema_size > 0
        assert any("Tools schema" in w for w in report.warnings)
    
    def test_pre_call_check_detects_large_system_prompt(self):
        """Test pre-call check detects large system prompt."""
        diagnostics = LLMDiagnostics(max_system_prompt_chars=100)
        
        long_prompt = "x" * 200
        payload = {
            "model": "claude-3-haiku",
            "system": long_prompt,
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 300,
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.system_prompt_ok is False
        assert report.system_prompt_size == 200
        assert any("System prompt size" in w for w in report.warnings)
    
    def test_pre_call_check_detects_too_many_messages(self):
        """Test pre-call check detects excessive message history."""
        diagnostics = LLMDiagnostics(max_history_messages=3)
        
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(5)
        ]
        
        payload = {
            "model": "claude-3-haiku",
            "system": "System prompt",
            "messages": messages,
            "tools": [],
            "max_tokens": 300,
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.history_ok is False
        assert report.history_message_count == 5
        assert any("Message history count" in w for w in report.warnings)
    
    def test_pre_call_check_detects_high_max_tokens(self):
        """Test pre-call check detects excessive max_tokens."""
        diagnostics = LLMDiagnostics()
        
        payload = {
            "model": "claude-3-haiku",
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 2000,  # Too high for parser
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.max_tokens_ok is False
        assert any("max_tokens" in w for w in report.warnings)
    
    def test_pre_call_check_detects_model_mismatch(self):
        """Test pre-call check detects model mismatch."""
        diagnostics = LLMDiagnostics()
        
        payload = {
            "model": "claude-3-opus",
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 300,
        }
        
        report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        assert report.model_validation is False
        assert any("Model mismatch" in w for w in report.warnings)
    
    def test_post_call_analysis_adds_usage_data(self):
        """Test post-call analysis adds usage data."""
        diagnostics = LLMDiagnostics()
        
        # Create a pre-report
        payload = {
            "model": "claude-3-haiku",
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 300,
        }
        pre_report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        # Mock response with usage data
        response = {
            "usage": {
                "input_tokens": 150,
                "output_tokens": 50,
            }
        }
        
        # Post-call analysis
        post_report = diagnostics.post_call_analysis(
            pre_report, response, duration=245.5, estimated_cost=0.1
        )
        
        assert post_report.input_tokens == 150
        assert post_report.output_tokens == 50
        assert post_report.duration_ms == 245.5
        assert post_report.estimated_cost == 0.1
    
    def test_post_call_analysis_detects_cost_spike(self):
        """Test post-call analysis detects cost spike."""
        diagnostics = LLMDiagnostics()
        
        # Create a pre-report
        payload = {
            "model": "claude-3-haiku",
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 300,
        }
        pre_report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        # Mock response with high cost
        response = {
            "usage": {
                "input_tokens": 10000,
                "output_tokens": 5000,
            }
        }
        
        # Post-call analysis with spike cost
        post_report = diagnostics.post_call_analysis(
            pre_report, response, duration=1000.0, estimated_cost=5.0
        )
        
        assert post_report.is_spike is True
        assert any("Cost spike" in w for w in post_report.warnings)
    
    def test_post_call_analysis_with_actual_cost(self):
        """Test post-call analysis with actual cost from API."""
        diagnostics = LLMDiagnostics()
        
        payload = {
            "model": "claude-3-haiku",
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [],
            "max_tokens": 300,
        }
        pre_report = diagnostics.pre_call_check(payload, "parser", "claude-3-haiku")
        
        # Mock response with OpenRouter cost data
        response = {
            "usage": {
                "input_tokens": 150,
                "output_tokens": 50,
                "native_tokens_cost": 0.0012,  # In dollars
            }
        }
        
        post_report = diagnostics.post_call_analysis(
            pre_report, response, duration=245.5, estimated_cost=0.1
        )
        
        assert post_report.actual_cost == 0.12  # 0.0012 * 100 = 0.12 cents
    
    def test_calculate_history_chars_string_content(self):
        """Test character calculation with string content."""
        diagnostics = LLMDiagnostics()
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        
        total = diagnostics._calculate_history_chars(messages)
        assert total == len("Hello") + len("Hi there")
    
    def test_calculate_history_chars_list_content(self):
        """Test character calculation with list content."""
        diagnostics = LLMDiagnostics()
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ]
            }
        ]
        
        total = diagnostics._calculate_history_chars(messages)
        assert total == len("Hello") + len("World")


class TestDiagnosticAlertSystem:
    """Test DiagnosticAlertSystem class."""
    
    def test_alert_system_initialization(self):
        """Test alert system can be initialized."""
        alert_system = DiagnosticAlertSystem(enabled=True)
        assert alert_system.enabled is True
    
    def test_should_alert_on_spike(self):
        """Test alert triggers on cost spike."""
        alert_system = DiagnosticAlertSystem(enabled=True)
        
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
            is_spike=True,
        )
        
        assert alert_system.should_alert(report) is True
    
    def test_should_alert_on_errors(self):
        """Test alert triggers on errors."""
        alert_system = DiagnosticAlertSystem(enabled=True)
        
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
            errors=["Critical error"],
        )
        
        assert alert_system.should_alert(report) is True
    
    def test_should_alert_on_multiple_warnings(self):
        """Test alert triggers on multiple warnings."""
        alert_system = DiagnosticAlertSystem(enabled=True)
        
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
            warnings=["Warning 1", "Warning 2", "Warning 3"],
        )
        
        assert alert_system.should_alert(report) is True
    
    def test_should_not_alert_when_disabled(self):
        """Test alert system respects enabled flag."""
        alert_system = DiagnosticAlertSystem(enabled=False)
        
        report = DiagnosticReport(
            timestamp=datetime.utcnow().isoformat(),
            operation_type="parser",
            model_used="claude-3-haiku",
            model_expected="claude-3-haiku",
            model_validation=True,
            has_tools_schema=False,
            tools_schema_size=0,
            system_prompt_size=100,
            system_prompt_ok=True,
            history_message_count=2,
            history_total_chars=500,
            history_ok=True,
            sheet_content_size=0,
            sheet_content_ok=True,
            max_tokens_requested=300,
            max_tokens_ok=True,
            is_spike=True,
        )
        
        assert alert_system.should_alert(report) is False
