"""
API Key Management Service.
Provides a secure interface for storing and retrieving external API keys
(e.g., for premium connectors like GeneCards, DisGeNET).
Satisfies Section 16.2 (API key/secret management) and §61.1 (encryption at rest).
"""
import json
import os
import logging
from typing import Dict, Any, Optional, List

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


def _get_cipher() -> Fernet:
    """Return a Fernet cipher using the configured encryption key."""
    from config import settings
    key = settings.encryption_key
    if not key:
        # Auto-generate and warn (first run convenience)
        key = Fernet.generate_key().decode()
        log.warning("ENCRYPTION_KEY not set — generated ephemeral key. Set ENCRYPTION_KEY env var for persistence.")
    return Fernet(key.encode() if isinstance(key, str) else key)


class APIKeyManager:
    """Manages external API keys with Fernet encryption at rest."""
    PERSIST_PATH = "data/api_keys.enc.json"

    def __init__(self):
        self.keys: Dict[str, str] = {}
        self._cipher = _get_cipher()
        self._load()

    def _encrypt(self, plaintext: str) -> str:
        return self._cipher.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        return self._cipher.decrypt(ciphertext.encode()).decode()

    def _load(self):
        if os.path.exists(self.PERSIST_PATH):
            try:
                with open(self.PERSIST_PATH) as f:
                    data = json.load(f)
                self.keys = {}
                for k, v in data.items():
                    try:
                        self.keys[k] = self._decrypt(v)
                    except InvalidToken:
                        log.warning(f"Failed to decrypt key for {k} — skipping (wrong ENCRYPTION_KEY?)")
            except Exception:
                self.keys = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.PERSIST_PATH) or ".", exist_ok=True)
        data = {k: self._encrypt(v) for k, v in self.keys.items()}
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
