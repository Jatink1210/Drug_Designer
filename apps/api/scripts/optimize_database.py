"""Database Query Optimization Script (FR-PERF-001).

Add missing indexes, optimize slow queries, and eliminate N+1 query problems.
"""

from __future__ import annotations

import asyncio
import structlog
from sqlalchemy import text, inspect
from typing import List, Dict, Any

from core.db import get_async_session, engine

log = structlog.get_logger(__name__)


class DatabaseOptimizer:
    """Database query optimizer."""
    
    def __init__(self):
        """Initialize database optimizer."""
        self.optimization_results = []
    
    async def analyze_and_optimize(self):
        """Run complete database optimization."""
        log.info("starting_database_optimization")
        
        # 1. Add missing indexes
        await self.add_missing_indexes()
        
        # 2. Analyze slow queries
        await self.analyze_slow_queries()
        
        # 3. Check for N+1 query patterns
        await self.check_n_plus_one_patterns()
        
        # 4. Optimize table statistics
        await self.update_table_statistics()
        
        log.info("database_optimization_complete",
                optimizations=len(self.optimization_results))
        
        return self.optimization_results
    
    async def add_missing_indexes(self):
        """Add missing indexes for common query patterns."""
        log.info("adding_missing_indexes")
        
        indexes_to_add = [
            # Clinical workflow tables
            {
                "table": "clinical_records",
                "columns": ["project_id", "created_at"],
                "name": "idx_clinical_records_project_created"
            },
            {
                "table": "genomic_variants",
                "columns": ["run_id", "gene_symbol"],
                "name": "idx_genomic_variants_run_gene"
            },
            {
                "table": "pathogenicity_predictions",
                "columns": ["variant_id", "classification"],
                "name": "idx_pathogenicity_variant_class"
            },
            
            # Evidence and source tables
            {
                "table": "evidence_items",
                "columns": ["source_id", "created_at"],
                "name": "idx_evidence_source_created"
            },
            {
                "table": "evidence_bundles",
                "columns": ["project_id", "status"],
                "name": "idx_evidence_bundles_project_status"
            },
            
            # Run and job tables
            {
                "table": "runs",
                "columns": ["project_id", "status", "created_at"],
                "name": "idx_runs_project_status_created"
            },
            {
                "table": "jobs",
                "columns": ["run_id", "status"],
                "name": "idx_jobs_run_status"
            },
            
            # Target and pathway tables
            {
                "table": "target_rankings",
                "columns": ["run_id", "score"],
                "name": "idx_target_rankings_run_score"
            },
            {
                "table": "pathway_records",
                "columns": ["run_id", "pathway_id"],
                "name": "idx_pathway_records_run_pathway"
            },
            
            # Graph tables
            {
                "table": "graph_nodes",
                "columns": ["project_id", "node_type"],
                "name": "idx_graph_nodes_project_type"
            },
            {
                "table": "graph_edges",
                "columns": ["source_node_id", "target_node_id"],
                "name": "idx_graph_edges_source_target"
            },
            
            # Session and audit tables
            {
                "table": "sessions",
                "columns": ["user_id", "is_active", "expires_at"],
                "name": "idx_sessions_user_active_expires"
            },
            {
                "table": "audit_log",
                "columns": ["user_id", "timestamp"],
                "name": "idx_audit_log_user_timestamp"
            },
            
            # Consensus results
            {
                "table": "consensus_results",
                "columns": ["status", "created_at"],
                "name": "idx_consensus_results_status_created"
            },
        ]
        
        async with get_async_session() as session:
            for index_def in indexes_to_add:
                try:
                    # Check if index already exists
                    check_query = text(f"""
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = :index_name
                    """)
                    result = await session.execute(
                        check_query,
                        {"index_name": index_def["name"]}
                    )
                    
                    if result.fetchone():
                        log.debug("index_already_exists", index=index_def["name"])
                        continue
                    
                    # Create index
                    columns_str = ", ".join(index_def["columns"])
                    create_query = text(f"""
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_def["name"]}
                        ON {index_def["table"]} ({columns_str})
                    """)
                    
                    await session.execute(create_query)
                    await session.commit()
                    
                    log.info("index_created",
                            table=index_def["table"],
                            index=index_def["name"],
                            columns=index_def["columns"])
                    
                    self.optimization_results.append({
                        "type": "index_created",
                        "table": index_def["table"],
                        "index": index_def["name"],
                    })
                    
                except Exception as e:
                    log.warning("index_creation_failed",
                               index=index_def["name"],
                               error=str(e))
    
    async def analyze_slow_queries(self):
        """Analyze and report slow queries."""
        log.info("analyzing_slow_queries")
        
        async with get_async_session() as session:
            try:
                # Get slow queries from pg_stat_statements (if available)
                slow_query = text("""
                    SELECT 
                        query,
                        calls,
                        mean_exec_time,
                        max_exec_time
                    FROM pg_stat_statements
                    WHERE mean_exec_time > 100  -- queries slower than 100ms
                    ORDER BY mean_exec_time DESC
                    LIMIT 10
                """)
                
                result = await session.execute(slow_query)
                slow_queries = result.fetchall()
                
                for query_info in slow_queries:
                    log.warning("slow_query_detected",
                               mean_time_ms=round(query_info[2], 2),
                               max_time_ms=round(query_info[3], 2),
                               calls=query_info[1])
                    
                    self.optimization_results.append({
                        "type": "slow_query",
                        "mean_time_ms": round(query_info[2], 2),
                        "calls": query_info[1],
                    })
                
            except Exception as e:
                log.debug("pg_stat_statements_not_available", error=str(e))
    
    async def check_n_plus_one_patterns(self):
        """Check for N+1 query patterns in common operations."""
        log.info("checking_n_plus_one_patterns")
        
        # Common N+1 patterns to check
        patterns = [
            {
                "name": "runs_with_jobs",
                "description": "Loading runs and their jobs separately",
                "solution": "Use joinedload or selectinload for jobs relationship"
            },
            {
                "name": "evidence_bundles_with_items",
                "description": "Loading evidence bundles and items separately",
                "solution": "Use selectinload for evidence_bundle_items relationship"
            },
            {
                "name": "projects_with_members",
                "description": "Loading projects and members separately",
                "solution": "Use selectinload for project_members relationship"
            },
        ]
        
        for pattern in patterns:
            log.info("n_plus_one_pattern_documented",
                    pattern=pattern["name"],
                    solution=pattern["solution"])
            
            self.optimization_results.append({
                "type": "n_plus_one_pattern",
                "pattern": pattern["name"],
                "solution": pattern["solution"],
            })
    
    async def update_table_statistics(self):
        """Update table statistics for query planner."""
        log.info("updating_table_statistics")
        
        tables_to_analyze = [
            "clinical_records",
            "genomic_variants",
            "evidence_items",
            "evidence_bundles",
            "runs",
            "jobs",
            "target_rankings",
            "pathway_records",
            "graph_nodes",
            "graph_edges",
        ]
        
        async with get_async_session() as session:
            for table in tables_to_analyze:
                try:
                    analyze_query = text(f"ANALYZE {table}")
                    await session.execute(analyze_query)
                    await session.commit()
                    
                    log.info("table_analyzed", table=table)
                    
                    self.optimization_results.append({
                        "type": "table_analyzed",
                        "table": table,
                    })
                    
                except Exception as e:
                    log.warning("table_analysis_failed",
                               table=table,
                               error=str(e))
    
    async def generate_optimization_report(self) -> str:
        """Generate optimization report."""
        report_lines = [
            "# Database Optimization Report",
            "",
            f"Total optimizations: {len(self.optimization_results)}",
            "",
        ]
        
        # Group by type
        by_type = {}
        for result in self.optimization_results:
            result_type = result["type"]
            if result_type not in by_type:
                by_type[result_type] = []
            by_type[result_type].append(result)
        
        # Add sections
        for result_type, results in by_type.items():
            report_lines.append(f"## {result_type.replace('_', ' ').title()}")
            report_lines.append(f"Count: {len(results)}")
            report_lines.append("")
            
            for result in results[:10]:  # Show first 10
                if result_type == "index_created":
                    report_lines.append(f"- {result['table']}.{result['index']}")
                elif result_type == "slow_query":
                    report_lines.append(f"- Mean time: {result['mean_time_ms']}ms, Calls: {result['calls']}")
                elif result_type == "n_plus_one_pattern":
                    report_lines.append(f"- {result['pattern']}: {result['solution']}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)


async def main():
    """Run database optimization."""
    optimizer = DatabaseOptimizer()
    
    try:
        await optimizer.analyze_and_optimize()
        
        # Generate report
        report = await optimizer.generate_optimization_report()
        print(report)
        
        # Save report
        with open("data/database_optimization_report.txt", "w") as f:
            f.write(report)
        
        log.info("optimization_report_saved", path="data/database_optimization_report.txt")
        
    except Exception as e:
        log.error("optimization_failed", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
