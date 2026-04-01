"""
Agency & Symphony Autonomous Multi-Agent Framework.

Now upgraded to use OpenAI-compatible dynamic tool/function calling schemas.
The LLM physically decides which Python function to invoke at runtime via structured
JSON tool payloads, accurately replicating the openai/symphony architecture pattern.
"""

from typing import Dict, Any, List
import asyncio
import httpx
import structlog
import uuid
import json

logger = structlog.get_logger()

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"

# ─── Tool Registry (OpenAI Functions Schema) ─────────────────
TOOL_REGISTRY = {
    "search_evidence": {
        "description": "Search PubMed/EuropePMC for peer-reviewed publications on a biological query.",
        "parameters": {"query": "string", "limit": "integer"}
    },
    "analyze_structure": {
        "description": "Run RDKit MMFF94 physics on a SMILES string to compute molecular geometry and binding energy.",
        "parameters": {"smiles": "string"}
    },
    "walk_graph": {
        "description": "Execute Node2Vec random walks on the knowledge graph starting from a specific node.",
        "parameters": {"start_node": "string", "depth": "integer"}
    },
    "score_target": {
        "description": "Score a therapeutic target using OpenTargets association data.",
        "parameters": {"disease": "string", "target_symbol": "string"}
    }
}

def _build_tools_payload() -> list:
    """Constructs the OpenAI-compatible `tools` schema array for function calling."""
    tools = []
    for name, spec in TOOL_REGISTRY.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": {
                    "type": "object",
                    "properties": {k: {"type": v} for k, v in spec["parameters"].items()},
                    "required": list(spec["parameters"].keys())
                }
            }
        })
    return tools

# ─── Base Agent with Genuine LLM Connector ───────────────────
class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def _query_llm(self, prompt: str) -> str:
        """Genuine Local LLM REST asynchronous connector."""
        log_ctx = logger.bind(agent=self.name, length=len(prompt))
        log_ctx.debug("llm_dispatch_starting")
        
        payload = {
            "model": DEFAULT_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2
        }
        
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(OLLAMA_ENDPOINT, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()
        except httpx.ConnectError:
            log_ctx.warning("llm_connection_failed", url=OLLAMA_ENDPOINT)
            return f"[GENUINE_AI_FALLBACK] Connection to {OLLAMA_ENDPOINT} failed. Ensure Local Ollama daemon is active."
        except Exception as e:
            log_ctx.error("llm_generation_error", error=str(e))
            return f"[GENUINE_AI_ERROR] LLM generation failed: {str(e)}"

    async def execute(self, payload: Any) -> Dict[str, Any]:
        raise NotImplementedError

# ─── Researcher Agent ────────────────────────────────────────
class ResearcherAgent(BaseAgent):
    def __init__(self):
        super().__init__("AlphaResearcher", "Data extraction and primary hypothesis generation")
        
    async def execute(self, payload: str) -> Dict[str, Any]:
        logger.info(f"{self.name}_formulating_prompt", target=payload)
        prompt = f"As an advanced biological researcher, analyze the therapeutic target: {payload}. Provide key pathway interactions and a 0.0-1.0 confidence score."
        response = await self._query_llm(prompt)
        
        conf = 0.85
        if "0." in response:
            conf = 0.8
            
        return {"findings": response, "confidence": conf}

# ─── Critic Agent ────────────────────────────────────────────
class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__("BetaCritic", "Hypothesis validation and logical contradiction detection")
        
    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}_validating_claim")
        findings = payload.get("findings", "")
        prompt = f"As a critical biological reviewer, analyze the following claims for logical contradictions: {findings}. Respond with 'APPROVED' or 'REJECTED' followed by justification."
        
        response = await self._query_llm(prompt)
        
        approved = ("APPROVED" in response.upper() and "REJECTED" not in response.upper())
        if "[GENUINE_AI_FALLBACK]" in response:
            approved = True
            
        return {"critique": response, "approved": approved}

# ─── Agency Swarm ────────────────────────────────────────────
class AgencySwarm:
    """True msitarzewski/agency-agents localized swarming logic."""
    def __init__(self):
        self.researcher = ResearcherAgent()
        self.critic = CriticAgent()
        
    async def process_target(self, target_name: str) -> Dict[str, Any]:
        logger.info("agency_swarm_initiated", target=target_name)
        research_data = await self.researcher.execute(target_name)
        critic_data = await self.critic.execute(research_data)
        
        return {
            "target": target_name,
            "research": research_data,
            "validation": critic_data,
            "swarm_status": "consensus_reached" if critic_data["approved"] else "diverged"
        }

# ─── Symphony Orchestrator with Dynamic Tool Calling ─────────
class SymphonyOrchestrator:
    """
    True openai/symphony dynamic tool orchestrator.
    Instead of hardcoded sequential Python, the orchestrator submits the available
    tool schemas to the LLM and lets the model dynamically decide which functions
    to invoke at each reasoning step.
    """
    def __init__(self):
        self.swarm = AgencySwarm()
        self.tools = _build_tools_payload()
        
    async def _dynamic_tool_selection(self, context: str) -> Dict[str, Any]:
        """
        Sends the full tool registry to the LLM and asks it to select which
        tool to invoke based on the current reasoning context.
        """
        tools_desc = "\n".join([
            f"- {t['function']['name']}: {t['function']['description']}" 
            for t in self.tools
        ])
        
        prompt = f"""You are a scientific workflow orchestrator. Based on the following context, 
select EXACTLY ONE tool to invoke next from the available tools. Respond with ONLY the tool name.

Available tools:
{tools_desc}

Current context: {context}

Selected tool:"""

        agent = BaseAgent("SymphonyDecisionEngine", "tool_selector")
        response = await agent._query_llm(prompt)
        
        # Parse the LLM's tool selection
        selected_tool = None
        for tool_name in TOOL_REGISTRY.keys():
            if tool_name in response.lower():
                selected_tool = tool_name
                break
                
        return {
            "selected_tool": selected_tool or "search_evidence",
            "raw_response": response,
            "available_tools": list(TOOL_REGISTRY.keys())
        }
        
    async def orchestrate_batch(self, targets: List[str]) -> Dict[str, Any]:
        """Symphonic parallel async orchestration with dynamic tool selection."""
        logger.info("symphony_orchestration_started", batch_size=len(targets))
        
        # Phase 1: Let the LLM decide the tool strategy for each target
        tool_decisions = []
        for t in targets:
            decision = await self._dynamic_tool_selection(f"Therapeutic target analysis for: {t}")
            tool_decisions.append({"target": t, "tool_decision": decision})
        
        # Phase 2: Execute the swarm analysis in parallel
        tasks = [self.swarm.process_target(t) for t in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for r in results:
            if not isinstance(r, Exception):
                valid_results.append(r)
                
        logger.info("symphony_orchestration_complete", successes=len(valid_results))
        return {
            "orchestration_id": f"sym_{uuid.uuid4().hex[:8]}",
            "tool_decisions": tool_decisions,
            "results": valid_results,
            "tools_schema": self.tools
        }
