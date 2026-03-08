from core.models import AppConfig
from core.provider_service import (
    discover_provider_models,
    get_provider_health,
    provider_key_from_label,
    provider_label_from_key,
    resolve_provider_base_url,
    test_settings_connection as run_settings_connection_test,
)


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_provider_label_roundtrip():
    label = provider_label_from_key("ollama")
    assert label == "Ollama (yerel)"
    assert provider_key_from_label(label) == "ollama"


def test_resolve_provider_base_url_appends_v1_when_needed():
    assert resolve_provider_base_url("openai", "https://api.openai.com") == "https://api.openai.com/v1"
    assert resolve_provider_base_url("custom", "http://localhost:8000") == "http://localhost:8000/v1"
    assert resolve_provider_base_url("gemini", "https://example.com/openai") == "https://example.com/openai"


def test_get_provider_health_returns_disabled_for_none():
    config = AppConfig(ai_provider="none")
    result = get_provider_health(config)

    assert result == {"status": "disabled", "message": "\u25cf Provider yok"}


def test_discover_provider_models_for_ollama(monkeypatch):
    def fake_get(url: str, timeout: float):
        assert url == "http://localhost:11434/api/tags"
        assert timeout == 5.0
        return _Response(200, {"models": [{"name": "llama3.2"}, {"name": "qwen2.5"}]})

    monkeypatch.setattr("core.provider_service.httpx.get", fake_get)

    models = discover_provider_models("ollama", "http://localhost:11434/v1")

    assert models == ["llama3.2", "qwen2.5"]


def test_test_settings_connection_formats_message(monkeypatch):
    def fake_post(url: str, data: dict, timeout: float):
        assert url == "https://demo-store.myikas.com/api/admin/oauth/token"
        assert data["client_id"] == "client-id"
        assert data["client_secret"] == "client-secret"
        assert timeout == 10.0
        return _Response(200, {})

    monkeypatch.setattr("core.provider_service.httpx.post", fake_post)

    result = run_settings_connection_test(
        {
            "store_name": "demo-store",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "ai_provider": "openai",
            "ai_api_key": "sk-test",
        }
    )

    assert result["ok"] is True
    assert result["ikas_ok"] is True
    assert "ikas: OK" in result["message"]
    assert "AI provider: openai" in result["message"]
