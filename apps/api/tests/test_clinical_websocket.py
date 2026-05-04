"""Tests for Clinical Workflow WebSocket Progress Updates.

Validates Task 6.1 implementation:
- Clinical workflow functions exist and have correct signatures
- Event emission works correctly
- Progress tracking is accurate
- Error notifications are properly formatted
- Message latency is acceptable
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from core.websocket_manager import (
    WebSocketManager,
    emit_clinical_workflow_started,
    emit_clinical_workflow_progress,
    emit_clinical_stage_complete,
    emit_clinical_workflow_error,
    emit_clinical_workflow_completed,
    emit_clinical_substage_progress,
    get_clinical_workflow_status,
    CLINICAL_STAGES,
    ERROR_TYPES
)


@pytest.fixture
def ws_manager():
    """Create a WebSocketManager instance for testing."""
    return WebSocketManager(max_event_history=50)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestClinicalWorkflowConstants:
    """Test clinical workflow constants and configuration."""
    
    def test_clinical_stages_count(self):
        """Verify 10 clinical stages are defined."""
        assert len(CLINICAL_STAGES) == 10
    
    def test_clinical_stages_names(self):
        """Verify all expected stage names are present."""
        expected_stages = [
            "EHR Data Ingestion",
            "AI Phenotype Clustering",
            "DL Tissue Analysis",
            "Neural Network Biomarker Quantification",
            "Genomic Sequencing",
            "DL Pathogenicity Prediction",
            "Knowledge Graph Cross-Referencing",
            "AI Disruption Modeling",
            "AI Targeted Drug Matching",
            "Advanced Therapy Stratification"
        ]
        assert CLINICAL_STAGES == expected_stages
    
    def test_error_types_defined(self):
        """Verify error type classifications are defined."""
        expected_types = ["data_error", "model_error", "system_error", "timeout_error", "validation_error"]
        for error_type in expected_types:
            assert error_type in ERROR_TYPES
            assert isinstance(ERROR_TYPES[error_type], str)


class TestClinicalWorkflowStarted:
    """Test emit_clinical_workflow_started function."""
    
    @pytest.mark.asyncio
    async def test_workflow_started_basic(self, ws_manager, mock_websocket):
        """Test basic workflow started event emission."""
        run_id = "test-run-123"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_started(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Test Clinical Workflow"
        )
        
        # Verify event was stored in history
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.workflow.started"
        assert events[0]["payload"]["workflow_name"] == "Test Clinical Workflow"
        assert events[0]["payload"]["total_stages"] == 10
        assert events[0]["payload"]["stages"] == CLINICAL_STAGES
    
    @pytest.mark.asyncio
    async def test_workflow_started_with_metadata(self, ws_manager, mock_websocket):
        """Test workflow started with custom metadata."""
        run_id = "test-run-456"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        metadata = {"patient_id": "P12345", "project_id": "PRJ-001"}
        await emit_clinical_workflow_started(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Patient Analysis",
            metadata=metadata
        )
        
        events = ws_manager._event_history[run_id]
        assert events[0]["payload"]["metadata"] == metadata


class TestClinicalWorkflowProgress:
    """Test emit_clinical_workflow_progress function."""
    
    @pytest.mark.asyncio
    async def test_progress_basic(self, ws_manager, mock_websocket):
        """Test basic progress event emission."""
        run_id = "test-run-789"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=3,
            stage_name="DL Tissue Analysis",
            progress_pct=45,
            message="Analyzing tissue sample 3 of 5"
        )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.workflow.progress"
        
        payload = events[0]["payload"]
        assert payload["stage_number"] == 3
        assert payload["stage_name"] == "DL Tissue Analysis"
        assert payload["progress_pct"] == 45
        assert payload["message"] == "Analyzing tissue sample 3 of 5"
        assert payload["total_stages"] == 10
    
    @pytest.mark.asyncio
    async def test_progress_with_eta(self, ws_manager, mock_websocket):
        """Test progress with ETA calculation."""
        run_id = "test-run-eta"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=5,
            stage_name="Genomic Sequencing",
            progress_pct=60,
            message="Processing variants",
            estimated_time_remaining=120
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["estimated_time_remaining_seconds"] == 120
        assert "estimated_completion_time" in payload
    
    @pytest.mark.asyncio
    async def test_progress_with_resource_usage(self, ws_manager, mock_websocket):
        """Test progress with resource monitoring."""
        run_id = "test-run-resources"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        resource_usage = {"memory_mb": 2048, "cpu_pct": 75, "gpu_pct": 90}
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=4,
            stage_name="Neural Network Biomarker Quantification",
            progress_pct=80,
            message="Quantifying biomarkers",
            resource_usage=resource_usage
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["resource_usage"]["memory_mb"] == 2048
        assert payload["resource_usage"]["cpu_percent"] == 75
        assert payload["resource_usage"]["gpu_percent"] == 90
    
    @pytest.mark.asyncio
    async def test_progress_with_quality_metrics(self, ws_manager, mock_websocket):
        """Test progress with quality metrics."""
        run_id = "test-run-quality"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        quality_metrics = {"accuracy": 0.95, "confidence": 0.88}
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=6,
            stage_name="DL Pathogenicity Prediction",
            progress_pct=70,
            message="Predicting pathogenicity",
            quality_metrics=quality_metrics
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["quality_metrics"] == quality_metrics
    
    @pytest.mark.asyncio
    async def test_progress_percentage_clamping(self, ws_manager, mock_websocket):
        """Test progress percentage is clamped to 0-100 range."""
        run_id = "test-run-clamp"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        # Test over 100
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=1,
            stage_name="EHR Data Ingestion",
            progress_pct=150,
            message="Test"
        )
        assert ws_manager._event_history[run_id][0]["payload"]["progress_pct"] == 100
        
        # Test under 0
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=1,
            stage_name="EHR Data Ingestion",
            progress_pct=-10,
            message="Test"
        )
        assert ws_manager._event_history[run_id][1]["payload"]["progress_pct"] == 0


class TestClinicalStageComplete:
    """Test emit_clinical_stage_complete function."""
    
    @pytest.mark.asyncio
    async def test_stage_complete_basic(self, ws_manager, mock_websocket):
        """Test basic stage completion event."""
        run_id = "test-run-complete"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        results = {"records_processed": 1000, "anomalies_detected": 5}
        await emit_clinical_stage_complete(
            manager=ws_manager,
            run_id=run_id,
            stage_number=3,
            stage_name="DL Tissue Analysis",
            results_summary=results
        )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.stage.complete"
        
        payload = events[0]["payload"]
        assert payload["stage_number"] == 3
        assert payload["stage_name"] == "DL Tissue Analysis"
        assert payload["results_summary"] == results
        assert payload["validation_passed"] is True
    
    @pytest.mark.asyncio
    async def test_stage_complete_with_quality_score(self, ws_manager, mock_websocket):
        """Test stage completion with quality validation."""
        run_id = "test-run-quality-complete"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        # High quality score
        await emit_clinical_stage_complete(
            manager=ws_manager,
            run_id=run_id,
            stage_number=2,
            stage_name="AI Phenotype Clustering",
            results_summary={"clusters": 5},
            quality_score=0.85
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["quality_score"] == 0.85
        assert "quality_warning" not in payload
        
        # Low quality score (should trigger warning)
        await emit_clinical_stage_complete(
            manager=ws_manager,
            run_id=run_id,
            stage_number=3,
            stage_name="DL Tissue Analysis",
            results_summary={"images": 10},
            quality_score=0.65
        )
        
        payload = ws_manager._event_history[run_id][1]["payload"]
        assert payload["quality_score"] == 0.65
        assert "quality_warning" in payload
    
    @pytest.mark.asyncio
    async def test_stage_complete_with_metrics(self, ws_manager, mock_websocket):
        """Test stage completion with processing metrics."""
        run_id = "test-run-metrics"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_stage_complete(
            manager=ws_manager,
            run_id=run_id,
            stage_number=5,
            stage_name="Genomic Sequencing",
            results_summary={"variants": 50000},
            processing_time_seconds=120.5,
            records_processed=50000
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["processing_time_seconds"] == 120.5
        assert payload["records_processed"] == 50000


class TestClinicalWorkflowError:
    """Test emit_clinical_workflow_error function."""
    
    @pytest.mark.asyncio
    async def test_error_basic(self, ws_manager, mock_websocket):
        """Test basic error event emission."""
        run_id = "test-run-error"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_error(
            manager=ws_manager,
            run_id=run_id,
            stage_number=4,
            stage_name="Neural Network Biomarker Quantification",
            error_message="Model inference failed",
            error_type="model_error"
        )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.workflow.error"
        
        payload = events[0]["payload"]
        assert payload["stage_number"] == 4
        assert payload["error_message"] == "Model inference failed"
        assert payload["error_type"] == "model_error"
        assert payload["recoverable"] is True
        assert len(payload["recovery_suggestions"]) > 0
    
    @pytest.mark.asyncio
    async def test_error_classification(self, ws_manager, mock_websocket):
        """Test error type classification."""
        run_id = "test-run-error-types"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        for error_type in ERROR_TYPES.keys():
            await emit_clinical_workflow_error(
                manager=ws_manager,
                run_id=run_id,
                stage_number=1,
                stage_name="EHR Data Ingestion",
                error_message=f"Test {error_type}",
                error_type=error_type
            )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == len(ERROR_TYPES)
        
        for i, error_type in enumerate(ERROR_TYPES.keys()):
            assert events[i]["payload"]["error_type"] == error_type
            assert events[i]["payload"]["error_type_description"] == ERROR_TYPES[error_type]
    
    @pytest.mark.asyncio
    async def test_error_with_recovery_suggestions(self, ws_manager, mock_websocket):
        """Test error with custom recovery suggestions."""
        run_id = "test-run-recovery"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        custom_suggestions = ["Check input format", "Retry with smaller batch"]
        await emit_clinical_workflow_error(
            manager=ws_manager,
            run_id=run_id,
            stage_number=1,
            stage_name="EHR Data Ingestion",
            error_message="Invalid data format",
            error_type="data_error",
            recovery_suggestions=custom_suggestions
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["recovery_suggestions"] == custom_suggestions
    
    @pytest.mark.asyncio
    async def test_error_invalid_type_fallback(self, ws_manager, mock_websocket):
        """Test error with invalid type falls back to system_error."""
        run_id = "test-run-invalid-type"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_error(
            manager=ws_manager,
            run_id=run_id,
            stage_number=1,
            stage_name="EHR Data Ingestion",
            error_message="Unknown error",
            error_type="invalid_error_type"
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["error_type"] == "system_error"


class TestClinicalWorkflowCompleted:
    """Test emit_clinical_workflow_completed function."""
    
    @pytest.mark.asyncio
    async def test_workflow_completed_basic(self, ws_manager, mock_websocket):
        """Test basic workflow completion event."""
        run_id = "test-run-done"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_completed(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Clinical Analysis",
            total_processing_time_seconds=600.0,
            stages_completed=10
        )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.workflow.completed"
        
        payload = events[0]["payload"]
        assert payload["workflow_name"] == "Clinical Analysis"
        assert payload["total_stages"] == 10
        assert payload["stages_completed"] == 10
        assert payload["success"] is True
        assert payload["total_processing_time_seconds"] == 600.0
    
    @pytest.mark.asyncio
    async def test_workflow_completed_with_artifacts(self, ws_manager, mock_websocket):
        """Test workflow completion with output artifacts."""
        run_id = "test-run-artifacts"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        artifacts = ["report.pdf", "results.json", "visualization.png"]
        await emit_clinical_workflow_completed(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Clinical Analysis",
            total_processing_time_seconds=600.0,
            stages_completed=10,
            output_artifacts=artifacts
        )
        
        payload = ws_manager._event_history[run_id][0]["payload"]
        assert payload["output_artifacts"] == artifacts


class TestClinicalSubstageProgress:
    """Test emit_clinical_substage_progress function."""
    
    @pytest.mark.asyncio
    async def test_substage_progress(self, ws_manager, mock_websocket):
        """Test substage progress event emission."""
        run_id = "test-run-substage"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_substage_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=3,
            stage_name="DL Tissue Analysis",
            substage_name="Image 3 of 10",
            substage_progress_pct=30,
            message="Analyzing tissue sample"
        )
        
        events = ws_manager._event_history[run_id]
        assert len(events) == 1
        assert events[0]["event"] == "clinical.substage.progress"
        
        payload = events[0]["payload"]
        assert payload["stage_number"] == 3
        assert payload["substage_name"] == "Image 3 of 10"
        assert payload["substage_progress_pct"] == 30


class TestGetClinicalWorkflowStatus:
    """Test get_clinical_workflow_status function."""
    
    @pytest.mark.asyncio
    async def test_status_not_found(self, ws_manager):
        """Test status for non-existent workflow."""
        status = get_clinical_workflow_status(ws_manager, "non-existent-run")
        assert status["status"] == "not_found"
    
    @pytest.mark.asyncio
    async def test_status_in_progress(self, ws_manager, mock_websocket):
        """Test status for in-progress workflow."""
        run_id = "test-run-status"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        # Emit some progress events
        await emit_clinical_workflow_started(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Test"
        )
        
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=5,
            stage_name="Genomic Sequencing",
            progress_pct=60,
            message="Processing"
        )
        
        status = get_clinical_workflow_status(ws_manager, run_id)
        assert status["status"] == "in_progress"
        assert status["current_stage"] == 5
        assert status["current_stage_name"] == "Genomic Sequencing"
        assert status["progress_pct"] == 60
    
    @pytest.mark.asyncio
    async def test_status_completed(self, ws_manager, mock_websocket):
        """Test status for completed workflow."""
        run_id = "test-run-status-done"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        await emit_clinical_workflow_completed(
            manager=ws_manager,
            run_id=run_id,
            workflow_name="Test",
            total_processing_time_seconds=600.0,
            stages_completed=10
        )
        
        status = get_clinical_workflow_status(ws_manager, run_id)
        assert status["status"] == "completed"


class TestMessageLatency:
    """Test message latency requirements (<100ms)."""
    
    @pytest.mark.asyncio
    async def test_progress_emission_latency(self, ws_manager, mock_websocket):
        """Test that progress event emission is fast (<100ms)."""
        run_id = "test-run-latency"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        start_time = time.time()
        await emit_clinical_workflow_progress(
            manager=ws_manager,
            run_id=run_id,
            stage_number=1,
            stage_name="EHR Data Ingestion",
            progress_pct=50,
            message="Processing"
        )
        latency_ms = (time.time() - start_time) * 1000
        
        # Should be well under 100ms (typically <10ms)
        assert latency_ms < 100, f"Latency {latency_ms}ms exceeds 100ms requirement"
    
    @pytest.mark.asyncio
    async def test_batch_emission_latency(self, ws_manager, mock_websocket):
        """Test latency for multiple rapid emissions."""
        run_id = "test-run-batch-latency"
        await ws_manager.connect(mock_websocket, run_id=run_id)
        
        start_time = time.time()
        for i in range(10):
            await emit_clinical_workflow_progress(
                manager=ws_manager,
                run_id=run_id,
                stage_number=1,
                stage_name="EHR Data Ingestion",
                progress_pct=i * 10,
                message=f"Processing {i}"
            )
        total_time_ms = (time.time() - start_time) * 1000
        avg_latency_ms = total_time_ms / 10
        
        # Average latency should be under 100ms
        assert avg_latency_ms < 100, f"Average latency {avg_latency_ms}ms exceeds 100ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
