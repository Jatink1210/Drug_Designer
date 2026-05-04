"""Audit logging helper — writes structured entries to the audit_log table."""

import hashlib
import csv
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from io import StringIO

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_tables import AuditLog


async def log_audit(
    session: AsyncSession,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Log audit event with IP and user agent hashing for privacy."""
    ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else ""
    ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16] if user_agent else ""
    
    record = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_hash,
        user_agent=ua_hash,
    )
    session.add(record)
    await session.flush()


async def log_clinical_data_access(
    session: AsyncSession,
    user_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> None:
    """
    Log clinical data access for HIPAA compliance.
    
    All PHI access must be logged with complete audit trail.
    """
    details = {
        'phi_access': True,
        'compliance': 'HIPAA',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    
    await log_audit(
        session=session,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


async def query_audit_logs(
    session: AsyncSession,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    phi_access_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> Dict[str, Any]:
    """
    Query audit logs with filters, pagination, and sorting.
    
    Returns dict with 'logs' list and 'total' count for pagination.
    """
    # Build query with filters
    conditions = []
    
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if action:
        conditions.append(AuditLog.action == action)
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    if phi_access_only:
        conditions.append(
            AuditLog.details.op('->>')('phi_access') == 'true'
        )
    
    # Count total matching records
    count_query = select(func.count()).select_from(AuditLog)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    result = await session.execute(count_query)
    total = result.scalar() or 0
    
    # Build main query with sorting
    query = select(AuditLog)
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply sorting
    sort_column = getattr(AuditLog, sort_by, AuditLog.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    return {
        'logs': [
            {
                'id': log.id,
                'user_id': log.user_id,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'details': log.details,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        'total': total,
        'limit': limit,
        'offset': offset,
    }


async def get_audit_statistics(
    session: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> Dict[str, Any]:
    """
    Get audit log statistics for monitoring and compliance.
    """
    # Build base conditions
    conditions = []
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    
    # Total events
    count_query = select(func.count()).select_from(AuditLog)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    result = await session.execute(count_query)
    total_events = result.scalar() or 0
    
    # Events by action
    action_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.action)
    if conditions:
        action_query = action_query.where(and_(*conditions))
    
    result = await session.execute(action_query)
    events_by_action = {row[0]: row[1] for row in result.all()}
    
    # Events by resource type
    resource_query = select(
        AuditLog.resource_type,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.resource_type)
    if conditions:
        resource_query = resource_query.where(and_(*conditions))
    
    result = await session.execute(resource_query)
    events_by_resource_type = {row[0]: row[1] for row in result.all()}
    
    # Events by user
    user_query = select(
        AuditLog.user_id,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.user_id)
    if conditions:
        user_query = user_query.where(and_(*conditions))
    
    result = await session.execute(user_query)
    events_by_user = {row[0]: row[1] for row in result.all()}
    
    # PHI access count
    phi_query = select(func.count()).select_from(AuditLog)
    phi_where_conditions = conditions.copy()
    phi_where_conditions.append(
        AuditLog.details.op('->>')('phi_access') == 'true'
    )
    phi_query = phi_query.where(and_(*phi_where_conditions))
    result = await session.execute(phi_query)
    phi_access_count = result.scalar() or 0
    
    return {
        'total_events': total_events,
        'events_by_action': events_by_action,
        'events_by_resource_type': events_by_resource_type,
        'events_by_user': events_by_user,
        'phi_access_count': phi_access_count,
        'period': {
            'start': start_date.isoformat() if start_date else None,
            'end': end_date.isoformat() if end_date else None,
        }
    }


async def export_audit_logs(
    session: AsyncSession,
    format: str = "csv",
    user_id: str | None = None,
    resource_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    phi_access_only: bool = False,
) -> str:
    """
    Export audit logs in CSV or JSON format for compliance reporting.
    
    Returns the exported data as a string.
    """
    # Query all matching logs (no pagination for export)
    result = await query_audit_logs(
        session=session,
        user_id=user_id,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        phi_access_only=phi_access_only,
        limit=100000,  # Large limit for export
        offset=0
    )
    
    logs = result['logs']
    
    if format.lower() == "csv":
        output = StringIO()
        if logs:
            fieldnames = ['id', 'user_id', 'action', 'resource_type', 'resource_id', 
                         'ip_address', 'user_agent', 'created_at', 'details']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for log in logs:
                row = {k: v for k, v in log.items() if k in fieldnames}
                row['details'] = json.dumps(row.get('details', {}))
                writer.writerow(row)
        
        return output.getvalue()
    
    elif format.lower() == "json":
        return json.dumps({
            'export_date': datetime.now(timezone.utc).isoformat(),
            'total_records': len(logs),
            'logs': logs
        }, indent=2)
    
    else:
        raise ValueError(f"Unsupported export format: {format}")


async def cleanup_old_audit_logs(
    session: AsyncSession,
    retention_days: int = 90
) -> int:
    """
    Clean up audit logs older than retention period.
    
    Returns the number of deleted records.
    Note: This violates append-only principle - use with caution and only for compliance.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    # Count records to be deleted
    count_query = select(func.count()).select_from(AuditLog).where(
        AuditLog.created_at < cutoff_date
    )
    result = await session.execute(count_query)
    count = result.scalar() or 0
    
    # Delete old records
    delete_query = select(AuditLog).where(AuditLog.created_at < cutoff_date)
    result = await session.execute(delete_query)
    old_logs = result.scalars().all()
    
    for log in old_logs:
        await session.delete(log)
    
    await session.flush()
    
    return count


async def detect_audit_anomalies(
    session: AsyncSession,
    user_id: str | None = None,
    lookback_hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Detect suspicious access patterns in audit logs.
    
    Returns list of detected anomalies with details.
    """
    anomalies = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    
    # Detect excessive access attempts
    conditions = [AuditLog.created_at >= cutoff_date]
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    
    # Count accesses per user
    access_query = select(
        AuditLog.user_id,
        func.count(AuditLog.id).label('count')
    ).where(and_(*conditions)).group_by(AuditLog.user_id)
    
    result = await session.execute(access_query)
    user_access_counts = result.all()
    
    # Flag users with >1000 accesses in lookback period
    for uid, count in user_access_counts:
        if count > 1000:
            anomalies.append({
                'type': 'excessive_access',
                'user_id': uid,
                'count': count,
                'period_hours': lookback_hours,
                'severity': 'high',
                'message': f'User {uid} made {count} accesses in {lookback_hours} hours'
            })
    
    # Detect PHI access outside business hours (example heuristic)
    phi_query = select(AuditLog)
    phi_where_conditions = conditions.copy()
    phi_where_conditions.append(
        AuditLog.details.op('->>')('phi_access') == 'true'
    )
    phi_query = phi_query.where(and_(*phi_where_conditions))
    result = await session.execute(phi_query)
    phi_logs = result.scalars().all()
    
    for log in phi_logs:
        if log.created_at:
            hour = log.created_at.hour
            # Flag access outside 6 AM - 10 PM
            if hour < 6 or hour > 22:
                anomalies.append({
                    'type': 'off_hours_phi_access',
                    'user_id': log.user_id,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'timestamp': log.created_at.isoformat(),
                    'severity': 'medium',
                    'message': f'PHI access at {log.created_at.strftime("%H:%M")} (off-hours)'
                })
    
    return anomalies
