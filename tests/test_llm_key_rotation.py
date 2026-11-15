import pytest
from unittest.mock import MagicMock
from services.llm_engine import LLMEngine


def run_sync(coro):
    """Jalankan coroutine synchronous tanpa butuh asyncio event loop socket."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


def test_get_gemini_keys_single(monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "primary_key_123")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_BACKUP", "")

    keys = LLMEngine.get_gemini_keys()
    assert keys == ["primary_key_123"]


def test_get_gemini_keys_comma_separated(monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "key_a, key_b, key_c")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_BACKUP", "")

    keys = LLMEngine.get_gemini_keys()
    assert keys == ["key_a", "key_b", "key_c"]


def test_get_gemini_keys_with_backup(monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "key_primary")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_BACKUP", "key_backup_1, key_backup_2")

    keys = LLMEngine.get_gemini_keys()
    assert keys == ["key_primary", "key_backup_1", "key_backup_2"]


def test_is_quota_or_rate_limit():
    assert LLMEngine._is_quota_or_rate_limit(Exception("429 RESOURCE_EXHAUSTED")) is True
    assert LLMEngine._is_quota_or_rate_limit(Exception("Quota exceeded for quota metric")) is True
    assert LLMEngine._is_quota_or_rate_limit(Exception("Too Many Requests")) is True
    assert LLMEngine._is_quota_or_rate_limit(Exception("500 Internal Server Error")) is False


def test_is_invalid_key_error():
    assert LLMEngine._is_invalid_key_error(Exception("400 INVALID_ARGUMENT: API key not valid")) is True
    assert LLMEngine._is_invalid_key_error(Exception("401 UNAUTHENTICATED")) is True
    assert LLMEngine._is_invalid_key_error(Exception("Network timeout")) is False


def test_call_gemini_rotates_to_backup_on_429(monkeypatch):
    """
    Ketika key #1 terkena 429 / quota exceeded, engine harus otomatis
    berpindah ke key #2 (backup) dan mengeksekusi request dengan sukses.
    """
    LLMEngine._ACTIVE_GEMINI_KEY_INDEX = 0

    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock_key_1")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_BACKUP", "mock_key_2")

    async def fail_429(**kwargs):
        raise Exception("429 RESOURCE_EXHAUSTED Quota exceeded for quota metric 'Generate Content API'")

    async def success_backup(**kwargs):
        resp = MagicMock()
        resp.text = "Analisis saham berhasil dari backup key"
        return resp

    mock_client_1 = MagicMock()
    mock_client_1.aio.models.generate_content = fail_429

    mock_client_2 = MagicMock()
    mock_client_2.aio.models.generate_content = success_backup

    LLMEngine._gemini_clients["mock_key_1"] = mock_client_1
    LLMEngine._gemini_clients["mock_key_2"] = mock_client_2

    engine = LLMEngine(provider="gemini")
    res = run_sync(engine._call_gemini("Analisis BBCA"))

    assert res == "Analisis saham berhasil dari backup key"
    assert LLMEngine._ACTIVE_GEMINI_KEY_INDEX == 1  # Successfully switched to key #2


def test_call_gemini_skips_invalid_key(monkeypatch):
    """
    Jika salah satu key invalid (400 INVALID_ARGUMENT), engine tidak boleh crash
    dan harus mencoba key berikutnya.
    """
    LLMEngine._ACTIVE_GEMINI_KEY_INDEX = 0

    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "bad_key_400")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_BACKUP", "good_backup_key")

    async def fail_invalid(**kwargs):
        raise Exception("400 INVALID_ARGUMENT: API key not valid")

    async def success_valid(**kwargs):
        resp = MagicMock()
        resp.text = "Sukses dari valid key"
        return resp

    mock_client_1 = MagicMock()
    mock_client_1.aio.models.generate_content = fail_invalid

    mock_client_2 = MagicMock()
    mock_client_2.aio.models.generate_content = success_valid

    LLMEngine._gemini_clients["bad_key_400"] = mock_client_1
    LLMEngine._gemini_clients["good_backup_key"] = mock_client_2

    engine = LLMEngine(provider="gemini")
    res = run_sync(engine._call_gemini("Analisis BBRI"))

    assert res == "Sukses dari valid key"
    assert LLMEngine._ACTIVE_GEMINI_KEY_INDEX == 1
