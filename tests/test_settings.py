import builtins
import importlib

import pytest

import config.settings as settings


REQUIRED_KEYS = [
    "IKAS_STORE_NAME",
    "IKAS_CLIENT_ID",
    "IKAS_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
]


def _clear_required_env(monkeypatch):
    for key in REQUIRED_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_get_config_raises_for_missing_required_env_without_tty(monkeypatch):
    _clear_required_env(monkeypatch)
    monkeypatch.setattr(settings.sys.stdin, "isatty", lambda: False)
    settings.reset_config()

    with pytest.raises(ValueError) as exc:
        settings.get_config()

    assert "Eksik zorunlu ortam degiskenleri" in str(exc.value)


def test_get_config_prompts_for_missing_required_env_with_tty(monkeypatch):
    _clear_required_env(monkeypatch)
    settings.reset_config()

    values = {
        "IKAS_STORE_NAME": "demo-store",
        "IKAS_CLIENT_ID": "client-id",
        "IKAS_CLIENT_SECRET": "client-secret",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }

    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return values["IKAS_STORE_NAME"] if prompt.startswith("IKAS_STORE_NAME") else values["IKAS_CLIENT_ID"]

    def fake_getpass(prompt):
        prompts.append(prompt)
        if prompt.startswith("IKAS_CLIENT_SECRET"):
            return values["IKAS_CLIENT_SECRET"]
        return values["ANTHROPIC_API_KEY"]

    monkeypatch.setattr(settings.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(settings, "getpass", fake_getpass)

    config = settings.get_config()

    assert config.ikas_store_name == values["IKAS_STORE_NAME"]
    assert config.ikas_client_id == values["IKAS_CLIENT_ID"]
    assert config.ikas_client_secret == values["IKAS_CLIENT_SECRET"]
    assert config.anthropic_api_key == values["ANTHROPIC_API_KEY"]
    assert any(p.startswith("IKAS_CLIENT_SECRET") for p in prompts)
    assert any(p.startswith("ANTHROPIC_API_KEY") for p in prompts)


def test_parse_bool_env_supports_multiple_truthy_values(monkeypatch):
    importlib.reload(settings)

    truthy_values = ["true", "TRUE", "1", "yes", "on"]
    for value in truthy_values:
        monkeypatch.setenv("DRY_RUN", value)
        assert settings._parse_bool_env("DRY_RUN", default=False) is True

    monkeypatch.setenv("DRY_RUN", "false")
    assert settings._parse_bool_env("DRY_RUN", default=True) is False
