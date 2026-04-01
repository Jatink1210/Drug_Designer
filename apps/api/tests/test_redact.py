"""Tests for the _redact() secret-scrubbing utility in job_logger."""

from services.job_logger import _redact


def test_redact_flat_dict_api_key():
    result = _redact({"api_key": "sk-abc123", "name": "test"})
    assert result["api_key"] == "***REDACTED***"
    assert result["name"] == "test"


def test_redact_flat_dict_all_secret_keys():
    data = {
        "api_key": "val1",
        "secret": "val2",
        "token": "val3",
        "password": "val4",
        "credential": "val5",
        "authorization": "val6",
    }
    result = _redact(data)
    for key in data:
        assert result[key] == "***REDACTED***", f"Key '{key}' was not redacted"


def test_redact_nested_dict():
    data = {"outer": {"api_key": "hidden", "safe": "visible"}}
    result = _redact(data)
    assert result["outer"]["api_key"] == "***REDACTED***"
    assert result["outer"]["safe"] == "visible"


def test_redact_list_of_dicts():
    data = [{"token": "abc"}, {"name": "ok"}]
    result = _redact(data)
    assert result[0]["token"] == "***REDACTED***"
    assert result[1]["name"] == "ok"


def test_redact_depth_limit():
    """Objects deeper than 10 levels are returned as-is."""
    deep = {"api_key": "should_survive"}
    result = _redact(deep, depth=11)
    assert result["api_key"] == "should_survive"


def test_redact_safe_keys_untouched():
    data = {"name": "aspirin", "query": "EGFR", "score": 0.95}
    result = _redact(data)
    assert result == data


def test_redact_string_matching_secret_pattern():
    """Strings that themselves match the secret-key regex get redacted."""
    result = _redact("my_api_key_value")
    assert result == "***REDACTED***"


def test_redact_non_secret_string_passes():
    result = _redact("just a normal string")
    assert result == "just a normal string"


def test_redact_mixed_types():
    data = {"count": 42, "ratio": 3.14, "empty": None, "password": "oops"}
    result = _redact(data)
    assert result["count"] == 42
    assert result["ratio"] == 3.14
    assert result["empty"] is None
    assert result["password"] == "***REDACTED***"


def test_redact_empty_dict():
    assert _redact({}) == {}


def test_redact_empty_list():
    assert _redact([]) == []


def test_redact_case_insensitive():
    data = {"API_KEY": "a", "Secret": "b", "TOKEN": "c", "Password": "d"}
    result = _redact(data)
    for key in data:
        assert result[key] == "***REDACTED***", f"Key '{key}' was not redacted"
