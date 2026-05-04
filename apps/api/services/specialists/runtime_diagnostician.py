"""G-8: Runtime Diagnostician specialist.

Local agent health monitor: detects hardware capabilities, resource pressure,
and reports actionable diagnostics.
"""

from __future__ import annotations

import platform
import sys
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class RuntimeDiagnosticianSpecialist:
    """Specialist: audits local agent runtime, reports hardware capabilities.

    Surfaces:
    - CPU / GPU / RAM availability
    - Python env info
    - Model availability checks
    - Worker queue health (Redis)
    """

    ROLE_ID = "runtime_diagnostician"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("runtime_diagnostician_initialized")

    async def diagnose(
        self,
        include_gpu: bool = True,
        include_redis: bool = True,
        include_models: bool = True,
    ) -> Dict[str, Any]:
        """Run full runtime diagnostic.

        Returns:
            Dict with: hardware, python_env, model_status, redis_health, recommendations
        """
        hardware = self._probe_hardware(include_gpu)
        python_env = self._probe_python()
        model_status = await self._probe_models() if include_models else {}
        redis_health = await self._probe_redis() if include_redis else {}

        recommendations = self._generate_recommendations(hardware, model_status, redis_health)

        return {
            "status": "ok",
            "hardware": hardware,
            "python_env": python_env,
            "model_status": model_status,
            "redis_health": redis_health,
            "recommendations": recommendations,
            "specialist": self.ROLE_ID,
        }

    def _probe_hardware(self, include_gpu: bool) -> Dict[str, Any]:
        hw: Dict[str, Any] = {
            "platform": platform.platform(),
            "cpu_count": None,
            "cpu_count_logical": None,
            "ram_total_gb": None,
            "ram_available_gb": None,
            "gpus": [],
        }
        try:
            import psutil  # type: ignore

            hw["cpu_count"] = psutil.cpu_count(logical=False)
            hw["cpu_count_logical"] = psutil.cpu_count(logical=True)
            vm = psutil.virtual_memory()
            hw["ram_total_gb"] = round(vm.total / 1e9, 2)
            hw["ram_available_gb"] = round(vm.available / 1e9, 2)
        except ImportError:
            pass

        if include_gpu:
            try:
                import torch  # type: ignore

                if torch.cuda.is_available():
                    hw["gpus"] = [
                        {
                            "index": i,
                            "name": torch.cuda.get_device_name(i),
                            "total_mem_gb": round(
                                torch.cuda.get_device_properties(i).total_memory / 1e9, 2
                            ),
                        }
                        for i in range(torch.cuda.device_count())
                    ]
            except ImportError:
                pass

        return hw

    def _probe_python(self) -> Dict[str, str]:
        return {
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform,
        }

    async def _probe_models(self) -> Dict[str, str]:
        statuses: Dict[str, str] = {}
        for model_name, import_path in [
            ("scibert", "services.ml.scibert_model"),
            ("gat", "services.ml.gat_model"),
            ("rgcn", "services.ml.rgcn_model"),
            ("ppo_optimizer", "services.ml.ppo_optimizer"),
        ]:
            try:
                __import__(import_path)
                statuses[model_name] = "available"
            except ImportError:
                statuses[model_name] = "not_installed"
            except Exception as exc:
                statuses[model_name] = f"error: {exc}"
        return statuses

    async def _probe_redis(self) -> Dict[str, Any]:
        health: Dict[str, Any] = {"status": "unknown"}
        try:
            from core.redis_client import get_redis_client

            redis = await get_redis_client()
            pong = await redis.ping()
            health["status"] = "healthy" if pong else "unhealthy"
        except Exception as exc:
            health["status"] = "unreachable"
            health["error"] = str(exc)
        return health

    def _generate_recommendations(
        self,
        hardware: Dict[str, Any],
        model_status: Dict[str, str],
        redis_health: Dict[str, Any],
    ) -> List[str]:
        recs: List[str] = []
        ram = hardware.get("ram_available_gb") or 0
        if isinstance(ram, (int, float)) and ram < 4:
            recs.append("Low available RAM (<4 GB). Consider closing background processes.")
        if not hardware.get("gpus"):
            recs.append("No GPU detected. PyTorch models will run on CPU (slower).")
        missing_models = [k for k, v in model_status.items() if v != "available"]
        if missing_models:
            recs.append(
                f"Models not available: {', '.join(missing_models)}. "
                "Run: pip install -r requirements.txt"
            )
        if redis_health.get("status") not in ("healthy", "unknown"):
            recs.append("Redis is unreachable. Worker queue will not function.")
        return recs
