# Clinical Workflow WebSocket Progress Updates

## Overview

This document describes the WebSocket progress update system for the 10-stage clinical workflow pipeline, implemented as part of Task 6.1.

## Features

### 1. Clinical Workflow Event Types

The system supports the following event types for clinical workflows:

- `clinical.workflow.started` - Workflow initiated
- `clinical.workflow.progress` - Stage progress update (2-5 second intervals)
- `clinical.stage.complete` - Stage completed successfully
- `clinical.workflow.error` - Error occurred during workflow
- `clinical.workflow.completed` - All 10 stages complete
- `clinical.substage.progress` - Fine-grained progress within a stage

### 2. 10-Stage Clinical Pipeline

The system tracks progress through these stages:

1. **EHR Data Ingestion** - Extract structured data from electronic health records
2. **AI Phenotype Clustering** - Cluster patient phenotypes using HDBSCAN
3. **DL Tissue Analysis** - Analyze histopathology images with deep learning
4. **Neural Network Biomarker Quantification** - Quantify biomarkers from flow cytometry
5. **Genomic Sequencing** - Process and annotate genomic variants
6. **DL Pathogenicity Prediction** - Predict variant pathogenicity with deep learning
7. **Knowledge Graph Cross-Referencing** - Cross-reference with biomedical databases
8. **AI Disruption Modeling** - Simulate mutation effects on pathways
9. **AI Targeted Drug Matching** - Match pathways to treatments
10. **Advanced Therapy Stratification** - Calculate therapy compatibility scores

### 3. Progress Tracking Features

#### Percentage Completion
- 0-100% progress per stage
- Overall workflow progress calculated across all stages
- Automatic clamping to valid range

#### Stage-Based Tracking
- Current stage number (1-10)
- Stage name
- Substage tracking for long-running stages

#### ETA Calculation
- Estimated time remaining in seconds
- Estimated completion timestamp
- Based on historical processing times

#### Quality Metrics
- Per-stage quality scores (0-1 scale)
- Quality warnings for scores below threshold (0.7)
- Overall workflow quality score

#### Resource Monitoring
- Memory usage (MB)
- CPU utilization (%)
- GPU utilization (%)

### 4. Error Handling

#### Error Classification
The system automatically classifies errors into types:

- `data_error` - Data validation or format errors
- `model_error` - ML/DL model execution errors
- `system_error` - Infrastructure or resource errors
- `timeout_error` - Operation exceeded time limit
- `validation_error` - Quality validation failed

#### Recovery Suggestions
Contextual recovery suggestions are automatically generated based on:
- Error type
- Stage where error occurred
- Error context

Example suggestions:
- "Verify input data format and completeness"
- "Check model availability and version"
- "Reduce batch size or input data volume"

### 5. Performance Requirements

- **Message Latency**: <100ms from emit to client receive
- **Update Frequency**: Every 2-5 seconds during active processing
- **Connection Efficiency**: Minimal bandwidth usage through efficient payload design

## API Reference

### Core Functions

#### `emit_clinical_workflow_started()`
Emit when clinical workflow begins.

```python
await emit_clinical_workflow_started(
    manager=ws_manager,
    run_id="run-123",
    workflow_name="Patient Analysis",
    metadata={"patient_id": "P12345"}
)
```

#### `emit_clinical_workflow_progress()`
Emit progress update during stage execution.

```python
await emit_clinical_workflow_progress(
    manager=ws_manager,
    run_id="run-123",
    stage_number=3,
    stage_name="DL Tissue Analysis",
    progress_pct=45,
    message="Analyzing tissue sample 3 of 5",
    substage="tissue_analysis",
    estimated_time_remaining=120,
    resource_usage={"memory_mb": 2048, "cpu_pct": 75, "gpu_pct": 90},
    quality_metrics={"accuracy": 0.95}
)
```

#### `emit_clinical_stage_complete()`
Emit when a stage completes successfully.

```python
await emit_clinical_stage_complete(
    manager=ws_manager,
    run_id="run-123",
    stage_number=3,
    stage_name="DL Tissue Analysis",
    results_summary={"images_analyzed": 5, "anomalies_detected": 3},
    quality_score=0.88,
    processing_time_seconds=120.0,
    records_processed=5
)
```

#### `emit_clinical_workflow_error()`
Emit when an error occurs.

```python
await emit_clinical_workflow_error(
    manager=ws_manager,
    run_id="run-123",
    stage_number=4,
    stage_name="Neural Network Biomarker Quantification",
    error_message="Model inference failed",
    error_type="model_error",
    recoverable=True,
    error_context={"model": "biomarker_v2", "batch_size": 32}
)
```

#### `emit_clinical_workflow_completed()`
Emit when all 10 stages complete.

```python
await emit_clinical_workflow_completed(
    manager=ws_manager,
    run_id="run-123",
    workflow_name="Patient Analysis",
    total_processing_time_seconds=600.0,
    stages_completed=10,
    overall_quality_score=0.89,
    output_artifacts=["report.pdf", "results.json"]
)
```

#### `emit_clinical_substage_progress()`
Emit fine-grained progress within a stage.

```python
await emit_clinical_substage_progress(
    manager=ws_manager,
    run_id="run-123",
    stage_number=3,
    stage_name="DL Tissue Analysis",
    substage_name="Image 3 of 10",
    substage_progress_pct=30,
    message="Analyzing tissue sample"
)
```

#### `get_clinical_workflow_status()`
Get current status of a workflow run.

```python
status = get_clinical_workflow_status(ws_manager, "run-123")
# Returns: {
#   "run_id": "run-123",
#   "status": "in_progress",
#   "current_stage": 5,
#   "current_stage_name": "Genomic Sequencing",
#   "progress_pct": 60,
#   "last_update": "2024-01-15T10:30:00Z"
# }
```

## Usage Example

See `examples/clinical_workflow_websocket_example.py` for a complete example demonstrating:
- Starting a clinical workflow
- Emitting progress updates
- Handling substage progress
- Error handling
- Workflow completion
- Status monitoring

## Integration Points

Clinical workflow services should call these functions to emit progress:

```python
from core.websocket_manager import get_ws_manager, emit_clinical_workflow_progress

# In your clinical workflow service
manager = get_ws_manager()

# Emit progress during processing
await emit_clinical_workflow_progress(
    manager=manager,
    run_id=run_id,
    stage_number=current_stage,
    stage_name=stage_name,
    progress_pct=progress,
    message=status_message
)
```

## Testing

Comprehensive test suite available in `tests/test_clinical_websocket.py`:

- 25 test cases covering all functions
- Tests for constants and configuration
- Tests for event emission
- Tests for error handling
- Tests for message latency (<100ms requirement)

Run tests:
```bash
cd apps/api
python -m pytest tests/test_clinical_websocket.py -v
```

## WebSocket Client Integration

Clients connect to: `ws://HOST:8000/ws/runs/{run_id}`

Example client code:
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/runs/${runId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event) {
    case 'clinical.workflow.progress':
      updateProgressBar(data.payload.progress_pct);
      updateStageInfo(data.payload.stage_name);
      break;
      
    case 'clinical.stage.complete':
      markStageComplete(data.payload.stage_number);
      break;
      
    case 'clinical.workflow.error':
      showError(data.payload.error_message);
      showRecoverySuggestions(data.payload.recovery_suggestions);
      break;
      
    case 'clinical.workflow.completed':
      showCompletionSummary(data.payload);
      break;
  }
};
```

## Performance Considerations

1. **Batch Updates**: Group multiple substage updates to reduce message frequency
2. **Efficient Payloads**: Only include necessary data in each message
3. **Connection Pooling**: Reuse WebSocket connections across multiple workflows
4. **Event History**: Limited to 200 events per run for reconnection replay

## Future Enhancements

Potential improvements for future iterations:

1. **Adaptive Update Frequency**: Adjust update frequency based on stage complexity
2. **Predictive ETA**: Machine learning-based ETA prediction
3. **Anomaly Detection**: Automatic detection of unusual processing patterns
4. **Performance Profiling**: Detailed performance metrics per stage
5. **Multi-Workflow Tracking**: Track multiple concurrent workflows per user

## Compliance

- **HIPAA**: All PHI is redacted from WebSocket messages
- **Audit Logging**: All workflow events are logged for compliance
- **Authentication**: JWT-based authentication required for WebSocket connections
- **Encryption**: TLS/SSL encryption for all WebSocket traffic in production
