"""Example: Clinical Workflow WebSocket Progress Updates

This example demonstrates how to use the clinical workflow WebSocket functions
to emit real-time progress updates during a 10-stage clinical pipeline execution.

Usage:
    from core.websocket_manager import get_ws_manager
    from examples.clinical_workflow_websocket_example import run_clinical_workflow_example
    
    # In your clinical workflow service:
    manager = get_ws_manager()
    await run_clinical_workflow_example(manager, run_id="clinical-run-123")
"""

import asyncio
from typing import Optional
from core.websocket_manager import (
    WebSocketManager,
    emit_clinical_workflow_started,
    emit_clinical_workflow_progress,
    emit_clinical_stage_complete,
    emit_clinical_workflow_error,
    emit_clinical_workflow_completed,
    emit_clinical_substage_progress,
    get_clinical_workflow_status,
    CLINICAL_STAGES
)


async def run_clinical_workflow_example(
    manager: WebSocketManager,
    run_id: str,
    simulate_error: bool = False
):
    """
    Example clinical workflow execution with WebSocket progress updates.
    
    This simulates a 10-stage clinical pipeline with real-time progress updates.
    
    Args:
        manager: WebSocketManager instance
        run_id: Unique workflow run identifier
        simulate_error: If True, simulates an error in stage 4
    """
    
    # Stage 1: Start workflow
    await emit_clinical_workflow_started(
        manager=manager,
        run_id=run_id,
        workflow_name="Patient Clinical Analysis",
        metadata={
            "patient_id": "P12345",
            "project_id": "PRJ-001",
            "initiated_by": "Dr. Smith"
        }
    )
    
    # Stage 1: EHR Data Ingestion
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=1,
        stage_name=CLINICAL_STAGES[0],
        progress_pct=0,
        message="Starting EHR data ingestion",
        estimated_time_remaining=300
    )
    
    # Simulate processing
    await asyncio.sleep(0.5)
    
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=1,
        stage_name=CLINICAL_STAGES[0],
        progress_pct=50,
        message="Parsing HL7 messages",
        resource_usage={"memory_mb": 512, "cpu_pct": 45, "gpu_pct": 0}
    )
    
    await asyncio.sleep(0.5)
    
    await emit_clinical_stage_complete(
        manager=manager,
        run_id=run_id,
        stage_number=1,
        stage_name=CLINICAL_STAGES[0],
        results_summary={
            "records_ingested": 1000,
            "phi_redacted": 150,
            "format": "HL7 v2.5"
        },
        quality_score=0.95,
        processing_time_seconds=30.5,
        records_processed=1000
    )
    
    # Stage 2: AI Phenotype Clustering
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=2,
        stage_name=CLINICAL_STAGES[1],
        progress_pct=0,
        message="Extracting phenotype terms",
        estimated_time_remaining=240
    )
    
    await asyncio.sleep(0.5)
    
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=2,
        stage_name=CLINICAL_STAGES[1],
        progress_pct=60,
        message="Running HDBSCAN clustering",
        quality_metrics={"silhouette_score": 0.78}
    )
    
    await asyncio.sleep(0.5)
    
    await emit_clinical_stage_complete(
        manager=manager,
        run_id=run_id,
        stage_number=2,
        stage_name=CLINICAL_STAGES[1],
        results_summary={
            "clusters_identified": 5,
            "rare_patterns": 2,
            "phenotype_terms": 250
        },
        quality_score=0.82,
        processing_time_seconds=25.0
    )
    
    # Stage 3: DL Tissue Analysis (with substage progress)
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=3,
        stage_name=CLINICAL_STAGES[2],
        progress_pct=0,
        message="Loading tissue images",
        estimated_time_remaining=180
    )
    
    # Simulate analyzing multiple tissue samples
    for i in range(1, 6):
        await emit_clinical_substage_progress(
            manager=manager,
            run_id=run_id,
            stage_number=3,
            stage_name=CLINICAL_STAGES[2],
            substage_name=f"Tissue sample {i} of 5",
            substage_progress_pct=i * 20,
            message=f"Analyzing tissue sample {i}"
        )
        await asyncio.sleep(0.3)
    
    await emit_clinical_stage_complete(
        manager=manager,
        run_id=run_id,
        stage_number=3,
        stage_name=CLINICAL_STAGES[2],
        results_summary={
            "images_analyzed": 5,
            "anomalies_detected": 3,
            "confidence_avg": 0.91
        },
        quality_score=0.88,
        processing_time_seconds=120.0,
        records_processed=5
    )
    
    # Stage 4: Neural Network Biomarker Quantification (with optional error)
    if simulate_error:
        await emit_clinical_workflow_error(
            manager=manager,
            run_id=run_id,
            stage_number=4,
            stage_name=CLINICAL_STAGES[3],
            error_message="Model inference failed: CUDA out of memory",
            error_type="model_error",
            recoverable=True,
            error_context={
                "model": "biomarker_quantification_v2",
                "batch_size": 32,
                "memory_required_mb": 8192
            }
        )
        return  # Stop workflow on error
    
    await emit_clinical_workflow_progress(
        manager=manager,
        run_id=run_id,
        stage_number=4,
        stage_name=CLINICAL_STAGES[3],
        progress_pct=50,
        message="Quantifying immune cell populations",
        resource_usage={"memory_mb": 4096, "cpu_pct": 80, "gpu_pct": 95}
    )
    
    await asyncio.sleep(0.5)
    
    await emit_clinical_stage_complete(
        manager=manager,
        run_id=run_id,
        stage_number=4,
        stage_name=CLINICAL_STAGES[3],
        results_summary={
            "cell_populations": 12,
            "abnormal_subsets": 2,
            "regulatory_t_cells_pct": 3.5
        },
        quality_score=0.93,
        processing_time_seconds=45.0
    )
    
    # Stages 5-10: Abbreviated for example
    for stage_num in range(5, 11):
        await emit_clinical_workflow_progress(
            manager=manager,
            run_id=run_id,
            stage_number=stage_num,
            stage_name=CLINICAL_STAGES[stage_num - 1],
            progress_pct=50,
            message=f"Processing {CLINICAL_STAGES[stage_num - 1]}",
            estimated_time_remaining=(11 - stage_num) * 20
        )
        
        await asyncio.sleep(0.3)
        
        await emit_clinical_stage_complete(
            manager=manager,
            run_id=run_id,
            stage_number=stage_num,
            stage_name=CLINICAL_STAGES[stage_num - 1],
            results_summary={"status": "completed"},
            quality_score=0.85 + (stage_num * 0.01)
        )
    
    # Workflow complete
    await emit_clinical_workflow_completed(
        manager=manager,
        run_id=run_id,
        workflow_name="Patient Clinical Analysis",
        total_processing_time_seconds=600.0,
        stages_completed=10,
        overall_quality_score=0.89,
        output_artifacts=[
            "clinical_report.pdf",
            "phenotype_clusters.json",
            "tissue_analysis_heatmaps.png",
            "therapy_recommendations.json"
        ],
        summary={
            "patient_id": "P12345",
            "diagnosis_confidence": 0.92,
            "recommended_therapies": 3,
            "risk_score": "moderate"
        }
    )
    
    # Get final status
    status = get_clinical_workflow_status(manager, run_id)
    print(f"Workflow status: {status}")


async def example_error_handling():
    """Example demonstrating error handling in clinical workflows."""
    from core.websocket_manager import get_ws_manager
    
    manager = get_ws_manager()
    run_id = "clinical-run-error-demo"
    
    # Simulate workflow with error
    await run_clinical_workflow_example(
        manager=manager,
        run_id=run_id,
        simulate_error=True
    )


async def example_status_monitoring():
    """Example demonstrating workflow status monitoring."""
    from core.websocket_manager import get_ws_manager
    
    manager = get_ws_manager()
    run_id = "clinical-run-monitor"
    
    # Start workflow in background
    asyncio.create_task(run_clinical_workflow_example(manager, run_id))
    
    # Monitor status periodically
    for _ in range(5):
        await asyncio.sleep(1)
        status = get_clinical_workflow_status(manager, run_id)
        print(f"Current status: {status}")


if __name__ == "__main__":
    # Run example
    from core.websocket_manager import get_ws_manager
    
    manager = get_ws_manager()
    asyncio.run(run_clinical_workflow_example(manager, "example-run-123"))
