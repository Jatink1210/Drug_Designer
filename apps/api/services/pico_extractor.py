"""PICO Extractor — Extracts Population, Intervention, Comparator, Outcome from text."""

import json
from typing import Any, Dict, Optional
import httpx
import structlog
from config import settings

log = structlog.get_logger()

async def extract_pico_data(text: str) -> Dict[str, Any]:
    """Uses Ollama or OpenAI to extract PICO parameters from abstract/text."""
    if not text or len(text) < 50:
        return {"population": "", "intervention": "", "comparator": "", "outcome": ""}
        
    prompt = f"""
    Analyze the following biomedical text and extract the PICO elements (Population, Intervention, Comparator, Outcome).
    Return ONLY a valid JSON object with these exact keys: "population", "intervention", "comparator", "outcome".
    If any element is missing, return an empty string for that key. Do not include markdown formatting like ```json.
    
    TEXT:
    {text[:2000]}
    """
    
    try:
        if settings.openai_api_key:
            return await _call_openai(prompt)
        elif settings.ollama_host:
            return await _call_ollama(prompt)
    except Exception as e:
        log.error("pico_extraction_failed", error=str(e))
        
    return {"population": "", "intervention": "", "comparator": "", "outcome": ""}

async def _call_ollama(prompt: str) -> Dict[str, Any]:
    url = f"{settings.ollama_host}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data.get("response", "{}"))

async def _call_openai(prompt: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "You are a specialized medical AI that extracts PICO parameters into valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

async def verify_claim(claim: str, evidence_text: str) -> Dict[str, Any]:
    """Tests an extracted claim against raw evidence text using LLMs to score confidence."""
    if not claim or not evidence_text:
        return {"supported": False, "confidence": 0.0, "reasoning": "Missing claim or evidence."}
        
    prompt = f"""
    Evaluate the following CLAIM against the provided EVIDENCE.
    Determine if the CLAIM is supported, contradicted, or not mentioned in the EVIDENCE.
    
    Return ONLY a valid JSON object with:
    - "supported": boolean (true if supported, false otherwise)
    - "confidence": float between 0.0 and 1.0
    - "reasoning": str (brief explanation)
    
    CLAIM: {claim}
    
    EVIDENCE:
    {evidence_text[:3000]}
    """
    
    try:
        if settings.openai_api_key:
            return await _call_openai(prompt)
        elif settings.ollama_host:
            return await _call_ollama(prompt)
    except Exception as e:
        log.error("claim_verification_failed", error=str(e))
        
    return {"supported": False, "confidence": 0.0, "reasoning": "Inference failed."}
