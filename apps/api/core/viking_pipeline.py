import asyncio
import uuid
import logging
from typing import Dict, Any, Callable, List

logger = logging.getLogger(__name__)

class VikingTask:
    def __init__(self, name: str, func: Callable, depends_on: List[str] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.func = func
        self.depends_on = depends_on or []
        self.status = "pending"
        self.result = None

class VikingPipeline:
    """
    OpenViking Integration: Directed Acyclic Graph (DAG) executor for 
    scientific workflows (e.g., Target Identification or SynthArena runs).
    Ensures reproducibility and proper dependency mapping.
    """
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.tasks: Dict[str, VikingTask] = {}
        self.results: Dict[str, Any] = {}
        logger.info(f"Initialized OpenViking Workflow DAG: {pipeline_id}")

    def add_task(self, name: str, func: Callable, depends_on: List[str] = None):
        self.tasks[name] = VikingTask(name, func, depends_on)

    async def execute(self) -> Dict[str, Any]:
        """
        Naively executes tasks in order, waiting for dependencies.
        (A true DAG runner would execute independent branches concurrently).
        """
        logger.info(f"Starting Viking Pipeline {self.pipeline_id} with {len(self.tasks)} stages")
        
        # Simple sequential execution respecting the order added (for demo)
        for name, task in self.tasks.items():
            task.status = "running"
            logger.info(f"  [Viking] Running node: {name}")
            
            # Prepare kwargs from dependencies
            kwargs = {dep: self.results[dep] for dep in task.depends_on if dep in self.results}
            
            # Execute
            try:
                if asyncio.iscoroutinefunction(task.func):
                    res = await task.func(**kwargs)
                else:
                    res = task.func(**kwargs)
                
                self.results[name] = res
                task.status = "success"
                task.result = res
            except Exception as e:
                task.status = "failed"
                logger.error(f"  [Viking] Task {name} failed: {e}")
                return {"status": "failed", "failed_at": name, "error": str(e)}
        
        return {"status": "success", "results": self.results}
