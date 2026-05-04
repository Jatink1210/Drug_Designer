"""
In-process Job Queue — asyncio-based task scheduling.
Replaces Redis for desktop/workbench mode while maintaining the same interface.
For production, wrap this with a Redis-backed implementation.
"""
import os
import asyncio
import uuid
import time
import logging
from typing import Dict, Any, Callable, Optional, List
from enum import Enum
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str
    name: str
    status: JobStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class AsyncJobQueue:
    """
    In-process job queue using asyncio.
    Provides Redis-equivalent job scheduling and tracking for desktop mode.
    """
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.jobs: Dict[str, Job] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers_started = False
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def _ensure_workers(self):
        if not self._workers_started:
            self._workers_started = True
            for i in range(self.max_concurrent):
                asyncio.create_task(self._worker(f"worker-{i}"))

    async def _worker(self, name: str):
        while True:
            try:
                job_id, coro_fn, args, kwargs = await self._queue.get()
                job = self.jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    self._queue.task_done()
                    continue
                
                job.status = JobStatus.RUNNING
                job.started_at = time.time()
                
                async with self._semaphore:
                    try:
                        result = await coro_fn(*args, **kwargs)
                        job.result = result
                        job.status = JobStatus.COMPLETED
                    except Exception as e:
                        job.error = str(e)
                        job.status = JobStatus.FAILED
                        log.error(f"Job {job_id} failed: {e}")
                    finally:
                        job.completed_at = time.time()
                        job.progress = 1.0
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Worker {name} error: {e}")

    async def submit(self, name: str, coro_fn: Callable, *args, metadata: Optional[Dict] = None, **kwargs) -> str:
        """Submit an async job. Returns the job ID."""
        await self._ensure_workers()
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = Job(id=job_id, name=name, status=JobStatus.QUEUED, created_at=time.time(), metadata=metadata or {})
        self.jobs[job_id] = job
        await self._queue.put((job_id, coro_fn, args, kwargs))
        log.info(f"Job submitted: {job_id} ({name})")
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        jobs = sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]
        return [
            {"id": j.id, "name": j.name, "status": j.status.value, 
             "progress": j.progress, "created_at": j.created_at,
             "started_at": j.started_at, "completed_at": j.completed_at,
             "error": j.error, "metadata": j.metadata}
            for j in jobs
        ]

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            return True
        return False

    def get_stats(self) -> Dict[str, int]:
        stats = {"total": len(self.jobs)}
        for status in JobStatus:
            stats[status.value] = sum(1 for j in self.jobs.values() if j.status == status)
        return stats

# Singleton
_queue = None
_redis_pool = None

class RedisArqQueue:
    """Distributed Redis-backed Job Queue using Arq."""
    def __init__(self, pool):
        self.pool = pool

    async def submit(self, name: str, coro_fn: Callable, *args, metadata: Optional[Dict] = None, **kwargs) -> str:
        # Arq expects the function name as a string, not the callable itself
        func_name = getattr(coro_fn, '__name__', name)
        job = await self.pool.enqueue_job(func_name, *args, **kwargs)
        if hasattr(job, "job_id"):
            log.info(f"Arq job submitted: {job.job_id} ({name})")
            return job.job_id
        return "unknown"

    def get_job(self, job_id: str):
        # Arq job status requires async; for this synchronous adapter, we return a mocked pending state
        # True implementations would use an async endpoint or await the result
        return Job(id=job_id, name="arq_job", status=JobStatus.QUEUED, created_at=time.time())

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return []

    def cancel_job(self, job_id: str) -> bool:
        return False

    def get_stats(self) -> Dict[str, int]:
        return {"total": 0, "queued": 0, "running": 0}

async def get_job_queue():
    """Returns the Redis Arq queue if configured, else the local AsyncJobQueue."""
    global _queue, _redis_pool
    # If production Redis is supplied and not default localhost
    from config import settings
    if "redis://" in settings.redis_url and "localhost" not in settings.redis_url or os.environ.get("FORCE_REDIS"):
        if _redis_pool is None:
            try:
                from arq import create_pool
                from arq.connections import RedisSettings
                import urllib.parse
                url = urllib.parse.urlparse(settings.redis_url)
                redis_settings = RedisSettings(host=url.hostname or "localhost", port=url.port or 6379, database=int((url.path or "/0").strip("/")))
                _redis_pool = await create_pool(redis_settings)
                _queue = RedisArqQueue(_redis_pool)
                log.info("job_queue_initialized_redis_arq")
            except ImportError:
                log.warning("arq not installed, falling back to local queue")
        if _queue:
            return _queue

    # Fallback to Local Desktop Mode
    if _queue is None or isinstance(_queue, RedisArqQueue):
        _queue = AsyncJobQueue()
        log.info("job_queue_initialized_local_asyncio")
    return _queue
