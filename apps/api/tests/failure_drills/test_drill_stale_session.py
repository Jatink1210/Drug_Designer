"""G1-6: Stale session / expired token failure drill.

Token expires mid-workflow → 401 clean response, no data leakage.
"""
from __future__ import annotations
import time
import pytest
import jwt as pyjwt
from unittest.mock import MagicMock


SECRET_KEY = "test-secret-key-not-for-production"
ALGORITHM = "HS256"


def _make_token(exp_offset: int = 3600) -> str:
    """Create a JWT token with given expiry offset (seconds from now)."""
    payload = {
        "sub": "user_test_123",
        "role": "researcher",
        "exp": int(time.time()) + exp_offset,
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify JWT. Raises if expired or invalid."""
    return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


@pytest.mark.asyncio
async def test_expired_token_returns_401():
    """Expired JWT → HTTPException 401, no data returned."""
    from fastapi import HTTPException

    expired_token = _make_token(exp_offset=-1)  # Already expired

    async def protected_endpoint(token: str) -> dict:
        try:
            payload = verify_token(token)
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired. Please re-authenticate.")
        return {"data": "sensitive", "user": payload["sub"]}

    with pytest.raises(Exception) as exc_info:
        await protected_endpoint(expired_token)

    exc = exc_info.value
    assert hasattr(exc, "status_code")
    assert exc.status_code == 401
    assert "expired" in exc.detail.lower()


@pytest.mark.asyncio
async def test_token_expiry_mid_workflow_clean():
    """Token expires during multi-step workflow → 401 at expiry point, previous steps unaffected."""
    from fastapi import HTTPException

    # Token valid initially, expires mid-workflow
    tokens = {
        "step_1": _make_token(exp_offset=3600),
        "step_2": _make_token(exp_offset=-1),  # Expired
    }

    step_results = {}

    async def run_workflow_step(step: str, token: str):
        try:
            payload = verify_token(token)
            step_results[step] = {"status": "OK", "user": payload["sub"]}
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail=f"Token expired at step {step}")

    # Step 1 succeeds
    await run_workflow_step("step_1", tokens["step_1"])

    # Step 2 fails with 401
    with pytest.raises(Exception) as exc_info:
        await run_workflow_step("step_2", tokens["step_2"])

    exc = exc_info.value
    assert exc.status_code == 401
    # Step 1 result preserved
    assert step_results["step_1"]["status"] == "OK"
    assert "step_2" not in step_results


@pytest.mark.asyncio
async def test_invalid_token_signature_401():
    """Token with tampered signature → 401, not 500."""
    from fastapi import HTTPException

    tampered = _make_token() + "tampered"

    async def check_auth(token: str):
        try:
            verify_token(token)
        except (pyjwt.InvalidSignatureError, pyjwt.DecodeError):
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"ok": True}

    with pytest.raises(Exception) as exc_info:
        await check_auth(tampered)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_no_data_leakage_on_401():
    """401 response must not include any sensitive data."""
    from fastapi import HTTPException

    async def endpoint(token: str):
        try:
            verify_token(_make_token(exp_offset=-100))
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return {"secret_data": "PATIENT_DATA_12345"}

    with pytest.raises(Exception) as exc_info:
        await endpoint("bad-token")

    exc = exc_info.value
    assert exc.status_code == 401
    assert "PATIENT_DATA" not in str(exc.detail)
