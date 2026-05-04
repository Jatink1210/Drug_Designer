"""Unit tests for WebSocket Manager.

Tests WebSocket connection management, event emission, and message routing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio
import json


class TestWebSocketManager:
    """Test WebSocket manager functionality."""
    
    def test_manager_initialization(self):
        """Test WebSocket manager initialization."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager(max_event_history=50)
        assert manager is not None
        assert manager._max_event_history == 50
    
    @pytest.mark.asyncio
    async def test_connect_websocket(self):
        """Test WebSocket connection."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run-123")
        
        mock_ws.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_websocket(self):
        """Test WebSocket disconnection."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run-123")
        manager.disconnect(run_id="test-run-123")
        
        # Verify disconnection
        assert "test-run-123" not in manager._connections
    
    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Test event emission."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run-123")
        await manager.emit(
            run_id="test-run-123",
            event="test.event",
            payload={"message": "test"}
        )
        
        mock_ws.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_event_history(self):
        """Test event history tracking."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager(max_event_history=10)
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run-123")
        
        # Emit multiple events
        for i in range(5):
            await manager.emit(
                run_id="test-run-123",
                event=f"test.event.{i}",
                payload={"index": i}
            )
        
        # Verify history
        history = manager._event_history.get("test-run-123", [])
        assert len(history) == 5
    
    @pytest.mark.asyncio
    async def test_event_history_limit(self):
        """Test event history respects max limit."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager(max_event_history=5)
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run-123")
        
        # Emit more events than limit
        for i in range(10):
            await manager.emit(
                run_id="test-run-123",
                event=f"test.event.{i}",
                payload={"index": i}
            )
        
        # Verify history is limited
        history = manager._event_history.get("test-run-123", [])
        assert len(history) <= 5
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_connections(self):
        """Test broadcasting to multiple connections."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # Connect multiple WebSockets
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        
        await manager.connect(mock_ws1, run_id="run-1")
        await manager.connect(mock_ws2, run_id="run-2")
        
        # Emit to specific run
        await manager.emit(run_id="run-1", event="test.event", payload={})
        
        # Only run-1 should receive
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_not_called()


class TestClinicalWorkflowEvents:
    """Test clinical workflow event functions."""
    
    @pytest.mark.asyncio
    async def test_emit_workflow_started(self):
        """Test workflow started event."""
        from core.websocket_manager import WebSocketManager, emit_clinical_workflow_started
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_workflow_started(
            manager=manager,
            run_id="test-run",
            workflow_name="Test Workflow"
        )
        
        mock_ws.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_emit_workflow_progress(self):
        """Test workflow progress event."""
        from core.websocket_manager import WebSocketManager, emit_clinical_workflow_progress
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_workflow_progress(
            manager=manager,
            run_id="test-run",
            stage_number=3,
            stage_name="DL Tissue Analysis",
            progress_pct=50,
            message="Processing"
        )
        
        mock_ws.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_emit_stage_complete(self):
        """Test stage complete event."""
        from core.websocket_manager import WebSocketManager, emit_clinical_stage_complete
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_stage_complete(
            manager=manager,
            run_id="test-run",
            stage_number=3,
            stage_name="DL Tissue Analysis",
            results_summary={"anomalies": 5}
        )
        
        mock_ws.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_emit_workflow_error(self):
        """Test workflow error event."""
        from core.websocket_manager import WebSocketManager, emit_clinical_workflow_error
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_workflow_error(
            manager=manager,
            run_id="test-run",
            stage_number=3,
            stage_name="DL Tissue Analysis",
            error_message="Model inference failed",
            error_type="model_error"
        )
        
        mock_ws.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_emit_workflow_completed(self):
        """Test workflow completed event."""
        from core.websocket_manager import WebSocketManager, emit_clinical_workflow_completed
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_workflow_completed(
            manager=manager,
            run_id="test-run",
            workflow_name="Clinical Analysis",
            total_processing_time_seconds=600.0,
            stages_completed=10
        )
        
        mock_ws.send_text.assert_called()


class TestWorkflowStatus:
    """Test workflow status retrieval."""
    
    def test_get_workflow_status_not_found(self):
        """Test status for non-existent workflow."""
        from core.websocket_manager import WebSocketManager, get_clinical_workflow_status
        
        manager = WebSocketManager()
        status = get_clinical_workflow_status(manager, "non-existent")
        
        assert status["status"] == "not_found"
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_in_progress(self):
        """Test status for in-progress workflow."""
        from core.websocket_manager import (
            WebSocketManager,
            emit_clinical_workflow_progress,
            get_clinical_workflow_status
        )
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        await emit_clinical_workflow_progress(
            manager=manager,
            run_id="test-run",
            stage_number=5,
            stage_name="Genomic Sequencing",
            progress_pct=60,
            message="Processing"
        )
        
        status = get_clinical_workflow_status(manager, "test-run")
        assert status["status"] == "in_progress"
        assert status["current_stage"] == 5


class TestErrorHandling:
    """Test error handling in WebSocket manager."""
    
    @pytest.mark.asyncio
    async def test_emit_to_disconnected_client(self):
        """Test emitting to disconnected client."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # Try to emit without connection
        try:
            await manager.emit(
                run_id="non-existent",
                event="test.event",
                payload={}
            )
            # Should not raise exception
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error handling."""
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock(side_effect=Exception("Connection error"))
        
        with pytest.raises(Exception):
            await manager.connect(mock_ws, run_id="test-run")


class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_emit_latency(self):
        """Test event emission latency."""
        import time
        from core.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        
        await manager.connect(mock_ws, run_id="test-run")
        
        start = time.time()
        await manager.emit(
            run_id="test-run",
            event="test.event",
            payload={"data": "test"}
        )
        latency = time.time() - start
        
        # Should be very fast (<100ms)
        assert latency < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
