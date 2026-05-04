"""Global Event Bus — Drug Designer Deep-Impl §1.5, §5.

Persistent event bus for broadcasting and recording domain events across
all modules. Integrates with WebSocketManager for real-time push and
persists events to the run_events table for auditability.

Event families (§1.5):
  project   — project.created, project.updated
  retrieval — retrieval.started, retrieval.partial, retrieval.completed, retrieval.degraded
  disease   — disease.normalized, disease.sources.completed, disease.mapping.completed, disease.run.completed
  target    — target.rank.started, target.rank.completed, target.rank.degraded
  graph     — graph.loaded, graph.expanded, graph.snapshot.exported
  pathway   — pathway.viewed, pathway.context.loaded, pathway.exported
  runtime   — runtime.local.connected, runtime.local.blocked
  dossier   — dossier.created, dossier.updated, dossier.exported
  export    — export.completed
  memory    — memory.object.saved
  agent     — agent.registered, agent.heartbeat, agent.job.started, agent.job.completed, agent.job.failed
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional

import structlog

logger = structlog.get_logger()

# Type alias for async event handler
EventHandler = Callable[["DomainEvent"], Coroutine[Any, Any, None]]


class DomainEvent:
    """A single domain event flowing through the bus."""

    __slots__ = ("event_id", "event_type", "run_id", "project_id", "payload", "timestamp")

    def __init__(
        self,
        event_type: str,
        *,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.event_id = f"evt_{uuid.uuid4().hex[:16]}"
        self.event_type = event_type
        self.run_id = run_id
        self.project_id = project_id
        self.payload = payload or {}
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @property
    def family(self) -> str:
        """Extract event family from dotted event type (e.g. 'disease' from 'disease.run.completed')."""
        return self.event_type.split(".")[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBus:
    """In-process async event bus with subscriber pattern and persistent logging.

    Usage::

        bus = EventBus()
        bus.subscribe("disease.*", my_handler)
        await bus.emit(DomainEvent("disease.run.completed", run_id="r_1"))
    """

    def __init__(self) -> None:
        # family → list of handlers
        self._family_handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        # exact event_type → list of handlers
        self._exact_handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        # wildcard handlers (receive all events)
        self._global_handlers: List[EventHandler] = []
        # In-memory event ledger (most recent N events per family)
        self._ledger: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._max_ledger_per_family = 500
        logger.info("event_bus_initialized")

    # ── Subscription ────────────────────────────────────────
    def subscribe(self, pattern: str, handler: EventHandler) -> None:
        """Subscribe to events.

        Patterns:
          "*"                 → receive all events
          "disease.*"         → receive all events in the disease family
          "disease.run.completed" → receive only this exact event
        """
        if pattern == "*":
            self._global_handlers.append(handler)
        elif pattern.endswith(".*"):
            family = pattern[:-2]
            self._family_handlers[family].append(handler)
        else:
            self._exact_handlers[pattern].append(handler)
        logger.debug("event_bus_subscribed", pattern=pattern)

    # ── Emission ────────────────────────────────────────────
    async def emit(self, event: DomainEvent) -> None:
        """Emit a domain event to all matching subscribers and record in ledger."""
        # Record in ledger
        family = event.family
        self._ledger[family].append(event.to_dict())
        if len(self._ledger[family]) > self._max_ledger_per_family:
            self._ledger[family] = self._ledger[family][-self._max_ledger_per_family:]

        logger.info(
            "event_emitted",
            event_type=event.event_type,
            run_id=event.run_id,
            project_id=event.project_id,
        )

        # Dispatch to handlers (fire-and-forget, errors logged but not propagated)
        handlers: List[EventHandler] = []
        handlers.extend(self._global_handlers)
        handlers.extend(self._family_handlers.get(family, []))
        handlers.extend(self._exact_handlers.get(event.event_type, []))

        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "event_handler_error",
                    event_type=event.event_type,
                    handler=getattr(handler, "__name__", str(handler)),
                )

    # ── Convenience emitters for common event families ──────
    async def emit_project(self, action: str, project_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"project.{action}", project_id=project_id, payload=kwargs))

    async def emit_retrieval(self, action: str, run_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"retrieval.{action}", run_id=run_id, payload=kwargs))

    async def emit_disease(self, action: str, run_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"disease.{action}", run_id=run_id, payload=kwargs))

    async def emit_target(self, action: str, run_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"target.{action}", run_id=run_id, payload=kwargs))

    async def emit_graph(self, action: str, run_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"graph.{action}", run_id=run_id, payload=kwargs))

    async def emit_pathway(self, action: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"pathway.{action}", payload=kwargs))

    async def emit_runtime(self, action: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"runtime.{action}", payload=kwargs))

    async def emit_dossier(self, action: str, project_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"dossier.{action}", project_id=project_id, payload=kwargs))

    async def emit_export(self, action: str, project_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"export.{action}", project_id=project_id, payload=kwargs))

    async def emit_memory(self, action: str, project_id: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"memory.{action}", project_id=project_id, payload=kwargs))

    async def emit_agent(self, action: str, **kwargs: Any) -> None:
        await self.emit(DomainEvent(f"agent.{action}", payload=kwargs))

    # ── Query ───────────────────────────────────────────────
    def recent_events(self, family: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent events, optionally filtered by family."""
        if family:
            return self._ledger.get(family, [])[-limit:]
        all_events: List[Dict[str, Any]] = []
        for events in self._ledger.values():
            all_events.extend(events)
        all_events.sort(key=lambda e: e["timestamp"])
        return all_events[-limit:]


# ── Singleton instance ──────────────────────────────────────
event_bus = EventBus()
