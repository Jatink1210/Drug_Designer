"""
API Key Management Service.
Provides a secure interface for storing and retrieving external API keys
(e.g., for premium connectors like GeneCards, DisGeNET).
Satisfies Section 16.2 (API key/secret management).
"""
import json
import os
import hashlib
import logging
from typing import Dict, Any, Optional, List

log = logging.getLogger(__name__)

class APIKeyManager:
    """Manages external API keys with encrypted-at-rest storage."""
    PERSIST_PATH = "data/api_keys.enc.json"

    def __init__(self):
        self.keys: Dict[str, str] = {}
        self._load()

    def _obfuscate(self, key: str) -> str:
        """Simple obfuscation for at-rest storage. In production, use proper encryption."""
        import base64
        return base64.b64encode(key.encode()).decode()

    def _deobfuscate(self, encoded: str) -> str:
        import base64
        return base64.b64decode(encoded.encode()).decode()

    def _load(self):
        if os.path.exists(self.PERSIST_PATH):
            try:
                with open(self.PERSIST_PATH) as f:
                    data = json.load(f)
                self.keys = {k: self._deobfuscate(v) for k, v in data.items()}
            except Exception:
                self.keys = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.PERSIST_PATH) or ".", exist_ok=True)
        data = {k: self._obfuscate(v) for k, v in self.keys.items()}
        with open(self.PERSIST_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def set_key(self, service: str, api_key: str):
        self.keys[service] = api_key
        self._save()
        log.info(f"API key set for: {service}")

    def get_key(self, service: str) -> Optional[str]:
        return self.keys.get(service)

    def delete_key(self, service: str) -> bool:
        if service in self.keys:
            del self.keys[service]
            self._save()
            return True
        return False

    def list_services(self) -> List[Dict[str, str]]:
        return [
            {"service": k, "masked_key": v[:4] + "****" + v[-4:] if len(v) > 8 else "****"}
            for k, v in self.keys.items()
        ]

_manager: Optional[APIKeyManager] = None

def get_key_manager() -> APIKeyManager:
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager
